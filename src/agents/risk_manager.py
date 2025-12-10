import math
import logging

from langchain_core.messages import HumanMessage

from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.tools.api import prices_to_df
from src.utils.api_utils import agent_endpoint, log_llm_interaction

import json
import ast

logger = logging.getLogger(__name__)

##### Risk Management Agent #####


@agent_endpoint("risk_management", "风险管理专家，评估投资风险并给出风险调整后的交易建议")
def risk_management_agent(state: AgentState):
    """Responsible for risk management"""
    show_workflow_status("Risk Manager")
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]
    data = state["data"]

    prices_df = prices_to_df(data["prices"])

    # Fetch debate room message instead of individual analyst messages
    try:
        debate_message = next(
            msg for msg in state["messages"] if msg.name == "debate_room_agent")
    except StopIteration:
        logger.warning("⚠️ 缺少 debate_room_agent 消息，使用默认值")
        debate_message = None

    # Parse debate results with fallback
    if debate_message:
        try:
            debate_results = json.loads(debate_message.content)
        except Exception as e:
            try:
                debate_results = ast.literal_eval(debate_message.content)
            except Exception as e2:
                logger.warning(f"⚠️ 无法解析 debate_room_agent 消息: {e2}，使用默认值")
                debate_results = {
                    "bull_confidence": 0.0,
                    "bear_confidence": 0.0,
                    "confidence": 0.0,
                    "signal": "neutral"
                }
    else:
        debate_results = {
            "bull_confidence": 0.0,
            "bear_confidence": 0.0,
            "confidence": 0.0,
            "signal": "neutral"
        }

    # 1. Calculate Risk Metrics with error handling
    try:
        if prices_df is None or prices_df.empty or len(prices_df) < 2:
            logger.warning("⚠️ 价格数据为空或不足，使用默认风险指标")
            volatility = 0.0
            var_95 = 0.0
            max_drawdown = 0.0
            volatility_percentile = 0.0
        else:
            returns = prices_df['close'].pct_change().dropna()
            if len(returns) == 0:
                volatility = 0.0
                var_95 = 0.0
                volatility_percentile = 0.0
            else:
                daily_vol = returns.std()
                # Annualized volatility approximation
                volatility = daily_vol * (252 ** 0.5) if not math.isnan(daily_vol) else 0.0

                # 计算波动率的历史分布
                try:
                    rolling_std = returns.rolling(window=min(120, len(returns))).std() * (252 ** 0.5)
                    volatility_mean = rolling_std.mean()
                    volatility_std = rolling_std.std()
                    if not math.isnan(volatility_mean) and not math.isnan(volatility_std) and volatility_std > 0:
                        volatility_percentile = (volatility - volatility_mean) / volatility_std
                    else:
                        volatility_percentile = 0.0
                except Exception as e:
                    logger.warning(f"⚠️ 计算波动率百分位数失败: {e}，使用默认值")
                    volatility_percentile = 0.0

                # Simple historical VaR at 95% confidence
                var_95 = returns.quantile(0.05) if len(returns) > 0 else 0.0
                if math.isnan(var_95):
                    var_95 = 0.0

            # 使用60天窗口计算最大回撤
            try:
                if len(prices_df) >= 60:
                    max_drawdown = (
                        prices_df['close'] / prices_df['close'].rolling(window=60).max() - 1).min()
                elif len(prices_df) >= 2:
                    max_drawdown = (
                        prices_df['close'] / prices_df['close'].rolling(window=len(prices_df)).max() - 1).min()
                else:
                    max_drawdown = 0.0
                if math.isnan(max_drawdown):
                    max_drawdown = 0.0
            except Exception as e:
                logger.warning(f"⚠️ 计算最大回撤失败: {e}，使用默认值")
                max_drawdown = 0.0
    except Exception as e:
        logger.error(f"⚠️ 计算风险指标时发生错误: {e}，使用默认值")
        volatility = 0.0
        var_95 = 0.0
        max_drawdown = 0.0
        volatility_percentile = 0.0

    # 2. Market Risk Assessment
    market_risk_score = 0

    # Volatility scoring based on percentile
    if volatility_percentile > 1.5:     # 高于1.5个标准差
        market_risk_score += 2
    elif volatility_percentile > 1.0:   # 高于1个标准差
        market_risk_score += 1

    # VaR scoring
    # Note: var_95 is typically negative. The more negative, the worse.
    if var_95 < -0.03:
        market_risk_score += 2
    elif var_95 < -0.02:
        market_risk_score += 1

    # Max Drawdown scoring
    if max_drawdown < -0.20:  # Severe drawdown
        market_risk_score += 2
    elif max_drawdown < -0.10:
        market_risk_score += 1

    # 3. Position Size Limits
    # Consider total portfolio value, not just cash
    try:
        if prices_df is not None and not prices_df.empty and len(prices_df) > 0:
            current_stock_value = portfolio['stock'] * prices_df['close'].iloc[-1]
        else:
            current_stock_value = 0.0
    except Exception as e:
        logger.warning(f"⚠️ 计算当前股票价值失败: {e}，使用默认值")
        current_stock_value = 0.0
    
    total_portfolio_value = portfolio['cash'] + current_stock_value

    # Start with 25% max position of total portfolio
    base_position_size = total_portfolio_value * 0.25

    if market_risk_score >= 4:
        # Reduce position for high risk
        max_position_size = base_position_size * 0.5
    elif market_risk_score >= 2:
        # Slightly reduce for moderate risk
        max_position_size = base_position_size * 0.75
    else:
        # Keep base size for low risk
        max_position_size = base_position_size

    # 4. Stress Testing
    stress_test_scenarios = {
        "market_crash": -0.20,
        "moderate_decline": -0.10,
        "slight_decline": -0.05
    }

    stress_test_results = {}
    current_position_value = current_stock_value

    for scenario, decline in stress_test_scenarios.items():
        potential_loss = current_position_value * decline
        portfolio_impact = potential_loss / (portfolio['cash'] + current_position_value) if (
            portfolio['cash'] + current_position_value) != 0 else math.nan
        stress_test_results[scenario] = {
            "potential_loss": potential_loss,
            "portfolio_impact": portfolio_impact
        }

    # 5. Risk-Adjusted Signal Analysis
    # Consider debate room confidence levels
    try:
        bull_confidence = debate_results.get("bull_confidence", 0.0)
        bear_confidence = debate_results.get("bear_confidence", 0.0)
        debate_confidence = debate_results.get("confidence", 0.0)
        debate_signal = debate_results.get("signal", "neutral")
    except Exception as e:
        logger.warning(f"⚠️ 获取辩论结果失败: {e}，使用默认值")
        bull_confidence = 0.0
        bear_confidence = 0.0
        debate_confidence = 0.0
        debate_signal = "neutral"

    # Add to risk score if confidence is low or debate was close
    try:
        confidence_diff = abs(bull_confidence - bear_confidence)
        if confidence_diff < 0.1:  # Close debate
            market_risk_score += 1
        if debate_confidence < 0.3:  # Low overall confidence
            market_risk_score += 1
    except Exception as e:
        logger.warning(f"⚠️ 计算风险评分调整失败: {e}")

    # Cap risk score at 10
    risk_score = min(round(market_risk_score), 10)

    # 6. Generate Trading Action
    # Consider debate room signal along with risk assessment

    if risk_score >= 9:
        trading_action = "hold"
    elif risk_score >= 7:
        trading_action = "reduce"
    else:
        if debate_signal == "bullish" and debate_confidence > 0.5:
            trading_action = "buy"
        elif debate_signal == "bearish" and debate_confidence > 0.5:
            trading_action = "sell"
        else:
            trading_action = "hold"

    message_content = {
        "max_position_size": float(max_position_size),
        "risk_score": risk_score,
        "trading_action": trading_action,
        "risk_metrics": {
            "volatility": float(volatility),
            "value_at_risk_95": float(var_95),
            "max_drawdown": float(max_drawdown),
            "market_risk_score": market_risk_score,
            "stress_test_results": stress_test_results
        },
        "debate_analysis": {
            "bull_confidence": bull_confidence,
            "bear_confidence": bear_confidence,
            "debate_confidence": debate_confidence,
            "debate_signal": debate_signal
        },
        "reasoning": f"Risk Score {risk_score}/10: Market Risk={market_risk_score}, "
                     f"Volatility={volatility:.2%}, VaR={var_95:.2%}, "
                     f"Max Drawdown={max_drawdown:.2%}, Debate Signal={debate_signal}"
    }

    # Create the risk management message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="risk_management_agent",
    )

    if show_reasoning:
        show_agent_reasoning(message_content, "Risk Management Agent")
        # 保存推理信息到metadata供API使用
        state["metadata"]["agent_reasoning"] = message_content

    show_workflow_status("Risk Manager", "completed")
    return {
        "messages": state["messages"] + [message],
        "data": {
            **data,
            "risk_analysis": message_content
        },
        "metadata": state["metadata"],
    }
