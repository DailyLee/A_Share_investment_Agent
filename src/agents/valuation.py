from langchain_core.messages import HumanMessage
from src.utils.logging_config import setup_logger
from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction
from src.config.industry_valuation_params import get_valuation_params, get_industry_description
import json

# 初始化 logger
logger = setup_logger('valuation_agent')


@agent_endpoint("valuation", "估值分析师，使用DCF和所有者收益法评估公司内在价值")
def valuation_agent(state: AgentState):
    """Responsible for valuation analysis"""
    show_workflow_status("Valuation Agent")
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    metrics = data["financial_metrics"][0]
    current_financial_line_item = data["financial_line_items"][0]
    previous_financial_line_item = data["financial_line_items"][1]
    
    # 市值单位是亿元，需要转换为元以匹配财务数据
    market_cap_yi = data["market_cap"]  # 原始市值（亿元）
    market_cap = market_cap_yi * 100_000_000  # 转换为元

    # 获取行业信息和对应的估值参数
    industry_name = data.get("industry", "")
    valuation_params = get_valuation_params(industry_name)
    industry_code = valuation_params["industry_code"]
    industry_desc = get_industry_description(industry_code)
    
    logger.info(f"股票行业: {industry_name}")
    logger.info(f"行业分类: {industry_desc}")
    logger.info(f"使用估值参数: {valuation_params}")

    reasoning = {
        "industry_info": {
            "industry_name": industry_name,
            "industry_classification": industry_desc,
            "params_applied": {
                "owner_earnings": valuation_params["owner_earnings"],
                "dcf": valuation_params["dcf"]
            }
        }
    }

    # Get earnings growth rate with fallback to default value
    earnings_growth = metrics.get("earnings_growth", 0.05)  # Default 5% if not available
    
    # Log warning if data is missing
    if "earnings_growth" not in metrics:
        logger.warning("earnings_growth not found in metrics, using default value of 5%")

    # Calculate working capital change
    working_capital_change = (current_financial_line_item.get(
        'working_capital') or 0) - (previous_financial_line_item.get('working_capital') or 0)

    # Owner Earnings Valuation (Buffett Method) - 使用行业特定参数
    oe_params = valuation_params["owner_earnings"]
    owner_earnings_value = calculate_owner_earnings_value(
        net_income=current_financial_line_item.get('net_income'),
        depreciation=current_financial_line_item.get(
            'depreciation_and_amortization'),
        capex=current_financial_line_item.get('capital_expenditure'),
        working_capital_change=working_capital_change,
        growth_rate=earnings_growth,
        required_return=oe_params["required_return"],
        margin_of_safety=oe_params["margin_of_safety"],
        terminal_growth_factor=oe_params["terminal_growth_factor"],
        terminal_growth_cap=oe_params["terminal_growth_cap"],
        use_maintenance_capex=oe_params["use_maintenance_capex"],
        maintenance_capex_ratio=oe_params["maintenance_capex_ratio"],
        use_declining_growth=oe_params["use_declining_growth"]
    )

    # DCF Valuation - 使用行业特定参数
    dcf_params = valuation_params["dcf"]
    dcf_value = calculate_intrinsic_value(
        free_cash_flow=current_financial_line_item.get('free_cash_flow'),
        growth_rate=earnings_growth,
        discount_rate=dcf_params["discount_rate"],
        terminal_growth_factor=dcf_params["terminal_growth_factor"],
        terminal_growth_cap=dcf_params["terminal_growth_cap"],
        num_years=5,
    )

    # Check if market_cap is valid
    if market_cap <= 0:
        logger.warning(f"Invalid market_cap: {market_cap}, cannot perform valuation analysis")
        signal = 'neutral'
        valuation_gap = 0
        dcf_gap = 0
        owner_earnings_gap = 0
        
        reasoning["dcf_analysis"] = {
            "signal": "neutral",
            "details": "Unable to calculate - market cap data unavailable"
        }
        
        reasoning["owner_earnings_analysis"] = {
            "signal": "neutral",
            "details": "Unable to calculate - market cap data unavailable"
        }
    else:
        # Calculate combined valuation gap (average of both methods)
        dcf_gap = (dcf_value - market_cap) / market_cap
        owner_earnings_gap = (owner_earnings_value - market_cap) / market_cap
        valuation_gap = (dcf_gap + owner_earnings_gap) / 2

        if valuation_gap > 0.10:  # Changed from 0.15 to 0.10 (10% undervalued)
            signal = 'bullish'
        elif valuation_gap < -0.20:  # Changed from -0.15 to -0.20 (20% overvalued)
            signal = 'bearish'
        else:
            signal = 'neutral'

        # 转换为亿元以便于阅读（除以1亿）
        dcf_value_yi = dcf_value / 100_000_000
        owner_earnings_value_yi = owner_earnings_value / 100_000_000
        market_cap_yi_display = market_cap / 100_000_000

        reasoning["dcf_analysis"] = {
            "signal": "bullish" if dcf_gap > 0.10 else "bearish" if dcf_gap < -0.20 else "neutral",
            "details": f"Intrinsic Value: ¥{dcf_value_yi:,.2f}亿, Market Cap: ¥{market_cap_yi_display:,.2f}亿, Gap: {dcf_gap:.1%}"
        }

        reasoning["owner_earnings_analysis"] = {
            "signal": "bullish" if owner_earnings_gap > 0.10 else "bearish" if owner_earnings_gap < -0.20 else "neutral",
            "details": f"Owner Earnings Value: ¥{owner_earnings_value_yi:,.2f}亿, Market Cap: ¥{market_cap_yi_display:,.2f}亿, Gap: {owner_earnings_gap:.1%}"
        }

    message_content = {
        "signal": signal,
        "confidence": f"{abs(valuation_gap):.0%}",
        "reasoning": reasoning
    }

    message = HumanMessage(
        content=json.dumps(message_content),
        name="valuation_agent",
    )

    if show_reasoning:
        show_agent_reasoning(message_content, "Valuation Analysis Agent")
        # 保存推理信息到metadata供API使用
        state["metadata"]["agent_reasoning"] = message_content

    show_workflow_status("Valuation Agent", "completed")
    # logger.info(
    # f"--- DEBUG: valuation_agent RETURN messages: {[msg.name for msg in [message]]} ---")
    return {
        "messages": [message],
        "data": {
            **data,
            "valuation_analysis": message_content
        },
        "metadata": state["metadata"],
    }


