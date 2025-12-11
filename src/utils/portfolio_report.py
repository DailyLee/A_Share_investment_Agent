"""投资组合报告生成工具模块

负责生成和保存投资分析报告，包括控制台输出和 Markdown 文件生成。
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from src.utils.logging_config import setup_logger
from src.agents.state import show_agent_reasoning

logger = setup_logger('portfolio_report')


def parse_llm_json_response(response: str) -> dict:
    """解析 LLM 返回的 JSON 响应，处理 markdown 代码块和额外文本
    
    Args:
        response: LLM 返回的原始响应字符串
        
    Returns:
        解析后的 JSON 字典
        
    Raises:
        json.JSONDecodeError: 如果无法解析为有效的 JSON
    """
    if not response:
        raise json.JSONDecodeError("Empty response", response, 0)
    
    # 清理响应
    cleaned_response = response.strip()
    
    # 方法1: 尝试直接解析
    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        pass
    
    # 方法2: 尝试提取 markdown 代码块中的 JSON
    # 匹配 ```json ... ``` 或 ``` ... ```
    json_block_patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',       # ``` ... ```
    ]
    
    for pattern in json_block_patterns:
        match = re.search(pattern, cleaned_response, re.DOTALL)
        if match:
            try:
                json_str = match.group(1).strip()
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    # 方法3: 尝试提取第一个 { ... } 之间的内容
    json_start = cleaned_response.find('{')
    if json_start >= 0:
        json_end = cleaned_response.rfind('}')
        if json_end > json_start:
            json_str = cleaned_response[json_start:json_end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    # 方法4: 尝试提取第一个 [ ... ] 之间的内容（如果是数组格式）
    array_start = cleaned_response.find('[')
    if array_start >= 0:
        array_end = cleaned_response.rfind(']')
        if array_end > array_start:
            json_str = cleaned_response[array_start:array_end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    # 如果所有方法都失败，抛出异常
    raise json.JSONDecodeError(
        f"无法解析 JSON。响应前200字符: {cleaned_response[:200]}",
        cleaned_response,
        0
    )


def parse_agent_message_content(content: str, agent_name: str = "unknown") -> dict:
    """解析 agent 消息内容，处理格式不一致问题
    
    Args:
        content: 消息内容（可能是 JSON 字符串或纯文本）
        agent_name: agent 名称，用于日志
        
    Returns:
        解析后的字典，如果解析失败返回空字典
    """
    if not content:
        return {}
    
    # 尝试解析为 JSON
    try:
        if isinstance(content, str):
            return json.loads(content)
        elif isinstance(content, dict):
            return content
        else:
            return {}
    except (json.JSONDecodeError, TypeError):
        # 如果不是 JSON，返回包含原始内容的字典
        logger.debug(f"{agent_name} 消息不是 JSON 格式，返回原始内容")
        return {"raw_content": content}


def format_decision(action: str, quantity: int, confidence: float, agent_signals: list, reasoning: str, reasoning_zh: str = "", market_wide_news_summary: str = "未提供", raw_agent_data: dict = None) -> dict:
    """Format the trading decision into a standardized output format.
    Think in English but output analysis in Chinese."""
    
    # 确保 agent_signals 是列表且每个元素都是字典
    if not isinstance(agent_signals, list):
        logger.warning(f"agent_signals 不是列表类型: {type(agent_signals)}, 值: {agent_signals}")
        agent_signals = []
    
    # 标准化 agent_signals：统一使用 'agent_name' 键
    # LLM 可能返回 'agent' 或 'agent_name'，我们统一转换为 'agent_name'
    normalized_signals = []
    for s in agent_signals:
        if isinstance(s, dict):
            # 创建标准化后的字典
            normalized_s = dict(s)  # 复制原字典
            
            # 如果只有 'agent' 键，添加 'agent_name' 键
            if "agent" in normalized_s and "agent_name" not in normalized_s:
                normalized_s["agent_name"] = normalized_s["agent"]
            # 如果只有 'agent_name' 键但没有 'agent'，也添加 'agent' 键以保持兼容
            elif "agent_name" in normalized_s and "agent" not in normalized_s:
                normalized_s["agent"] = normalized_s["agent_name"]
            
            # 只要有 'agent' 或 'agent_name' 键，就认为是有效信号
            if "agent_name" in normalized_s or "agent" in normalized_s:
                normalized_signals.append(normalized_s)
    
    valid_signals = normalized_signals
    
    # 记录标准化结果
    if len(valid_signals) < len(agent_signals):
        invalid_count = len(agent_signals) - len(valid_signals)
        logger.warning(f"标准化后过滤掉了 {invalid_count} 个无效的 agent_signals（总共 {len(agent_signals)} 个）")
        logger.debug(f"标准化后的有效信号数量: {len(valid_signals)}")
        for i, s in enumerate(valid_signals):
            logger.debug(f"有效 signal[{i}]: agent_name={s.get('agent_name')}, signal={s.get('signal')}, confidence={s.get('confidence')}")

    # 从 agent_signals 中获取信号和置信度
    fundamental_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") == "fundamental_analysis"), None)
    valuation_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") == "valuation_analysis"), None)
    technical_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") == "technical_analysis"), None)
    sentiment_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") == "sentiment_analysis"), None)
    risk_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") == "risk_management"), None)
    
    # 定义辅助函数（必须在使用之前定义）
    def parse_confidence(confidence_value):
        """解析置信度值，支持字符串和数字格式
        统一处理逻辑：确保返回0-1之间的浮点数
        """
        if confidence_value is None:
            return 0.0
        if isinstance(confidence_value, str):
            cleaned = confidence_value.strip().replace('%', '')
            try:
                value = float(cleaned)
                # 如果大于1，假设是百分比形式，需要除以100
                return value / 100.0 if value > 1.0 else value
            except ValueError:
                return 0.0
        if isinstance(confidence_value, (int, float)):
            # 如果大于1，假设是百分比形式，需要除以100
            return float(confidence_value) / 100.0 if confidence_value > 1.0 else float(confidence_value)
        return 0.0
    
    # 从原始 agent 数据中获取详细信息（如果可用）
    # 优先使用原始数据，因为它包含完整的 reasoning 信息
    fundamental_signal = raw_agent_data.get("fundamentals", {}) if raw_agent_data else {}
    if fundamental_signal_summary:
        # 合并信号摘要（signal, confidence）到原始数据
        fundamental_signal = {**fundamental_signal, **fundamental_signal_summary}
        # 确保 confidence 被正确标准化
        if "confidence" in fundamental_signal:
            fundamental_signal["confidence"] = parse_confidence(fundamental_signal["confidence"])
    
    valuation_signal = raw_agent_data.get("valuation", {}) if raw_agent_data else {}
    if valuation_signal_summary:
        valuation_signal = {**valuation_signal, **valuation_signal_summary}
        # 确保 confidence 被正确标准化（可能是字符串格式如 "38%"）
        if "confidence" in valuation_signal:
            valuation_signal["confidence"] = parse_confidence(valuation_signal["confidence"])
    
    technical_signal = raw_agent_data.get("technical", {}) if raw_agent_data else {}
    if technical_signal_summary:
        technical_signal = {**technical_signal, **technical_signal_summary}
        # 确保 confidence 被正确标准化
        if "confidence" in technical_signal:
            technical_signal["confidence"] = parse_confidence(technical_signal["confidence"])
    
    sentiment_signal = raw_agent_data.get("sentiment", {}) if raw_agent_data else {}
    if sentiment_signal_summary:
        sentiment_signal = {**sentiment_signal, **sentiment_signal_summary}
        # 确保 confidence 被正确标准化
        if "confidence" in sentiment_signal:
            sentiment_signal["confidence"] = parse_confidence(sentiment_signal["confidence"])
    
    risk_signal = raw_agent_data.get("risk", {}) if raw_agent_data else {}
    if risk_signal_summary:
        risk_signal = {**risk_signal, **risk_signal_summary}
    # Existing macro signal from macro_analyst_agent (tool-based)
    # LLM 可能返回 "selected_stock_macro_analysis" 或 "macro_analyst_agent"
    general_macro_signal_summary = next(
        (s for s in valid_signals if s.get("agent_name") in ["macro_analyst_agent", "selected_stock_macro_analysis"]), None)
    
    general_macro_signal = raw_agent_data.get("macro_analyst", {}) if raw_agent_data else {}
    if general_macro_signal_summary:
        general_macro_signal = {**general_macro_signal, **general_macro_signal_summary}
    # New market-wide news summary signal from macro_news_agent
    # LLM 可能返回 "market_wide_news_summary(沪深300指数)" 或 "macro_news_agent"
    market_wide_news_signal = next(
        (s for s in valid_signals if s.get("agent_name") and ("macro_news" in s.get("agent_name", "") or "market_wide" in s.get("agent_name", ""))), None)

    def signal_to_chinese(signal_data):
        if not signal_data:
            return "无数据"
        if signal_data.get("signal") == "bullish":
            return "看多"
        if signal_data.get("signal") == "bearish":
            return "看空"
        return "中性"
    
    def get_valuation_details(valuation_signal):
        """根据估值方法类型返回相应的估值详情"""
        if not valuation_signal:
            return "   - 估值数据不可用"
        
        reasoning = valuation_signal.get('reasoning', {})
        valuation_method = reasoning.get('valuation_method', '')
        company_type = reasoning.get('company_type', '')
        
        # 检查是否为已盈利成长型公司（三种方法）
        if 'Three Methods' in valuation_method or company_type == 'Profitable Growth Company':
            dcf_details = reasoning.get('dcf_analysis', {}).get('details', '无数据')
            oe_details = reasoning.get('owner_earnings_analysis', {}).get('details', '无数据')
            revenue_details = reasoning.get('revenue_based_analysis', {}).get('details', '无数据')
            combined_info = reasoning.get('combined_valuation', {})
            combined_gap = combined_info.get('combined_gap', 'N/A')
            
            # 确保格式一致，移除可能的额外空格和换行，统一处理
            dcf_details = str(dcf_details).strip().replace('\n', ' ').replace('\r', '')
            oe_details = str(oe_details).strip().replace('\n', ' ').replace('\r', '')
            revenue_details = str(revenue_details).strip().replace('\n', ' ').replace('\r', '')
            combined_gap = str(combined_gap).strip()
            
            # 处理DCF详情：转换英文格式为中文格式，避免重复前缀
            # 旧的valuation.py返回英文格式：Intrinsic Value: ¥...亿, Market Cap: ¥...亿, Gap: ...%
            # 新的valuation_v2.py返回中文格式：DCF估值: ¥...亿, 市值: ¥...亿, 差距: ...%
            if dcf_details.startswith('Intrinsic Value:'):
                # 转换英文格式为中文格式
                dcf_display = dcf_details.replace('Intrinsic Value:', 'DCF估值:').replace('Market Cap:', '市值:').replace('Gap:', '差距:')
            elif dcf_details.startswith('DCF估值:'):
                dcf_display = dcf_details
            elif dcf_details.startswith('DCF估值: '):
                dcf_display = dcf_details
            else:
                dcf_display = f"DCF估值: {dcf_details}"
            
            # 处理所有者收益法详情：转换英文格式为中文格式
            if oe_details.startswith('Owner Earnings Value:'):
                # 转换英文格式为中文格式
                oe_display = oe_details.replace('Owner Earnings Value:', '所有者收益法估值:').replace('Market Cap:', '市值:').replace('Gap:', '差距:')
            elif oe_details.startswith('所有者收益法估值:'):
                oe_display = oe_details
            elif oe_details.startswith('所有者收益法估值: '):
                oe_display = oe_details
            else:
                oe_display = f"所有者收益法估值: {oe_details}"
            
            # 统一格式：每行3个空格 + "- " + 内容
            return f"   - {dcf_display}\n   - {oe_display}\n   - 营收估值法: {revenue_details}\n   - 综合估值差距: {combined_gap}"
        
        # 检查是否为基于营收的估值（未盈利成长型公司）
        if 'Revenue-Based' in valuation_method or company_type.startswith('Growth'):
            revenue_analysis = reasoning.get('revenue_based_analysis', {})
            details = revenue_analysis.get('details', '无数据')
            return f"   - 营收估值法（成长型公司）: {details}"
        
        # 标准估值方法（DCF + 所有者收益法）
        dcf_details = reasoning.get('dcf_analysis', {}).get('details', '无数据')
        oe_details = reasoning.get('owner_earnings_analysis', {}).get('details', '无数据')
        
        # 确保格式一致，移除可能的额外空格和换行
        dcf_details = str(dcf_details).strip().replace('\n', ' ').replace('\r', '')
        oe_details = str(oe_details).strip().replace('\n', ' ').replace('\r', '')
        
        # 处理DCF详情：转换英文格式为中文格式，避免重复前缀
        # 旧的valuation.py返回英文格式：Intrinsic Value: ¥...亿, Market Cap: ¥...亿, Gap: ...%
        # 新的valuation_v2.py返回中文格式：DCF估值: ¥...亿, 市值: ¥...亿, 差距: ...%
        if dcf_details.startswith('Intrinsic Value:'):
            # 转换英文格式为中文格式
            dcf_display = dcf_details.replace('Intrinsic Value:', 'DCF估值:').replace('Market Cap:', '市值:').replace('Gap:', '差距:')
        elif dcf_details.startswith('DCF估值:'):
            dcf_display = dcf_details
        elif dcf_details.startswith('DCF估值: '):
            dcf_display = dcf_details
        else:
            dcf_display = f"DCF估值: {dcf_details}"
        
        # 处理所有者收益法详情：转换英文格式为中文格式
        if oe_details.startswith('Owner Earnings Value:'):
            # 转换英文格式为中文格式
            oe_display = oe_details.replace('Owner Earnings Value:', '所有者收益法估值:').replace('Market Cap:', '市值:').replace('Gap:', '差距:')
        elif oe_details.startswith('所有者收益法估值:'):
            oe_display = oe_details
        elif oe_details.startswith('所有者收益法估值: '):
            oe_display = oe_details
        else:
            oe_display = f"所有者收益法估值: {oe_details}"
        
        # 统一格式：每行3个空格 + "- " + 内容
        return f"   - {dcf_display}\n   - {oe_display}"

    detailed_analysis = f"""
