# -*- coding: utf-8 -*-
"""
改进的估值分析代理（V2）

使用改进的DCF和所有者收益法估值模型
基于state中已有的财务数据（来自Akshare）
"""

from langchain_core.messages import HumanMessage
from src.utils.logging_config import setup_logger
from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction
from src.config.industry_valuation_params import get_valuation_params, get_industry_description, classify_industry
from src.valuation.advanced_dcf import (
    calculate_wacc,
    estimate_growth_rates,
    calculate_three_stage_dcf
)
from src.valuation.owner_earnings import (
    estimate_maintenance_capex,
    calculate_owner_earnings,
    calculate_three_stage_owner_earnings_value
)
from src.valuation.revenue_based_valuation import calculate_revenue_based_valuation
import json

# 初始化 logger
logger = setup_logger('valuation_agent_v2')

# 中国市场参数
CHINA_RISK_FREE_RATE = 0.028  # 10年期国债收益率约2.8%
CHINA_MARKET_RISK_PREMIUM = 0.055  # 市场风险溢价约5.5%（调整：从7%降低到5.5%，更符合中国市场实际情况）
DEFAULT_BETA = 1.0  # 默认贝塔系数
DEFAULT_COST_OF_DEBT = 0.045  # 默认债务成本约4.5%
DEFAULT_TAX_RATE = 0.25  # 默认税率25%

# 行业贝塔值（参考值）
INDUSTRY_BETAS = {
    "utilities": 0.6,         # 公用事业
    "heavy_industry": 0.9,    # 重工业
    "technology": 1.3,        # 科技
    "finance": 0.8,           # 金融
    "consumer": 0.9,          # 消费
    "healthcare": 1.0,        # 医药
    "real_estate": 1.1,       # 房地产
    "manufacturing": 1.0,     # 制造业
    "services": 1.0,          # 服务业
    "default": 1.0
}

# 成长型行业列表（这些行业更容易出现成长型公司）
GROWTH_INDUSTRIES = ["technology", "healthcare", "services"]


def identify_growth_company(fin_data: dict, industry_code: str, market_cap: float) -> dict:
    """
    使用综合指标识别成长型公司
    
    识别标准（满足任一条件即可）：
    1. 净利润≤0 且 营收>0 且 营收增长率>5%（亏损但增长）
    2. 营收增长率>20%（高增长）
    3. P/S比率>5 且 净利润率<5%（市场高估值但利润率低，说明在投入期）
    4. P/E比率>50 且 净利润率<10%（高估值但利润率低）
    5. 成长型行业 + 营收增长率>15% + 净利润率<10%
    6. 资本支出/营收>0.15 且 营收增长率>10%（高资本支出投入增长）
    
    Args:
        fin_data: 财务数据字典
        industry_code: 行业代码
        market_cap: 市值（元）
    
    Returns:
        dict: 如果是成长型公司，返回包含reason的字典；否则返回False
    """
    net_income = fin_data.get("net_income", 0)
    operating_revenue = fin_data.get("operating_revenue", 0)
    revenue_growth = fin_data.get("revenue_growth", 0)
    earnings_growth = fin_data.get("earnings_growth", 0)
    ps_ratio = fin_data.get("price_to_sales", 0)
    pe_ratio = fin_data.get("pe_ratio", 0)
    net_margin = fin_data.get("net_margin", 0)
    capex = fin_data.get("capex", 0)
    
    # 条件1：亏损但营收增长
    if net_income <= 0 and operating_revenue > 0 and revenue_growth > 0.05:
        return {
            "is_growth": True,
            "reason": f"亏损但营收增长（营收增长率: {revenue_growth:.1%}）"
        }
    
    # 条件2：高营收增长（>20%）
    if revenue_growth > 0.20:
        return {
            "is_growth": True,
            "reason": f"高营收增长（营收增长率: {revenue_growth:.1%}）"
        }
    
    # 条件3：高P/S比率 + 低利润率（市场高估值但利润率低）
    if ps_ratio > 5.0 and net_margin < 0.05 and operating_revenue > 0:
        return {
            "is_growth": True,
            "reason": f"高P/S比率({ps_ratio:.1f}) + 低利润率({net_margin:.1%})，市场给予高估值但仍在投入期"
        }
    
    # 条件4：高P/E比率 + 低利润率
    if pe_ratio > 50 and net_margin < 0.10 and net_income > 0:
        return {
            "is_growth": True,
            "reason": f"高P/E比率({pe_ratio:.1f}) + 低利润率({net_margin:.1%})，高估值但利润率低"
        }
    
    # 条件5：成长型行业 + 高增长 + 低利润率
    if industry_code in GROWTH_INDUSTRIES and revenue_growth > 0.15 and net_margin < 0.10:
        return {
            "is_growth": True,
            "reason": f"成长型行业({industry_code}) + 高增长({revenue_growth:.1%}) + 低利润率({net_margin:.1%})"
        }
    
    # 条件6：高资本支出投入增长
    capex_to_revenue = capex / operating_revenue if operating_revenue > 0 else 0
    if capex_to_revenue > 0.15 and revenue_growth > 0.10:
        return {
            "is_growth": True,
            "reason": f"高资本支出投入({capex_to_revenue:.1%}) + 营收增长({revenue_growth:.1%})，积极投资未来增长"
        }
    
    # 条件7：营收增长>15% 且 利润增长不稳定（波动大或为负）
    if revenue_growth > 0.15:
        # 如果利润增长为负或远低于营收增长，说明在投入期
        if earnings_growth < 0 or (earnings_growth > 0 and earnings_growth < revenue_growth * 0.5):
            return {
                "is_growth": True,
                "reason": f"高营收增长({revenue_growth:.1%})但利润增长滞后({earnings_growth:.1%})，处于投入期"
            }
    
    return {"is_growth": False}


