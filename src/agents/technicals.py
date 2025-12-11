import math
from typing import Dict
from src.utils.logging_config import setup_logger

from langchain_core.messages import HumanMessage

from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.utils.api_utils import agent_endpoint, log_llm_interaction

import json
import pandas as pd
import numpy as np

from src.tools.api import prices_to_df

# 初始化 logger
logger = setup_logger('technical_analyst_agent')

# A股市场常量
A_SHARE_TRADING_DAYS_PER_YEAR = 240  # A股市场每年交易日约240-250天
A_SHARE_LIMIT_UP_THRESHOLD = 0.099  # 涨停阈值（考虑浮点误差，使用9.9%）
A_SHARE_LIMIT_DOWN_THRESHOLD = -0.099  # 跌停阈值
A_SHARE_ST_LIMIT_UP_THRESHOLD = 0.049  # ST股票涨停阈值（5%）
A_SHARE_ST_LIMIT_DOWN_THRESHOLD = -0.049  # ST股票跌停阈值


##### Technical Analyst #####
@agent_endpoint("technical_analyst", "技术分析师，提供基于价格走势、指标和技术模式的交易信号")
def technical_analyst_agent(state: AgentState):
    """
    Sophisticated technical analysis system that combines multiple trading strategies:
    1. Trend Following
    2. Mean Reversion
    3. Momentum
    4. Volatility Analysis
    5. Statistical Arbitrage Signals
    """
    logger.info("\n--- DEBUG: technical_analyst_agent START ---")
    show_workflow_status("Technical Analyst")
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    prices = data["prices"]
    prices_df = prices_to_df(prices)

    # 检查价格数据是否为空
    if prices_df is None or prices_df.empty or len(prices_df) < 2:
        logger.warning("价格数据为空或不足，返回默认中性信号")
        default_analysis = {
            "signal": "neutral",
            "confidence": "0%",
            "strategy_signals": {
                "trend_following": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "mean_reversion": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "momentum": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "volatility": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "statistical_arbitrage": {"signal": "neutral", "confidence": "0%", "metrics": {}}
            }
        }
        message = HumanMessage(
            content=json.dumps(default_analysis),
            name="technical_analyst_agent",
        )
        if show_reasoning:
            show_agent_reasoning(default_analysis, "Technical Analyst")
            state["metadata"]["agent_reasoning"] = default_analysis
        show_workflow_status("Technical Analyst", "completed")
        return {
            "messages": [message],
            "data": data,
            "metadata": state["metadata"],
        }
    
    # 检测和处理停牌数据（A股市场特点）
    # 停牌特征：成交量接近0或为0，价格可能保持不变
    if 'volume' in prices_df.columns:
        recent_volumes = prices_df['volume'].iloc[-5:] if len(prices_df) >= 5 else prices_df['volume']
        avg_recent_volume = recent_volumes.mean()
        # 如果最近5天平均成交量小于历史平均的1%，可能是停牌
        if len(prices_df) > 20:
            historical_avg_volume = prices_df['volume'].iloc[:-5].mean() if len(prices_df) > 5 else prices_df['volume'].mean()
            if historical_avg_volume > 0 and avg_recent_volume / historical_avg_volume < 0.01:
                logger.warning("检测到可能的停牌情况（成交量异常低），技术分析结果可能不准确")
        # 如果当前成交量为0，肯定是停牌
        if len(prices_df) > 0 and prices_df['volume'].iloc[-1] == 0:
            logger.warning("检测到停牌（成交量为0），技术分析结果可能不准确")

    # Initialize confidence variable
    confidence = 0.0

    # Calculate indicators
    # 1. MACD (Moving Average Convergence Divergence)
    try:
        macd_line, signal_line = calculate_macd(prices_df)
    except Exception as e:
        logger.error(f"计算MACD指标时出错: {e}")
        # 返回默认中性信号
        default_analysis = {
            "signal": "neutral",
            "confidence": "0%",
            "strategy_signals": {
                "trend_following": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "mean_reversion": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "momentum": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "volatility": {"signal": "neutral", "confidence": "0%", "metrics": {}},
                "statistical_arbitrage": {"signal": "neutral", "confidence": "0%", "metrics": {}}
            }
        }
        message = HumanMessage(
            content=json.dumps(default_analysis),
            name="technical_analyst_agent",
        )
        if show_reasoning:
            show_agent_reasoning(default_analysis, "Technical Analyst")
            state["metadata"]["agent_reasoning"] = default_analysis
        show_workflow_status("Technical Analyst", "completed")
        return {
            "messages": [message],
            "data": data,
            "metadata": state["metadata"],
        }

    # 2. RSI (Relative Strength Index)
    try:
        rsi = calculate_rsi(prices_df)
    except Exception as e:
        logger.error(f"计算RSI指标时出错: {e}")
        rsi = pd.Series([50.0] * len(prices_df))  # 默认中性值

    # 3. Bollinger Bands (Bollinger Bands)
    try:
        upper_band, lower_band = calculate_bollinger_bands(prices_df)
    except Exception as e:
        logger.error(f"计算布林带指标时出错: {e}")
        current_price = prices_df['close'].iloc[-1] if len(prices_df) > 0 else 0
        upper_band = pd.Series([current_price * 1.1] * len(prices_df))
        lower_band = pd.Series([current_price * 0.9] * len(prices_df))

    # 4. OBV (On-Balance Volume)
    try:
        obv = calculate_obv(prices_df)
    except Exception as e:
        logger.error(f"计算OBV指标时出错: {e}")
        obv = pd.Series([0.0] * len(prices_df))

    # Generate individual signals
    signals = []

    # 检查数据长度是否足够
    if len(macd_line) < 2 or len(signal_line) < 2:
        logger.warning("MACD数据不足，使用默认中性信号")
        signals.append('neutral')
    else:
        # MACD signal
        try:
            if macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
                signals.append('bullish')
            elif macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
                signals.append('bearish')
            else:
                signals.append('neutral')
        except (IndexError, KeyError) as e:
            logger.warning(f"MACD信号计算错误: {e}，使用中性信号")
            signals.append('neutral')

    # RSI signal - 针对A股市场调整阈值（A股波动性更大，使用35/65而不是30/70）
    try:
        if len(rsi) > 0 and rsi.iloc[-1] < 35:  # A股市场：超卖阈值从30调整为35
            signals.append('bullish')
        elif len(rsi) > 0 and rsi.iloc[-1] > 65:  # A股市场：超买阈值从70调整为65
            signals.append('bearish')
        else:
            signals.append('neutral')
    except (IndexError, KeyError) as e:
        logger.warning(f"RSI信号计算错误: {e}，使用中性信号")
        signals.append('neutral')

    # Bollinger Bands signal
    try:
        if len(prices_df) > 0 and len(lower_band) > 0 and len(upper_band) > 0:
            current_price = prices_df['close'].iloc[-1]
            if current_price < lower_band.iloc[-1]:
                signals.append('bullish')
            elif current_price > upper_band.iloc[-1]:
                signals.append('bearish')
            else:
                signals.append('neutral')
        else:
            signals.append('neutral')
    except (IndexError, KeyError) as e:
        logger.warning(f"布林带信号计算错误: {e}，使用中性信号")
        signals.append('neutral')

    # OBV signal
    try:
        if len(obv) >= 5:
            obv_slope = obv.diff().iloc[-5:].mean()
            if obv_slope > 0:
                signals.append('bullish')
            elif obv_slope < 0:
                signals.append('bearish')
            else:
                signals.append('neutral')
        else:
            signals.append('neutral')
    except (IndexError, KeyError) as e:
        logger.warning(f"OBV信号计算错误: {e}，使用中性信号")
        signals.append('neutral')

    # Calculate price drop
    try:
        if len(prices_df) >= 5:
            price_drop = (prices_df['close'].iloc[-1] -
                          prices_df['close'].iloc[-5]) / prices_df['close'].iloc[-5]
        else:
            price_drop = 0
    except (IndexError, KeyError) as e:
        logger.warning(f"价格变化计算错误: {e}")
        price_drop = 0

    # Add price drop signal - 考虑A股涨跌停板限制
    try:
        if len(rsi) > 0 and len(prices_df) > 0:
            # 检查是否为涨跌停板（A股±10%，ST股票±5%）
            current_pct_change = prices_df.get('pct_change', pd.Series([0] * len(prices_df)))
            if len(current_pct_change) > 0:
                last_pct_change = current_pct_change.iloc[-1] if hasattr(current_pct_change, 'iloc') else 0
                is_limit_up = (last_pct_change >= A_SHARE_LIMIT_UP_THRESHOLD) or (last_pct_change >= A_SHARE_ST_LIMIT_UP_THRESHOLD)
                is_limit_down = (last_pct_change <= A_SHARE_LIMIT_DOWN_THRESHOLD) or (last_pct_change <= A_SHARE_ST_LIMIT_DOWN_THRESHOLD)
                
                # 如果涨停，降低看涨信号权重（涨停后可能回调）
                if is_limit_up:
                    logger.info("检测到涨停板，调整信号权重")
                    # 涨停时，如果RSI已经很高，可能是超买信号
                    if rsi.iloc[-1] > 70:
                        signals.append('bearish')
                        confidence += 0.15
                # 如果跌停，可能是超卖机会
                elif is_limit_down:
                    logger.info("检测到跌停板，可能是超卖机会")
                    if rsi.iloc[-1] < 40:
                        signals.append('bullish')
                        confidence += 0.25  # 跌停+低RSI，较强的超卖信号
                # 正常情况下的价格下跌信号
                elif price_drop < -0.05 and rsi.iloc[-1] < 40:  # 5% drop and RSI below 40
                    signals.append('bullish')
                    confidence += 0.2
                elif price_drop < -0.03 and rsi.iloc[-1] < 45:  # 3% drop and RSI below 45
                    signals.append('bullish')
                    confidence += 0.1
    except (IndexError, KeyError) as e:
        logger.warning(f"价格下跌信号计算错误: {e}")

    # Add reasoning collection
    try:
        obv_slope = obv.diff().iloc[-5:].mean() if len(obv) >= 5 else 0
        rsi_value = rsi.iloc[-1] if len(rsi) > 0 else 50.0
        reasoning = {
            "MACD": {
                "signal": signals[0] if len(signals) > 0 else "neutral",
                "details": f"MACD Line crossed {'above' if signals[0] == 'bullish' else 'below' if signals[0] == 'bearish' else 'neither above nor below'} Signal Line" if len(signals) > 0 else "MACD data unavailable"
            },
            "RSI": {
                "signal": signals[1] if len(signals) > 1 else "neutral",
                "details": f"RSI is {rsi_value:.2f} ({'oversold' if len(signals) > 1 and signals[1] == 'bullish' else 'overbought' if len(signals) > 1 and signals[1] == 'bearish' else 'neutral'})"
            },
            "Bollinger": {
                "signal": signals[2] if len(signals) > 2 else "neutral",
                "details": f"Price is {'below lower band' if len(signals) > 2 and signals[2] == 'bullish' else 'above upper band' if len(signals) > 2 and signals[2] == 'bearish' else 'within bands'}"
            },
            "OBV": {
                "signal": signals[3] if len(signals) > 3 else "neutral",
                "details": f"OBV slope is {obv_slope:.2f} ({signals[3] if len(signals) > 3 else 'neutral'})"
            }
        }
    except Exception as e:
        logger.error(f"构建推理信息时出错: {e}")
        reasoning = {
            "MACD": {"signal": "neutral", "details": "Data unavailable"},
            "RSI": {"signal": "neutral", "details": "Data unavailable"},
            "Bollinger": {"signal": "neutral", "details": "Data unavailable"},
            "OBV": {"signal": "neutral", "details": "Data unavailable"}
        }

    # Determine overall signal
    bullish_signals = signals.count('bullish')
    bearish_signals = signals.count('bearish')

    if bullish_signals > bearish_signals:
        overall_signal = 'bullish'
    elif bearish_signals > bullish_signals:
        overall_signal = 'bearish'
    else:
        overall_signal = 'neutral'

    # Calculate confidence level based on the proportion of indicators agreeing
    total_signals = len(signals)
    confidence = max(bullish_signals, bearish_signals) / total_signals

    # Generate the message content
    message_content = {
        "signal": overall_signal,
        "confidence": f"{round(confidence * 100)}%",
        "reasoning": {
            "MACD": reasoning["MACD"],
            "RSI": reasoning["RSI"],
            "Bollinger": reasoning["Bollinger"],
            "OBV": reasoning["OBV"]
        }
    }

    # 1. Trend Following Strategy
    try:
        trend_signals = calculate_trend_signals(prices_df)
    except Exception as e:
        logger.error(f"计算趋势信号时出错: {e}")
        trend_signals = {"signal": "neutral", "confidence": 0.0, "metrics": {}}

    # 2. Mean Reversion Strategy
    try:
        mean_reversion_signals = calculate_mean_reversion_signals(prices_df)
    except Exception as e:
        logger.error(f"计算均值回归信号时出错: {e}")
        mean_reversion_signals = {"signal": "neutral", "confidence": 0.0, "metrics": {}}

    # 3. Momentum Strategy
    try:
        momentum_signals = calculate_momentum_signals(prices_df)
    except Exception as e:
        logger.error(f"计算动量信号时出错: {e}")
        momentum_signals = {"signal": "neutral", "confidence": 0.0, "metrics": {}}

    # 4. Volatility Strategy
    try:
        volatility_signals = calculate_volatility_signals(prices_df)
    except Exception as e:
        logger.error(f"计算波动率信号时出错: {e}")
        volatility_signals = {"signal": "neutral", "confidence": 0.0, "metrics": {}}

    # 5. Statistical Arbitrage Signals
    try:
        stat_arb_signals = calculate_stat_arb_signals(prices_df)
    except Exception as e:
        logger.error(f"计算统计套利信号时出错: {e}")
        stat_arb_signals = {"signal": "neutral", "confidence": 0.0, "metrics": {}}

    # Combine all signals using a weighted ensemble approach
    # 针对A股市场优化权重：A股散户主导，技术分析更有效，均值回归和动量策略权重较高
    strategy_weights = {
        'trend': 0.30,           # 趋势跟踪：A股市场趋势性较强
        'mean_reversion': 0.30,   # 均值回归：A股市场波动大，均值回归机会多（从0.25提高到0.30）
        'momentum': 0.25,        # 动量策略：保持原有权重
        'volatility': 0.10,      # 波动率：降低权重（从0.15降到0.10），A股波动率信号相对不稳定
        'stat_arb': 0.05         # 统计套利：保持低权重
    }

    combined_signal = weighted_signal_combination({
        'trend': trend_signals,
        'mean_reversion': mean_reversion_signals,
        'momentum': momentum_signals,
        'volatility': volatility_signals,
        'stat_arb': stat_arb_signals
    }, strategy_weights)

    # Generate detailed analysis report
    analysis_report = {
        "signal": combined_signal['signal'],
        "confidence": f"{round(combined_signal['confidence'] * 100)}%",
        "strategy_signals": {
            "trend_following": {
                "signal": trend_signals['signal'],
                "confidence": f"{round(trend_signals['confidence'] * 100)}%",
                "metrics": normalize_pandas(trend_signals['metrics'])
            },
            "mean_reversion": {
                "signal": mean_reversion_signals['signal'],
                "confidence": f"{round(mean_reversion_signals['confidence'] * 100)}%",
                "metrics": normalize_pandas(mean_reversion_signals['metrics'])
            },
            "momentum": {
                "signal": momentum_signals['signal'],
                "confidence": f"{round(momentum_signals['confidence'] * 100)}%",
                "metrics": normalize_pandas(momentum_signals['metrics'])
            },
            "volatility": {
                "signal": volatility_signals['signal'],
                "confidence": f"{round(volatility_signals['confidence'] * 100)}%",
                "metrics": normalize_pandas(volatility_signals['metrics'])
            },
            "statistical_arbitrage": {
                "signal": stat_arb_signals['signal'],
                "confidence": f"{round(stat_arb_signals['confidence'] * 100)}%",
                "metrics": normalize_pandas(stat_arb_signals['metrics'])
            }
        }
    }

    # Create the technical analyst message
    message = HumanMessage(
        content=json.dumps(analysis_report),
        name="technical_analyst_agent",
    )

    if show_reasoning:
        show_agent_reasoning(analysis_report, "Technical Analyst")
        # 保存推理信息到state的metadata供API使用
        state["metadata"]["agent_reasoning"] = analysis_report

    show_workflow_status("Technical Analyst", "completed")

    # 添加调试信息，打印将要返回的消息名称
    # logger.info(
    # f"--- DEBUG: technical_analyst_agent RETURN messages: {[msg.name for msg in [message]]} ---")

    return {
        "messages": [message],
        "data": data,
        "metadata": state["metadata"],
    }


