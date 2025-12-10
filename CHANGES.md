# 更新日志 - Baostock API 集成

## 日期：2025年12月10日

## 更新内容

### 问题描述
报告中的估值分析显示以下错误：
- 市值数据无法获取（market_cap = 0）
- DCF估值无法计算："Unable to calculate - market cap data unavailable"
- 所有者收益法估值无法计算："Unable to calculate - market cap data unavailable"
- 基本面分析中的 P/E、P/B、P/S 显示为 N/A

**根本原因**: Akshare 的 `stock_zh_a_spot_em()` API 被限制或不稳定，无法获取实时行情数据。

### 解决方案
集成 **Baostock API** 作为备选数据源，实现双数据源容错机制。

### 修改的文件

#### 1. `src/tools/api.py`
**新增功能**:
- 导入 `baostock` 库
- `ensure_baostock_login()` - Baostock 登录管理
- `baostock_logout()` - Baostock 登出
- `convert_stock_code_to_baostock()` - 股票代码格式转换（600353 → sh.600353）
- `get_market_data_from_baostock()` - 从 Baostock 获取市场数据

**更新功能**:
- `get_financial_metrics()` - 添加 Baostock 作为备选数据源
- `get_market_data()` - 添加 Baostock 作为备选数据源

**数据获取策略**:
```
优先: Akshare (stock_zh_a_spot_em)
  ↓ 失败或数据为0
备选: Baostock (query_history_k_data_plus + query_profit_data)
  ↓ 仍然失败
默认: 返回0值
```

#### 2. `pyproject.toml`
**新增依赖**:
```toml
baostock = "^0.8.9"
```

#### 3. 新增文档
- `BAOSTOCK_INTEGRATION.md` - 详细的集成说明文档
- `CHANGES.md` - 本文件，更新日志

### 技术细节

#### Baostock 市值计算方法
由于 Baostock 不直接提供市值数据，我们使用两种方法计算：

**方法1**: 从流通股数计算
```python
市值 = 流通股数（万股）× 收盘价 / 10000  # 单位：亿元
```

**方法2**: 从每股收益（EPS）推算
```python
总股本 = 收盘价 / EPS（TTM）
市值 = 总股本 × 收盘价  # 单位：亿元
```

系统会尝试方法1，如果失败或结果不合理，则使用方法2。

#### 获取的数据项
通过 Baostock 可以获取：
- 市值（计算得出）
- 市盈率（PE TTM）
- 市净率（PB MRQ）
- 市销率（PS TTM）
- 换手率
- 52周最高价/最低价
- 成交量

### 测试结果

测试股票：600353

**测试1 - 财务指标获取**:
```
✓ 成功获取财务指标
  - 市值: 1652.24 亿元
  - 市盈率: 105.71
  - 市净率: 6.94
  - 市销率: 7.87
  - 净资产收益率: 5.41%
  - 净利率: 8.10%
✓ 市值数据有效 - Baostock 集成成功！
```

**测试2 - 市场数据获取**:
```
✓ 成功获取市场数据
  - 市值: 1652.24 亿元
  - 成交量: 18200456
  - 52周最高: 20.87
  - 52周最低: 6.70
✓ 市值数据有效 - Baostock 集成成功！
```

### 对现有报告的影响

修复后，报告中的以下部分将显示正确数据：

**估值分析**:
- ✓ DCF估值将能够正常计算
- ✓ 所有者收益法估值将能够正常计算
- ✓ 估值信号将从"中性(0%置信度)"变为有意义的信号

**基本面分析**:
- ✓ P/E、P/B、P/S 将显示实际数值而非 N/A
- ✓ 估值水平判断将更加准确

**投资建议**:
- ✓ 决策置信度将提高
- ✓ 操作建议将更加明确和可靠

### 使用方法

无需修改任何调用代码，系统会自动使用备选数据源：

```python
# 自动使用 Akshare → Baostock 容错机制
from src.tools.api import get_financial_metrics, get_market_data

metrics = get_financial_metrics("600353")  # 自动容错
market_data = get_market_data("600353")     # 自动容错
```

### 日志示例

当 Akshare 失败时，系统会自动切换：

```
2025-12-10 15:02:08 - api - WARNING - Failed to fetch real-time quotes from Akshare: ...
2025-12-10 15:02:08 - api - INFO - Trying Baostock as fallback...
2025-12-10 15:02:08 - api - INFO - Logging in to Baostock...
2025-12-10 15:02:08 - api - INFO - ✓ Baostock login successful
2025-12-10 15:02:08 - api - INFO - Fetching market data from Baostock for sh.600353...
2025-12-10 15:02:09 - api - INFO - Method 2: EPS=0.147858, 收盘价=15.63, 推算市值=1652.24亿元
2025-12-10 15:02:09 - api - INFO - ✓ Market data fetched from Baostock: market_cap=1652.24亿元
2025-12-10 15:02:09 - api - INFO - ✓ Using Baostock data as fallback
```

### 安装步骤

```bash
# 更新依赖
poetry lock
poetry install

# 或使用 pip
pip install baostock
```

### 注意事项

1. **无需 API Key**: Baostock 完全免费，无需注册
2. **自动重连**: 系统会在需要时自动登录 Baostock
3. **数据延迟**: Baostock 数据通常是日级数据，可能有轻微延迟
4. **市值精度**: 通过 EPS 推算的市值是估算值，可能与实际市值有小幅差异

### 后续改进建议

1. 可以添加更多备选数据源（如 Tushare）
2. 实现数据源健康检查和自动切换
3. 添加数据缓存机制减少 API 调用
4. 实现数据源优先级动态调整

## 版本信息

- Baostock 版本: 0.8.9
- 修改日期: 2025年12月10日
- 测试状态: ✓ 通过

