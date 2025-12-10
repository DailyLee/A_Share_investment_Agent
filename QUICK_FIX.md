# 🚀 新闻功能快速修复

## 问题症状
- ✗ 情绪分析显示：`Based on 0 recent news articles`
- ✗ 宏观分析显示：`关键因素: ` (空)
- ✗ 大盘新闻显示：`Expecting value: line 1 column 1 (char 0)`

## 一键修复

```bash
./fix_news_issues.sh
```

## 手动修复（3步）

```bash
# 1. 安装浏览器驱动
playwright install chromium

# 2. 清除错误缓存
rm -f src/data/macro_summary.json src/data/*_cache.json
rm -rf src/data/stock_news/*

# 3. 测试验证
poetry run python test_news_apis.py
```

## 验证修复

```bash
# 重新运行分析
poetry run python src/main.py --ticker 600353

# 检查报告中新闻数量应该 > 0
cat reports/600353_*.md | grep "Based on"
```

## 详细说明

查看 [NEWS_FIX_GUIDE.md](NEWS_FIX_GUIDE.md) 了解完整的问题分析和解决方案。