def calculate_trend_signals(prices_df):
    """
    Advanced trend following strategy using multiple timeframes and indicators
    """
    # Check if we have enough data (need at least 55 periods for EMA55)
    min_required = 55
    if len(prices_df) < min_required:
        return {
            'signal': 'neutral',
            'confidence': 0.0,
            'metrics': {
                'adx': 0.0,
                'trend_strength': 0.0
            }
        }
    
    # Calculate EMAs for multiple timeframes
    ema_8 = calculate_ema(prices_df, 8)
    ema_21 = calculate_ema(prices_df, 21)
    ema_55 = calculate_ema(prices_df, 55)

    # Calculate ADX for trend strength
    adx = calculate_adx(prices_df, 14)

    # Calculate Ichimoku Cloud
    ichimoku = calculate_ichimoku(prices_df)

    # Determine trend direction and strength
    short_trend = ema_8 > ema_21
    medium_trend = ema_21 > ema_55
    long_trend = ema_8 > ema_55  # 直接比较短期和长期EMA

    # Combine signals with confidence weighting
    # Handle NaN values in ADX
    adx_value = adx['adx'].iloc[-1]
    if pd.isna(adx_value):
        trend_strength = 0.0
    else:
        trend_strength = adx_value / 100.0

    # Improved trend detection: use multiple conditions with different confidence levels
    short_bullish = short_trend.iloc[-1]
    medium_bullish = medium_trend.iloc[-1]
    long_bullish = long_trend.iloc[-1]
    
    # Count bullish conditions
    bullish_count = sum([short_bullish, medium_bullish, long_bullish])
    
    if bullish_count >= 2:  # At least 2 out of 3 conditions are bullish
        signal = 'bullish'
        # Confidence based on trend strength and number of conditions met
        confidence = trend_strength * (0.6 + 0.2 * bullish_count)  # 0.6-1.0 multiplier
        confidence = min(confidence, 1.0)
    elif bullish_count <= 1:  # At most 1 condition is bullish (i.e., 2+ are bearish)
        signal = 'bearish'
        bearish_count = 3 - bullish_count
        confidence = trend_strength * (0.6 + 0.2 * bearish_count)
        confidence = min(confidence, 1.0)
    else:
        signal = 'neutral'
        confidence = 0.5

    return {
        'signal': signal,
        'confidence': confidence,
        'metrics': {
            'adx': float(adx['adx'].iloc[-1]),
            'trend_strength': float(trend_strength),
            # 'ichimoku': ichimoku
        }
    }


