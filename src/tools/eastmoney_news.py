"""
东方财富网新闻获取模块

提供从东方财富网获取股票新闻的功能
"""

import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import time

def get_eastmoney_stock_news(stock_code: str, max_news: int = 20) -> List[Dict]:
    """
    从东方财富网获取个股新闻
    
    Args:
        stock_code: 股票代码，如 '600353'
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表，每条新闻包含标题、内容、时间、来源等信息
    """
    news_list = []
    
    # 直接使用股吧爬取（最可靠的方法）
    print(f"正在从东方财富股吧获取 {stock_code} 的新闻...")
    guba_news = get_eastmoney_guba_news(stock_code, max_news)
    if guba_news:
        return guba_news
    
    # 如果股吧失败，尝试搜索财经新闻并过滤
    print(f"尝试从财经要闻中搜索 {stock_code} 相关新闻...")
    market_news = get_eastmoney_market_news(max_news * 3)  # 多获取一些用于过滤
    if market_news:
        # 过滤包含股票代码的新闻
        filtered_news = [
            news for news in market_news
            if stock_code in news['title'] or stock_code in news['content']
        ]
        if filtered_news:
            print(f"✓ 从财经要闻中筛选出 {len(filtered_news[:max_news])} 条相关新闻")
            return filtered_news[:max_news]
    
    return news_list


