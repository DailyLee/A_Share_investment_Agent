# Baostock API 集成说明

## 概述

为了解决某些数据API被限制的问题，我们已将 **Baostock API** 集成到项目中作为备选数据源。当主要的 Akshare API 调用失败或返回无效数据时，系统会自动切换到 Baostock API。

## 主要改进

### 1. 新增的数据源
- **Baostock**: 一个免费、开源的证券数据平台，专门针对中国A股市场

### 2. 修改的文件

#### `src/tools/api.py`
- 添加了 `baostock` 库导入
- 添加了 Baostock 登录/登出管理函数
- 添加了 `convert_stock_code_to_baostock()` - 股票代码格式转换函数
- 添加了 `get_market_data_from_baostock()` - 从 Baostock 获取市场数据
- 更新了 `get_financial_metrics()` - 添加 Baostock 作为备选数据源
- 更新了 `get_market_data()` - 添加 Baostock 作为备选数据源

#### `pyproject.toml`
- 添加了 `baostock = "^0.8.9"` 依赖

## 数据获取逻辑

系统现在采用**双数据源策略**：

```
1. 尝试从 Akshare 获取数据
   ├─ 成功 → 使用 Akshare 数据
   └─ 失败或数据为0
      └─ 尝试从 Baostock 获取数据
         ├─ 成功 → 使用 Baostock 数据
         └─ 失败 → 使用默认值（0）
```

## 获取的数据项

### 通过 Baostock 获取的市场数据：
- **市值** (market_cap): 流通市值，单位：亿元
- **市盈率** (pe_ratio): 滚动市盈率 (TTM)
- **市净率** (price_to_book): 最近一季度市净率 (MRQ)
- **市销率** (price_to_sales): 滚动市销率 (TTM)
- **换手率** (turnover)
- **52周最高价** (fifty_two_week_high)
- **52周最低价** (fifty_two_week_low)
- **成交量** (volume)

## 安装步骤

### 1. 安装依赖

使用 Poetry:
```bash
poetry install
```

或者使用 pip（如果你使用 requirements.txt）:
```bash
pip install baostock
```

### 2. 无需额外配置

Baostock 不需要 API Key 或账号注册，可以直接使用。系统会在需要时自动登录。

## 使用示例

不需要修改任何调用代码，系统会自动使用备选数据源：

```python
from src.tools.api import get_financial_metrics, get_market_data

# 获取财务指标（自动使用 Baostock 作为备选）
metrics = get_financial_metrics("600353")

# 获取市场数据（自动使用 Baostock 作为备选）
market_data = get_market_data("600353")
```

## 日志输出

系统会在日志中清楚地标注数据来源：

```
✓ Real-time quotes fetched from Akshare
```

或

```
Failed to fetch real-time quotes from Akshare: ...
Trying Baostock as fallback...
✓ Market data fetched from Baostock: market_cap=XXX亿元
✓ Using Baostock data as fallback
```

## 注意事项

1. **股票代码格式**: Baostock 使用格式 `sh.600353`（上海）或 `sz.000001`（深圳），系统会自动转换
2. **市值单位**: Baostock 返回的市值单位是**亿元**，与 Akshare 一致
3. **数据延迟**: Baostock 的数据可能有轻微延迟（通常是日级数据）
4. **自动登出**: Baostock 连接在程序运行期间保持，如需手动登出可调用 `baostock_logout()`

## 常见问题

### Q: 为什么估值分析显示 "Unable to calculate"？
A: 这通常是因为市值数据为0。现在系统会自动尝试从 Baostock 获取数据，应该能解决这个问题。

### Q: Baostock 数据准确吗？
A: Baostock 的数据来自官方交易所，是可靠的。但建议在实际交易前交叉验证数据。

### Q: 如何查看使用了哪个数据源？
A: 查看日志文件 `logs/api.log`，里面会显示数据来源。

## 技术细节

### Baostock API 调用示例

```python
import baostock as bs

# 登录
lg = bs.login()

# 查询历史K线数据
rs = bs.query_history_k_data_plus(
    "sh.600353",
    "date,close,peTTM,pbMRQ,psTTM",
    start_date='2024-01-01',
    end_date='2024-12-31',
    frequency="d",
    adjustflag="3"
)

# 查询股票基本信息
rs = bs.query_stock_basic(code="sh.600353")

# 登出
bs.logout()
```

## 更新日期

2025年12月10日

