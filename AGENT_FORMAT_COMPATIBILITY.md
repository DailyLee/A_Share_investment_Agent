# Agent 数据格式兼容性检查报告

## 发现的问题

### 1. Confidence 字段格式不一致

| Agent | Confidence 格式 | 示例 | 问题 |
|-------|----------------|------|------|
| `fundamentals_agent` | 字符串百分比 | `"75%"` | 需要解析 |
| `technical_analyst_agent` | 字符串百分比 | `"23%"` | 需要解析 |
| `valuation_agent` | 字符串百分比 | `"10%"` | 需要解析 |
| `sentiment_agent` | 数字 (0-1) | `0.7` | 格式正确 |
| `risk_management_agent` | 无 confidence 字段 | N/A | 使用 risk_score 代替 |

**修复方案**: 已添加 `normalize_confidence()` 函数统一处理所有格式。

### 2. Agent Name 字段不一致

| Agent | 返回格式 | 问题 |
|-------|---------|------|
| LLM 返回的 `agent_signals` | `{"agent": "technical_analysis", ...}` | 使用 `"agent"` 键 |
| 代码期望格式 | `{"agent_name": "technical_analysis", ...}` | 使用 `"agent_name"` 键 |

**修复方案**: 已添加标准化逻辑，自动将 `"agent"` 转换为 `"agent_name"`。

### 3. Message Content 格式不一致

| Agent | Content 格式 | 问题 |
|-------|-------------|------|
| `macro_news_agent` | 纯文本 | 不是 JSON 格式 |
| 其他 agents | JSON 字符串 | 格式正确 |

**修复方案**: 已添加 `parse_agent_message_content()` 函数处理 JSON 和非 JSON 格式。

### 4. Signal 字段命名不一致

| Agent | Signal 字段 | 问题 |
|-------|------------|------|
| `risk_management_agent` | `"trading_action"` | 不是 `"signal"` |
| 其他 agents | `"signal"` | 格式正确 |

**修复方案**: 在解析时统一处理，将 `"trading_action"` 映射为 `"signal"`。

## 已实现的修复

### 1. `parse_agent_message_content()` 函数
- 统一解析所有 agent 的消息内容
- 支持 JSON 字符串和纯文本格式
- 自动处理解析错误

### 2. `normalize_confidence()` 函数
- 统一处理所有 confidence 格式：
  - 字符串百分比: `"75%"` → `0.75`
  - 字符串数字: `"0.75"` → `0.75`
  - 数字 (0-1): `0.75` → `0.75`
  - 数字 (>1): `75` → `0.75` (假设是百分比)

### 3. Agent Signals 标准化
- 自动将 `"agent"` 键转换为 `"agent_name"` 键
- 支持两种格式同时存在
- 过滤无效信号

### 4. 统一的数据提取
- 所有 agent 消息都通过 `parse_agent_message_content()` 解析
- 标准化后的数据用于 LLM prompt
- 保留原始数据用于后续处理

## 建议的改进

### 1. 统一所有 Agent 的输出格式

建议所有 agent 都返回以下标准格式：

```json
{
  "agent_name": "agent_name",
  "signal": "bullish|bearish|neutral",
  "confidence": 0.75,  // 0-1 之间的浮点数
  "reasoning": "...",
  "details": {...}  // 可选，包含详细信息
}
```

### 2. 更新各个 Agent

需要更新的 agents:
- [ ] `fundamentals_agent`: 将 confidence 改为数字格式
- [ ] `technical_analyst_agent`: 将 confidence 改为数字格式
- [ ] `valuation_agent`: 将 confidence 改为数字格式
- [ ] `macro_news_agent`: 改为返回 JSON 格式
- [ ] `risk_management_agent`: 添加 `signal` 字段（或统一使用 `trading_action`）

### 3. 添加格式验证

建议添加格式验证函数，在 agent 返回消息时验证格式是否正确。

## 当前状态

✅ 已修复的问题:
- Confidence 格式不一致
- Agent name 字段不一致
- Message content 格式不一致
- Signal 字段命名不一致

⚠️ 待改进:
- 统一所有 agent 的输出格式（向后兼容）
- 添加格式验证
- 更新文档说明各 agent 的输出格式

