# 新估值模型使用指南

## 快速开始

### 1. 测试单个股票

```bash
python3 test_new_valuation.py 600000 银行
```

参数说明：
- 第一个参数：股票代码（如 600000）
- 第二个参数：行业名称（如 银行、食品饮料、计算机等）

### 2. 在系统中启用新估值模型

有两种方式启用新的估值模型：

#### 方式1：直接替换（推荐用于新系统）

在 `src/agents/workflow.py` 或相关文件中：

```python
# 旧代码
from src.agents.valuation import valuation_agent

# 新代码
from src.agents.valuation_v2 import valuation_agent_v2 as valuation_agent
```

#### 方式2：作为新的节点添加（推荐用于现有系统）

保留原有的估值代理，新增一个估值V2节点：

```python
from src.agents.valuation import valuation_agent
from src.agents.valuation_v2 import valuation_agent_v2

# 在workflow中添加新节点
workflow.add_node("valuation_v2", valuation_agent_v2)
```

## 新功能特性

### 1. 三阶段DCF模型

**阶段1 - 高增长期（5年）**
- 基于历史数据估算的高增长率
- 适用于企业快速发展阶段

**阶段2 - 过渡期（5年）**
- 增长率逐年递减
- 从高增长平滑过渡到稳定增长

**阶段3 - 永续期**
- 使用稳定的永续增长率（约3%）
- 反映企业长期稳定发展

### 2. 改进的所有者收益法

**所有者收益公式**：
```
所有者收益 = 净利润 + 折旧摊销 - 维持性资本支出 - 营运资金增加
```

**关键改进**：
- 更准确的维持性资本支出估算（基于历史数据和行业标准）
- 区分维持性支出和扩张性支出
- 应用安全边际原则

### 3. WACC计算

自动计算加权平均资本成本：
- 使用CAPM模型计算权益成本
- 考虑债务税盾效应
- 根据行业设置Beta系数

### 4. 行业特定参数

系统自动识别股票所属行业，并应用相应的参数：
- Beta系数
- 要求回报率
- 安全边际
- 维持性资本支出比率

## 输出示例

```json
{
  "signal": "bullish",
  "confidence": "15%",
  "reasoning": {
    "industry_info": {
      "industry_name": "银行",
      "industry_classification": "金融行业（银行/证券/保险）",
      "industry_beta": 0.8,
      "params_applied": {
        "wacc": "10.00%",
        "high_growth_rate": "5.00%",
        "terminal_growth_rate": "3.00%",
        "required_return": "11.00%",
        "margin_of_safety": "20%"
      }
    },
    "dcf_analysis": {
      "signal": "neutral",
      "details": "DCF估值: ¥4500.00亿, 市值: ¥4000.00亿, 差距: 12.5%",
      "stage_breakdown": {
        "stage1": "¥1500.00亿",
        "stage2": "¥1200.00亿",
        "stage3": "¥2800.00亿"
      }
    },
    "owner_earnings_analysis": {
      "signal": "bullish",
      "details": "所有者收益法估值: ¥4426.86亿, 市值: ¥4000.00亿, 差距: 10.7%",
      "owner_earnings": "¥391.71亿",
      "maintenance_capex_ratio": "40.0%",
      "stage_breakdown": {
        "stage1": "¥1662.93亿",
        "stage2": "¥1204.23亿",
        "stage3": "¥2666.42亿"
      }
    }
  }
}
```

## 与旧模型的对比

| 特性 | 旧模型 | 新模型 |
|------|--------|--------|
| 增长模型 | 单阶段或简单递减 | 三阶段（高增长-过渡-永续） |
| 折现率 | 固定值 | WACC（基于CAPM） |
| 数据来源 | Akshare（有限） | Baostock（详细8期数据） |
| 维持性资本支出 | 简单比例 | 基于历史数据和行业标准 |
| 增长率估算 | 单一指标 | 多维度（FCF、营收、EBIT） |
| 行业适配 | 基本参数 | 详细的行业参数（Beta等） |
| 安全边际 | 固定 | 根据行业风险调整 |

## 适用场景

### 适合使用新模型的情况：

✅ 成熟上市公司（有充足历史数据）
✅ 现金流相对稳定的企业
✅ 需要详细估值分析的场景
✅ 需要分阶段预测的情况

### 不太适合的情况：

❌ 初创企业（历史数据不足）
❌ 处于重大转型期的企业
❌ 财务数据不完整的企业
❌ 金融行业（银行/保险）的DCF（但所有者收益法仍适用）

## 常见问题

### Q1: 为什么银行的FCF为0？
A: 金融机构（银行、保险）的自由现金流概念不太适用，因为其业务模式与实体企业不同。建议使用所有者收益法或股利折现模型（DDM）。

### Q2: 如何调整行业参数？
A: 编辑 `src/config/industry_valuation_params.py` 文件，修改相应行业的参数。

### Q3: 估值结果偏差较大怎么办？
A: 
1. 检查财务数据质量
2. 验证行业分类是否正确
3. 考虑使用敏感性分析
4. 结合其他估值方法（如相对估值法）

### Q4: 新模型运行较慢怎么办？
A: 新模型需要获取更多财务数据，首次运行会较慢。可以：
1. 实现数据缓存机制
2. 只在需要详细分析时使用新模型
3. 对于快速扫描，继续使用旧模型

### Q5: 如何回退到旧模型？
A: 新模型包含自动回退机制。如果Baostock数据不可用，会自动使用旧的估值方法。也可以直接使用 `valuation_agent` 而不是 `valuation_agent_v2`。

## 最佳实践

1. **数据验证**: 使用前先验证财务数据的完整性和准确性
2. **行业分类**: 确保行业分类正确，这会影响参数选择
3. **结合使用**: 将DCF和所有者收益法结合使用，互相验证
4. **敏感性分析**: 考虑不同增长率和折现率的影响
5. **定期更新**: 随着新财报发布，定期更新估值
6. **多方法验证**: 结合相对估值法（PE、PB等）进行交叉验证

## 进一步学习

推荐阅读：
1. "Investment Valuation" by Aswath Damodaran
2. "Valuation" by McKinsey & Company
3. Warren Buffett's Berkshire Hathaway Letters to Shareholders
4. "Security Analysis" by Benjamin Graham

在线资源：
- Damodaran Online (http://pages.stern.nyu.edu/~adamodar/)
- CFA Institute 估值资源
- Baostock API文档 (http://baostock.com)

## 技术支持

如遇到问题，请检查：
1. 日志文件中的详细错误信息
2. Baostock登录状态
3. 网络连接
4. Python依赖包版本

## 更新日志

**v2.0 (2025-12-10)**
- ✨ 新增三阶段DCF模型
- ✨ 改进的所有者收益法
- ✨ 集成Baostock详细财务数据
- ✨ WACC自动计算
- ✨ 行业特定参数
- 🐛 修复维持性资本支出估算问题
- 📝 完善文档和测试

**v1.0 (之前)**
- 基础DCF模型
- 基础所有者收益法
- 使用Akshare数据