def calculate_mean_reversion_signals(prices_df):
    """
    Mean reversion strategy using statistical measures and Bollinger Bands
    针对A股市场优化：考虑涨跌停板、成交量异常等情况
    """
    # Check if we have enough data (need at least 50 periods for MA50, but RSI can work with less)
    min_required = 14  # Minimum for RSI
    if len(prices_df) < min_required:
        return {
            'signal': 'neutral',
            'confidence': 0.0,
            'metrics': {
                'z_score': 0.0,
                'price_vs_bb': 0.5,
                'rsi_14': 50.0,
                'rsi_28': 50.0,
                'volume_anomaly': False
            }
        }
    
    # Calculate z-score of price relative to moving average
    ma_50 = prices_df['close'].rolling(window=50).mean()
    std_50 = prices_df['close'].rolling(window=50).std()
    z_score = (prices_df['close'] - ma_50) / std_50.replace(0, np.nan)

    # Calculate Bollinger Bands - A股市场可以使用稍大的标准差倍数
    bb_upper, bb_lower = calculate_bollinger_bands(prices_df, window=20, num_std=2.2)

    # Calculate RSI with multiple timeframes
    rsi_14 = calculate_rsi(prices_df, 14)
    rsi_28 = calculate_rsi(prices_df, 28)
    
    # 检测成交量异常（A股市场成交量对技术分析很重要）
    volume_ma_20 = prices_df['volume'].rolling(window=20, min_periods=10).mean()
    volume_ratio = prices_df['volume'] / volume_ma_20.replace(0, np.nan)
    volume_anomaly = False
    current_volume_ratio = 1.0  # 默认值
    if len(volume_ratio) > 0:
        current_volume_ratio = volume_ratio.iloc[-1] if pd.notna(volume_ratio.iloc[-1]) else 1.0
        # 异常放量：成交量是平均的2倍以上
        # 异常缩量：成交量是平均的0.5倍以下
        volume_anomaly = (pd.notna(current_volume_ratio) and 
                         (current_volume_ratio > 2.0 or current_volume_ratio < 0.5))

    # Safely extract RSI values FIRST, before using them in conditions
    rsi_14_value = rsi_14.iloc[-1]
    rsi_28_value = rsi_28.iloc[-1]
    
    # Convert to float, handling NaN values
    rsi_14_float = float(rsi_14_value) if pd.notna(rsi_14_value) else 50.0
    rsi_28_float = float(rsi_28_value) if pd.notna(rsi_28_value) else 50.0

    # Mean reversion signals
    # Handle NaN values in z_score
    z_score_value = z_score.iloc[-1]
    if pd.isna(z_score_value):
        z_score_value = 0.0
    
    extreme_z_score = abs(z_score_value) > 2
    
    # Handle division by zero when Bollinger Bands width is 0
    bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
    if pd.isna(bb_range) or bb_range <= 0:
        # When Bollinger Bands width is 0 or NaN, assume price is at middle (0.5)
        price_vs_bb = 0.5
    else:
        price_vs_bb = (prices_df['close'].iloc[-1] - bb_lower.iloc[-1]) / bb_range

    # Improved mean reversion signals with more practical thresholds for A-share market
    # Use OR logic instead of AND to make signals more frequent
    # Also incorporate RSI for confirmation and volume anomaly detection
    
    # 检查涨跌停板情况
    current_pct_change = 0.0
    is_limit_up = False
    is_limit_down = False
    if 'pct_change' in prices_df.columns and len(prices_df) > 0:
        current_pct_change = prices_df['pct_change'].iloc[-1] if pd.notna(prices_df['pct_change'].iloc[-1]) else 0.0
        is_limit_up = (current_pct_change >= A_SHARE_LIMIT_UP_THRESHOLD) or (current_pct_change >= A_SHARE_ST_LIMIT_UP_THRESHOLD)
        is_limit_down = (current_pct_change <= A_SHARE_LIMIT_DOWN_THRESHOLD) or (current_pct_change <= A_SHARE_ST_LIMIT_DOWN_THRESHOLD)
    
    # Bullish conditions (oversold) - 针对A股市场优化
    bullish_conditions = [
        z_score_value < -1.5,  # Price significantly below MA50 (relaxed from -2)
        price_vs_bb < 0.3,     # Price near lower Bollinger Band (relaxed from 0.2)
        rsi_14_float < 35,     # RSI oversold (A股市场阈值从30调整为35)
        is_limit_down          # 跌停板可能是超卖机会
    ]
    # 如果出现异常放量且价格下跌，可能是恐慌性抛售，也是买入机会
    if volume_anomaly and current_volume_ratio > 2.0 and z_score_value < -1.0:
        bullish_conditions.append(True)
    bullish_count = sum(bullish_conditions)
    
    # Bearish conditions (overbought) - 针对A股市场优化
    bearish_conditions = [
        z_score_value > 1.5,   # Price significantly above MA50 (relaxed from 2)
        price_vs_bb > 0.7,     # Price near upper Bollinger Band (relaxed from 0.8)
        rsi_14_float > 65,     # RSI overbought (A股市场阈值从70调整为65)
        is_limit_up            # 涨停板后可能回调
    ]
    # 如果出现异常放量且价格高位，可能是见顶信号
    if volume_anomaly and current_volume_ratio > 2.0 and z_score_value > 1.0:
        bearish_conditions.append(True)
    bearish_count = sum(bearish_conditions)
    
    # Generate signal based on conditions met
    if bullish_count >= 2:  # At least 2 oversold conditions
        signal = 'bullish'
        # Confidence based on how extreme the deviation is
        if z_score_value < -1.5:
            confidence = min(abs(z_score_value) / 3, 1.0)  # Strong deviation
        else:
            confidence = 0.6 + 0.2 * (bullish_count - 1)  # Moderate deviation
        confidence = min(confidence, 1.0)
    elif bearish_count >= 2:  # At least 2 overbought conditions
        signal = 'bearish'
        if z_score_value > 1.5:
            confidence = min(abs(z_score_value) / 3, 1.0)  # Strong deviation
        else:
            confidence = 0.6 + 0.2 * (bearish_count - 1)  # Moderate deviation
        confidence = min(confidence, 1.0)
    else:
        signal = 'neutral'
        # Even in neutral, provide some confidence based on proximity to extremes
        if abs(z_score_value) > 1.0 or rsi_14_float < 40 or rsi_14_float > 60:
            confidence = 0.4  # Somewhat informative
        else:
            confidence = 0.3  # Not very informative
    
    # Ensure RSI values are valid floats (not NaN)
    # This is a safety check in case the conversion above failed
    if pd.isna(rsi_14_float) or not isinstance(rsi_14_float, (int, float)) or np.isnan(rsi_14_float):
        rsi_14_float = 50.0
    if pd.isna(rsi_28_float) or not isinstance(rsi_28_float, (int, float)) or np.isnan(rsi_28_float):
        rsi_28_float = 50.0

    # 获取当前成交量比率用于返回
    current_volume_ratio_value = float(volume_ratio.iloc[-1]) if len(volume_ratio) > 0 and pd.notna(volume_ratio.iloc[-1]) else 1.0
    
    return {
        'signal': signal,
        'confidence': confidence,
        'metrics': {
            'z_score': float(z_score_value) if not pd.isna(z_score_value) else 0.0,
            'price_vs_bb': float(price_vs_bb) if not pd.isna(price_vs_bb) else 0.5,
            'rsi_14': float(rsi_14_float),
            'rsi_28': float(rsi_28_float),
            'volume_anomaly': bool(volume_anomaly),
            'volume_ratio': current_volume_ratio_value,
            'is_limit_up': bool(is_limit_up),
            'is_limit_down': bool(is_limit_down)
        }
    }