def extract_financial_data_from_state(data: dict) -> dict:
    """
    从state中提取财务数据
    
    Args:
        data: state中的data字典
    
    Returns:
        包含所有财务数据的字典
    """
    financial_metrics = data.get("financial_metrics", [{}])[0]
    current_line_item = data.get("financial_line_items", [{}])[0] if data.get("financial_line_items") else {}
    previous_line_item = data.get("financial_line_items", [{}])[1] if len(data.get("financial_line_items", [])) > 1 else {}
    
    # 获取市场数据
    market_cap_yi = data.get("market_cap", 0)
    market_cap = market_cap_yi * 100_000_000 if market_cap_yi > 0 else 0
    
    # 计算P/S比率
    operating_revenue = current_line_item.get("operating_revenue", 0)
    ps_ratio = market_cap / operating_revenue if operating_revenue > 0 and market_cap > 0 else 0
    
    # 计算净利润率
    net_income = current_line_item.get("net_income", 0)
    net_margin = net_income / operating_revenue if operating_revenue > 0 else 0
    
    # A股市场特点：考虑股息率（高股息率股票更受青睐）
    # 注意：这里假设可以从财务数据中获取分红数据，如果没有则设为0
    dividend_paid = current_line_item.get("dividend_paid", 0)  # 分红金额
    dividend_yield = dividend_paid / market_cap if market_cap > 0 and dividend_paid > 0 else 0
    
    return {
        # 从financial_metrics获取
        "earnings_growth": financial_metrics.get("earnings_growth", 0.05),
        "revenue_growth": financial_metrics.get("revenue_growth", 0.05),
        "pe_ratio": financial_metrics.get("pe_ratio", 0),
        "price_to_sales": financial_metrics.get("price_to_sales", ps_ratio),  # 优先使用financial_metrics中的值
        "net_margin": financial_metrics.get("net_margin", net_margin),
        
        # 从current_line_item获取（最新期）
        "net_income": net_income,
        "operating_revenue": operating_revenue,
        "operating_profit": current_line_item.get("operating_profit", 0),
        "depreciation": current_line_item.get("depreciation_and_amortization", 0),
        "capex": current_line_item.get("capital_expenditure", 0),
        "free_cash_flow": current_line_item.get("free_cash_flow", 0),
        "working_capital": current_line_item.get("working_capital", 0),
        "dividend_paid": dividend_paid,  # 分红金额
        "dividend_yield": dividend_yield,  # 股息率
        
        # 从previous_line_item获取（上期）
        "prev_net_income": previous_line_item.get("net_income", 0),
        "prev_operating_revenue": previous_line_item.get("operating_revenue", 0),
        "prev_operating_profit": previous_line_item.get("operating_profit", 0),
        "prev_working_capital": previous_line_item.get("working_capital", 0),
        
        # 市场数据
        "market_cap": market_cap,
    }


