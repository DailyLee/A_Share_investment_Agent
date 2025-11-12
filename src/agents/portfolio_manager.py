from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
import json
import re
import os
from datetime import datetime
from src.utils.logging_config import setup_logger

from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.tools.openrouter_config import get_chat_completion
from src.utils.api_utils import agent_endpoint, log_llm_interaction

# 初始化 logger
logger = setup_logger('portfolio_management_agent')

##### Portfolio Management Agent #####

# Helper function to get the latest message by agent name


def get_latest_message_by_name(messages: list, name: str):
    for msg in reversed(messages):
        if msg.name == name:
            return msg
    logger.warning(
        f"Message from agent '{name}' not found in portfolio_management_agent.")
    # Return a dummy message object or raise an error, depending on desired handling
    # For now, returning a dummy message to avoid crashing, but content will be None.
    return HumanMessage(content=json.dumps({"signal": "error", "details": f"Message from {name} not found"}), name=name)


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


def normalize_confidence(confidence_value) -> float:
    """标准化 confidence 值为 0-1 之间的浮点数
    
    处理不同格式：
    - 字符串 "75%" -> 0.75
    - 字符串 "0.75" -> 0.75
    - 数字 0.75 -> 0.75
    - 数字 75 -> 0.75 (假设是百分比)
    
    Args:
        confidence_value: 原始 confidence 值
        
    Returns:
        标准化后的浮点数 (0-1)
    """
    if confidence_value is None:
        return 0.0
    
    if isinstance(confidence_value, (int, float)):
        # 如果是数字，检查是否大于1（可能是百分比形式）
        if confidence_value > 1.0:
            return confidence_value / 100.0
        return float(confidence_value)
    
    if isinstance(confidence_value, str):
        # 移除空格和百分号
        cleaned = confidence_value.strip().replace('%', '')
        try:
            value = float(cleaned)
            # 如果大于1，假设是百分比形式
            if value > 1.0:
                return value / 100.0
            return value
        except ValueError:
            logger.warning(f"无法解析 confidence 值: {confidence_value}")
            return 0.0
    
    return 0.0


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


