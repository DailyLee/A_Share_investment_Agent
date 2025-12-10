# -*- coding: utf-8 -*-
"""
使用Baostock获取更详细的财务数据
提供DCF和所有者收益法所需的所有财务指标
"""

import baostock as bs
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from src.utils.logging_config import setup_logger

logger = setup_logger('baostock_financial')

# Baostock 连接状态
_bs_logged_in = False


def ensure_baostock_login():
    """确保 Baostock 已登录"""
    global _bs_logged_in
    if not _bs_logged_in:
        logger.info("Logging in to Baostock...")
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"Baostock login failed: {lg.error_msg}")
            return False
        _bs_logged_in = True
        logger.info("✓ Baostock login successful")
    return True


def baostock_logout():
    """登出 Baostock"""
    global _bs_logged_in
    if _bs_logged_in:
        bs.logout()
        _bs_logged_in = False
        logger.info("✓ Baostock logged out")


def convert_stock_code_to_baostock(symbol: str) -> str:
    """将股票代码转换为 Baostock 格式"""
    if symbol.startswith('6'):
        return f'sh.{symbol}'
    elif symbol.startswith(('0', '3')):
        return f'sz.{symbol}'
    else:
        return f'sh.{symbol}'


def get_latest_quarter() -> Tuple[int, int]:
    """
    获取最新的可用季度
    
    Returns:
        Tuple[int, int]: (年份, 季度)
    """
    now = datetime.now()
    year = now.year
    month = now.month
    
    # 财报通常在下一季度的某个时间发布
    # 例如，Q1财报在4月底发布，Q2在7月底，Q3在10月底，Q4在次年3月底
    if month <= 4:
        # 1-4月，使用去年Q4
        return year - 1, 4
    elif month <= 7:
        # 5-7月，使用今年Q1
        return year, 1
    elif month <= 10:
        # 8-10月，使用今年Q2
        return year, 2
    else:
        # 11-12月，使用今年Q3
        return year, 3


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全地将值转换为浮点数"""
    try:
        if value is None or value == '' or value == 'None':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def get_comprehensive_financial_data(symbol: str, num_periods: int = 8) -> Dict[str, Any]:
    """
    获取全面的财务数据，包括利润表、资产负债表和现金流量表
    
    Args:
        symbol: 股票代码（不带前缀）
        num_periods: 获取的历史期数（默认8个季度，即2年）
    
    Returns:
        Dict包含所有财务数据
    """
    if not ensure_baostock_login():
        logger.error("Failed to login to Baostock")
        return {}
    
    bs_code = convert_stock_code_to_baostock(symbol)
    year, quarter = get_latest_quarter()
    
    logger.info(f"Fetching comprehensive financial data for {bs_code}")
    logger.info(f"Latest quarter: {year}Q{quarter}")
    
    # 存储多期数据
    all_data = {
        'profit': [],
        'balance': [],
        'cash_flow': [],
        'periods': []
    }
    
    # 获取历史多期数据
    for i in range(num_periods):
        current_year = year
        current_quarter = quarter - i
        
        # 处理季度跨年
        while current_quarter <= 0:
            current_quarter += 4
            current_year -= 1
        
        period_label = f"{current_year}Q{current_quarter}"
        all_data['periods'].append(period_label)
        
        # 获取利润表数据
        try:
            rs_profit = bs.query_profit_data(code=bs_code, year=current_year, quarter=current_quarter)
            if rs_profit.error_code == '0':
                profit_list = []
                while (rs_profit.error_code == '0') & rs_profit.next():
                    profit_list.append(rs_profit.get_row_data())
                if profit_list:
                    profit_df = pd.DataFrame(profit_list, columns=rs_profit.fields)
                    all_data['profit'].append(profit_df)
                    logger.info(f"✓ Profit data fetched for {period_label}")
                else:
                    all_data['profit'].append(pd.DataFrame())
                    logger.warning(f"No profit data for {period_label}")
            else:
                all_data['profit'].append(pd.DataFrame())
                logger.warning(f"Failed to fetch profit data for {period_label}: {rs_profit.error_msg}")
        except Exception as e:
            logger.error(f"Error fetching profit data for {period_label}: {e}")
            all_data['profit'].append(pd.DataFrame())
        
        # 获取资产负债表数据
        try:
            rs_balance = bs.query_balance_data(code=bs_code, year=current_year, quarter=current_quarter)
            if rs_balance.error_code == '0':
                balance_list = []
                while (rs_balance.error_code == '0') & rs_balance.next():
                    balance_list.append(rs_balance.get_row_data())
                if balance_list:
                    balance_df = pd.DataFrame(balance_list, columns=rs_balance.fields)
                    all_data['balance'].append(balance_df)
                    logger.info(f"✓ Balance data fetched for {period_label}")
                else:
                    all_data['balance'].append(pd.DataFrame())
                    logger.warning(f"No balance data for {period_label}")
            else:
                all_data['balance'].append(pd.DataFrame())
                logger.warning(f"Failed to fetch balance data for {period_label}: {rs_balance.error_msg}")
        except Exception as e:
            logger.error(f"Error fetching balance data for {period_label}: {e}")
            all_data['balance'].append(pd.DataFrame())
        
        # 获取现金流量表数据
        try:
            rs_cash = bs.query_cash_flow_data(code=bs_code, year=current_year, quarter=current_quarter)
            if rs_cash.error_code == '0':
                cash_list = []
                while (rs_cash.error_code == '0') & rs_cash.next():
                    cash_list.append(rs_cash.get_row_data())
                if cash_list:
                    cash_df = pd.DataFrame(cash_list, columns=rs_cash.fields)
                    all_data['cash_flow'].append(cash_df)
                    logger.info(f"✓ Cash flow data fetched for {period_label}")
                else:
                    all_data['cash_flow'].append(pd.DataFrame())
                    logger.warning(f"No cash flow data for {period_label}")
            else:
                all_data['cash_flow'].append(pd.DataFrame())
                logger.warning(f"Failed to fetch cash flow data for {period_label}: {rs_cash.error_msg}")
        except Exception as e:
            logger.error(f"Error fetching cash flow data for {period_label}: {e}")
            all_data['cash_flow'].append(pd.DataFrame())
    
    return all_data


def extract_dcf_inputs(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从财务数据中提取DCF模型所需的输入
    
    Returns:
        Dict包含DCF所需的所有输入数据：
        - fcf_history: 历史自由现金流（列表）
        - revenue_history: 历史营收（列表）
        - nopat_history: 税后经营利润历史（列表）
        - capex_history: 资本支出历史（列表）
        - depreciation_history: 折旧摊销历史（列表）
        - working_capital_history: 营运资金历史（列表）
        - total_debt: 总债务
        - cash_and_equivalents: 现金及现金等价物
        - total_equity: 股东权益
        - tax_rate: 有效税率
        - shares_outstanding: 总股本
    """
    if not financial_data or not financial_data.get('periods'):
        logger.warning("No financial data available for DCF analysis")
        return {}
    
    result = {
        'fcf_history': [],
        'revenue_history': [],
        'ebit_history': [],
        'nopat_history': [],
        'capex_history': [],
        'depreciation_history': [],
        'working_capital_history': [],
        'net_income_history': [],
        'operating_cash_flow_history': [],
        'periods': financial_data['periods']
    }
    
    # 提取每期数据
    for i, period in enumerate(financial_data['periods']):
        profit_df = financial_data['profit'][i] if i < len(financial_data['profit']) else pd.DataFrame()
        balance_df = financial_data['balance'][i] if i < len(financial_data['balance']) else pd.DataFrame()
        cash_df = financial_data['cash_flow'][i] if i < len(financial_data['cash_flow']) else pd.DataFrame()
        
        # 从利润表提取
        if not profit_df.empty:
            row = profit_df.iloc[0]
            
            # 营业收入（TTM累计）
            revenue = safe_float(row.get('revenue', 0))
            result['revenue_history'].append(revenue)
            
            # EBIT（营业利润）
            ebit = safe_float(row.get('operatingProfit', 0))
            result['ebit_history'].append(ebit)
            
            # 净利润
            net_income = safe_float(row.get('netProfit', 0))
            result['net_income_history'].append(net_income)
            
            # 税率
            total_profit = safe_float(row.get('totalProfit', 0))
            income_tax = safe_float(row.get('incomeTax', 0))
            tax_rate = income_tax / total_profit if total_profit != 0 else 0.25
            
            # NOPAT = EBIT * (1 - tax_rate)
            nopat = ebit * (1 - tax_rate)
            result['nopat_history'].append(nopat)
        else:
            result['revenue_history'].append(0)
            result['ebit_history'].append(0)
            result['net_income_history'].append(0)
            result['nopat_history'].append(0)
        
        # 从现金流量表提取
        if not cash_df.empty:
            row = cash_df.iloc[0]
            
            # 折旧摊销
            depreciation = safe_float(row.get('CADepreciation', 0))
            result['depreciation_history'].append(depreciation)
            
            # 资本支出（购建固定资产、无形资产和其他长期资产支付的现金）
            capex = safe_float(row.get('IApayOther', 0))
            result['capex_history'].append(abs(capex))  # 通常为负值，取绝对值
            
            # 经营活动现金流
            operating_cf = safe_float(row.get('CAToOperations', 0))
            result['operating_cash_flow_history'].append(operating_cf)
        else:
            result['depreciation_history'].append(0)
            result['capex_history'].append(0)
            result['operating_cash_flow_history'].append(0)
        
        # 从资产负债表提取
        if not balance_df.empty:
            row = balance_df.iloc[0]
            
            # 营运资金 = 流动资产 - 流动负债
            current_assets = safe_float(row.get('totalCurrentAssets', 0))
            current_liabilities = safe_float(row.get('totalCurrentLiab', 0))
            working_capital = current_assets - current_liabilities
            result['working_capital_history'].append(working_capital)
            
            # 只在最新期提取以下数据
            if i == 0:
                # 总债务
                short_term_debt = safe_float(row.get('shortTermLoan', 0))
                long_term_debt = safe_float(row.get('longTermLoan', 0))
                bonds_payable = safe_float(row.get('bond', 0))
                result['total_debt'] = short_term_debt + long_term_debt + bonds_payable
                
                # 现金及现金等价物
                result['cash_and_equivalents'] = safe_float(row.get('moneyFunds', 0))
                
                # 股东权益
                result['total_equity'] = safe_float(row.get('totalSHEquity', 0))
                
                # 总股本
                result['shares_outstanding'] = safe_float(row.get('totalShare', 0))
        else:
            result['working_capital_history'].append(0)
    
    # 计算历史自由现金流
    # FCF = NOPAT + 折旧摊销 - 资本支出 - 营运资金变化
    for i in range(len(result['nopat_history'])):
        nopat = result['nopat_history'][i]
        depreciation = result['depreciation_history'][i]
        capex = result['capex_history'][i]
        
        # 计算营运资金变化
        if i < len(result['working_capital_history']) - 1:
            wc_change = result['working_capital_history'][i] - result['working_capital_history'][i + 1]
        else:
            wc_change = 0
        
        fcf = nopat + depreciation - capex - wc_change
        result['fcf_history'].append(fcf)
    
    # 设置默认值
    if 'total_debt' not in result:
        result['total_debt'] = 0
    if 'cash_and_equivalents' not in result:
        result['cash_and_equivalents'] = 0
    if 'total_equity' not in result:
        result['total_equity'] = 0
    if 'shares_outstanding' not in result:
        result['shares_outstanding'] = 0
    
    # 计算平均税率
    if result['ebit_history'] and result['nopat_history']:
        valid_tax_rates = []
        for ebit, nopat in zip(result['ebit_history'], result['nopat_history']):
            if ebit > 0:
                tax_rate = 1 - (nopat / ebit)
                if 0 <= tax_rate <= 0.5:  # 合理的税率范围
                    valid_tax_rates.append(tax_rate)
        result['tax_rate'] = sum(valid_tax_rates) / len(valid_tax_rates) if valid_tax_rates else 0.25
    else:
        result['tax_rate'] = 0.25  # 默认税率25%
    
    logger.info(f"✓ Extracted DCF inputs for {len(result['periods'])} periods")
    logger.info(f"Latest FCF: ¥{result['fcf_history'][0]/100000000:.2f}亿" if result['fcf_history'] else "No FCF data")
    
    return result