def calculate_momentum_signals(prices_df):
    """
    Multi-factor momentum strategy with conservative settings
    针对A股市场优化：考虑涨跌停板对动量的影响
    """
    # Price momentum with adjusted min_periods
    returns = prices_df['close'].pct_change()
    mom_1m = returns.rolling(21, min_periods=5).sum()  # 短期动量允许较少数据点
    mom_3m = returns.rolling(63, min_periods=42).sum()  # 中期动量要求更多数据点
    mom_6m = returns.rolling(126, min_periods=63).sum()  # 长期动量保持严格要求

    # Volume momentum - A股市场成交量很重要
    volume_ma = prices_df['volume'].rolling(21, min_periods=10).mean()
    volume_momentum = prices_df['volume'] / volume_ma.replace(0, np.nan)
    
    # 检测涨跌停板对动量的影响
    limit_up_count = 0
    limit_down_count = 0
    if 'pct_change' in prices_df.columns and len(prices_df) >= 5:
        recent_pct_changes = prices_df['pct_change'].iloc[-5:]
        limit_up_count = ((recent_pct_changes >= A_SHARE_LIMIT_UP_THRESHOLD) | 
                         (recent_pct_changes >= A_SHARE_ST_LIMIT_UP_THRESHOLD)).sum()
        limit_down_count = ((recent_pct_changes <= A_SHARE_LIMIT_DOWN_THRESHOLD) | 
                           (recent_pct_changes <= A_SHARE_ST_LIMIT_DOWN_THRESHOLD)).sum()

    # 处理NaN值 - 使用更保守的方法
    # 如果数据不足，使用0而不是用短期数据填充，避免误导性信号
    mom_1m = mom_1m.fillna(0)
    mom_3m = mom_3m.fillna(0)  # 如果数据不足，使用0
    mom_6m = mom_6m.fillna(0)  # 如果数据不足，使用0

    # Calculate momentum score with more weight on longer timeframes
    momentum_score = (
        0.2 * mom_1m +  # 降低短期权重
        0.3 * mom_3m +
        0.5 * mom_6m    # 增加长期权重
    ).iloc[-1]

    # Volume confirmation - A股市场成交量确认很重要
    volume_confirmation = False
    current_volume_momentum = 1.0
    if len(volume_momentum) > 0 and pd.notna(volume_momentum.iloc[-1]):
        current_volume_momentum = volume_momentum.iloc[-1]
        volume_confirmation = current_volume_momentum > 1.0

    # 调整信号：考虑涨跌停板
    # 如果连续涨停，动量可能被高估，需要谨慎
    if limit_up_count >= 2:
        momentum_score = momentum_score * 0.7  # 降低动量分数，因为涨停限制了真实动量
        logger.info(f"检测到{limit_up_count}次涨停，调整动量分数")
    # 如果连续跌停，动量可能被低估
    if limit_down_count >= 2:
        momentum_score = momentum_score * 0.7  # 同样降低，因为跌停限制了真实动量
        logger.info(f"检测到{limit_down_count}次跌停，调整动量分数")

    # 改进的信号判断逻辑：如果动量非常大，即使成交量不确认，也应该给予一定的信号
    # 这避免了强大的正动量（如6月动量48%）被完全忽略
    if momentum_score > 0.15:  # 非常大的动量（15%以上）
        if volume_confirmation:
            signal = 'bullish'
            confidence = min(abs(momentum_score) * 5, 1.0)
        else:
            # 即使成交量不确认，也给予看涨信号（但降低置信度）
            # 因为强大的历史动量不应该被完全忽略
            signal = 'bullish'
            confidence = min(abs(momentum_score) * 3, 0.75)  # 降低置信度但不过度惩罚
        # 如果有涨停，降低置信度（涨停后可能回调）
        if limit_up_count > 0:
            confidence = confidence * 0.8
    elif momentum_score > 0.05 and volume_confirmation:
        signal = 'bullish'
        confidence = min(abs(momentum_score) * 5, 1.0)
        if limit_up_count > 0:
            confidence = confidence * 0.8
    elif momentum_score < -0.15:  # 非常大的负动量
        if volume_confirmation:
            signal = 'bearish'
            confidence = min(abs(momentum_score) * 5, 1.0)
        else:
            # 即使成交量不确认，也给予看跌信号（但降低置信度）
            signal = 'bearish'
            confidence = min(abs(momentum_score) * 3, 0.75)
        if limit_down_count > 0:
            confidence = confidence * 0.8
    elif momentum_score < -0.05 and volume_confirmation:
        signal = 'bearish'
        confidence = min(abs(momentum_score) * 5, 1.0)
        if limit_down_count > 0:
            confidence = confidence * 0.8
    else:
        signal = 'neutral'
        confidence = 0.5

    return {
        'signal': signal,
        'confidence': confidence,
        'metrics': {
            'momentum_1m': float(mom_1m.iloc[-1]) if pd.notna(mom_1m.iloc[-1]) else 0.0,
            'momentum_3m': float(mom_3m.iloc[-1]) if pd.notna(mom_3m.iloc[-1]) else 0.0,
            'momentum_6m': float(mom_6m.iloc[-1]) if pd.notna(mom_6m.iloc[-1]) else 0.0,
            'volume_momentum': float(current_volume_momentum),
            'limit_up_count': int(limit_up_count),
            'limit_down_count': int(limit_down_count)
        }
    }


