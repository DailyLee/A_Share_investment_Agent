#!/bin/bash
# 修复新闻获取相关问题的脚本

echo "========================================"
echo "新闻功能修复脚本"
echo "========================================"
echo ""

# 检查是否在正确的目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

echo "步骤 1: 安装 Playwright 浏览器驱动..."
echo "----------------------------------------"
playwright install chromium
if [ $? -eq 0 ]; then
    echo "✅ Playwright 浏览器驱动安装成功"
else
    echo "⚠️  Playwright 安装可能失败，请手动运行: playwright install chromium"
fi
echo ""

echo "步骤 2: 清除错误的缓存文件..."
echo "----------------------------------------"
# 清除宏观新闻缓存
if [ -f "src/data/macro_summary.json" ]; then
    echo "删除: src/data/macro_summary.json"
    rm -f src/data/macro_summary.json
    echo "✅ 宏观新闻缓存已清除"
else
    echo "ℹ️  宏观新闻缓存不存在，跳过"
fi

# 清除股票新闻缓存
if [ -d "src/data/stock_news" ]; then
    echo "删除: src/data/stock_news/*"
    rm -rf src/data/stock_news/*
    echo "✅ 股票新闻缓存已清除"
else
    echo "ℹ️  股票新闻缓存目录不存在，跳过"
fi

# 清除情感分析缓存
if [ -f "src/data/sentiment_cache.json" ]; then
    echo "删除: src/data/sentiment_cache.json"
    rm -f src/data/sentiment_cache.json
    echo "✅ 情感分析缓存已清除"
else
    echo "ℹ️  情感分析缓存不存在，跳过"
fi

# 清除宏观分析缓存
if [ -f "src/data/macro_analysis_cache.json" ]; then
    echo "删除: src/data/macro_analysis_cache.json"
    rm -f src/data/macro_analysis_cache.json
    echo "✅ 宏观分析缓存已清除"
else
    echo "ℹ️  宏观分析缓存不存在，跳过"
fi
echo ""

echo "步骤 3: 测试新闻API功能..."
echo "----------------------------------------"
echo "运行测试脚本..."
poetry run python test_news_apis.py
TEST_RESULT=$?
echo ""

if [ $TEST_RESULT -eq 0 ]; then
    echo "========================================"
    echo "✅ 修复完成！所有测试通过"
    echo "========================================"
    echo ""
    echo "现在可以重新运行分析："
    echo "  poetry run python src/main.py --ticker 600353"
else
    echo "========================================"
    echo "⚠️  修复完成，但部分测试未通过"
    echo "========================================"
    echo ""
    echo "请查看上面的测试结果，根据建议进行进一步操作"
    echo ""
    echo "如果问题仍然存在，可能是因为："
    echo "  1. Akshare API 暂时不可用（稍后重试）"
    echo "  2. 网络连接问题"
    echo "  3. Google 搜索被封锁（需要使用代理）"
fi
echo ""
