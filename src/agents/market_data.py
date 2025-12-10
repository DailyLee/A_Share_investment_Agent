from langchain_core.messages import HumanMessage
from src.tools.openrouter_config import get_chat_completion
from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.tools.api import get_financial_metrics, get_financial_statements, get_market_data, get_price_history
from src.utils.logging_config import setup_logger
from src.utils.api_utils import agent_endpoint, log_llm_interaction

from datetime import datetime, timedelta
import pandas as pd

# 设置日志记录
logger = setup_logger('market_data_agent')


@agent_endpoint("market_data", "市场数据收集，负责获取股价历史、财务指标和市场信息")
def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    show_workflow_status("Market Data Agent")
    show_reasoning = state["metadata"]["show_reasoning"]

    messages = state["messages"]
    data = state["data"]

    # Set default dates
    current_date = datetime.now()
    yesterday = current_date - timedelta(days=1)
    end_date = data["end_date"] or yesterday.strftime('%Y-%m-%d')

    # Ensure end_date is not in the future
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    if end_date_obj > yesterday:
        end_date = yesterday.strftime('%Y-%m-%d')
        end_date_obj = yesterday

    if not data["start_date"]:
        # Calculate 1 year before end_date
        start_date = end_date_obj - timedelta(days=365)  # 默认获取一年的数据
        start_date = start_date.strftime('%Y-%m-%d')
    else:
        start_date = data["start_date"]

    # Get all required data
    ticker = data["ticker"]

    # 获取价格数据并验证
    prices_df = get_price_history(ticker, start_date, end_date)
    if prices_df is None or prices_df.empty:
        logger.warning(f"警告：无法获取{ticker}的价格数据，将使用空数据继续")
        prices_df = pd.DataFrame(
            columns=['close', 'open', 'high', 'low', 'volume'])

    # 获取财务指标
    try:
        financial_metrics = get_financial_metrics(ticker)
    except Exception as e:
        logger.error(f"获取财务指标失败: {str(e)}")
        financial_metrics = {}

    # 获取财务报表
    try:
        financial_line_items = get_financial_statements(ticker)
    except Exception as e:
        logger.error(f"获取财务报表失败: {str(e)}")
        financial_line_items = {}

    # 获取市场数据
    try:
        market_data = get_market_data(ticker)
    except Exception as e:
        logger.error(f"获取市场数据失败: {str(e)}")
        market_data = {"market_cap": 0}

    # 确保数据格式正确
    if not isinstance(prices_df, pd.DataFrame):
        prices_df = pd.DataFrame(
            columns=['close', 'open', 'high', 'low', 'volume'])

    # 转换价格数据为字典格式
    prices_dict = prices_df.to_dict('records')

    # 获取股票名称和行业
    stock_name = market_data.get("stock_name", "")
    industry = market_data.get("industry", "")
    if stock_name:
        logger.info(f"获取到股票名称: {stock_name}")
    else:
        logger.warning(f"无法获取 {ticker} 的股票名称")
    
    if industry:
        logger.info(f"获取到行业信息: {industry}")
    else:
        logger.warning(f"无法获取 {ticker} 的行业信息")
    
    # 获取 market_cap，优先使用 market_data，如果为0则尝试从 financial_metrics 获取
    market_cap = market_data.get("market_cap", 0)
    if market_cap <= 0 and financial_metrics and len(financial_metrics) > 0:
        # 尝试从 financial_metrics 中获取 market_cap 作为后备方案
        fallback_market_cap = financial_metrics[0].get("market_cap", 0)
        if fallback_market_cap > 0:
            logger.info(f"从 financial_metrics 获取 market_cap: {fallback_market_cap}")
            market_cap = fallback_market_cap
            # 更新 market_data 中的 market_cap
            market_data["market_cap"] = market_cap
        else:
            logger.warning(f"无法获取 {ticker} 的市场市值数据，market_cap 将为 0")

    # 保存推理信息到metadata供API使用
    market_data_summary = {
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "data_collected": {
            "price_history": len(prices_dict) > 0,
            "financial_metrics": len(financial_metrics) > 0,
            "financial_statements": len(financial_line_items) > 0,
            "market_data": len(market_data) > 0
        },
        "summary": f"为{ticker}收集了从{start_date}到{end_date}的市场数据，包括价格历史、财务指标和市场信息"
    }

    if show_reasoning:
        show_agent_reasoning(market_data_summary, "Market Data Agent")
        state["metadata"]["agent_reasoning"] = market_data_summary

    return {
        "messages": messages,
        "data": {
            **data,
            "stock_name": stock_name,
            "industry": industry,
            "prices": prices_dict,
            "start_date": start_date,
            "end_date": end_date,
            "financial_metrics": financial_metrics,
            "financial_line_items": financial_line_items,
            "market_cap": market_cap,
            "market_data": market_data,
        },
        "metadata": state["metadata"],
    }