def calculate_volatility_signals(prices_df):
    """
    Optimized volatility calculation with shorter lookback periods
    针对A股市场优化：使用240个交易日进行年化（A股每年交易日约240-250天）
    """
    returns = prices_df['close'].pct_change()

    # 使用更短的周期和最小周期要求计算历史波动率
    # A股市场：使用240个交易日进行年化（而不是252）
    hist_vol = returns.rolling(21, min_periods=10).std() * math.sqrt(A_SHARE_TRADING_DAYS_PER_YEAR)

    # 使用更短的周期计算波动率均值，并允许更少的数据点
    vol_ma = hist_vol.rolling(42, min_periods=21).mean()
    vol_regime = hist_vol / vol_ma

    # 使用更灵活的标准差计算
    vol_std = hist_vol.rolling(42, min_periods=21).std()
    
    # Handle division by zero safely
    vol_z_score = np.where(
        (pd.notna(vol_std)) & (vol_std > 0),
        (hist_vol - vol_ma) / vol_std,
        0.0  # When std is 0 or NaN, z-score is 0
    )
    vol_z_score = pd.Series(vol_z_score, index=hist_vol.index)

    # ATR计算优化
    atr = calculate_atr(prices_df, period=14, min_periods=7)
    atr_ratio = atr / prices_df['close'].replace(0, np.nan)

    # Fill NaN values properly (avoid direct iloc assignment)
    vol_regime = vol_regime.fillna(1.0)  # 假设处于正常波动率区间
    vol_z_score = vol_z_score.fillna(0.0)  # 假设处于均值位置

    # Generate signal based on volatility regime
    current_vol_regime = vol_regime.iloc[-1]
    vol_z = vol_z_score.iloc[-1]

    if current_vol_regime < 0.8 and vol_z < -1:
        signal = 'bullish'  # Low vol regime, potential for expansion
        confidence = min(abs(vol_z) / 3, 1.0)
    elif current_vol_regime > 1.2 and vol_z > 1:
        signal = 'bearish'  # High vol regime, potential for contraction
        confidence = min(abs(vol_z) / 3, 1.0)
    else:
        signal = 'neutral'
        confidence = 0.5

    return {
        'signal': signal,
        'confidence': confidence,
        'metrics': {
            'historical_volatility': float(hist_vol.iloc[-1]),
            'volatility_regime': float(current_vol_regime),
            'volatility_z_score': float(vol_z),
            'atr_ratio': float(atr_ratio.iloc[-1])
        }
    }