====================================
          投资分析报告
====================================

一、策略分析

【权重说明（根据A股市场特点调整）：技术25% + 基本面20% + 估值15% + 宏观25% + 情绪15% = 100%】

1. 技术分析 (权重25%):
   信号: {signal_to_chinese(technical_signal)}
   置信度: {((technical_signal or {}).get('confidence', 0.0) * 100):.0f}%
   要点:
   - 趋势跟踪: ADX={((technical_signal or {}).get('strategy_signals', {}).get('trend_following', {}).get('metrics', {}).get('adx', 0.0)):.2f}
   - 均值回归: RSI(14)={((technical_signal or {}).get('strategy_signals', {}).get('mean_reversion', {}).get('metrics', {}).get('rsi_14', 0.0)):.2f}
   - 动量指标:
     * 1月动量={((technical_signal or {}).get('strategy_signals', {}).get('momentum', {}).get('metrics', {}).get('momentum_1m', 0.0)):.2%}
     * 3月动量={((technical_signal or {}).get('strategy_signals', {}).get('momentum', {}).get('metrics', {}).get('momentum_3m', 0.0)):.2%}
     * 6月动量={((technical_signal or {}).get('strategy_signals', {}).get('momentum', {}).get('metrics', {}).get('momentum_6m', 0.0)):.2%}
   - 波动性: {((technical_signal or {}).get('strategy_signals', {}).get('volatility', {}).get('metrics', {}).get('historical_volatility', 0.0)):.2%}