@agent_endpoint("valuation_v2", "改进的估值分析师，使用三阶段DCF和所有者收益法评估公司内在价值")
def valuation_agent_v2(state: AgentState):
    """
    改进的估值分析代理
    
    主要改进：
    1. 三阶段DCF模型（高增长期 -> 过渡期 -> 永续期）
    2. 改进的所有者收益法（更准确的维持性资本支出估算）
    3. WACC计算
    4. 更合理的增长率估算
    5. 基于state中已有的财务数据（Akshare）
    """
    show_workflow_status("Valuation Agent V2")
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    
    # 获取基本信息
    ticker = data["ticker"]
    industry_name = data.get("industry", "")
    market_cap_yi = data.get("market_cap", 0)  # 市值（亿元）
    market_cap = market_cap_yi * 100_000_000  # 转换为元
    
    # 获取行业信息和估值参数
    valuation_params = get_valuation_params(industry_name)
    industry_code = valuation_params["industry_code"]
    industry_desc = get_industry_description(industry_code)
    industry_beta = INDUSTRY_BETAS.get(industry_code, DEFAULT_BETA)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"开始估值分析: {ticker}")
    logger.info(f"行业: {industry_name} ({industry_desc})")
    logger.info(f"市值: ¥{market_cap_yi:.2f}亿")
    logger.info(f"{'='*60}\n")
    
    try:
        # 从state中提取财务数据
        fin_data = extract_financial_data_from_state(data)
        
        # 使用综合指标识别成长型公司
        growth_check = identify_growth_company(fin_data, industry_code, market_cap)
        is_growth_company = growth_check.get("is_growth", False)
        is_profitable = fin_data.get("net_income", 0) > 0
        
        # 如果是成长型公司且已盈利，使用三种方法：DCF、所有者收益法、营收估值法
        if is_growth_company and is_profitable:
            logger.info("检测到已盈利的成长型公司，使用三种估值方法：DCF + 所有者收益法 + 营收估值法")
            logger.info(f"识别原因: {growth_check.get('reason', 'N/A')}")
            return handle_profitable_growth_company_valuation(state, fin_data, industry_code, market_cap, valuation_params)
        
        # 如果是成长型公司但未盈利，只使用营收估值法
        if is_growth_company and not is_profitable:
            logger.info("检测到成长型公司（未盈利），使用基于营收的估值方法")
            logger.info(f"识别原因: {growth_check.get('reason', 'N/A')}")
            return handle_growth_company_valuation(state, fin_data, industry_code, market_cap)
        
        # 如果不是成长型公司且未盈利，回退到传统方法
        if not is_profitable:
            logger.warning("财务数据不完整或净利润为负，回退到传统方法")
            return fallback_to_traditional_valuation(state)
        
        # 计算税率（基于营业利润和净利润）
        if fin_data["operating_profit"] > 0 and fin_data["net_income"] > 0:
            tax_rate = 1 - (fin_data["net_income"] / fin_data["operating_profit"])
            tax_rate = max(0.15, min(tax_rate, 0.35))  # 限制在15%-35%之间
        else:
            tax_rate = DEFAULT_TAX_RATE
        
        logger.info(f"估算税率: {tax_rate:.1%}")
        
        # ==================== 增长率估算 ====================
        # 使用历史增长率和行业增长率
        earnings_growth = fin_data.get("earnings_growth", 0.05)
        revenue_growth = fin_data.get("revenue_growth", 0.05)
        
        # 综合增长率（营收增长40% + 利润增长60%）
        high_growth_rate = 0.4 * revenue_growth + 0.6 * earnings_growth
        high_growth_rate = max(0.03, min(high_growth_rate, 0.30))  # 限制在3%-30%
        
        transition_growth_rate = high_growth_rate * 0.7
        # A股市场长期增长率：考虑中国GDP增速放缓趋势，永续增长率设为2.5%（更保守）
        # 相比成熟市场，A股市场长期增长潜力略高但波动性也更大
        terminal_growth_rate = 0.025  # A股市场永续增长率2.5%（从3%降低到2.5%，更符合长期趋势）
        
        logger.info(f"高增长率: {high_growth_rate:.2%}")
        logger.info(f"过渡增长率: {transition_growth_rate:.2%}")
        logger.info(f"永续增长率: {terminal_growth_rate:.2%}")
        
        # ==================== DCF估值 ====================
        logger.info("\n" + "="*60)
        logger.info("DCF估值分析")
        logger.info("="*60)
        
        # 计算WACC（使用市值作为权益价值的代理）
        total_equity = market_cap if market_cap > 0 else fin_data["net_income"] * 15  # PE=15作为后备
        total_debt = 0  # 简化处理，实际中可以从资产负债表获取
        
        wacc = calculate_wacc(
            risk_free_rate=CHINA_RISK_FREE_RATE,
            market_risk_premium=CHINA_MARKET_RISK_PREMIUM,
            beta=industry_beta,
            total_debt=total_debt,
            total_equity=total_equity,
            cost_of_debt=DEFAULT_COST_OF_DEBT,
            tax_rate=tax_rate
        )
        
        # 执行三阶段DCF估值
        initial_fcf = fin_data["free_cash_flow"]
        
        if initial_fcf > 0:
            dcf_result = calculate_three_stage_dcf(
                initial_fcf=initial_fcf,
                high_growth_rate=high_growth_rate,
                transition_growth_rate=transition_growth_rate,
                terminal_growth_rate=terminal_growth_rate,
                wacc=wacc,
                high_growth_years=5,
                transition_years=5,
                total_debt=total_debt,
                cash_and_equivalents=0,
                shares_outstanding=0
            )
            
            dcf_value = dcf_result.get('enterprise_value', 0)
            dcf_value_yi = dcf_value / 100_000_000
            
            logger.info(f"DCF企业价值: ¥{dcf_value_yi:.2f}亿")
        else:
            logger.warning(f"自由现金流为负或为零({initial_fcf/100000000:.2f}亿)，无法执行DCF估值")
            dcf_value = 0
            dcf_value_yi = 0
            dcf_result = {"enterprise_value": 0, "error": "Invalid FCF"}
        
        # ==================== 所有者收益法估值 ====================
        logger.info("\n" + "="*60)
        logger.info("所有者收益法估值分析")
        logger.info("="*60)
        
        # 估算维持性资本支出比率
        # 使用简化的行业标准比率
        maintenance_ratios = {
            "utilities": 0.7,
            "heavy_industry": 0.6,
            "technology": 0.3,
            "finance": 0.4,
            "consumer": 0.5,
            "healthcare": 0.4,
            "real_estate": 0.5,
            "manufacturing": 0.6,
            "services": 0.4,
            "default": 0.5
        }
        maintenance_ratio = maintenance_ratios.get(industry_code, 0.5)
        
        logger.info(f"维持性资本支出比率: {maintenance_ratio:.1%}")
        
        # 计算所有者收益
        # 营运资金变化：如果变化异常大，使用平滑处理
        working_capital_change = fin_data["working_capital"] - fin_data.get("prev_working_capital", fin_data["working_capital"])
        
        # 对于公用事业等资本密集型行业，营运资金变化可能很大
        # 如果营运资金变化超过净利润的50%，可能是异常值，需要平滑处理
        if abs(working_capital_change) > abs(fin_data["net_income"]) * 0.5:
            # 使用营收的一定比例作为营运资金变化的估算（更稳定）
            # 对于公用事业，营运资金变化通常与营收相关
            if fin_data["operating_revenue"] > 0:
                # 使用营收的2-5%作为营运资金变化的估算
                wc_change_ratio = 0.03 if industry_code == "utilities" else 0.02
                working_capital_change = fin_data["operating_revenue"] * wc_change_ratio
                logger.warning(f"营运资金变化异常大({working_capital_change/100000000:.2f}亿)，使用平滑估算: {working_capital_change/100000000:.2f}亿")
            else:
                # 如果营收也为0，则使用0
                working_capital_change = 0
        
        owner_earnings = calculate_owner_earnings(
            net_income=fin_data["net_income"],
            depreciation=fin_data["depreciation"],
            capex=fin_data["capex"],
            working_capital_change=working_capital_change,
            maintenance_capex_ratio=maintenance_ratio
        )
        
        # 如果所有者收益为负或异常小，使用净利润作为后备
        if owner_earnings <= 0 or owner_earnings < fin_data["net_income"] * 0.1:
            logger.warning(f"所有者收益异常小({owner_earnings/100000000:.2f}亿)，使用净利润作为后备")
            # 使用净利润的80%作为所有者收益的估算（保守估计）
            owner_earnings = fin_data["net_income"] * 0.8
        
        if owner_earnings > 0:
            oe_params = valuation_params["owner_earnings"]
            
            oe_result = calculate_three_stage_owner_earnings_value(
                initial_owner_earnings=owner_earnings,
                high_growth_rate=high_growth_rate,
                transition_growth_rate=transition_growth_rate,
                terminal_growth_rate=terminal_growth_rate,
                required_return=oe_params["required_return"],
                high_growth_years=5,
                transition_years=5,
                margin_of_safety=oe_params["margin_of_safety"],
                total_debt=total_debt,
                cash_and_equivalents=0
            )
            
            oe_value = oe_result.get('intrinsic_value_with_margin', 0)
            oe_value_yi = oe_value / 100_000_000
            
            logger.info(f"所有者收益法价值（含安全边际）: ¥{oe_value_yi:.2f}亿")
        else:
            logger.warning(f"所有者收益为负或为零({owner_earnings/100000000:.2f}亿)，无法执行所有者收益法估值")
            oe_value = 0
            oe_value_yi = 0
            oe_result = {"intrinsic_value_with_margin": 0, "error": "Invalid owner earnings"}
        
        # ==================== 综合估值分析 ====================
        logger.info("\n" + "="*60)
        logger.info("综合估值分析")
        logger.info("="*60)
        
        # 检查市值是否有效
        if market_cap <= 0:
            logger.warning("市值数据无效，无法进行估值比较")
            signal = 'neutral'
            valuation_gap = 0
            dcf_gap = 0
            oe_gap = 0
        else:
            # 计算估值差距
            if dcf_value > 0:
                dcf_gap = (dcf_value - market_cap) / market_cap
            else:
                dcf_gap = 0
            
            if oe_value > 0:
                oe_gap = (oe_value - market_cap) / market_cap
            else:
                oe_gap = 0
            
            # 检查两种估值方法的差异
            if dcf_value > 0 and oe_value > 0:
                # 计算两种方法的差异比例
                valuation_ratio = max(dcf_value, oe_value) / min(dcf_value, oe_value)
                
                if valuation_ratio > 3.0:  # 如果差异超过3倍，认为差异过大
                    logger.warning(f"⚠️ 两种估值方法差异过大（{valuation_ratio:.1f}倍）")
                    logger.warning(f"   DCF估值: ¥{dcf_value_yi:.2f}亿")
                    logger.warning(f"   所有者收益法估值: ¥{oe_value_yi:.2f}亿")
                    logger.warning(f"   建议：优先使用DCF估值（更适用于现金流稳定的公司）")
                    
                    # 如果差异过大，优先使用DCF（对于现金流稳定的公司更可靠）
                    # 或者使用两种方法的几何平均（更保守）
                    if industry_code in ["utilities", "finance", "consumer"]:
                        # 对于现金流稳定的行业，优先使用DCF
                        valuation_gap = dcf_gap
                        logger.info("使用DCF估值（现金流稳定行业）")
                    else:
                        # 其他行业使用几何平均（更保守）
                        geometric_mean_value = (dcf_value * oe_value) ** 0.5
                        geometric_mean_gap = (geometric_mean_value - market_cap) / market_cap
                        valuation_gap = geometric_mean_gap
                        logger.info(f"使用几何平均估值: ¥{geometric_mean_value/100000000:.2f}亿")
                else:
                    # 差异在合理范围内，使用加权平均
                    valuation_gap = 0.6 * dcf_gap + 0.4 * oe_gap
            elif dcf_value > 0:
                # 只有DCF有效
                valuation_gap = dcf_gap
            elif oe_value > 0:
                # 只有所有者收益法有效
                valuation_gap = oe_gap
            else:
                # 都无效，使用传统方法
                logger.warning("两种估值方法都无效，回退到传统方法")
                return fallback_to_traditional_valuation(state)
            
            logger.info(f"DCF估值: ¥{dcf_value_yi:.2f}亿")
            logger.info(f"所有者收益法估值: ¥{oe_value_yi:.2f}亿")
            logger.info(f"当前市值: ¥{market_cap_yi:.2f}亿")
            logger.info(f"DCF估值差距: {dcf_gap:.1%}")
            logger.info(f"所有者收益法差距: {oe_gap:.1%}")
            logger.info(f"综合估值差距: {valuation_gap:.1%}")
            
            # 估值合理性检查：如果估值与市值差距过大（>50%），给出警告
            if abs(valuation_gap) > 0.50:
                logger.warning(f"⚠️ 估值与市值差距过大（{valuation_gap:.1%}），可能存在以下问题：")
                logger.warning(f"   1. 折现率或要求回报率可能过高")
                logger.warning(f"   2. 安全边际可能过大")
                logger.warning(f"   3. 增长率假设可能过于保守")
                logger.warning(f"   4. 财务数据可能不准确（如自由现金流、所有者收益为负）")
                logger.warning(f"   建议：检查财务数据质量和估值参数设置")
            
            # 确定信号（基于A股市场特点优化阈值）
            # A股市场特点：波动性大，需要更大的安全边际
            # 低估阈值：15%（A股市场低估机会相对较多，但需要谨慎）
            # 高估阈值：-20%（A股市场高估时波动可能更大）
            if valuation_gap > 0.15:  # 低估超过15%
                signal = 'bullish'
            elif valuation_gap < -0.20:  # 高估超过20%
                signal = 'bearish'
            else:
                signal = 'neutral'
        
        # 构建推理信息
        reasoning = {
            "industry_info": {
                "industry_name": industry_name,
                "industry_classification": industry_desc,
                "industry_beta": industry_beta,
                "params_applied": {
                    "wacc": f"{wacc:.2%}",
                    "high_growth_rate": f"{high_growth_rate:.2%}",
                    "terminal_growth_rate": f"{terminal_growth_rate:.2%}",
                    "required_return": f"{valuation_params['owner_earnings']['required_return']:.2%}",
                    "margin_of_safety": f"{valuation_params['owner_earnings']['margin_of_safety']:.0%}",
                    "maintenance_capex_ratio": f"{maintenance_ratio:.0%}"
                }
            },
            "dcf_analysis": {
                "signal": "bullish" if dcf_gap > 0.15 else "bearish" if dcf_gap < -0.20 else "neutral",
                "details": f"DCF估值: ¥{dcf_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {dcf_gap:.1%}" if dcf_value > 0 else "DCF估值不可用",
                "stage_breakdown": {
                    "stage1": f"¥{dcf_result.get('stage1_value', 0)/100000000:.2f}亿",
                    "stage2": f"¥{dcf_result.get('stage2_value', 0)/100000000:.2f}亿",
                    "stage3": f"¥{dcf_result.get('stage3_value', 0)/100000000:.2f}亿"
                } if dcf_value > 0 else {}
            },
            "owner_earnings_analysis": {
                "signal": "bullish" if oe_gap > 0.15 else "bearish" if oe_gap < -0.20 else "neutral",
                "details": f"所有者收益法估值: ¥{oe_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {oe_gap:.1%}" if oe_value > 0 else "所有者收益法估值不可用",
                "owner_earnings": f"¥{owner_earnings/100000000:.2f}亿" if owner_earnings > 0 else "N/A",
                "maintenance_capex_ratio": f"{maintenance_ratio:.1%}",
                "stage_breakdown": {
                    "stage1": f"¥{oe_result.get('stage1_value', 0)/100000000:.2f}亿",
                    "stage2": f"¥{oe_result.get('stage2_value', 0)/100000000:.2f}亿",
                    "stage3": f"¥{oe_result.get('stage3_value', 0)/100000000:.2f}亿"
                } if oe_value > 0 else {}
            },
            "valuation_method": "Three-Stage DCF + Owner Earnings (Buffett Method)",
            "a_share_market_features": {
                "note": "基于A股市场特点优化：波动性大、政策敏感性强、估值体系更关注PE/PB",
                "risk_free_rate": f"{CHINA_RISK_FREE_RATE:.2%}",
                "market_risk_premium": f"{CHINA_MARKET_RISK_PREMIUM:.2%}",
                "terminal_growth_rate": "2.5%",
                "dividend_yield": f"{fin_data.get('dividend_yield', 0):.2%}" if fin_data.get('dividend_yield', 0) > 0 else "N/A"
            }
        }
        
        # 计算置信度：当两种方法方向相反时，使用两种方法差距的加权平均绝对值
        # 而不是综合估值差距的绝对值，以避免相互抵消导致置信度为0
        if dcf_value > 0 and oe_value > 0:
            # 两种方法都有效时，使用两种方法差距绝对值的加权平均
            confidence_value = 0.6 * abs(dcf_gap) + 0.4 * abs(oe_gap)
        else:
            # 只有一种方法有效时，使用该方法的差距绝对值
            confidence_value = abs(valuation_gap)
        
        message_content = {
            "signal": signal,
            "confidence": f"{confidence_value:.0%}",
            "reasoning": reasoning
        }
        
        message = HumanMessage(
            content=json.dumps(message_content),
            name="valuation_agent_v2",
        )
        
        if show_reasoning:
            show_agent_reasoning(message_content, "Valuation Analysis Agent V2")
            state["metadata"]["agent_reasoning"] = message_content
        
        show_workflow_status("Valuation Agent V2", "completed")
        
        return {
            "messages": [message],
            "data": {
                **data,
                "valuation_analysis": message_content
            },
            "metadata": state["metadata"],
        }
    
    except Exception as e:
        logger.error(f"估值分析出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 发生错误时回退到传统方法
        logger.info("回退到传统估值方法")
        return fallback_to_traditional_valuation(state)


def handle_profitable_growth_company_valuation(
    state: AgentState,
    fin_data: dict,
    industry_code: str,
    market_cap: float,
    valuation_params: dict
) -> dict:
    """
    处理已盈利成长型公司的估值
    
    使用三种估值方法：
    1. DCF估值
    2. 所有者收益法
    3. 营收估值法
    """
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    ticker = data["ticker"]
    industry_name = data.get("industry", "")
    market_cap_yi = data.get("market_cap", 0)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"已盈利成长型公司估值分析: {ticker}")
    logger.info(f"行业: {industry_name}")
    logger.info(f"当前市值: ¥{market_cap_yi:.2f}亿")
    logger.info(f"{'='*60}\n")
    
    # ==================== 计算税率 ====================
    if fin_data["operating_profit"] > 0 and fin_data["net_income"] > 0:
        tax_rate = 1 - (fin_data["net_income"] / fin_data["operating_profit"])
        tax_rate = max(0.15, min(tax_rate, 0.35))
    else:
        tax_rate = DEFAULT_TAX_RATE
    
    # ==================== 增长率估算 ====================
    earnings_growth = fin_data.get("earnings_growth", 0.05)
    revenue_growth = fin_data.get("revenue_growth", 0.05)
    
    # 综合增长率（营收增长40% + 利润增长60%）
    high_growth_rate = 0.4 * revenue_growth + 0.6 * earnings_growth
    high_growth_rate = max(0.03, min(high_growth_rate, 0.30))
    
    transition_growth_rate = high_growth_rate * 0.7
    terminal_growth_rate = 0.025
    
    # ==================== DCF估值 ====================
    logger.info("\n" + "="*60)
    logger.info("方法1: DCF估值分析")
    logger.info("="*60)
    
    total_equity = market_cap if market_cap > 0 else fin_data["net_income"] * 15
    total_debt = 0
    industry_beta = INDUSTRY_BETAS.get(industry_code, DEFAULT_BETA)
    
    wacc = calculate_wacc(
        risk_free_rate=CHINA_RISK_FREE_RATE,
        market_risk_premium=CHINA_MARKET_RISK_PREMIUM,
        beta=industry_beta,
        total_debt=total_debt,
        total_equity=total_equity,
        cost_of_debt=DEFAULT_COST_OF_DEBT,
        tax_rate=tax_rate
    )
    
    initial_fcf = fin_data["free_cash_flow"]
    if initial_fcf > 0:
        dcf_result = calculate_three_stage_dcf(
            initial_fcf=initial_fcf,
            high_growth_rate=high_growth_rate,
            transition_growth_rate=transition_growth_rate,
            terminal_growth_rate=terminal_growth_rate,
            wacc=wacc,
            high_growth_years=5,
            transition_years=5,
            total_debt=total_debt,
            cash_and_equivalents=0,
            shares_outstanding=0
        )
        dcf_value = dcf_result.get('enterprise_value', 0)
        dcf_value_yi = dcf_value / 100_000_000
    else:
        logger.warning(f"自由现金流为负或为零，无法执行DCF估值")
        dcf_value = 0
        dcf_value_yi = 0
        dcf_result = {"enterprise_value": 0, "error": "Invalid FCF"}
    
    # ==================== 所有者收益法估值 ====================
    logger.info("\n" + "="*60)
    logger.info("方法2: 所有者收益法估值分析")
    logger.info("="*60)
    
    maintenance_ratios = {
        "utilities": 0.7, "heavy_industry": 0.6, "technology": 0.3,
        "finance": 0.4, "consumer": 0.5, "healthcare": 0.4,
        "real_estate": 0.5, "manufacturing": 0.6, "services": 0.4,
        "default": 0.5
    }
    maintenance_ratio = maintenance_ratios.get(industry_code, 0.5)
    
    working_capital_change = fin_data["working_capital"] - fin_data.get("prev_working_capital", fin_data["working_capital"])
    if abs(working_capital_change) > abs(fin_data["net_income"]) * 0.5:
        if fin_data["operating_revenue"] > 0:
            wc_change_ratio = 0.03 if industry_code == "utilities" else 0.02
            working_capital_change = fin_data["operating_revenue"] * wc_change_ratio
    
    owner_earnings = calculate_owner_earnings(
        net_income=fin_data["net_income"],
        depreciation=fin_data["depreciation"],
        capex=fin_data["capex"],
        working_capital_change=working_capital_change,
        maintenance_capex_ratio=maintenance_ratio
    )
    
    if owner_earnings <= 0 or owner_earnings < fin_data["net_income"] * 0.1:
        owner_earnings = fin_data["net_income"] * 0.8
    
    if owner_earnings > 0:
        oe_params = valuation_params["owner_earnings"]
        oe_result = calculate_three_stage_owner_earnings_value(
            initial_owner_earnings=owner_earnings,
            high_growth_rate=high_growth_rate,
            transition_growth_rate=transition_growth_rate,
            terminal_growth_rate=terminal_growth_rate,
            required_return=oe_params["required_return"],
            high_growth_years=5,
            transition_years=5,
            margin_of_safety=oe_params["margin_of_safety"],
            total_debt=total_debt,
            cash_and_equivalents=0
        )
        oe_value = oe_result.get('intrinsic_value_with_margin', 0)
        oe_value_yi = oe_value / 100_000_000
    else:
        oe_value = 0
        oe_value_yi = 0
        oe_result = {"intrinsic_value_with_margin": 0, "error": "Invalid owner earnings"}
    
    # ==================== 营收估值法 ====================
    logger.info("\n" + "="*60)
    logger.info("方法3: 营收估值法分析")
    logger.info("="*60)
    
    operating_revenue = fin_data.get("operating_revenue", 0)
    net_income = fin_data.get("net_income", 0)
    net_margin = fin_data.get("net_margin", 0)
    
    years_to_profitability = 2 if industry_code == "technology" else 3
    target_profit_margin = 0.15 if industry_code == "technology" else 0.10
    
    revenue_result = calculate_revenue_based_valuation(
        operating_revenue=operating_revenue,
        revenue_growth_rate=revenue_growth,
        industry_code=industry_code,
        market_cap=market_cap,
        years_to_profitability=years_to_profitability,
        target_profit_margin=target_profit_margin,
        current_net_income=net_income,
        current_net_margin=net_margin
    )
    
    revenue_value = revenue_result.get('revenue_value', 0)
    revenue_value_yi = revenue_value / 100_000_000
    
    # ==================== 综合估值分析 ====================
    logger.info("\n" + "="*60)
    logger.info("综合估值分析（三种方法）")
    logger.info("="*60)
    
    if market_cap <= 0:
        logger.warning("市值数据无效，无法进行估值比较")
        signal = 'neutral'
        valuation_gap = 0
        dcf_gap = 0
        oe_gap = 0
        revenue_gap = 0
    else:
        # 计算各方法的估值差距
        dcf_gap = (dcf_value - market_cap) / market_cap if dcf_value > 0 else 0
        oe_gap = (oe_value - market_cap) / market_cap if oe_value > 0 else 0
        revenue_gap = (revenue_value - market_cap) / market_cap if revenue_value > 0 else 0
        
        # 计算有效方法数量
        valid_methods = []
        if dcf_value > 0:
            valid_methods.append(("dcf", dcf_gap))
        if oe_value > 0:
            valid_methods.append(("oe", oe_gap))
        if revenue_value > 0:
            valid_methods.append(("revenue", revenue_gap))
        
        if len(valid_methods) == 0:
            logger.warning("三种估值方法都无效，回退到传统方法")
            return fallback_to_traditional_valuation(state)
        
        # 对于已盈利成长型公司，使用加权平均
        # DCF和所有者收益法各30%，营收估值法40%（因为成长型公司更关注营收增长）
        weights = {"dcf": 0.3, "oe": 0.3, "revenue": 0.4}
        total_weight = sum(weights.get(method[0], 0) for method in valid_methods)
        
        if total_weight > 0:
            valuation_gap = sum(weights.get(method[0], 0) * method[1] for method in valid_methods) / total_weight
        else:
            # 如果权重计算有问题，使用简单平均
            valuation_gap = sum(method[1] for method in valid_methods) / len(valid_methods)
        
        logger.info(f"DCF估值: ¥{dcf_value_yi:.2f}亿, 差距: {dcf_gap:.1%}")
        logger.info(f"所有者收益法估值: ¥{oe_value_yi:.2f}亿, 差距: {oe_gap:.1%}")
        logger.info(f"营收估值法: ¥{revenue_value_yi:.2f}亿, 差距: {revenue_gap:.1%}")
        logger.info(f"当前市值: ¥{market_cap_yi:.2f}亿")
        logger.info(f"综合估值差距: {valuation_gap:.1%}")
        
        # 确定信号
        if valuation_gap > 0.15:
            signal = 'bullish'
        elif valuation_gap < -0.20:
            signal = 'bearish'
        else:
            signal = 'neutral'
    
    # 构建推理信息
    reasoning = {
        "valuation_method": "Three Methods: DCF + Owner Earnings + Revenue-Based (for Profitable Growth Companies)",
        "company_type": "Profitable Growth Company",
        "dcf_analysis": {
            "signal": "bullish" if dcf_gap > 0.15 else "bearish" if dcf_gap < -0.20 else "neutral",
            "details": f"DCF估值: ¥{dcf_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {dcf_gap:.1%}" if dcf_value > 0 else "DCF估值不可用",
            "stage_breakdown": {
                "stage1": f"¥{dcf_result.get('stage1_value', 0)/100000000:.2f}亿",
                "stage2": f"¥{dcf_result.get('stage2_value', 0)/100000000:.2f}亿",
                "stage3": f"¥{dcf_result.get('stage3_value', 0)/100000000:.2f}亿"
            } if dcf_value > 0 else {}
        },
        "owner_earnings_analysis": {
            "signal": "bullish" if oe_gap > 0.15 else "bearish" if oe_gap < -0.20 else "neutral",
            "details": f"所有者收益法估值: ¥{oe_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {oe_gap:.1%}" if oe_value > 0 else "所有者收益法估值不可用",
            "owner_earnings": f"¥{owner_earnings/100000000:.2f}亿" if owner_earnings > 0 else "N/A"
        },
        "revenue_based_analysis": {
            "signal": "bullish" if revenue_gap > 0.15 else "bearish" if revenue_gap < -0.20 else "neutral",
            "details": f"营收估值: ¥{revenue_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {revenue_gap:.1%}" if revenue_value > 0 else "营收估值不可用",
            "ps_ratio": f"{revenue_result.get('ps_ratio', 0):.2f}",
            "revenue_growth_rate": f"{revenue_growth:.2%}"
        },
        "combined_valuation": {
            "dcf_weight": "30%",
            "owner_earnings_weight": "30%",
            "revenue_weight": "40%",
            "combined_gap": f"{valuation_gap:.1%}"
        }
    }
    
    # 计算置信度：使用三种方法差距绝对值的加权平均
    confidence_value = 0.0
    if dcf_value > 0 and oe_value > 0 and revenue_value > 0:
        confidence_value = 0.3 * abs(dcf_gap) + 0.3 * abs(oe_gap) + 0.4 * abs(revenue_gap)
    elif len(valid_methods) > 0:
        # 如果只有部分方法有效，使用有效方法的加权平均
        total_weight = sum(weights.get(method[0], 0) for method in valid_methods)
        if total_weight > 0:
            confidence_value = sum(weights.get(method[0], 0) * abs(method[1]) for method in valid_methods) / total_weight
        else:
            confidence_value = sum(abs(method[1]) for method in valid_methods) / len(valid_methods)
    
    message_content = {
        "signal": signal,
        "confidence": f"{confidence_value:.0%}",
        "reasoning": reasoning
    }
    
    message = HumanMessage(
        content=json.dumps(message_content),
        name="valuation_agent_v2",
    )
    
    if show_reasoning:
        show_agent_reasoning(message_content, "Valuation Analysis Agent V2 (Profitable Growth Company)")
        state["metadata"]["agent_reasoning"] = message_content
    
    show_workflow_status("Valuation Agent V2 (Profitable Growth Company)", "completed")
    
    return {
        "messages": [message],
        "data": {
            **data,
            "valuation_analysis": message_content
        },
        "metadata": state["metadata"],
    }


