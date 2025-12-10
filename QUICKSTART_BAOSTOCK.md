# Baostock 集成 - 快速开始

## 🎯 解决的问题

如果你看到这样的错误信息：
- ❌ "Unable to calculate - market cap data unavailable"
- ❌ "P/E: N/A, P/B: N/A, P/S: N/A"
- ❌ 估值分析置信度为 0%

**好消息！** 这些问题现在已经通过 Baostock API 集成解决了！

## 🚀 快速开始

### 步骤 1: 安装依赖

```bash
cd /Users/li.dai/A_Share_investment_Agent
poetry install
```

### 步骤 2: 运行分析（无需修改代码）

```bash
# 运行分析（系统会自动使用 Baostock 作为备选）
poetry run python src/main.py --ticker 600353 --show-reasoning
```

就是这么简单！系统会自动处理 API 切换。

## ✨ 工作原理

```
┌─────────────────────────────────────────────────────┐
│  获取市值和估值数据                                 │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │  尝试 Akshare API       │
         └─────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
      成功 ▼                 失败 ▼
    ┌─────────┐         ┌──────────────────┐
    │ 使用数据 │         │ 自动切换到       │
    └─────────┘         │ Baostock API     │
                        └──────────────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                 成功 ▼                 失败 ▼
               ┌─────────┐         ┌─────────┐
               │ 使用数据 │         │ 使用默认值│
               └─────────┘         └─────────┘
```

## 📊 对比效果

### 修复前
```
## 估值分析 (权重35%):
   信号: 中性
   置信度: 0%
   要点:
   - DCF估值: Unable to calculate - market cap data unavailable
   - 所有者收益法: Unable to calculate - market cap data unavailable
```

### 修复后
```
## 估值分析 (权重35%):
   信号: 看多/看空/中性
   置信度: 25%+
   要点:
   - DCF估值: Intrinsic Value: $XXX, Market Cap: $YYY, Gap: ZZ%
   - 所有者收益法: Owner Earnings Value: $XXX, Market Cap: $YYY, Gap: ZZ%
```

## 🔍 验证集成是否工作

查看日志文件 `logs/api.log`，你应该看到：

```
✓ Market data fetched from Baostock: market_cap=XXXX亿元
✓ Using Baostock data as fallback
```

## 💡 常见问题

### Q1: 需要配置什么吗？
**A**: 不需要！Baostock 完全免费，无需 API Key 或注册。

### Q2: 会影响现有代码吗？
**A**: 不会！这是一个**透明的备选方案**，现有代码无需修改。

### Q3: 数据准确吗？
**A**: Baostock 数据来自官方交易所，准确可靠。

### Q4: 如何知道使用了哪个数据源？
**A**: 查看日志，会显示"from Akshare"或"from Baostock"。

### Q5: Baostock 会比 Akshare 慢吗？
**A**: 只在 Akshare 失败时才会调用 Baostock，正常情况下不影响速度。

## 📝 示例输出

运行分析后，你会看到：

```bash
2025-12-10 15:02:08 - api - INFO - Fetching real-time quotes...
2025-12-10 15:02:08 - api - WARNING - Failed to fetch real-time quotes from Akshare
2025-12-10 15:02:08 - api - INFO - Trying Baostock as fallback...
2025-12-10 15:02:09 - api - INFO - ✓ Market data fetched from Baostock: market_cap=1652.24亿元
```

报告中将显示：

```markdown
## 估值分析 (权重35%):
   信号: 看多
   置信度: 35%
   要点:
   - DCF估值: Intrinsic Value: $1,800亿, Market Cap: $1,652亿, Gap: 9%
   - 所有者收益法: Owner Earnings Value: $1,750亿, Market Cap: $1,652亿, Gap: 6%
```

## 🎉 就是这样！

现在你的投资分析系统更加可靠了。即使某个 API 不可用，系统也能继续工作。

---

**需要帮助？** 查看 `BAOSTOCK_INTEGRATION.md` 了解更多技术细节。

**遇到问题？** 检查 `logs/api.log` 文件查看详细的错误信息。