2. 基本面分析 (权重20%):
   信号: {signal_to_chinese(fundamental_signal)}
   置信度: {((fundamental_signal or {}).get('confidence', 0.0) * 100):.0f}%
   要点:
   - 盈利能力: {(fundamental_signal or {}).get('reasoning', {}).get('profitability_signal', {}).get('details', '无数据')}
   - 增长情况: {(fundamental_signal or {}).get('reasoning', {}).get('growth_signal', {}).get('details', '无数据')}
   - 财务健康: {(fundamental_signal or {}).get('reasoning', {}).get('financial_health_signal', {}).get('details', '无数据')}
   - 估值水平: {(fundamental_signal or {}).get('reasoning', {}).get('price_ratios_signal', {}).get('details', '无数据')}

3. 估值分析 (权重15%):
   信号: {signal_to_chinese(valuation_signal)}
   置信度: {parse_confidence((valuation_signal or {}).get('confidence', 0.0)) * 100:.0f}%
   要点:
   {get_valuation_details(valuation_signal)}

4. 宏观分析 (综合权重25%):
   a) 常规宏观分析 (来自 Macro Analyst Agent):
      信号: {signal_to_chinese(general_macro_signal)}
      置信度: {((general_macro_signal or {}).get('confidence', 0.0) * 100):.0f}%
      宏观环境: {(general_macro_signal or {}).get('macro_environment', '无数据')}
      对股票影响: {(general_macro_signal or {}).get('impact_on_stock', '无数据')}
      关键因素: {', '.join((general_macro_signal or {}).get('key_factors', ['无数据']))}

   b) 大盘宏观新闻分析 (来自 Macro News Agent):
      信号: {signal_to_chinese(market_wide_news_signal)}
      置信度: {((market_wide_news_signal or {}).get('confidence', 0.0) * 100):.0f}%
      摘要或结论: {(market_wide_news_signal or {}).get('reasoning', market_wide_news_summary)}

