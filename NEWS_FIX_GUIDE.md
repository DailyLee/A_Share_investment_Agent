# 新闻功能修复指南

## 📋 问题概述

根据对报告和日志的分析，发现以下三个模块没有获取到数据：

1. **情绪分析** - 获取到 0 条新闻
2. **宏观分析** (Macro Analyst) - 关键因素字段为空
3. **大盘宏观新闻分析** (Macro News Agent) - JSON解析错误

## 🔍 根本原因

### 1. Playwright 浏览器驱动未安装

**错误信息：**
```
BrowserType.launch: Executable doesn't exist at /Users/li.dai/Library/Caches/ms-playwright/chromium_headless_shell-1169/chrome-mac/headless_shell
```

**影响范围：**
- Google 搜索无法工作
- 无法通过智能搜索获取股票新闻

### 2. Akshare API 数据格式问题

**错误信息：**
```
Expecting value: line 1 column 1 (char 0)
```

**影响范围：**
- 个股新闻获取失败
- 沪深300新闻获取失败
- 所有基于新闻的分析无法进行

### 3. 缓存中保存了错误数据

**表现：**
- `macro_summary.json` 中保存了空数据（新闻数量为0）
- 导致即使API修复后仍然读取错误的缓存

## 🛠️ 快速修复步骤

### 方法 1: 自动修复（推荐）

运行提供的修复脚本：

```bash
# 确保脚本有执行权限
chmod +x fix_news_issues.sh

# 运行修复脚本
./fix_news_issues.sh
```

这个脚本会自动：
1. 安装 Playwright 浏览器驱动
2. 清除所有错误的缓存文件
3. 运行测试验证修复是否成功

### 方法 2: 手动修复

#### 步骤 1: 安装 Playwright

```bash
# 安装 Playwright 浏览器
playwright install chromium

# 验证安装
playwright --version
```

#### 步骤 2: 清除缓存

```bash
# 清除宏观新闻缓存
rm -f src/data/macro_summary.json

# 清除股票新闻缓存
rm -rf src/data/stock_news/*

# 清除情感分析缓存
rm -f src/data/sentiment_cache.json

# 清除宏观分析缓存
rm -f src/data/macro_analysis_cache.json
```

#### 步骤 3: 运行测试

```bash
# 运行测试脚本验证修复
poetry run python test_news_apis.py
```

#### 步骤 4: 重新运行分析

```bash
# 重新运行投资分析
poetry run python src/main.py --ticker 600353
```

## 🔧 改进内容

我已经对以下文件进行了改进：

### 1. `news_crawler.py`

**改进内容：**
- ✅ 添加了重试机制（最多3次）
- ✅ 改进了 JSON 解析错误处理
- ✅ 添加了更详细的错误日志

**关键改动：**
```python
# 添加了重试逻辑
max_retries = 3
retry_delay = 2  # 秒

for attempt in range(max_retries):
    try:
        # 获取新闻
        ...
    except json.JSONDecodeError as e:
        # 特殊处理JSON错误
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            continue
```

### 2. `macro_news_agent.py`

**改进内容：**
- ✅ 添加了重试机制
- ✅ 区分不同类型的错误
- ✅ 提供更友好的错误信息

## 📊 测试工具

### test_news_apis.py

这个测试脚本会验证以下功能：

1. **Akshare API** - 测试个股新闻和沪深300新闻
2. **Playwright** - 测试浏览器驱动是否正常
3. **Google 搜索** - 测试搜索功能
4. **完整新闻爬虫** - 测试端到端的新闻获取流程

**运行方式：**
```bash
poetry run python test_news_apis.py
```

**预期输出：**
```
============================================================
测试总结
============================================================
akshare        : ✓ 通过
playwright     : ✓ 通过
google_search  : ✓ 通过
news_crawler   : ✓ 通过

✓ 所有测试通过！
```

## ⚠️ 可能遇到的问题

### 问题 1: Playwright 安装失败

**解决方法：**
```bash
# 使用系统 Python 安装
pip install playwright
playwright install chromium

# 或者使用 Poetry
poetry add playwright
poetry run playwright install chromium
```

### 问题 2: Akshare API 持续失败

**可能原因：**
- API 服务器暂时不可用
- 网络连接问题
- IP 被限流

**解决方法：**
1. 等待几分钟后重试
2. 检查网络连接
3. 使用 Google 搜索作为备选（需要先修复 Playwright）

### 问题 3: Google 搜索被封锁

**解决方法：**
1. 配置代理
2. 依赖 Akshare 作为主要数据源

## 📝 验证修复是否成功

修复完成后，重新运行分析并检查报告：

```bash
poetry run python src/main.py --ticker 600353
```

**检查报告中的以下部分：**

✅ **情绪分析应该显示：**
```
## 情绪分析 (权重10%):
   信号: [bullish/bearish/neutral]
   置信度: XX%
   分析: Based on N recent news articles, sentiment score: X.XX
```
其中 N 应该 > 0

✅ **宏观分析应该显示：**
```
## 宏观分析 (综合权重15%):
   a) 常规宏观分析 (来自 Macro Analyst Agent):
      ...
      关键因素: [列出具体因素]
```

✅ **大盘宏观新闻分析应该显示：**
```
   b) 大盘宏观新闻分析 (来自 Macro News Agent):
      信号: [具体信号]
      置信度: XX%
      摘要或结论: [具体分析内容，不是错误信息]
```

## 📞 需要帮助？

如果按照本指南操作后问题仍未解决，请提供以下信息：

1. `test_news_apis.py` 的完整输出
2. 运行 `poetry run python src/main.py --ticker 600353` 的终端输出
3. 错误日志（如果有）

## 📅 维护建议

为了避免将来出现类似问题：

1. **定期清理缓存：**
   ```bash
   # 每周清理一次缓存
   rm -rf src/data/stock_news/*
   rm -f src/data/*_cache.json
   ```

2. **监控 API 状态：**
   - 定期运行 `test_news_apis.py` 检查 API 健康状况

3. **更新依赖：**
   ```bash
   poetry update akshare playwright
   ```

4. **添加监控告警：**
   - 当新闻获取失败时，应该发送通知
   - 可以考虑添加 Slack/Email 告警

---

**最后更新：** 2025-12-10  
**文档版本：** 1.0