def handle_growth_company_valuation(
    state: AgentState,
    fin_data: dict,
    industry_code: str,
    market_cap: float
) -> dict:
    """
    处理成长型亏损公司的估值
    
    使用基于营收的估值方法：
    1. P/S倍数法
    2. 未来盈利能力预测法
    """
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    ticker = data["ticker"]
    industry_name = data.get("industry", "")
    market_cap_yi = data.get("market_cap", 0)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"成长型公司估值分析: {ticker}")
    logger.info(f"行业: {industry_name}")
    logger.info(f"当前市值: ¥{market_cap_yi:.2f}亿")
    logger.info(f"{'='*60}\n")
    
    # 获取营收数据
    operating_revenue = fin_data.get("operating_revenue", 0)
    revenue_growth = fin_data.get("revenue_growth", 0.10)  # 默认10%增长
    
    # 根据行业调整参数
    years_to_profitability = 3  # 默认3年后盈利
    target_profit_margin = 0.10  # 目标净利润率10%
    
    if industry_code == "technology":
        years_to_profitability = 2  # 科技公司可能更快盈利
        target_profit_margin = 0.15  # 科技公司利润率可能更高
    elif industry_code == "healthcare":
        years_to_profitability = 4  # 医药公司可能需要更长时间
        target_profit_margin = 0.20  # 医药公司利润率通常较高
    
    # 获取当前盈利数据（如果已盈利）
    net_income = fin_data.get("net_income", 0)
    net_margin = fin_data.get("net_margin", 0)
    
    # 执行基于营收的估值
    revenue_result = calculate_revenue_based_valuation(
        operating_revenue=operating_revenue,
        revenue_growth_rate=revenue_growth,
        industry_code=industry_code,
        market_cap=market_cap,
        years_to_profitability=years_to_profitability,
        target_profit_margin=target_profit_margin,
        current_net_income=net_income,
        current_net_margin=net_margin
    )
    
    revenue_value = revenue_result.get('revenue_value', 0)
    revenue_value_yi = revenue_value / 100_000_000
    
    # 计算估值差距
    if market_cap > 0:
        revenue_gap = (revenue_value - market_cap) / market_cap
    else:
        revenue_gap = 0
    
    # 确定信号
    if revenue_gap > 0.15:
        signal = 'bullish'
    elif revenue_gap < -0.20:
        signal = 'bearish'
    else:
        signal = 'neutral'
    
    # 构建推理信息
    reasoning = {
        "valuation_method": "Revenue-Based Valuation (for Growth Companies)",
        "company_type": "Growth Company (Currently Unprofitable)",
        "revenue_analysis": {
            "current_revenue": f"¥{operating_revenue/100000000:.2f}亿",
            "revenue_growth_rate": f"{revenue_growth:.2%}",
            "years_to_profitability": years_to_profitability,
            "target_profit_margin": f"{target_profit_margin:.0%}"
        },
        "valuation_details": {
            "ps_method_value": f"¥{revenue_result.get('revenue_value_ps', 0)/100000000:.2f}亿",
            "dcf_method_value": f"¥{revenue_result.get('revenue_value_dcf', 0)/100000000:.2f}亿",
            "combined_value": f"¥{revenue_value_yi:.2f}亿",
            "ps_ratio": f"{revenue_result.get('ps_ratio', 0):.2f}"
        },
        "revenue_based_analysis": {
            "signal": signal,
            "details": f"营收估值: ¥{revenue_value_yi:.2f}亿, 市值: ¥{market_cap_yi:.2f}亿, 差距: {revenue_gap:.1%}" if market_cap > 0 else "营收估值: ¥{revenue_value_yi:.2f}亿, 市值数据不可用"
        }
    }
    
    # 置信度计算：使用营收增长率和估值差距
    confidence_value = min(abs(revenue_gap), revenue_growth) if market_cap > 0 else revenue_growth
    
    message_content = {
        "signal": signal,
        "confidence": f"{confidence_value:.0%}",
        "reasoning": reasoning
    }
    
    message = HumanMessage(
        content=json.dumps(message_content),
        name="valuation_agent_v2",
    )
    
    if show_reasoning:
        show_agent_reasoning(message_content, "Valuation Analysis Agent V2 (Growth Company)")
        state["metadata"]["agent_reasoning"] = message_content
    
    show_workflow_status("Valuation Agent V2 (Growth Company)", "completed")
    
    return {
        "messages": [message],
        "data": {
            **data,
            "valuation_analysis": message_content
        },
        "metadata": state["metadata"],
    }


def fallback_to_traditional_valuation(state: AgentState):
    """
    回退到传统估值方法
    当无法使用新方法时使用
    """
    from src.agents.valuation import valuation_agent
    logger.info("使用传统估值方法...")
    return valuation_agent(state)