5. 情绪分析 (权重15%):
   信号: {signal_to_chinese(sentiment_signal)}
   置信度: {((sentiment_signal or {}).get('confidence', 0.0) * 100):.0f}%
   分析: {(sentiment_signal or {}).get('reasoning', '无详细分析')}

二、风险评估
风险评分: {(risk_signal or {}).get('risk_score', '无数据')}/10
主要指标:
- 波动率: {((risk_signal or {}).get('risk_metrics', {}).get('volatility', 0.0) * 100):.1f}%
- 最大回撤: {((risk_signal or {}).get('risk_metrics', {}).get('max_drawdown', 0.0) * 100):.1f}%
- VaR(95%): {((risk_signal or {}).get('risk_metrics', {}).get('value_at_risk_95', 0.0) * 100):.1f}%
- 市场风险: {(risk_signal or {}).get('risk_metrics', {}).get('market_risk_score', '无数据')}/10

三、投资建议
操作建议: {'买入' if action == 'buy' else '卖出' if action == 'sell' else '持有'}
交易数量: {quantity}股
决策置信度: {confidence*100:.0f}%

四、决策依据

### 中文说明
{reasoning_zh if reasoning_zh else '（未提供中文说明）'}

### English Explanation
{reasoning}

===================================="""

    return {
        "action": action,
        "quantity": quantity,
        "confidence": confidence,
        "agent_signals": agent_signals,
        "分析报告": detailed_analysis
    }


def generate_portfolio_report(final_state: Dict[str, Any], show_reasoning: bool = False) -> Optional[str]:
    """生成并保存投资组合分析报告
    
    Args:
        final_state: 工作流的最终状态
        show_reasoning: 是否显示详细推理信息
        
    Returns:
        报告文件路径，如果生成失败返回 None
    """
    try:
        # 获取 portfolio_management_agent 的决策
        portfolio_decision_details = final_state.get("metadata", {}).get("portfolio_management_agent_decision_details", {})
        
        if not portfolio_decision_details or "error" in portfolio_decision_details:
            logger.warning("无法获取投资组合决策详情，跳过报告生成")
            return None
        
        # 解析决策 JSON
        agent_reasoning = final_state.get("metadata", {}).get("agent_reasoning", "")
        if not agent_reasoning:
            logger.warning("无法获取 agent_reasoning，跳过报告生成")
            return None
        
        try:
            # 使用 parse_llm_json_response 来处理可能包含 markdown 代码块的响应
            decision_json = parse_llm_json_response(agent_reasoning)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"无法解析 agent_reasoning 为 JSON: {str(e)}")
            logger.debug(f"agent_reasoning 前500字符: {agent_reasoning[:500]}")
            return None
        
        action = decision_json.get("action", "hold")
        quantity = decision_json.get("quantity", 0)
        confidence = decision_json.get("confidence", 0.0)
        agent_signals = decision_json.get("agent_signals", [])
        reasoning = decision_json.get("reasoning", "")
        reasoning_zh = decision_json.get("reasoning_zh", "")
        
        # 获取市场新闻摘要
        market_wide_news_summary = final_state.get("data", {}).get(
            "macro_news_analysis_result", "大盘宏观新闻分析不可用或未提供。")
        
        # 收集原始 agent 数据
        messages = final_state.get("messages", [])
        raw_agent_data = {}
        
        # 从消息中提取各个 agent 的数据
        agent_name_map = {
            "technical_analyst_agent": "technical",
            "fundamentals_agent": "fundamentals",
            "sentiment_agent": "sentiment",
            "valuation_agent": "valuation",
            "valuation_agent_v2": "valuation",  # 支持V2版本的估值代理
            "risk_management_agent": "risk",
            "macro_analyst_agent": "macro_analyst",
        }
        
        for msg in messages:
            agent_name = msg.name
            if agent_name in agent_name_map:
                try:
                    agent_data = parse_agent_message_content(msg.content, agent_name)
                    if agent_data:
                        raw_agent_data[agent_name_map[agent_name]] = agent_data
                except Exception as e:
                    logger.debug(f"解析 {agent_name} 的数据时出错: {e}")
        
        # 格式化报告
        formatted_report = format_decision(
            action=action,
            quantity=quantity,
            confidence=confidence,
            agent_signals=agent_signals,
            reasoning=reasoning,
            reasoning_zh=reasoning_zh,
            market_wide_news_summary=market_wide_news_summary,
            raw_agent_data=raw_agent_data
        )
        
        if not formatted_report or "分析报告" not in formatted_report:
            logger.warning("格式化报告失败")
            return None
        
        # 打印报告到控制台
        logger.info("\n" + "="*60)
        logger.info("📊 投资分析报告")
        logger.info("="*60)
        logger.info(formatted_report["分析报告"])
        logger.info("="*60 + "\n")
        
        if show_reasoning:
            show_agent_reasoning("portfolio_management_agent", formatted_report["分析报告"])
        
        # 生成并保存 Markdown 文件
        ticker = final_state.get("data", {}).get("ticker", "UNKNOWN")
        stock_name = final_state.get("data", {}).get("stock_name", "")
        current_date = datetime.now().strftime("%Y%m%d")
        report_filename = f"{ticker}_{current_date}.md"
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        reports_dir = os.path.join(project_root, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        report_filepath = os.path.join(reports_dir, report_filename)
        
        # 构建 Markdown 内容
        report_text = formatted_report["分析报告"]
        # 将等号分隔线转换为 markdown 分隔线
        report_text = re.sub(r'={60,}', '---', report_text)
        # 将文本中的标题转换为 markdown 标题
        report_text = re.sub(r'^(\d+[\.、])\s*(.+)$', r'## \2', report_text, flags=re.MULTILINE)
        
        # 如果启用了 show_reasoning，收集所有 agent 的详细推理信息
        detailed_reasoning_section = ""
        if show_reasoning:
            detailed_reasoning_parts = []
            
            # Agent 名称映射（中文显示名称）
            agent_display_name_map = {
                "technical_analyst_agent": "技术分析师",
                "fundamentals_agent": "基本面分析师",
                "sentiment_agent": "情绪分析师",
                "valuation_agent": "估值分析师",
                "valuation_agent_v2": "估值分析师（V2）",  # 支持V2版本的估值代理
                "risk_management_agent": "风险管理专家",
                "macro_analyst_agent": "宏观分析师",
                "macro_news_agent": "宏观新闻分析师",
                "researcher_bull_agent": "看多研究员",
                "researcher_bear_agent": "看空研究员",
                "debate_room_agent": "辩论室"
            }
            
            # 收集各个 agent 的详细数据
            for msg in messages:
                agent_name = msg.name
                if agent_name and agent_name in agent_display_name_map:
                    try:
                        # 解析消息内容
                        agent_data = parse_agent_message_content(msg.content, agent_name)
                        if agent_data:
                            display_name = agent_display_name_map.get(agent_name, agent_name)
                            detailed_reasoning_parts.append(f"""