def calculate_owner_earnings_value(
    net_income: float,
    depreciation: float,
    capex: float,
    working_capital_change: float,
    growth_rate: float = 0.05,
    required_return: float = 0.15,
    margin_of_safety: float = 0.25,
    num_years: int = 5,
    terminal_growth_factor: float = 0.4,
    terminal_growth_cap: float = 0.03,
    use_maintenance_capex: bool = False,
    maintenance_capex_ratio: float = 0.5,
    use_declining_growth: bool = True
) -> float:
    """
    使用改进的所有者收益法计算公司价值。

    Args:
        net_income: 净利润
        depreciation: 折旧和摊销
        capex: 资本支出
        working_capital_change: 营运资金变化
        growth_rate: 预期增长率
        required_return: 要求回报率
        margin_of_safety: 安全边际
        num_years: 预测年数
        terminal_growth_factor: 永续增长率系数（永续增长率 = growth_rate * factor）
        terminal_growth_cap: 永续增长率上限
        use_maintenance_capex: 是否只扣除维持性资本支出
        maintenance_capex_ratio: 维持性资本支出占总资本支出的比例
        use_declining_growth: 是否使用递减增长率模型（稳定行业应设为False）

    Returns:
        float: 计算得到的公司价值
    """
    try:
        # 数据有效性检查
        if not all(isinstance(x, (int, float)) for x in [net_income, depreciation, capex, working_capital_change]):
            return 0

        # 根据参数决定是否只扣除维持性资本支出
        effective_capex = capex * maintenance_capex_ratio if use_maintenance_capex else capex
        
        # 计算初始所有者收益
        owner_earnings = (
            net_income +
            depreciation -
            effective_capex -
            working_capital_change
        )

        if owner_earnings <= 0:
            return 0

        # 调整增长率，确保合理性
        growth_rate = min(max(growth_rate, 0), 0.25)  # 限制在0-25%之间

        # 计算预测期收益现值
        future_values = []
        for year in range(1, num_years + 1):
            if use_declining_growth:
                # 使用递减增长率模型（适合周期性行业）
                year_growth = growth_rate * (1 - year / (2 * num_years))
            else:
                # 使用恒定增长率模型（适合稳定行业）
                year_growth = growth_rate
            
            future_value = owner_earnings * (1 + year_growth) ** year
            discounted_value = future_value / (1 + required_return) ** year
            future_values.append(discounted_value)

        # 计算永续价值 - 使用传入的参数
        terminal_growth = min(growth_rate * terminal_growth_factor, terminal_growth_cap)
        terminal_value = (
            future_values[-1] * (1 + terminal_growth)) / (required_return - terminal_growth)
        terminal_value_discounted = terminal_value / \
            (1 + required_return) ** num_years

        # 计算总价值并应用安全边际
        intrinsic_value = sum(future_values) + terminal_value_discounted
        value_with_safety_margin = intrinsic_value * (1 - margin_of_safety)

        return max(value_with_safety_margin, 0)  # 确保不返回负值

    except Exception as e:
        print(f"所有者收益计算错误: {e}")
        return 0


