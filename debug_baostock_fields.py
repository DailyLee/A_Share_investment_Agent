#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试Baostock返回的字段名
"""

import baostock as bs
import pandas as pd

# 登录
lg = bs.login()
print(f"登录结果: {lg.error_msg}")

# 测试股票
symbol = "sh.600519"
year = 2025
quarter = 3

print(f"\n测试股票: {symbol}, {year}Q{quarter}\n")

# 1. 利润表
print("="*60)
print("利润表字段")
print("="*60)
rs_profit = bs.query_profit_data(code=symbol, year=year, quarter=quarter)
if rs_profit.error_code == '0':
    profit_list = []
    while (rs_profit.error_code == '0') & rs_profit.next():
        profit_list.append(rs_profit.get_row_data())
    if profit_list:
        profit_df = pd.DataFrame(profit_list, columns=rs_profit.fields)
        print(f"字段列表: {list(profit_df.columns)}")
        print(f"\n前几列数据:")
        print(profit_df.iloc[0])

# 2. 资产负债表
print("\n" + "="*60)
print("资产负债表字段")
print("="*60)
rs_balance = bs.query_balance_data(code=symbol, year=year, quarter=quarter)
if rs_balance.error_code == '0':
    balance_list = []
    while (rs_balance.error_code == '0') & rs_balance.next():
        balance_list.append(rs_balance.get_row_data())
    if balance_list:
        balance_df = pd.DataFrame(balance_list, columns=rs_balance.fields)
        print(f"字段列表: {list(balance_df.columns)}")
        print(f"\n前几列数据:")
        print(balance_df.iloc[0])

# 3. 现金流量表
print("\n" + "="*60)
print("现金流量表字段")
print("="*60)
rs_cash = bs.query_cash_flow_data(code=symbol, year=year, quarter=quarter)
if rs_cash.error_code == '0':
    cash_list = []
    while (rs_cash.error_code == '0') & rs_cash.next():
        cash_list.append(rs_cash.get_row_data())
    if cash_list:
        cash_df = pd.DataFrame(cash_list, columns=rs_cash.fields)
        print(f"字段列表: {list(cash_df.columns)}")
        print(f"\n前几列数据:")
        print(cash_df.iloc[0])

# 登出
bs.logout()
print("\n完成！")