### {display_name} ({agent_name})

```json
{json.dumps(agent_data, ensure_ascii=False, indent=2)}
```
""")
                    except Exception as e:
                        logger.debug(f"解析 {agent_name} 的详细推理信息时出错: {e}")
            
            if detailed_reasoning_parts:
                detailed_reasoning_section = f"""

---

## 详细推理信息

> 以下内容包含各个分析 Agent 的完整推理过程和详细数据，仅在启用 `--show-reasoning` 参数时显示。

{''.join(detailed_reasoning_parts)}
"""
        
        # 构建股票名称行（如果有的话）
        stock_name_line = f"- **股票名称**: {stock_name}\n" if stock_name else ""
        
        markdown_content = f"""# 投资分析报告

## 基本信息

- **股票代码**: {ticker}
{stock_name_line}- **分析日期**: {datetime.now().strftime("%Y年%m月%d日")}
- **报告生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{report_text}

---

## 最终决策

- **操作建议**: {'买入' if action == 'buy' else '卖出' if action == 'sell' else '持有'}
- **交易数量**: {quantity} 股
- **决策置信度**: {confidence*100:.1f}%

## 原始决策数据

<details>
<summary>点击查看原始 JSON 数据</summary>

```json
{json.dumps(decision_json, ensure_ascii=False, indent=2)}
```

</details>
{detailed_reasoning_section}
---

*本报告由 AI 投资分析系统自动生成，仅供参考，不构成投资建议。市场有风险，投资需谨慎。*
"""
        
        # 保存文件
        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"✅ 投资分析报告已保存至: {report_filepath}")
        return report_filepath
        
    except Exception as e:
        logger.warning(f"生成投资分析报告时出错: {e}")
        logger.exception("详细错误:")
        return None