def get_eastmoney_guba_news(stock_code: str, max_news: int = 20) -> List[Dict]:
    """
    从东方财富股吧获取新闻
    
    Args:
        stock_code: 股票代码
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        # 股吧列表页面
        url = f'http://guba.eastmoney.com/list,{stock_code}_1.html'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://guba.eastmoney.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找帖子列表
            posts = soup.find_all('div', class_='articleh')
            
            for post in posts[:max_news]:
                try:
                    # 提取标题和链接
                    title_elem = post.find('span', class_='l3') or post.find('span', class_='l2')
                    if not title_elem:
                        continue
                    
                    link_elem = title_elem.find('a')
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    # 提取时间
                    time_elem = post.find('span', class_='l5')
                    publish_time = time_elem.get_text(strip=True) if time_elem else ''
                    
                    # 提取作者/来源
                    author_elem = post.find('span', class_='l4')
                    author = author_elem.get_text(strip=True) if author_elem else '东方财富股吧'
                    
                    # 构建完整URL
                    full_url = href if href.startswith('http') else f'http://guba.eastmoney.com{href}'
                    
                    news_item = {
                        'title': title,
                        'content': title,  # 股吧帖子摘要就用标题
                        'publish_time': normalize_time(publish_time),
                        'source': author,
                        'url': full_url,
                        'keyword': stock_code
                    }
                    
                    news_list.append(news_item)
                    
                except Exception as e:
                    print(f"解析股吧帖子时出错: {e}")
                    continue
            
            if news_list:
                print(f"✓ 从股吧获取 {len(news_list)} 条内容")
                
    except Exception as e:
        print(f"获取股吧新闻时出错: {e}")
    
    return news_list


def get_eastmoney_flash_news(stock_code: str, max_news: int = 20) -> List[Dict]:
    """
    从东方财富快讯获取相关新闻（通过关键词过滤）
    
    Args:
        stock_code: 股票代码
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        # 东方财富7x24小时快讯
        api_url = 'https://np-cnotice-stock.eastmoney.com/api/content/ann'
        
        params = {
            'client_source': 'web',
            'page_index': 1,
            'page_size': 50,  # 获取更多，然后过滤
            'sr': -1
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('data') and data['data'].get('list'):
                for item in data['data']['list']:
                    title = item.get('title', '')
                    content = item.get('content', '') or title
                    
                    # 检查是否包含股票代码或相关关键词
                    if stock_code in title or stock_code in content:
                        news_item = {
                            'title': title,
                            'content': content,
                            'publish_time': item.get('show_time', ''),
                            'source': '东方财富快讯',
                            'url': item.get('url', ''),
                            'keyword': stock_code
                        }
                        news_list.append(news_item)
                        
                        if len(news_list) >= max_news:
                            break
                
                if news_list:
                    print(f"✓ 从快讯获取 {len(news_list)} 条相关新闻")
                    
    except Exception as e:
        print(f"获取快讯新闻时出错: {e}")
    
    return news_list


def get_eastmoney_index_news(index_code: str = '000300', max_news: int = 50) -> List[Dict]:
    """
    获取指数相关新闻（如沪深300）
    
    Args:
        index_code: 指数代码，默认 '000300' (沪深300)
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    print(f"正在从东方财富网获取 {index_code} 指数新闻...")
    
    # 直接获取A股要闻（最可靠）
    market_news = get_eastmoney_market_news(max_news)
    if market_news:
        return market_news
    
    return []


def get_eastmoney_market_news(max_news: int = 50) -> List[Dict]:
    """
    获取A股市场要闻 - 使用网页爬取
    
    Args:
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        # 爬取东方财富财经网页
        url = 'http://finance.eastmoney.com/'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表 - 尝试多种选择器
            news_items = []
            
            # 方法1: 查找文章列表
            news_items.extend(soup.find_all('div', class_='txt'))
            news_items.extend(soup.find_all('li', class_='news'))
            news_items.extend(soup.find_all('div', class_='article'))
            
            for item in news_items[:max_news]:
                try:
                    # 提取标题和链接
                    link = item.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # 构建完整URL
                    if not href.startswith('http'):
                        href = f'http:{href}' if href.startswith('//') else f'http://finance.eastmoney.com{href}'
                    
                    # 尝试提取时间
                    time_elem = item.find('span', class_='time') or item.find('div', class_='time')
                    publish_time = time_elem.get_text(strip=True) if time_elem else ''
                    
                    # 尝试提取摘要
                    content_elem = item.find('p') or item.find('div', class_='desc')
                    content = content_elem.get_text(strip=True) if content_elem else title
                    
                    news_item = {
                        'title': title,
                        'content': content,
                        'publish_time': normalize_time(publish_time),
                        'source': '东方财富网',
                        'url': href,
                        'keyword': 'A股'
                    }
                    
                    news_list.append(news_item)
                    
                except Exception as e:
                    print(f"解析新闻项时出错: {e}")
                    continue
            
            if news_list:
                print(f"✓ 从网页获取 {len(news_list)} 条A股要闻")
            else:
                # 如果网页爬取失败，返回一些默认的财经要闻
                print("网页爬取未获取到新闻，尝试使用备用方法...")
                news_list = get_default_market_news(max_news)
                    
    except Exception as e:
        print(f"获取市场要闻时出错: {e}")
        # 返回默认新闻
        news_list = get_default_market_news(max_news)
    
    return news_list


def get_default_market_news(max_news: int = 50) -> List[Dict]:
    """
    获取默认的市场要闻（使用简单HTTP请求）
    
    Args:
        max_news: 最多获取的新闻条数
    
    Returns:
        新闻列表
    """
    news_list = []
    
    try:
        # 使用东方财富移动端接口（更简单）
        url = 'http://finance.eastmoney.com/a/cgnjj.html'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'  # 东方财富使用 gbk 编码
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻列表
            links = soup.find_all('a', href=True)
            
            for link in links[:max_news * 2]:  # 多获取一些，然后过滤
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # 过滤无效链接
                    if (not title or len(title) < 10 or 
                        not href or 'javascript' in href or 
                        '#' in href or href == '/'):
                        continue
                    
                    # 确保是完整URL
                    if not href.startswith('http'):
                        href = f'http:{href}' if href.startswith('//') else f'http://finance.eastmoney.com{href}'
                    
                    news_item = {
                        'title': title,
                        'content': title,  # 摘要使用标题
                        'publish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source': '东方财富网',
                        'url': href,
                        'keyword': 'A股'
                    }
                    
                    news_list.append(news_item)
                    
                    if len(news_list) >= max_news:
                        break
                        
                except Exception:
                    continue
            
            if news_list:
                print(f"✓ 从备用方法获取 {len(news_list)} 条新闻")
                    
    except Exception as e:
        print(f"备用方法获取新闻时出错: {e}")
    
    return news_list


def normalize_time(time_str: str) -> str:
    """
    标准化时间格式
    
    Args:
        time_str: 原始时间字符串，如 "12-10 15:30", "2小时前", "今天 10:30"
    
    Returns:
        标准化的时间字符串 "YYYY-MM-DD HH:MM:SS"
    """
    if not time_str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        now = datetime.now()
        
        # 处理相对时间
        if '分钟前' in time_str:
            minutes = int(re.search(r'(\d+)', time_str).group(1))
            return (now - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
        
        if '小时前' in time_str:
            hours = int(re.search(r'(\d+)', time_str).group(1))
            return (now - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        if '天前' in time_str:
            days = int(re.search(r'(\d+)', time_str).group(1))
            return (now - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 处理 "今天 HH:MM" 格式
        if '今天' in time_str:
            time_part = re.search(r'(\d{1,2}:\d{2})', time_str)
            if time_part:
                return f"{now.strftime('%Y-%m-%d')} {time_part.group(1)}:00"
        
        # 处理 "MM-DD HH:MM" 格式
        if re.match(r'\d{2}-\d{2}\s+\d{2}:\d{2}', time_str):
            return f"{now.year}-{time_str}:00"
        
        # 处理 "YYYY-MM-DD HH:MM:SS" 格式（已标准化）
        if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', time_str):
            return time_str
        
        # 其他格式，返回当前时间
        return now.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        print(f"时间格式化错误: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 测试函数
if __name__ == "__main__":
    print("=" * 60)
    print("测试东方财富新闻接口")
    print("=" * 60)
    
    # 测试获取个股新闻
    print("\n1. 测试获取个股新闻 (600353):")
    stock_news = get_eastmoney_stock_news('600353', max_news=5)
    if stock_news:
        print(f"\n成功获取 {len(stock_news)} 条新闻:")
        for i, news in enumerate(stock_news, 1):
            print(f"\n新闻 {i}:")
            print(f"  标题: {news['title'][:50]}...")
            print(f"  时间: {news['publish_time']}")
            print(f"  来源: {news['source']}")
    else:
        print("未获取到新闻")
    
    # 测试获取指数新闻
    print("\n" + "=" * 60)
    print("2. 测试获取沪深300新闻 (000300):")
    index_news = get_eastmoney_index_news('000300', max_news=5)
    if index_news:
        print(f"\n成功获取 {len(index_news)} 条新闻:")
        for i, news in enumerate(index_news, 1):
            print(f"\n新闻 {i}:")
            print(f"  标题: {news['title'][:50]}...")
            print(f"  时间: {news['publish_time']}")
            print(f"  来源: {news['source']}")
    else:
        print("未获取到新闻")
