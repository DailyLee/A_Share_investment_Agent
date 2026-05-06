import math
from langchain_core.messages import HumanMessage
from src.utils.logging_config import setup_logger

from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction
from src.config.industry_valuation_params import classify_industry

import json


def _safe_val(v, default=0):
    """将 nan/None 转换为 default，避免 nan 参与比较"""
    if v is None:
        return default
    try:
        if math.isnan(v):
            return default
    except TypeError:
        pass
    return v

# 初始化 logger
logger = setup_logger('fundamentals_agent')

##### Fundamental Agent #####


@agent_endpoint("fundamentals", "基本面分析师，分析公司财务指标、盈利能力和增长潜力")
def fundamentals_agent(state: AgentState):
    """
    基本面分析代理
    
    基于A股市场特点优化：
    1. 盈利能力阈值：ROE > 12%, Net Margin > 10%, Op Margin > 8%（更符合A股实际情况）
    2. 增长指标阈值：Revenue/Earnings/Book Value Growth > 10%（保持合理）
    3. 财务健康阈值：Current Ratio > 1.2, Debt-to-Equity < 60%（更符合A股杠杆水平）
    4. 估值比率阈值：P/E < 30, P/B < 5, P/S < 3（更符合A股估值水平）
    
    本地计算：
    - 评分计算（profitability_score, growth_score, health_score, price_ratio_score）
    - 综合信号判断（基于各维度评分）
    - 置信度计算（基于信号一致性）
    """
    show_workflow_status("Fundamentals Analyst")
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    
    # 检查财务指标数据是否可用
    financial_metrics_list = data.get("financial_metrics", [])
    if not financial_metrics_list or len(financial_metrics_list) == 0:
        logger.warning("⚠️ 财务指标数据不可用（可能 API 调用失败）")
        metrics = {}
    else:
        metrics = financial_metrics_list[0]
        # 检查 metrics 是否为空字典
        if not metrics or len(metrics) == 0:
            logger.warning("⚠️ 财务指标数据为空字典（可能 API 调用失败）")
            metrics = {}

    # Initialize signals list for different fundamental aspects
    signals = []
    reasoning = {}

    # 检测是否为金融行业
    industry_name = data.get("industry", "")
    industry_code = classify_industry(industry_name)
    is_finance = (industry_code == "finance")

    # 1. Profitability Analysis
    return_on_equity = _safe_val(metrics.get("return_on_equity"))
    net_margin = _safe_val(metrics.get("net_margin"))
    operating_margin = _safe_val(metrics.get("operating_margin"))

    if is_finance:
        # 金融公司：net_margin/operating_margin 通常为 nan，用 P/E 和 P/B 辅助判断
        # ROE 已在数据源层面做了年化处理（使用上年年报ROE或简单年化）
        pe_ratio_val = _safe_val(metrics.get("pe_ratio"))
        pb_ratio_val = _safe_val(metrics.get("price_to_book"))

        profitability_score = 0
        if return_on_equity > 0.10:
            profitability_score += 1
        if return_on_equity > 0.15:
            profitability_score += 1
        if 0 < pe_ratio_val < 20:
            profitability_score += 1

        signals.append('bullish' if profitability_score >= 2 else 'bearish' if profitability_score == 0 else 'neutral')
        reasoning["profitability_signal"] = {
            "signal": signals[0],
            "details": f"ROE: {return_on_equity:.2%}, P/E: {pe_ratio_val:.2f}, P/B: {pb_ratio_val:.2f} (金融行业)"
        }
    else:
        thresholds = [
            (return_on_equity, 0.12),
            (net_margin, 0.10),
            (operating_margin, 0.08)
        ]
        profitability_score = sum(
            metric is not None and metric > threshold
            for metric, threshold in thresholds
        )

        signals.append('bullish' if profitability_score >=
                       2 else 'bearish' if profitability_score == 0 else 'neutral')
        has_data = any(metrics.get(key) is not None for key in ['return_on_equity', 'net_margin', 'operating_margin'])

        reasoning["profitability_signal"] = {
            "signal": signals[0],
            "details": (
                f"ROE: {return_on_equity:.2%}" if return_on_equity else "ROE: N/A"
            ) + ", " + (
                f"Net Margin: {net_margin:.2%}" if net_margin else "Net Margin: N/A"
            ) + ", " + (
                f"Op Margin: {operating_margin:.2%}" if operating_margin else "Op Margin: N/A"
            ) + (" (数据获取失败，请检查 API 连接)" if not has_data else "")
        }

    # 2. Growth Analysis
    revenue_growth = _safe_val(metrics.get("revenue_growth"))
    earnings_growth = _safe_val(metrics.get("earnings_growth"))
    book_value_growth = _safe_val(metrics.get("book_value_growth"))

    if is_finance:
        # 金融公司 revenue_growth 通常为 nan，以 earnings_growth 和 book_value_growth 为主
        growth_score = 0
        if earnings_growth > 0.10:
            growth_score += 1
        if book_value_growth > 0.08:
            growth_score += 1
        if earnings_growth > 0:
            growth_score += 1

        signals.append('bullish' if growth_score >= 2 else 'bearish' if growth_score == 0 else 'neutral')
        reasoning["growth_signal"] = {
            "signal": signals[1],
            "details": f"Earnings Growth: {earnings_growth:.2%}, Book Value Growth: {book_value_growth:.2%} (金融行业)"
        }
    else:
        thresholds = [
            (revenue_growth, 0.10),
            (earnings_growth, 0.10),
            (book_value_growth, 0.10)
        ]
        growth_score = sum(
            metric is not None and metric > threshold
            for metric, threshold in thresholds
        )

        signals.append('bullish' if growth_score >=
                       2 else 'bearish' if growth_score == 0 else 'neutral')
        has_growth_data = any(metrics.get(key) is not None for key in ['revenue_growth', 'earnings_growth'])

        reasoning["growth_signal"] = {
            "signal": signals[1],
            "details": (
                f"Revenue Growth: {revenue_growth:.2%}" if revenue_growth else "Revenue Growth: N/A"
            ) + ", " + (
                f"Earnings Growth: {earnings_growth:.2%}" if earnings_growth else "Earnings Growth: N/A"
            ) + (" (数据获取失败，请检查 API 连接)" if not has_growth_data else "")
        }

    # 3. Financial Health
    current_ratio = _safe_val(metrics.get("current_ratio"))
    debt_to_equity = _safe_val(metrics.get("debt_to_equity"))
    free_cash_flow_per_share = _safe_val(metrics.get("free_cash_flow_per_share"))
    earnings_per_share = _safe_val(metrics.get("earnings_per_share"))

    if is_finance:
        # 金融公司：高杠杆是常态，不适用传统流动比率和资产负债率标准
        health_score = 0
        if debt_to_equity > 0 and debt_to_equity < 0.95:
            health_score += 1
        if earnings_per_share and earnings_per_share > 0:
            health_score += 1
        if book_value_growth > 0:
            health_score += 1

        signals.append('bullish' if health_score >= 2 else 'bearish' if health_score == 0 else 'neutral')
        reasoning["financial_health_signal"] = {
            "signal": signals[2],
            "details": f"D/E: {debt_to_equity:.2f}, EPS: {earnings_per_share:.2f}, BV Growth: {book_value_growth:.2%} (金融行业)"
        }
    else:
        health_score = 0
        if current_ratio and current_ratio > 1.2:
            health_score += 1
        if debt_to_equity and debt_to_equity < 0.6:
            health_score += 1
        if (free_cash_flow_per_share and earnings_per_share and
                free_cash_flow_per_share > earnings_per_share * 0.6):
            health_score += 1

        signals.append('bullish' if health_score >=
                       2 else 'bearish' if health_score == 0 else 'neutral')
        has_health_data = any(metrics.get(key) is not None for key in ['current_ratio', 'debt_to_equity'])

        reasoning["financial_health_signal"] = {
            "signal": signals[2],
            "details": (
                f"Current Ratio: {current_ratio:.2f}" if current_ratio else "Current Ratio: N/A"
            ) + ", " + (
                f"D/E: {debt_to_equity:.2f}" if debt_to_equity else "D/E: N/A"
            ) + (" (数据获取失败，请检查 API 连接)" if not has_health_data else "")
        }

    # 4. Price to X ratios
    # 基于A股市场特点优化估值比率阈值
    # A股市场特点：整体估值水平低于成熟市场，但部分成长股估值可能较高
    pe_ratio = metrics.get("pe_ratio", 0)
    price_to_book = metrics.get("price_to_book", 0)
    price_to_sales = metrics.get("price_to_sales", 0)

    # A股市场阈值（更符合实际情况）
    thresholds = [
        (pe_ratio, 30),  # A股市场P/E < 30就算合理（从25提高到30）
        (price_to_book, 5),  # A股市场P/B < 5就算合理（从3提高到5）
        (price_to_sales, 3)  # A股市场P/S < 3就算合理（从5降低到3，更保守）
    ]
    price_ratio_score = sum(
        metric is not None and metric < threshold
        for metric, threshold in thresholds
    )

    signals.append('bullish' if price_ratio_score >=
                   2 else 'bearish' if price_ratio_score == 0 else 'neutral')
    has_valuation_data = any([pe_ratio, price_to_book, price_to_sales])
    
    reasoning["price_ratios_signal"] = {
        "signal": signals[3],
        "details": (
            f"P/E: {pe_ratio:.2f}" if pe_ratio else "P/E: N/A"
        ) + ", " + (
            f"P/B: {price_to_book:.2f}" if price_to_book else "P/B: N/A"
        ) + ", " + (
            f"P/S: {price_to_sales:.2f}" if price_to_sales else "P/S: N/A"
        ) + (" (数据获取失败，请检查 API 连接)" if not has_valuation_data else "")
    }

    # Determine overall signal
    # 优化逻辑：考虑neutral信号的影响，使用加权评分
    # 评分规则：bullish=+1, neutral=0, bearish=-1
    signal_scores = {'bullish': 1, 'neutral': 0, 'bearish': -1}
    total_score = sum(signal_scores[s] for s in signals)
    
    bullish_signals = signals.count('bullish')
    bearish_signals = signals.count('bearish')
    neutral_signals = signals.count('neutral')
    total_signals = len(signals)
    
    # 如果总评分为正，偏向看多；为负，偏向看空；为0，中性
    # 但也要考虑明确的信号数量：如果有2个或以上明确信号（bullish或bearish），优先采用
    if bullish_signals >= 2 and total_score > 0:
        overall_signal = 'bullish'
    elif bearish_signals >= 2 and total_score < 0:
        overall_signal = 'bearish'
    elif total_score > 0:
        overall_signal = 'bullish'
    elif total_score < 0:
        overall_signal = 'bearish'
    else:
        overall_signal = 'neutral'

    # Calculate confidence level
    # 置信度基于明确信号（bullish或bearish）的比例
    # 如果全是neutral，置信度较低
    if bullish_signals + bearish_signals == 0:
        confidence = 0.1  # 全是neutral，置信度很低
    else:
        confidence = max(bullish_signals, bearish_signals) / total_signals

    message_content = {
        "signal": overall_signal,
        "confidence": f"{round(confidence * 100)}%",
        "reasoning": reasoning
    }

    # Create the fundamental analysis message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="fundamentals_agent",
    )

    # Print the reasoning if the flag is set
    if show_reasoning:
        show_agent_reasoning(message_content, "Fundamental Analysis Agent")
        # 保存推理信息到metadata供API使用
        state["metadata"]["agent_reasoning"] = message_content

    show_workflow_status("Fundamentals Analyst", "completed")
    # logger.info(f"--- DEBUG: fundamentals_agent RETURN messages: {[msg.name for msg in [message]]} ---")
    return {
        "messages": [message],
        "data": {
            **data,
            "fundamental_analysis": message_content
        },
        "metadata": state["metadata"],
    }