def calculate_stat_arb_signals(prices_df):
    """
    Optimized statistical arbitrage signals with shorter lookback periods
    """
    # Calculate price distribution statistics
    returns = prices_df['close'].pct_change()

    # 使用更短的周期计算偏度和峰度
    skew = returns.rolling(42, min_periods=21).skew()
    kurt = returns.rolling(42, min_periods=21).kurt()

    # 优化Hurst指数计算
    hurst = calculate_hurst_exponent(prices_df['close'], max_lag=10)

    # 处理NaN值 (使用fillna而不是直接赋值)
    skew = skew.fillna(0.0)  # 假设正态分布
    kurt = kurt.fillna(3.0)  # 假设正态分布

    # Generate signal based on statistical properties
    if hurst < 0.4 and skew.iloc[-1] > 1:
        signal = 'bullish'
        confidence = (0.5 - hurst) * 2
    elif hurst < 0.4 and skew.iloc[-1] < -1:
        signal = 'bearish'
        confidence = (0.5 - hurst) * 2
    else:
        signal = 'neutral'
        confidence = 0.5

    return {
        'signal': signal,
        'confidence': confidence,
        'metrics': {
            'hurst_exponent': float(hurst),
            'skewness': float(skew.iloc[-1]),
            'kurtosis': float(kurt.iloc[-1])
        }
    }


