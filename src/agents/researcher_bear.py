from langchain_core.messages import HumanMessage
from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction
from src.utils.logging_config import setup_logger
import json
import ast

logger = setup_logger('researcher_bear_agent')


@agent_endpoint("researcher_bear", "空方研究员，从看空角度分析市场数据并提出风险警示")
def researcher_bear_agent(state: AgentState):
    """Analyzes signals from a bearish perspective and generates cautionary investment thesis."""
    show_workflow_status("Bearish Researcher")
    show_reasoning = state["metadata"]["show_reasoning"]

    # Fetch messages from analysts (with error handling)
    try:
        technical_message = next(
            msg for msg in state["messages"] if msg.name == "technical_analyst_agent")
    except StopIteration:
        logger.warning("未找到technical_analyst_agent消息，使用默认值")
        technical_message = None
    
    try:
        fundamentals_message = next(
            msg for msg in state["messages"] if msg.name == "fundamentals_agent")
    except StopIteration:
        logger.warning("未找到fundamentals_agent消息，使用默认值")
        fundamentals_message = None
    
    try:
        sentiment_message = next(
            msg for msg in state["messages"] if msg.name == "sentiment_agent")
    except StopIteration:
        logger.warning("未找到sentiment_agent消息，使用默认值")
        sentiment_message = None
    
    # 支持valuation_agent和valuation_agent_v2
    valuation_message = None
    try:
        valuation_message = next(
            msg for msg in state["messages"] if msg.name == "valuation_agent_v2")
    except StopIteration:
        try:
            valuation_message = next(
                msg for msg in state["messages"] if msg.name == "valuation_agent")
        except StopIteration:
            logger.warning("未找到valuation_agent消息，使用默认值")
    
    # 如果缺少关键消息，返回默认值
    if not all([technical_message, fundamentals_message, sentiment_message, valuation_message]):
        logger.error("缺少关键分析消息，无法生成看空论点")
        default_message = {
            "perspective": "bearish",
            "confidence": 0.0,
            "thesis_points": ["数据不足，无法生成看空论点"],
            "reasoning": "缺少必要的分析数据"
        }
        message = HumanMessage(
            content=json.dumps(default_message),
            name="researcher_bear_agent",
        )
        show_workflow_status("Bearish Researcher", "completed")
        return {
            "messages": state["messages"] + [message],
            "data": state["data"],
            "metadata": state["metadata"],
        }

    # 解析消息内容，处理可能的错误
    try:
        fundamental_signals = json.loads(fundamentals_message.content) if fundamentals_message else {"signal": "neutral", "confidence": "0%"}
        technical_signals = json.loads(technical_message.content) if technical_message else {"signal": "neutral", "confidence": "0%"}
        sentiment_signals = json.loads(sentiment_message.content) if sentiment_message else {"signal": "neutral", "confidence": "0%"}
        valuation_signals = json.loads(valuation_message.content) if valuation_message else {"signal": "neutral", "confidence": "0%"}
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"解析消息内容时出错: {e}，尝试使用ast.literal_eval")
        try:
            fundamental_signals = ast.literal_eval(fundamentals_message.content) if fundamentals_message else {"signal": "neutral", "confidence": "0%"}
            technical_signals = ast.literal_eval(technical_message.content) if technical_message else {"signal": "neutral", "confidence": "0%"}
            sentiment_signals = ast.literal_eval(sentiment_message.content) if sentiment_message else {"signal": "neutral", "confidence": "0%"}
            valuation_signals = ast.literal_eval(valuation_message.content) if valuation_message else {"signal": "neutral", "confidence": "0%"}
        except Exception as e2:
            logger.error(f"解析消息内容失败: {e2}，使用默认值")
            fundamental_signals = {"signal": "neutral", "confidence": "0%"}
            technical_signals = {"signal": "neutral", "confidence": "0%"}
            sentiment_signals = {"signal": "neutral", "confidence": "0%"}
            valuation_signals = {"signal": "neutral", "confidence": "0%"}

    # Analyze from bearish perspective
    bearish_points = []
    confidence_scores = []

    # Technical Analysis
    if technical_signals["signal"] == "bearish":
        bearish_points.append(
            f"Technical indicators show bearish momentum with {technical_signals['confidence']} confidence")
        confidence_scores.append(
            float(str(technical_signals["confidence"]).replace("%", "")) / 100)
    else:
        bearish_points.append(
            "Technical rally may be temporary, suggesting potential reversal")
        confidence_scores.append(0.3)

    # Fundamental Analysis
    if fundamental_signals["signal"] == "bearish":
        bearish_points.append(
            f"Concerning fundamentals with {fundamental_signals['confidence']} confidence")
        confidence_scores.append(
            float(str(fundamental_signals["confidence"]).replace("%", "")) / 100)
    else:
        bearish_points.append(
            "Current fundamental strength may not be sustainable")
        confidence_scores.append(0.3)

    # Sentiment Analysis
    if sentiment_signals["signal"] == "bearish":
        bearish_points.append(
            f"Negative market sentiment with {sentiment_signals['confidence']} confidence")
        confidence_scores.append(
            float(str(sentiment_signals["confidence"]).replace("%", "")) / 100)
    else:
        bearish_points.append(
            "Market sentiment may be overly optimistic, indicating potential risks")
        confidence_scores.append(0.3)

    # Valuation Analysis
    if valuation_signals["signal"] == "bearish":
        bearish_points.append(
            f"Stock appears overvalued with {valuation_signals['confidence']} confidence")
        confidence_scores.append(
            float(str(valuation_signals["confidence"]).replace("%", "")) / 100)
    else:
        bearish_points.append(
            "Current valuation may not fully reflect downside risks")
        confidence_scores.append(0.3)

    # Calculate overall bearish confidence
    avg_confidence = sum(confidence_scores) / len(confidence_scores)

    message_content = {
        "perspective": "bearish",
        "confidence": avg_confidence,
        "thesis_points": bearish_points,
        "reasoning": "Bearish thesis based on comprehensive analysis of technical, fundamental, sentiment, and valuation factors"
    }

    message = HumanMessage(
        content=json.dumps(message_content),
        name="researcher_bear_agent",
    )

    if show_reasoning:
        show_agent_reasoning(message_content, "Bearish Researcher")
        # 保存推理信息到metadata供API使用
        state["metadata"]["agent_reasoning"] = message_content

    show_workflow_status("Bearish Researcher", "completed")
    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
        "metadata": state["metadata"],
    }
