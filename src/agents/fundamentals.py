from langchain_core.messages import HumanMessage
from src.utils.logging_config import setup_logger

from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction

import json

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

    # 1. Profitability Analysis
    # 基于A股市场特点优化阈值
    # A股市场特点：整体盈利能力低于成熟市场，ROE和利润率通常较低
    return_on_equity = metrics.get("return_on_equity", 0)
    net_margin = metrics.get("net_margin", 0)
    operating_margin = metrics.get("operating_margin", 0)

    # A股市场阈值（更符合实际情况）
    thresholds = [
        (return_on_equity, 0.12),  # A股市场ROE > 12%就算不错（从15%降低到12%）
        (net_margin, 0.10),  # A股市场净利润率 > 10%就算不错（从20%降低到10%）
        (operating_margin, 0.08)  # A股市场营业利润率 > 8%就算不错（从15%降低到8%）
    ]
    profitability_score = sum(
        metric is not None and metric > threshold
        for metric, threshold in thresholds
    )

    signals.append('bullish' if profitability_score >=
                   2 else 'bearish' if profitability_score == 0 else 'neutral')
    # 检查是否有任何财务数据
    has_data = any(metrics.get(key) is not None for key in ['return_on_equity', 'net_margin', 'operating_margin'])
    
    reasoning["profitability_signal"] = {
        "signal": signals[0],
        "details": (
            f"ROE: {metrics.get('return_on_equity', 0):.2%}" if metrics.get(
                "return_on_equity") is not None else "ROE: N/A"
        ) + ", " + (
            f"Net Margin: {metrics.get('net_margin', 0):.2%}" if metrics.get(
                "net_margin") is not None else "Net Margin: N/A"
        ) + ", " + (
            f"Op Margin: {metrics.get('operating_margin', 0):.2%}" if metrics.get(
                "operating_margin") is not None else "Op Margin: N/A"
        ) + (" (数据获取失败，请检查 API 连接)" if not has_data else "")
    }

    # 2. Growth Analysis
    # 基于A股市场特点：增长指标阈值保持10%合理（A股市场增长波动性大）
    revenue_growth = metrics.get("revenue_growth", 0)
    earnings_growth = metrics.get("earnings_growth", 0)
    book_value_growth = metrics.get("book_value_growth", 0)

    thresholds = [
        (revenue_growth, 0.10),  # 10% revenue growth（A股市场合理阈值）
        (earnings_growth, 0.10),  # 10% earnings growth（A股市场合理阈值）
        (book_value_growth, 0.10)  # 10% book value growth（A股市场合理阈值）
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
            f"Revenue Growth: {metrics.get('revenue_growth', 0):.2%}" if metrics.get(
                "revenue_growth") is not None else "Revenue Growth: N/A"
        ) + ", " + (
            f"Earnings Growth: {metrics.get('earnings_growth', 0):.2%}" if metrics.get(
                "earnings_growth") is not None else "Earnings Growth: N/A"
        ) + (" (数据获取失败，请检查 API 连接)" if not has_growth_data else "")
    }

    # 3. Financial Health
    # 基于A股市场特点优化财务健康指标
    current_ratio = metrics.get("current_ratio", 0)
    debt_to_equity = metrics.get("debt_to_equity", 0)  # 注意：这里实际是资产负债率（0-1之间）
    free_cash_flow_per_share = metrics.get("free_cash_flow_per_share", 0)
    earnings_per_share = metrics.get("earnings_per_share", 0)

    health_score = 0
    # A股市场：流动比率 > 1.2 就算不错（从1.5降低到1.2，更符合A股实际情况）
    if current_ratio and current_ratio > 1.2:  # Good liquidity
        health_score += 1
    # A股市场：资产负债率 < 60% 就算不错（从50%提高到60%，A股公司杠杆通常较高）
    # 注意：debt_to_equity 实际存储的是资产负债率（百分比转小数），所以 < 0.6 表示 < 60%
    if debt_to_equity and debt_to_equity < 0.6:  # Reasonable debt levels for A-share market
        health_score += 1
    # A股市场：自由现金流/每股收益 > 0.6 就算不错（从0.8降低到0.6，更符合A股实际情况）
    if (free_cash_flow_per_share and earnings_per_share and
            free_cash_flow_per_share > earnings_per_share * 0.6):  # Good FCF conversion
        health_score += 1

    signals.append('bullish' if health_score >=
                   2 else 'bearish' if health_score == 0 else 'neutral')
    has_health_data = any(metrics.get(key) is not None for key in ['current_ratio', 'debt_to_equity'])
    
    reasoning["financial_health_signal"] = {
        "signal": signals[2],
        "details": (
            f"Current Ratio: {metrics.get('current_ratio', 0):.2f}" if metrics.get(
                "current_ratio") is not None else "Current Ratio: N/A"
        ) + ", " + (
            f"D/E: {metrics.get('debt_to_equity', 0):.2f}" if metrics.get(
                "debt_to_equity") is not None else "D/E: N/A"
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