def weighted_signal_combination(signals, weights):
    """
    Combines multiple trading signals using a weighted approach
    针对A股市场优化：如果动量非常大，临时增加动量策略的权重
    """
    # 如果动量非常大（如6月动量>30%），临时增加动量策略的权重
    # 这确保强大的历史动量不会被其他策略完全抵消
    momentum_signal = signals.get('momentum', {})
    momentum_metrics = momentum_signal.get('metrics', {})
    momentum_6m = abs(momentum_metrics.get('momentum_6m', 0)) if isinstance(momentum_metrics, dict) else 0
    
    adjusted_weights = weights.copy()
    if momentum_6m > 0.3:  # 6月动量超过30%（绝对值）
        # 临时增加动量策略权重（最多增加10%）
        momentum_weight_increase = min(momentum_6m * 0.2, 0.10)  # 最多增加10%
        original_momentum_weight = weights.get('momentum', 0.25)
        adjusted_weights['momentum'] = original_momentum_weight + momentum_weight_increase
        
        # 按比例减少其他权重，保持总和为1
        total_other_weight = sum(w for k, w in weights.items() if k != 'momentum')
        if total_other_weight > 0:
            reduction_factor = (total_other_weight - momentum_weight_increase) / total_other_weight
            for key in adjusted_weights:
                if key != 'momentum':
                    adjusted_weights[key] = weights[key] * reduction_factor
        
        logger.info(f"检测到6月动量{momentum_6m:.2%}，临时增加动量策略权重至{adjusted_weights['momentum']:.2%}")
    
    weights = adjusted_weights
    
    # Convert signals to numeric values
    signal_values = {
        'bullish': 1,
        'neutral': 0,
        'bearish': -1
    }

    weighted_sum = 0
    total_confidence = 0

    for strategy, signal in signals.items():
        numeric_signal = signal_values[signal['signal']]
        weight = weights[strategy]
        confidence = signal['confidence']

        weighted_sum += numeric_signal * weight * confidence
        total_confidence += weight * confidence

    # Normalize the weighted sum
    if total_confidence > 0:
        final_score = weighted_sum / total_confidence
    else:
        final_score = 0

    # Convert back to signal
    if final_score > 0.2:
        signal = 'bullish'
    elif final_score < -0.2:
        signal = 'bearish'
    else:
        signal = 'neutral'

    # Calculate confidence based on weighted average of individual confidences
    # This better reflects the overall confidence level
    if total_confidence > 0:
        # Normalize total_confidence by sum of weights to get average confidence
        total_weight = sum(weights.values())
        avg_confidence = total_confidence / total_weight if total_weight > 0 else 0.0
        # Combine with signal strength
        final_confidence = min(avg_confidence * (1 + abs(final_score)), 1.0)
    else:
        final_confidence = 0.0

    return {
        'signal': signal,
        'confidence': final_confidence
    }