def extract_owner_earnings_inputs(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从财务数据中提取所有者收益法所需的输入
    
    Returns:
        Dict包含所有者收益法所需的输入：
        - net_income_history: 净利润历史
        - depreciation_history: 折旧摊销历史
        - capex_history: 资本支出历史
        - working_capital_change_history: 营运资金变化历史
        - maintenance_capex_ratio: 维持性资本支出比率（估算）
    """
    if not financial_data or not financial_data.get('periods'):
        logger.warning("No financial data available for Owner Earnings analysis")
        return {}
    
    result = {
        'net_income_history': [],
        'depreciation_history': [],
        'capex_history': [],
        'working_capital_history': [],
        'working_capital_change_history': [],
        'revenue_history': [],
        'periods': financial_data['periods']
    }
    
    # 提取每期数据
    for i, period in enumerate(financial_data['periods']):
        profit_df = financial_data['profit'][i] if i < len(financial_data['profit']) else pd.DataFrame()
        balance_df = financial_data['balance'][i] if i < len(financial_data['balance']) else pd.DataFrame()
        cash_df = financial_data['cash_flow'][i] if i < len(financial_data['cash_flow']) else pd.DataFrame()
        
        # 净利润
        if not profit_df.empty:
            net_income = safe_float(profit_df.iloc[0].get('netProfit', 0))
            revenue = safe_float(profit_df.iloc[0].get('revenue', 0))
            result['net_income_history'].append(net_income)
            result['revenue_history'].append(revenue)
        else:
            result['net_income_history'].append(0)
            result['revenue_history'].append(0)
        
        # 折旧摊销和资本支出
        if not cash_df.empty:
            row = cash_df.iloc[0]
            depreciation = safe_float(row.get('CADepreciation', 0))
            capex = safe_float(row.get('IApayOther', 0))
            result['depreciation_history'].append(depreciation)
            result['capex_history'].append(abs(capex))
        else:
            result['depreciation_history'].append(0)
            result['capex_history'].append(0)
        
        # 营运资金
        if not balance_df.empty:
            row = balance_df.iloc[0]
            current_assets = safe_float(row.get('totalCurrentAssets', 0))
            current_liabilities = safe_float(row.get('totalCurrentLiab', 0))
            working_capital = current_assets - current_liabilities
            result['working_capital_history'].append(working_capital)
        else:
            result['working_capital_history'].append(0)
    
    # 计算营运资金变化
    for i in range(len(result['working_capital_history']) - 1):
        wc_change = result['working_capital_history'][i] - result['working_capital_history'][i + 1]
        result['working_capital_change_history'].append(wc_change)
    
    # 估算维持性资本支出比率
    # 维持性资本支出 ≈ 折旧摊销（用于维持现有产能）
    # 计算历史平均的 折旧/资本支出 比率
    valid_ratios = []
    for dep, capex in zip(result['depreciation_history'], result['capex_history']):
        if capex > 0:
            ratio = dep / capex
            if 0 < ratio <= 1:  # 合理范围
                valid_ratios.append(ratio)
    
    if valid_ratios:
        result['maintenance_capex_ratio'] = sum(valid_ratios) / len(valid_ratios)
    else:
        result['maintenance_capex_ratio'] = 0.5  # 默认50%
    
    logger.info(f"✓ Extracted Owner Earnings inputs for {len(result['periods'])} periods")
    logger.info(f"Latest Net Income: ¥{result['net_income_history'][0]/100000000:.2f}亿" if result['net_income_history'] else "No data")
    logger.info(f"Estimated maintenance capex ratio: {result['maintenance_capex_ratio']:.1%}")
    
    return result


if __name__ == "__main__":
    # 测试代码
    symbol = "600000"  # 浦发银行
    
    # 获取财务数据
    financial_data = get_comprehensive_financial_data(symbol, num_periods=8)
    
    # 提取DCF输入
    dcf_inputs = extract_dcf_inputs(financial_data)
    print("\n=== DCF Inputs ===")
    for key, value in dcf_inputs.items():
        if isinstance(value, list) and value:
            print(f"{key}: {[f'{v/100000000:.2f}亿' if isinstance(v, (int, float)) and abs(v) > 1000000 else v for v in value[:3]]}")
        else:
            print(f"{key}: {value/100000000:.2f}亿" if isinstance(value, (int, float)) and abs(value) > 1000000 else f"{key}: {value}")
    
    # 提取所有者收益输入
    oe_inputs = extract_owner_earnings_inputs(financial_data)
    print("\n=== Owner Earnings Inputs ===")
    for key, value in oe_inputs.items():
        if isinstance(value, list) and value:
            print(f"{key}: {[f'{v/100000000:.2f}亿' if isinstance(v, (int, float)) and abs(v) > 1000000 else v for v in value[:3]]}")
        else:
            print(f"{key}: {value}")
    
    baostock_logout()