def calculate_intrinsic_value(
    free_cash_flow: float,
    growth_rate: float = 0.05,
    discount_rate: float = 0.10,
    num_years: int = 5,
    terminal_growth_factor: float = 0.4,
    terminal_growth_cap: float = 0.03
) -> float:
    """
    使用改进的DCF方法计算内在价值，考虑增长率和风险因素。

    Args:
        free_cash_flow: 自由现金流
        growth_rate: 预期增长率
        discount_rate: 基础折现率
        num_years: 预测年数
        terminal_growth_factor: 永续增长率系数（永续增长率 = growth_rate * factor）
        terminal_growth_cap: 永续增长率上限

    Returns:
        float: 计算得到的内在价值
    """
    try:
        if not isinstance(free_cash_flow, (int, float)) or free_cash_flow <= 0:
            return 0

        # 调整增长率，确保合理性
        growth_rate = min(max(growth_rate, 0), 0.25)  # 限制在0-25%之间

        # 调整永续增长率，使用传入的参数
        terminal_growth_rate = min(growth_rate * terminal_growth_factor, terminal_growth_cap)

        # 计算预测期现金流现值
        present_values = []
        for year in range(1, num_years + 1):
            future_cf = free_cash_flow * (1 + growth_rate) ** year
            present_value = future_cf / (1 + discount_rate) ** year
            present_values.append(present_value)

        # 计算永续价值
        terminal_year_cf = free_cash_flow * (1 + growth_rate) ** num_years
        terminal_value = terminal_year_cf * \
            (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
        terminal_present_value = terminal_value / \
            (1 + discount_rate) ** num_years

        # 总价值
        total_value = sum(present_values) + terminal_present_value

        return max(total_value, 0)  # 确保不返回负值

    except Exception as e:
        print(f"DCF计算错误: {e}")
        return 0


def calculate_working_capital_change(
    current_working_capital: float,
    previous_working_capital: float,
) -> float:
    """
    Calculate the absolute change in working capital between two periods.
    A positive change means more capital is tied up in working capital (cash outflow).
    A negative change means less capital is tied up (cash inflow).

    Args:
        current_working_capital: Current period's working capital
        previous_working_capital: Previous period's working capital

    Returns:
        float: Change in working capital (current - previous)
    """
    return current_working_capital - previous_working_capital