def normalize_pandas(obj):
    """Convert pandas Series/DataFrames to primitive Python types"""
    if isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict('records')
    elif isinstance(obj, dict):
        return {k: normalize_pandas(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [normalize_pandas(item) for item in obj]
    elif isinstance(obj, (int, float)) and pd.isna(obj):
        # Handle NaN values: convert to None or a default value
        # For RSI, use 50.0 as default (neutral value)
        return None  # Will be handled by report template default
    return obj


def calculate_macd(prices_df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    ema_12 = prices_df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = prices_df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI) using Wilder's smoothing method
    
    Args:
        prices_df: DataFrame with price data
        period: Period for RSI calculation (default 14)
    
    Returns:
        pd.Series: RSI values
    """
    delta = prices_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    
    # Use Wilder's smoothing method (EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    # Handle division by zero: when avg_loss is 0, RSI should be 100 (or 50 if avg_gain is also 0)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # Fill NaN values: when avg_loss is 0, if avg_gain > 0 then RSI = 100, else RSI = 50
    # Use pd.Series with same index for fillna to work correctly
    fill_values = pd.Series(
        np.where(avg_gain > 0, 100.0, 50.0),
        index=rsi.index
    )
    rsi = rsi.fillna(fill_values)
    
    # Ensure no NaN values remain (fallback to 50 if still NaN)
    rsi = rsi.fillna(50.0)
    
    return rsi


def calculate_bollinger_bands(
    prices_df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0
) -> tuple[pd.Series, pd.Series]:
    """
    计算布林带 - 针对A股市场优化
    
    Args:
        prices_df: 价格数据DataFrame
        window: 移动平均窗口（默认20）
        num_std: 标准差倍数（默认2.0，A股市场波动性较大，可以考虑使用2.2）
    
    Returns:
        (上轨, 下轨)
    """
    sma = prices_df['close'].rolling(window).mean()
    std_dev = prices_df['close'].rolling(window).std()
    # A股市场波动性较大，可以使用稍大的标准差倍数（如2.2）
    # 但为了保持通用性，默认仍使用2.0，可在调用时调整
    upper_band = sma + (std_dev * num_std)
    lower_band = sma - (std_dev * num_std)
    return upper_band, lower_band


def calculate_ema(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Calculate Exponential Moving Average

    Args:
        df: DataFrame with price data
        window: EMA period

    Returns:
        pd.Series: EMA values
    """
    return df['close'].ewm(span=window, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX)

    Args:
        df: DataFrame with OHLC data
        period: Period for calculations

    Returns:
        DataFrame with ADX values
    """
    # Calculate True Range
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift())
    df['low_close'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

    # Calculate Directional Movement
    df['up_move'] = df['high'] - df['high'].shift()
    df['down_move'] = df['low'].shift() - df['low']

    df['plus_dm'] = np.where(
        (df['up_move'] > df['down_move']) & (df['up_move'] > 0),
        df['up_move'],
        0
    )
    df['minus_dm'] = np.where(
        (df['down_move'] > df['up_move']) & (df['down_move'] > 0),
        df['down_move'],
        0
    )

    # Calculate ADX using Wilder's smoothing
    # Use alpha=1/period for Wilder's smoothing (equivalent to ewm with alpha)
    tr_smoothed = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smoothed = df['plus_dm'].ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smoothed = df['minus_dm'].ewm(alpha=1/period, adjust=False).mean()
    
    # Calculate +DI and -DI, handle division by zero
    df['+di'] = np.where(
        tr_smoothed > 0,
        100 * (plus_dm_smoothed / tr_smoothed),
        0
    )
    df['-di'] = np.where(
        tr_smoothed > 0,
        100 * (minus_dm_smoothed / tr_smoothed),
        0
    )
    
    # Calculate DX, handle division by zero when both DI are 0
    di_sum = df['+di'] + df['-di']
    df['dx'] = np.where(
        di_sum > 0,
        100 * abs(df['+di'] - df['-di']) / di_sum,
        0  # When both DI are 0, DX is 0
    )
    
    # Calculate ADX using Wilder's smoothing
    df['adx'] = df['dx'].ewm(alpha=1/period, adjust=False).mean()

    return df[['adx', '+di', '-di']]


def calculate_ichimoku(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculate Ichimoku Cloud indicators

    Args:
        df: DataFrame with OHLC data

    Returns:
        Dictionary containing Ichimoku components
    """
    # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
    period9_high = df['high'].rolling(window=9).max()
    period9_low = df['low'].rolling(window=9).min()
    tenkan_sen = (period9_high + period9_low) / 2

    # Kijun-sen (Base Line): (26-period high + 26-period low)/2
    period26_high = df['high'].rolling(window=26).max()
    period26_low = df['low'].rolling(window=26).min()
    kijun_sen = (period26_high + period26_low) / 2

    # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)

    # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2
    period52_high = df['high'].rolling(window=52).max()
    period52_low = df['low'].rolling(window=52).min()
    senkou_span_b = ((period52_high + period52_low) / 2).shift(26)

    # Chikou Span (Lagging Span): Close shifted back 26 periods
    chikou_span = df['close'].shift(-26)

    return {
        'tenkan_sen': tenkan_sen,
        'kijun_sen': kijun_sen,
        'senkou_span_a': senkou_span_a,
        'senkou_span_b': senkou_span_b,
        'chikou_span': chikou_span
    }


def calculate_atr(df: pd.DataFrame, period: int = 14, min_periods: int = 7) -> pd.Series:
    """
    Optimized ATR calculation with minimum periods parameter

    Args:
        df: DataFrame with OHLC data
        period: Period for ATR calculation
        min_periods: Minimum number of periods required

    Returns:
        pd.Series: ATR values
    """
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(period, min_periods=min_periods).mean()


def calculate_hurst_exponent(price_series: pd.Series, max_lag: int = 10) -> float:
    """
    Optimized Hurst exponent calculation with shorter lookback and better error handling

    Args:
        price_series: Array-like price data
        max_lag: Maximum lag for R/S calculation (reduced from 20 to 10)

    Returns:
        float: Hurst exponent
    """
    try:
        # 使用对数收益率而不是价格
        returns = np.log(price_series / price_series.shift(1)).dropna()

        # 如果数据不足，返回0.5（随机游走）
        if len(returns) < max_lag * 2:
            return 0.5

        lags = range(2, max_lag)
        # 使用更稳定的计算方法
        tau = [np.sqrt(np.std(np.subtract(returns[lag:], returns[:-lag])))
               for lag in lags]

        # 添加小的常数避免log(0)
        tau = [max(1e-8, t) for t in tau]

        # 使用对数回归计算Hurst指数
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        h = reg[0]

        # 限制Hurst指数在合理范围内
        return max(0.0, min(1.0, h))

    except (ValueError, RuntimeWarning, np.linalg.LinAlgError):
        # 如果计算失败，返回0.5表示随机游走
        return 0.5


def calculate_obv(prices_df: pd.DataFrame) -> pd.Series:
    """
    计算OBV（On-Balance Volume）指标
    针对A股市场优化：处理停牌、异常成交量等情况
    """
    obv = [0]
    for i in range(1, len(prices_df)):
        current_volume = prices_df['volume'].iloc[i] if 'volume' in prices_df.columns else 0
        prev_volume = prices_df['volume'].iloc[i - 1] if 'volume' in prices_df.columns else 0
        
        # 处理停牌情况：如果成交量为0或异常低，OBV保持不变
        if current_volume == 0 or (prev_volume > 0 and current_volume / prev_volume < 0.01):
            obv.append(obv[-1])  # 停牌时OBV不变
            continue
        
        current_close = prices_df['close'].iloc[i]
        prev_close = prices_df['close'].iloc[i - 1]
        
        if current_close > prev_close:
            obv.append(obv[-1] + current_volume)
        elif current_close < prev_close:
            obv.append(obv[-1] - current_volume)
        else:
            obv.append(obv[-1])  # 价格不变，OBV不变
    
    # 创建OBV Series，确保索引与prices_df一致
    obv_series = pd.Series(obv, index=prices_df.index)
    return obv_series
