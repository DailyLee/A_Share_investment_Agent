"""
新浪财经新闻获取模块

提供从新浪财经获取股票新闻的功能
"""

import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict
from bs4 import BeautifulSoup


def get_sina_stock_news(stock_code: str, max_news: int = 20) -> List[Dict]:
    """
    从新浪财经获取个股新闻
    
    Args:
        stock_code: 股票代码，如 '600353'
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        print(f"正在从新浪财经获取 {stock_code} 的新闻...")
        
        # 判断市场
        if stock_code.startswith('6'):
            symbol = f'sh{stock_code}'
        else:
            symbol = f'sz{stock_code}'
        
        # 新浪财经个股新闻页面
        url = f'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php?symbol={symbol}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'  # 新浪使用 gbk 编码
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表
            news_items = soup.find_all('li')
            
            for item in news_items[:max_news]:
                try:
                    # 查找链接
                    link = item.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # 查找时间
                    time_elem = item.find('span', class_='time') or item.find('span')
                    publish_time = ''
                    if time_elem:
                        publish_time = time_elem.get_text(strip=True)
                    
                    # 标准化时间
                    publish_time = normalize_sina_time(publish_time)
                    
                    news_item = {
                        'title': title,
                        'content': title,  # 摘要使用标题
                        'publish_time': publish_time,
                        'source': '新浪财经',
                        'url': href,
                        'keyword': stock_code
                    }
                    
                    news_list.append(news_item)
                    
                except Exception as e:
                    print(f"解析新闻项时出错: {e}")
                    continue
            
            if news_list:
                print(f"✓ 成功获取 {len(news_list)} 条新浪财经新闻")
                
    except Exception as e:
        print(f"获取新浪财经新闻时出错: {e}")
    
    return news_list


def get_sina_market_news(max_news: int = 50) -> List[Dict]:
    """
    获取新浪财经市场要闻
    
    Args:
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        print("正在从新浪财经获取市场要闻...")
        
        # 新浪财经首页
        url = 'https://finance.sina.com.cn/stock/'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有链接
            links = soup.find_all('a', href=True)
            
            for link in links:
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # 过滤：标题太短、非新闻链接
                    if (len(title) < 10 or 
                        'javascript' in href or 
                        not href.startswith('http') or
                        'sina.com.cn' not in href):
                        continue
                    
                    # 过滤非财经相关
                    if not any(keyword in href for keyword in ['finance', 'stock', 'money']):
                        continue
                    
                    news_item = {
                        'title': title,
                        'content': title,
                        'publish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source': '新浪财经',
                        'url': href,
                        'keyword': 'A股'
                    }
                    
                    news_list.append(news_item)
                    
                    if len(news_list) >= max_news:
                        break
                        
                except Exception:
                    continue
            
            if news_list:
                print(f"✓ 获取 {len(news_list)} 条新浪财经要闻")
                
    except Exception as e:
        print(f"获取新浪财经要闻时出错: {e}")
    
    return news_list


def normalize_sina_time(time_str: str) -> str:
    """
    标准化新浪财经的时间格式
    
    Args:
        time_str: 原始时间字符串
    
    Returns:
        标准化的时间字符串
    """
    if not time_str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        now = datetime.now()
        
        # 处理 "MM月DD日 HH:MM" 格式
        match = re.search(r'(\d+)月(\d+)日\s+(\d+):(\d+)', time_str)
        if match:
            month, day, hour, minute = match.groups()
            return f"{now.year}-{int(month):02d}-{int(day):02d} {hour}:{minute}:00"
        
        # 处理 "YYYY-MM-DD HH:MM:SS" 格式
        if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', time_str):
            return time_str
        
        # 处理相对时间
        if '分钟前' in time_str:
            minutes = int(re.search(r'(\d+)', time_str).group(1))
            return (now - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
        
        if '小时前' in time_str:
            hours = int(re.search(r'(\d+)', time_str).group(1))
            return (now - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 默认返回当前时间
        return now.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 测试函数
if __name__ == "__main__":
    print("=" * 60)
    print("测试新浪财经新闻接口")
    print("=" * 60)
    
    # 测试获取个股新闻
    print("\n1. 测试获取个股新闻 (600353):")
    stock_news = get_sina_stock_news('600353', max_news=5)
    if stock_news:
        print(f"\n成功获取 {len(stock_news)} 条新闻:")
        for i, news in enumerate(stock_news, 1):
            print(f"\n新闻 {i}:")
            print(f"  标题: {news['title'][:50]}...")
            print(f"  时间: {news['publish_time']}")
            print(f"  URL: {news['url'][:60]}...")
    else:
        print("未获取到新闻")
    
    # 测试获取市场要闻
    print("\n" + "=" * 60)
    print("2. 测试获取市场要闻:")
    market_news = get_sina_market_news(max_news=5)
    if market_news:
        print(f"\n成功获取 {len(market_news)} 条新闻:")
        for i, news in enumerate(market_news, 1):
            print(f"\n新闻 {i}:")
            print(f"  标题: {news['title'][:50]}...")
            print(f"  URL: {news['url'][:60]}...")
    else:
        print("未获取到新闻")
