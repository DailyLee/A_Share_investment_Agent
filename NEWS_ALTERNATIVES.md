# 📰 A股新闻数据源替代方案

## ❌ Baostock 不支持新闻

**确认：** Baostock 主要提供交易数据和财务数据，**不提供新闻数据**。

---

## 🔄 可用的替代方案

### 方案 1: Tushare Pro ⭐ 推荐

**简介：** 专业的中国金融数据接口

**优点：**
- ✅ 提供新闻数据接口
- ✅ 数据质量高、稳定
- ✅ 有完整的 Python SDK
- ✅ 支持历史新闻查询

**缺点：**
- ⚠️ 需要注册并获取 token
- ⚠️ 部分功能需要积分

**安装：**
```bash
poetry add tushare
```

**使用示例：**
```python
import tushare as ts

# 设置 token
ts.set_token('your_token_here')
pro = ts.pro_api()

# 获取新闻
news_df = pro.news(
    src='sina',  # 新浪财经
    start_date='20251201',
    end_date='20251210'
)

# 获取特定股票的新闻
stock_news = pro.news(
    src='sina',
    start_date='20251201',
    end_date='20251210',
    # 可以通过关键词过滤
)
```

**注册地址：** https://tushare.pro/register

---

### 方案 2: 东方财富网 API 🌟

**简介：** 直接调用东方财富的新闻接口

**优点：**
- ✅ 免费
- ✅ 数据及时
- ✅ 覆盖全面
- ✅ 不需要注册

**实现方案：**

```python
import requests
import pandas as pd
from datetime import datetime

def get_eastmoney_news(stock_code: str, page_size: int = 20):
    """
    从东方财富网获取股票新闻
    
    Args:
        stock_code: 股票代码，如 '600353'
        page_size: 获取新闻条数
    
    Returns:
        新闻列表
    """
    # 判断股票市场
    market = '1' if stock_code.startswith('6') else '0'
    
    # 构建 API URL
    url = 'https://searchapi.eastmoney.com/api/suggest/get'
    params = {
        'input': stock_code,
        'type': '14',  # 14 表示股票新闻
        'count': page_size,
        'token': 'D43BF722C8E33BDC906FB84D85E326E8',
        'market': market
    }
    
    # 或者使用个股资讯接口
    news_url = f'https://np-listapi.eastmoney.com/comm/wap/getListInfo'
    news_params = {
        'cb': 'callback',
        'client': 'wap',
        'type': '1',  # 1=个股新闻
        'mTypeAndCode': f'{market}.{stock_code}',
        'pageSize': page_size,
        'pageIndex': 1,
        'callback': 'jQuery'
    }
    
    try:
        response = requests.get(news_url, params=news_params, timeout=10)
        # 解析 JSONP 响应
        # ... 处理响应数据
        return news_list
    except Exception as e:
        print(f"获取东方财富新闻失败: {e}")
        return []
```

---

### 方案 3: 新浪财经 API 📱

**简介：** 新浪财经的股票新闻接口

**优点：**
- ✅ 免费
- ✅ 响应快
- ✅ 历史悠久，相对稳定

**实现方案：**

```python
import requests
import json
from datetime import datetime

def get_sina_finance_news(stock_code: str, max_news: int = 20):
    """
    从新浪财经获取股票新闻
    
    Args:
        stock_code: 股票代码
        max_news: 最多获取条数
    
    Returns:
        新闻列表
    """
    # 新浪财经新闻 API
    url = 'https://finance.sina.com.cn/realstock/company/{}/nc.shtml'
    
    # 或者使用移动端 API
    mobile_api = 'https://interface.sina.cn/stock/stock_news.d.json'
    params = {
        'symbol': f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}',
        'page': 1,
        'num': max_news
    }
    
    try:
        response = requests.get(mobile_api, params=params, timeout=10)
        data = response.json()
        
        news_list = []
        for item in data.get('result', {}).get('data', []):
            news_item = {
                'title': item.get('title', ''),
                'content': item.get('summary', ''),
                'publish_time': item.get('ctime', ''),
                'source': '新浪财经',
                'url': item.get('url', '')
            }
            news_list.append(news_item)
        
        return news_list
    except Exception as e:
        print(f"获取新浪财经新闻失败: {e}")
        return []
```

---

### 方案 4: 直接网页爬取 🕷️