@agent_endpoint("portfolio_management", "负责投资组合管理和最终交易决策")
def portfolio_management_agent(state: AgentState):
    """Responsible for portfolio management"""
    agent_name = "portfolio_management_agent"
    logger.info(f"\n--- DEBUG: {agent_name} START ---")
    logger.info(f"🔍 DEBUG: 收到的消息列表: {[msg.name for msg in state['messages']]}")
    logger.info(f"🔍 DEBUG: 消息数量: {len(state['messages'])}")

    # Log raw incoming messages
    # logger.info(
    # f"--- DEBUG: {agent_name} RAW INCOMING messages: {[msg.name for msg in state['messages']]} ---")
    # for i, msg in enumerate(state['messages']):
    #     logger.info(
    #         f"  DEBUG RAW MSG {i}: name='{msg.name}', content_preview='{str(msg.content)[:100]}...'")

    # Clean and unique messages by agent name, taking the latest if duplicates exist
    # This is crucial because this agent is a sink for multiple paths.
    unique_incoming_messages = {}
    for msg in state["messages"]:
        # Keep overriding with later messages to get the latest by name
        unique_incoming_messages[msg.name] = msg

    cleaned_messages_for_processing = list(unique_incoming_messages.values())
    # logger.info(
    # f"--- DEBUG: {agent_name} CLEANED messages for processing: {[msg.name for msg in cleaned_messages_for_processing]} ---")

    show_workflow_status(f"{agent_name}: --- Executing Portfolio Manager ---")
    show_reasoning_flag = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]

    # 保护检查：确保关键消息存在
    # 如果缺少 macro_analyst_agent 或 risk_management_agent，说明工作流执行顺序有问题
    # 在这种情况下，提前返回，不执行主要逻辑，避免重复打印报告
    required_agents = ["macro_analyst_agent", "risk_management_agent"]
    missing_agents = [agent for agent in required_agents 
                     if not any(msg.name == agent for msg in cleaned_messages_for_processing)]
    
    if missing_agents:
        logger.warning(f"⚠️ 缺少关键消息: {missing_agents}，portfolio_management_agent 可能被过早触发，跳过本次执行")
        logger.warning(f"当前消息列表: {[msg.name for msg in cleaned_messages_for_processing]}")
        # 提前返回，不执行主要逻辑，避免重复打印报告
        # 返回当前状态，等待所有输入都准备好
        return {
            "messages": state["messages"],
            "data": state["data"],
            "metadata": state["metadata"]
        }

    # Get messages from other agents using the cleaned list
    technical_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "technical_analyst_agent")
    fundamentals_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "fundamentals_agent")
    sentiment_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "sentiment_agent")
    valuation_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "valuation_agent")
    risk_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "risk_management_agent")
    tool_based_macro_message = get_latest_message_by_name(
        cleaned_messages_for_processing, "macro_analyst_agent")  # This is the main analysis path output

    # Extract and parse content from messages, handling format inconsistencies
    technical_data = parse_agent_message_content(
        technical_message.content if technical_message else None, "technical_analyst_agent")
    fundamentals_data = parse_agent_message_content(
        fundamentals_message.content if fundamentals_message else None, "fundamentals_agent")
    sentiment_data = parse_agent_message_content(
        sentiment_message.content if sentiment_message else None, "sentiment_agent")
    valuation_data = parse_agent_message_content(
        valuation_message.content if valuation_message else None, "valuation_agent")
    risk_data = parse_agent_message_content(
        risk_message.content if risk_message else None, "risk_management_agent")
    tool_based_macro_data = parse_agent_message_content(
        tool_based_macro_message.content if tool_based_macro_message else None, "macro_analyst_agent")
    
    # 标准化 confidence 值并重新序列化为 JSON 字符串（用于 LLM prompt）
    # 同时保留原始数据用于后续处理
    # Technical agent 有复杂的结构，保留 strategy_signals
    technical_content_data = {
        "signal": technical_data.get("signal", "error"),
        "confidence": normalize_confidence(technical_data.get("confidence", 0.0)),
    }
    if "strategy_signals" in technical_data:
        technical_content_data["strategy_signals"] = technical_data["strategy_signals"]
    if "reasoning" in technical_data:
        technical_content_data["reasoning"] = technical_data["reasoning"]
    technical_content = json.dumps(technical_content_data)
    fundamentals_content = json.dumps({
        "signal": fundamentals_data.get("signal", "error"),
        "confidence": normalize_confidence(fundamentals_data.get("confidence", 0.0)),
        "details": fundamentals_data.get("details", "Fundamentals message missing" if not fundamentals_data else "Available")
    })
    sentiment_content = json.dumps({
        "signal": sentiment_data.get("signal", "error"),
        "confidence": normalize_confidence(sentiment_data.get("confidence", 0.0)),
        "details": sentiment_data.get("details", "Sentiment message missing" if not sentiment_data else "Available")
    })
    valuation_content = json.dumps({
        "signal": valuation_data.get("signal", "error"),
        "confidence": normalize_confidence(valuation_data.get("confidence", 0.0)),
        "details": valuation_data.get("details", "Valuation message missing" if not valuation_data else "Available")
    })
    risk_content = json.dumps({
        "signal": risk_data.get("trading_action", "error"),
        "max_position_size": risk_data.get("max_position_size", 0),
        "risk_score": risk_data.get("risk_score", 0),
        "details": risk_data.get("details", "Risk message missing" if not risk_data else "Available")
    })
    tool_based_macro_content = json.dumps({
        "signal": tool_based_macro_data.get("impact_on_stock", "error"),
        "macro_environment": tool_based_macro_data.get("macro_environment", "neutral"),
        "details": tool_based_macro_data.get("details", "Tool-based Macro message missing" if not tool_based_macro_data else "Available")
    })

    # Market-wide news summary from macro_news_agent (already correctly fetched from state["data"])
    market_wide_news_summary_content = state["data"].get(
        "macro_news_analysis_result", "大盘宏观新闻分析不可用或未提供。")
    # Optional: also try to get the message object for consistency in agent_signals, though data field is primary source
    macro_news_agent_message_obj = get_latest_message_by_name(
        cleaned_messages_for_processing, "macro_news_agent")

    system_message_content = """You are a portfolio manager making final trading decisions.
            Your job is to make a trading decision based on the team's analysis while strictly adhering
            to risk management constraints.

            RISK MANAGEMENT CONSTRAINTS:
            - You MUST NOT exceed the max_position_size specified by the risk manager
            - You MUST follow the trading_action (buy/sell/hold) recommended by risk management
            - These are hard constraints that cannot be overridden by other signals

            When weighing the different signals for direction and timing:
            1. Valuation Analysis (30% weight)
            2. Fundamental Analysis (25% weight)
            3. Technical Analysis (20% weight)
            4. Macro Analysis (15% weight) - This encompasses TWO inputs:
               a) General Macro Environment (from Macro Analyst Agent, tool-based)
               b) Daily Market-Wide News Summary (from Macro News Agent)
               Both provide context for external risks and opportunities.
            5. Sentiment Analysis (10% weight)

            The decision process should be:
            1. First check risk management constraints
            2. Then evaluate valuation signal
            3. Then evaluate fundamentals signal
            4. Consider BOTH the General Macro Environment AND the Daily Market-Wide News Summary.
            5. Use technical analysis for timing
            6. Consider sentiment for final adjustment

            Provide the following in your output JSON:
            - "action": "buy" | "sell" | "hold",
            - "quantity": <positive integer>
            - "confidence": <float between 0 and 1>
            - "agent_signals": <list of agent signals including agent name, signal (bullish | bearish | neutral), and their confidence>.
              IMPORTANT: Your 'agent_signals' list MUST include entries for:
                - "technical_analysis"
                - "fundamental_analysis"
                - "sentiment_analysis"
                - "valuation_analysis"
                - "risk_management"
                - "selected_stock_macro_analysis" (representing the tool-based macro input from macro_analyst_agent)
                - "market_wide_news_summary(沪深300指数)" (representing the daily news summary input from macro_news_agent - provide a brief signal like bullish/bearish/neutral for the news summary itself, or state if it was primarily factored into overall reasoning with confidence reflecting its impact)
            - "reasoning": <concise explanation of the decision including how you weighted ALL signals, including both macro inputs>

            Trading Rules:
            - Never exceed risk management position limits
            - Only buy if you have available cash
            - Only sell if you have shares to sell
            - Quantity must be ≤ current position for sells
            - Quantity must be ≤ max_position_size from risk management"""
    system_message = {
        "role": "system",
        "content": system_message_content
    }

    user_message_content = f"""Based on the team's analysis below, make your trading decision.

            Technical Analysis Signal: {technical_content}
            Fundamental Analysis Signal: {fundamentals_content}
            Sentiment Analysis Signal: {sentiment_content}
            Valuation Analysis Signal: {valuation_content}
            Risk Management Signal: {risk_content}
            General Macro Analysis (from Macro Analyst Agent): {tool_based_macro_content}
            Daily Market-Wide News Summary (from Macro News Agent):
            {market_wide_news_summary_content}

            Current Portfolio:
            Cash: {portfolio['cash']:.2f}
            Current Position: {portfolio['stock']} shares

            Output JSON only. Ensure 'agent_signals' includes all required agents as per system prompt."""
    user_message = {
        "role": "user",
        "content": user_message_content
    }

    show_agent_reasoning(
        agent_name, f"Preparing LLM. User msg includes: TA, FA, Sent, Val, Risk, GeneralMacro, MarketNews.")

    llm_interaction_messages = [system_message, user_message]
    llm_response_content = get_chat_completion(llm_interaction_messages)

    current_metadata = state["metadata"]
    current_metadata["current_agent_name"] = agent_name

    def get_llm_result_for_logging_wrapper():
        return llm_response_content
    log_llm_interaction(state)(get_llm_result_for_logging_wrapper)()

    if llm_response_content is None:
        show_agent_reasoning(
            agent_name, "LLM call failed. Using default conservative decision.")
        # Ensure the dummy response matches the expected structure for agent_signals
        llm_response_content = json.dumps({
            "action": "hold",
            "quantity": 0,
            "confidence": 0.7,
            "agent_signals": [
                {"agent_name": "technical_analysis",
                    "signal": "neutral", "confidence": 0.0},
                {"agent_name": "fundamental_analysis",
                    "signal": "neutral", "confidence": 0.0},
                {"agent_name": "sentiment_analysis",
                    "signal": "neutral", "confidence": 0.0},
                {"agent_name": "valuation_analysis",
                    "signal": "neutral", "confidence": 0.0},
                {"agent_name": "risk_management",
                    "signal": "hold", "confidence": 1.0},
                {"agent_name": "macro_analyst_agent",
                    "signal": "neutral", "confidence": 0.0},
                {"agent_name": "macro_news_agent",
                    "signal": "unavailable_or_llm_error", "confidence": 0.0}
            ],
            "reasoning": "LLM API error. Defaulting to conservative hold based on risk management."
        })

    final_decision_message = HumanMessage(
        content=llm_response_content,
        name=agent_name,
    )

    if show_reasoning_flag:
        show_agent_reasoning(
            agent_name, f"Final LLM decision JSON: {llm_response_content}")

    agent_decision_details_value = {}
    formatted_report = None
    try:
        # 使用改进的 JSON 解析函数
        decision_json = parse_llm_json_response(llm_response_content)
        action = decision_json.get("action", "hold")
        quantity = decision_json.get("quantity", 0)
        confidence = decision_json.get("confidence", 0.0)
        agent_signals = decision_json.get("agent_signals", [])
        reasoning = decision_json.get("reasoning", "")
        
        agent_decision_details_value = {
            "action": action,
            "quantity": quantity,
            "confidence": confidence,
            "reasoning_snippet": reasoning[:150] + "..." if reasoning else ""
        }
        
        # 格式化并打印投资分析报告
        try:
            # 记录 agent_signals 的结构以便调试
            logger.debug(f"agent_signals 类型: {type(agent_signals)}, 长度: {len(agent_signals) if isinstance(agent_signals, list) else 'N/A'}")
            if isinstance(agent_signals, list) and len(agent_signals) > 0:
                logger.debug(f"第一个 signal 的类型: {type(agent_signals[0])}, 内容: {agent_signals[0]}")
            
            # 传递原始 agent 数据以获取详细信息
            formatted_report = format_decision(
                action=action,
                quantity=quantity,
                confidence=confidence,
                agent_signals=agent_signals,
                reasoning=reasoning,
                market_wide_news_summary=market_wide_news_summary_content,
                # 传递原始 agent 数据以获取详细信息
                raw_agent_data={
                    "fundamentals": fundamentals_data,
                    "valuation": valuation_data,
                    "technical": technical_data,
                    "sentiment": sentiment_data,
                    "risk": risk_data,
                    "macro_analyst": tool_based_macro_data
                }
            )
            
            # 打印投资分析报告（只打印一次）
            # 检查是否已经打印过报告（通过检查 metadata 中的标志）
            report_already_printed = state["metadata"].get("portfolio_report_printed", False)
            
            if formatted_report and "分析报告" in formatted_report and not report_already_printed:
                logger.info("\n" + "="*60)
                logger.info("📊 投资分析报告")
                logger.info("="*60)
                logger.info(formatted_report["分析报告"])
                logger.info("="*60 + "\n")
                
                # 如果启用了 show_reasoning，也通过 show_agent_reasoning 显示
                if show_reasoning_flag:
                    show_agent_reasoning(agent_name, formatted_report["分析报告"])
                
                # 保存为 markdown 文件
                try:
                    ticker = state["data"].get("ticker", "UNKNOWN")
                    current_date = datetime.now().strftime("%Y%m%d")
                    report_filename = f"{ticker}_{current_date}.md"
                    
                    # 创建 reports 目录（如果不存在）
                    # 获取项目根目录：从 src/agents/portfolio_manager.py 向上三级
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    reports_dir = os.path.join(project_root, "reports")
                    os.makedirs(reports_dir, exist_ok=True)
                    
                    report_filepath = os.path.join(reports_dir, report_filename)
                    
                    # 构建完整的 markdown 报告
                    # 将文本报告转换为 markdown 格式（处理等号分隔线）
                    report_text = formatted_report["分析报告"]
                    # 将等号分隔线转换为 markdown 分隔线
                    report_text = re.sub(r'={60,}', '---', report_text)
                    # 将文本中的标题转换为 markdown 标题
                    report_text = re.sub(r'^(\d+[\.、])\s*(.+)$', r'## \2', report_text, flags=re.MULTILINE)
                    
                    # 如果启用了 show_reasoning，收集所有 agent 的详细推理信息
                    detailed_reasoning_section = ""
                    if show_reasoning_flag:
                        detailed_reasoning_parts = []
                        
                        # Agent 名称映射（中文显示名称）
                        agent_name_map = {
                            "technical_analyst_agent": "技术分析师",
                            "fundamentals_agent": "基本面分析师",
                            "sentiment_agent": "情绪分析师",
                            "valuation_agent": "估值分析师",
                            "risk_management_agent": "风险管理专家",
                            "macro_analyst_agent": "宏观分析师",
                            "macro_news_agent": "宏观新闻分析师",
                            "researcher_bull_agent": "看多研究员",
                            "researcher_bear_agent": "看空研究员",
                            "debate_room_agent": "辩论室"
                        }
                        
                        # 收集各个 agent 的详细数据
                        for msg in cleaned_messages_for_processing:
                            agent_name = msg.name
                            if agent_name and agent_name in agent_name_map:
                                try:
                                    # 解析消息内容
                                    agent_data = parse_agent_message_content(msg.content, agent_name)
                                    if agent_data:
                                        display_name = agent_name_map.get(agent_name, agent_name)
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
                    
                    markdown_content = f"""# 投资分析报告

## 基本信息

- **股票代码**: {ticker}
- **分析日期**: {datetime.now().strftime("%Y年%m月%d日")}
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
                except Exception as e:
                    logger.warning(f"保存 markdown 报告时出错: {e}")
                    logger.exception("详细错误:")
                
                # 标记报告已打印，避免重复打印
                state["metadata"]["portfolio_report_printed"] = True
            elif report_already_printed:
                logger.debug("投资分析报告已打印，跳过重复打印")
        except Exception as e:
            logger.warning(f"格式化投资分析报告时出错: {e}")
            logger.exception("详细错误:")
            
    except json.JSONDecodeError as e:
        agent_decision_details_value = {
            "error": "Failed to parse LLM decision JSON from portfolio manager",
            "raw_response_snippet": llm_response_content[:500] + "..." if len(llm_response_content) > 500 else llm_response_content
        }
        logger.error(f"无法解析 LLM 返回的 JSON: {str(e)}")
        logger.error(f"LLM 原始响应（前500字符）: {llm_response_content[:500]}")
        logger.exception("JSON 解析错误详情:")

    show_workflow_status(f"{agent_name}: --- Portfolio Manager Completed ---")
    logger.info(f"🏁 DEBUG: {agent_name} 执行完成，准备返回结果")
    logger.info(f"🔍 DEBUG: 返回的消息数量: {len(cleaned_messages_for_processing) + 1}")

    # The portfolio_management_agent is a terminal or near-terminal node in terms of new message generation for the main state.
    # It should return its own decision, and an updated state["messages"] that includes its decision.
    # As it's a汇聚点, it should ideally start with a cleaned list of messages from its inputs.
    # The cleaned_messages_for_processing already did this. We append its new message to this cleaned list.

    # If we strictly want to follow the pattern of `state["messages"] + [new_message]` for all non-leaf nodes,
    # then the `cleaned_messages_for_processing` should become the new `state["messages"]` for this node's context.
    # However, for simplicity and robustness, let's assume its output `messages` should just be its own message added to the cleaned input it processed.

    final_messages_output = cleaned_messages_for_processing + [final_decision_message]
    # Alternative if we want to be super strict about adding to the raw incoming state["messages"]:
    # final_messages_output = state["messages"] + [final_decision_message]
    # But this ^ is prone to the duplication we are trying to solve if not careful.
    # The most robust is that portfolio_manager provides its clear output, and the graph handles accumulation if needed for further steps (none in this case as it's END).

    logger.info(
        f"🔍 DEBUG: {agent_name} RETURN messages: {[msg.name for msg in final_messages_output]}")
    logger.info(f"✅ DEBUG: {agent_name} 返回状态字典，包含 {len(final_messages_output)} 条消息")

    return {
        "messages": final_messages_output,
        "data": state["data"],
        "metadata": {
            **state["metadata"],
            f"{agent_name}_decision_details": agent_decision_details_value,
            "agent_reasoning": llm_response_content
        }
    }


def format_decision(action: str, quantity: int, confidence: float, agent_signals: list, reasoning: str, market_wide_news_summary: str = "未提供", raw_agent_data: dict = None) -> dict:
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
    
    # 从原始 agent 数据中获取详细信息（如果可用）
    # 优先使用原始数据，因为它包含完整的 reasoning 信息
    fundamental_signal = raw_agent_data.get("fundamentals", {}) if raw_agent_data else {}
    if fundamental_signal_summary:
        # 合并信号摘要（signal, confidence）到原始数据
        fundamental_signal = {**fundamental_signal, **fundamental_signal_summary}
    
    valuation_signal = raw_agent_data.get("valuation", {}) if raw_agent_data else {}
    if valuation_signal_summary:
        valuation_signal = {**valuation_signal, **valuation_signal_summary}
    
    technical_signal = raw_agent_data.get("technical", {}) if raw_agent_data else {}
    if technical_signal_summary:
        technical_signal = {**technical_signal, **technical_signal_summary}
    
    sentiment_signal = raw_agent_data.get("sentiment", {}) if raw_agent_data else {}
    if sentiment_signal_summary:
        sentiment_signal = {**sentiment_signal, **sentiment_signal_summary}
    
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

    detailed_analysis = f"""
