from langchain_core.messages import HumanMessage
from src.agents.state import AgentState, show_agent_reasoning, show_workflow_status
from src.tools.news_crawler import get_stock_news, get_industry_news, get_news_sentiment
from src.utils.logging_config import setup_logger
from src.utils.api_utils import agent_endpoint, log_llm_interaction
import json
from datetime import datetime, timedelta

# 设置日志记录
logger = setup_logger('sentiment_agent')


def _filter_recent_news(news_list: list, days: int = 7) -> list:
    """过滤指定天数内的新闻"""
    cutoff_date = datetime.now() - timedelta(days=days)
    recent = []
    for news in news_list:
        if 'publish_time' in news:
            try:
                news_date = datetime.strptime(
                    news['publish_time'], '%Y-%m-%d %H:%M:%S')
                if news_date > cutoff_date:
                    recent.append(news)
            except ValueError:
                recent.append(news)
        else:
            recent.append(news)
    return recent


def _merge_news_lists(stock_news: list, industry_news: list) -> list:
    """合并个股新闻和行业新闻，按标题去重"""
    seen_titles = set()
    merged = []

    for news in stock_news:
        title = news.get('title', '')
        if title and title not in seen_titles:
            seen_titles.add(title)
            news['news_type'] = '个股新闻'
            merged.append(news)

    for news in industry_news:
        title = news.get('title', '')
        if title and title not in seen_titles:
            seen_titles.add(title)
            news['news_type'] = '行业新闻'
            merged.append(news)

    try:
        merged.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
    except Exception:
        pass

    return merged


@agent_endpoint("sentiment", "情感分析师，分析个股新闻和行业新闻的市场情绪")
def sentiment_agent(state: AgentState):
    """Responsible for sentiment analysis using both stock and industry news"""
    show_workflow_status("Sentiment Analyst")
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    symbol = data["ticker"]
    industry = data.get("industry", "")
    logger.info(f"正在分析股票: {symbol}, 所属行业: {industry or '未知'}")

    num_of_news = data.get("num_of_news", 20)
    end_date = data.get("end_date")

    # 获取个股新闻
    stock_news_count = num_of_news
    stock_news = get_stock_news(symbol, max_news=stock_news_count, date=end_date)
    recent_stock_news = _filter_recent_news(stock_news)
    logger.info(f"个股新闻: 获取 {len(stock_news)} 条, 近7天 {len(recent_stock_news)} 条")

    # 获取行业新闻
    industry_news_count = max(num_of_news // 2, 5)
    recent_industry_news = []
    if industry:
        industry_news = get_industry_news(industry, max_news=industry_news_count, date=end_date)
        recent_industry_news = _filter_recent_news(industry_news)
        logger.info(f"行业新闻({industry}): 获取 {len(industry_news)} 条, 近7天 {len(recent_industry_news)} 条")
    else:
        logger.warning("未获取到行业信息，跳过行业新闻")

    # 合并个股新闻和行业新闻
    merged_news = _merge_news_lists(recent_stock_news, recent_industry_news)
    logger.info(f"合并后新闻总数: {len(merged_news)} 条 (个股 {len(recent_stock_news)} + 行业 {len(recent_industry_news)}, 去重后)")

    sentiment_score = get_news_sentiment(merged_news, num_of_news=num_of_news)

    # 根据情感分数生成交易信号和置信度
    if sentiment_score >= 0.5:
        signal = "bullish"
        confidence = str(round(abs(sentiment_score) * 100)) + "%"
    elif sentiment_score <= -0.5:
        signal = "bearish"
        confidence = str(round(abs(sentiment_score) * 100)) + "%"
    else:
        signal = "neutral"
        confidence = str(round((1 - abs(sentiment_score)) * 100)) + "%"

    # 生成分析结果
    stock_count = len(recent_stock_news)
    industry_count = len(recent_industry_news)
    reasoning_text = (
        f"Based on {len(merged_news)} recent news articles "
        f"(stock: {stock_count}, industry[{industry or 'N/A'}]: {industry_count}), "
        f"sentiment score: {sentiment_score:.2f}"
    )
    message_content = {
        "signal": signal,
        "confidence": confidence,
        "reasoning": reasoning_text
    }

    if show_reasoning:
        show_agent_reasoning(message_content, "Sentiment Analysis Agent")
        state["metadata"]["agent_reasoning"] = message_content

    message = HumanMessage(
        content=json.dumps(message_content),
        name="sentiment_agent",
    )

    show_workflow_status("Sentiment Analyst", "completed")
    return {
        "messages": [message],
        "data": {
            **data,
            "sentiment_analysis": sentiment_score
        },
        "metadata": state["metadata"],
    }