**优点：**
- ✅ 完全控制
- ✅ 可以获取详细内容
- ✅ 可以自定义数据源

**缺点：**
- ⚠️ 需要处理反爬
- ⚠️ 页面结构变化需要更新

**推荐爬取网站：**

1. **东方财富网**
   - URL: `http://guba.eastmoney.com/list,{stock_code}.html`
   - 内容丰富，更新及时

2. **雪球**
   - URL: `https://xueqiu.com/S/{market}{stock_code}`
   - 包含用户讨论和新闻

3. **同花顺**
   - URL: `http://news.10jqka.com.cn/cjzx_{stock_code}/`
   - 专业财经新闻

**实现建议：**
```python
import requests
from bs4 import BeautifulSoup

def crawl_eastmoney_news(stock_code: str):
    """爬取东方财富网新闻"""
    url = f'http://guba.eastmoney.com/list,{stock_code}.html'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 解析新闻列表
    # ...
```

---

### 方案 5: RSS 订阅源 📡

**优点：**
- ✅ 标准格式
- ✅ 易于解析
- ✅ 实时更新

**可用的 RSS 源：**

```python
import feedparser

# 财经网站 RSS 订阅
rss_feeds = {
    '新浪财经': 'https://feed.sina.com.cn/finance/roll/index.xml',
    '网易财经': 'http://money.163.com/special/00251G8F/rss_finance.xml',
    '东方财富': 'http://feed.eastmoney.com/news/all.xml'
}

def get_news_from_rss(rss_url: str, keyword: str = None):
    """从 RSS 获取新闻并过滤"""
    feed = feedparser.parse(rss_url)
    
    news_list = []
    for entry in feed.entries:
        # 如果提供了关键词，进行过滤
        if keyword and keyword not in entry.title:
            continue
            
        news_item = {
            'title': entry.title,
            'content': entry.summary,
            'publish_time': entry.published,
            'url': entry.link
        }
        news_list.append(news_item)
    
    return news_list
```

---

## 🎯 推荐实施方案

### 短期方案（立即可用）

**使用东方财富网直接 API + 网页爬取**

1. 主要使用东方财富网 API
2. Google 搜索作为补充（需要代理）
3. 如果都失败，返回中性信号

**实现步骤：**

```bash
# 1. 创建新的新闻获取模块
touch src/tools/eastmoney_news.py

# 2. 修改 news_crawler.py 添加新数据源
# 3. 测试新数据源
```

### 中期方案（需要注册）

**使用 Tushare Pro**

1. 注册 Tushare Pro 账号
2. 获取 API token
3. 集成到现有系统

**优点：** 数据质量高，稳定性好

### 长期方案（最佳实践）

**多数据源混合策略**

```
┌─────────────────────────────────────┐
│        新闻数据获取策略             │
├─────────────────────────────────────┤
│ 1. Tushare Pro (主要)              │
│ 2. 东方财富 API (备用1)             │
│ 3. 新浪财经 API (备用2)             │
│ 4. Google 搜索 (补充)               │
│ 5. RSS 订阅 (实时监控)              │
└─────────────────────────────────────┘
```

---

## 💻 快速实现：东方财富网方案

我可以立即为您实现东方财富网的新闻获取功能。这个方案：
- ✅ 免费
- ✅ 不需要注册
- ✅ 可以立即使用
- ✅ 数据质量好

**是否需要我实现这个方案？**

实现后您就可以：
1. 不依赖 Akshare
2. 不需要 Google 搜索（避免被墙问题）
3. 获得稳定的新闻数据

---

## 📊 各方案对比

| 方案 | 免费 | 稳定性 | 实时性 | 难度 | 推荐度 |
|------|------|--------|--------|------|--------|
| Tushare Pro | 部分 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 低 | ⭐⭐⭐⭐⭐ |
| 东方财富API | ✅ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐ |
| 新浪财经API | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 中 | ⭐⭐⭐ |
| 网页爬取 | ✅ | ⭐⭐ | ⭐⭐⭐⭐ | 高 | ⭐⭐ |
| RSS订阅 | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 低 | ⭐⭐⭐ |

---

## 🚀 下一步

**选择一个方案，我可以立即帮您实现！**

推荐顺序：
1. **东方财富 API** - 立即可用，免费稳定
2. **Tushare Pro** - 长期最佳方案
3. **多数据源混合** - 最稳定的生产方案

您想使用哪个方案？