====================================
          投资分析报告
====================================

一、策略分析

1. 基本面分析 (权重30%):
   信号: {signal_to_chinese(fundamental_signal)}
   置信度: {((fundamental_signal or {}).get('confidence', 0.0) * 100):.0f}%
   要点:
   - 盈利能力: {(fundamental_signal or {}).get('reasoning', {}).get('profitability_signal', {}).get('details', '无数据')}
   - 增长情况: {(fundamental_signal or {}).get('reasoning', {}).get('growth_signal', {}).get('details', '无数据')}
   - 财务健康: {(fundamental_signal or {}).get('reasoning', {}).get('financial_health_signal', {}).get('details', '无数据')}
   - 估值水平: {(fundamental_signal or {}).get('reasoning', {}).get('price_ratios_signal', {}).get('details', '无数据')}

2. 估值分析 (权重35%):
   信号: {signal_to_chinese(valuation_signal)}
   置信度: {((valuation_signal or {}).get('confidence', 0.0) * 100):.0f}%
   要点:
   - DCF估值: {(valuation_signal or {}).get('reasoning', {}).get('dcf_analysis', {}).get('details', '无数据')}
   - 所有者收益法: {(valuation_signal or {}).get('reasoning', {}).get('owner_earnings_analysis', {}).get('details', '无数据')}

3. 技术分析 (权重25%):
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

4. 宏观分析 (综合权重15%):
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

5. 情绪分析 (权重10%):
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
{reasoning}

===================================="""

    return {
        "action": action,
        "quantity": quantity,
        "confidence": confidence,
        "agent_signals": agent_signals,
        "分析报告": detailed_analysis
    }
