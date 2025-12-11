from typing import Dict, Any, List
import pandas as pd
import akshare as ak
import baostock as bs
from datetime import datetime, timedelta
import json
import numpy as np
from src.utils.logging_config import setup_logger

# 设置日志记录
logger = setup_logger('api')

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


def convert_stock_code_to_baostock(symbol: str) -> str:
    """
    将股票代码转换为 Baostock 格式
    例如: 600353 -> sh.600353, 000001 -> sz.000001
    """
    if symbol.startswith('6'):
        return f'sh.{symbol}'
    elif symbol.startswith(('0', '3')):
        return f'sz.{symbol}'
    else:
        return f'sh.{symbol}'  # 默认使用上海


def get_market_data_from_baostock(symbol: str) -> Dict[str, Any]:
    """使用 Baostock 获取市场数据（作为备选方案）"""
    try:
        if not ensure_baostock_login():
            return None
        
        bs_code = convert_stock_code_to_baostock(symbol)
        logger.info(f"Fetching market data from Baostock for {bs_code}...")
        
        # 获取股票名称
        stock_name = ""
        try:
            rs_basic = bs.query_stock_basic(code=bs_code)
            if rs_basic.error_code == '0':
                basic_list = []
                while (rs_basic.error_code == '0') & rs_basic.next():
                    basic_list.append(rs_basic.get_row_data())
                if basic_list:
                    basic_df = pd.DataFrame(basic_list, columns=rs_basic.fields)
                    if not basic_df.empty and 'code_name' in basic_df.columns:
                        stock_name = basic_df.iloc[0].get('code_name', '')
                        logger.info(f"获取到股票名称: {stock_name}")
        except Exception as e:
            logger.warning(f"Failed to fetch stock name from Baostock: {e}")
        
        # 获取最近一天的K线数据来获取市值等信息
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # 扩大到30天
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,close,peTTM,pbMRQ,psTTM,turn,tradestatus",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 后复权
        )
        
        if rs.error_code != '0':
            logger.error(f"Baostock query error: {rs.error_msg}")
            return None
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.warning(f"No data returned from Baostock for {bs_code}")
            return None
        
        # 转换为DataFrame并获取最新数据
        df = pd.DataFrame(data_list, columns=rs.fields)
        df = df[df['tradestatus'] == '1']  # 只保留交易日
        
        if df.empty:
            logger.warning(f"No trading data available from Baostock for {bs_code}")
            return None
        
        latest = df.iloc[-1]
        close_price = float(latest['close'])
        pe_ratio = float(latest.get('peTTM', 0)) if latest.get('peTTM') and latest.get('peTTM') != '' else 0
        pb_ratio = float(latest.get('pbMRQ', 0)) if latest.get('pbMRQ') and latest.get('pbMRQ') != '' else 0
        ps_ratio = float(latest.get('psTTM', 0)) if latest.get('psTTM') and latest.get('psTTM') != '' else 0
        
        # 尝试多种方式获取市值
        market_cap = 0
        
        # 方法1: 从 query_profit_data 获取总股本（最可靠的方法）
        try:
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            
            # 尝试最近2个季度
            for quarter_offset in range(0, 2):
                year = current_year
                quarter = current_quarter - quarter_offset
                if quarter <= 0:
                    year -= 1
                    quarter += 4
                
                rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs_profit.error_code == '0':
                    profit_list = []
                    while (rs_profit.error_code == '0') & rs_profit.next():
                        profit_list.append(rs_profit.get_row_data())
                    
                    if profit_list:
                        profit_df = pd.DataFrame(profit_list, columns=rs_profit.fields)
                        if not profit_df.empty:
                            # 尝试获取 totalShare（总股本）
                            total_share_str = profit_df.iloc[0].get('totalShare', '0')
                            if total_share_str and total_share_str != '':
                                try:
                                    total_shares = float(total_share_str)  # 单位：股
                                    # 市值 = 总股本（股） * 股价（元） / 1亿 = 亿元
                                    market_cap = total_shares * close_price / 100_000_000
                                    logger.info(f"Method 1: 总股本={total_shares:,.0f}股 ({total_shares/100_000_000:.2f}亿股), 收盘价={close_price}元, 市值={market_cap:.2f}亿元")
                                    break
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Failed to parse totalShare: {e}")
                
                if market_cap > 0:
                    break
        except Exception as e:
            logger.warning(f"Method 1 failed: {e}")
        
        # 方法2: 如果方法1失败，尝试使用流通股本作为后备
        if market_cap <= 0:
            try:
                current_year = datetime.now().year
                current_quarter = (datetime.now().month - 1) // 3 + 1
                
                # 尝试更多历史季度（最近4个季度）
                for quarter_offset in range(2, 6):  # 从第3个季度开始（方法1已经试过前2个）
                    year = current_year
                    quarter = current_quarter - quarter_offset
                    if quarter <= 0:
                        year -= 1
                        quarter += 4
                    
                    rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                    if rs_profit.error_code == '0':
                        profit_list = []
                        while (rs_profit.error_code == '0') & rs_profit.next():
                            profit_list.append(rs_profit.get_row_data())
                        
                        if profit_list:
                            profit_df = pd.DataFrame(profit_list, columns=rs_profit.fields)
                            if not profit_df.empty:
                                # 尝试 totalShare
                                total_share_str = profit_df.iloc[0].get('totalShare', '0')
                                if total_share_str and total_share_str != '':
                                    try:
                                        total_shares = float(total_share_str)
                                        market_cap = total_shares * close_price / 100_000_000
                                        logger.info(f"Method 2: 总股本={total_shares:,.0f}股 ({total_shares/100_000_000:.2f}亿股), 收盘价={close_price}元, 市值={market_cap:.2f}亿元 (历史数据: {year}Q{quarter})")
                                        break
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"Failed to parse totalShare: {e}")
                                
                                # 后备方案：使用流通股本 liqaShare
                                if market_cap <= 0:
                                    liqa_share_str = profit_df.iloc[0].get('liqaShare', '0')
                                    if liqa_share_str and liqa_share_str != '':
                                        try:
                                            liqa_shares = float(liqa_share_str)
                                            market_cap = liqa_shares * close_price / 100_000_000
                                            logger.info(f"Method 2 (liqaShare): 流通股本={liqa_shares:,.0f}股 ({liqa_shares/100_000_000:.2f}亿股), 收盘价={close_price}元, 流通市值={market_cap:.2f}亿元 (历史数据: {year}Q{quarter})")
                                            break
                                        except (ValueError, TypeError) as e:
                                            logger.warning(f"Failed to parse liqaShare: {e}")
                    
                    if market_cap > 0:
                        break
            
            except Exception as e:
                logger.warning(f"Method 2 failed: {e}")
        
        # 如果所有方法都失败，记录警告但返回其他可用数据
        if market_cap <= 0:
            logger.warning("Could not calculate market cap from Baostock, but returning other available data")
        else:
            logger.info(f"✓ Market data fetched from Baostock: market_cap={market_cap:.2f}亿元")
        
        return {
            "stock_name": stock_name,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "price_to_book": pb_ratio,
            "price_to_sales": ps_ratio,
            "turnover": float(latest.get('turn', 0)) if latest.get('turn') and latest.get('turn') != '' else 0,
        }
        
    except Exception as e:
        logger.error(f"Error fetching market data from Baostock: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def get_financial_metrics(symbol: str) -> Dict[str, Any]:
    """获取财务指标数据"""
    logger.info(f"Getting financial indicators for {symbol}...")
    try:
        # 获取实时行情数据（用于市值和估值比率）
        logger.info("Fetching real-time quotes...")
        stock_data = None
        baostock_data = None
        
        try:
            realtime_data = ak.stock_zh_a_spot_em()
            if realtime_data is not None and not realtime_data.empty:
                stock_data_filtered = realtime_data[realtime_data['代码'] == symbol]
                if not stock_data_filtered.empty:
                    stock_data = stock_data_filtered.iloc[0]
                    logger.info("✓ Real-time quotes fetched from Akshare")
                else:
                    logger.warning(f"No real-time quotes found for {symbol}")
            else:
                logger.warning("No real-time quotes data available")
        except Exception as e:
            logger.warning(f"Failed to fetch real-time quotes from Akshare: {e}")
            logger.info("Trying Baostock as fallback...")
        
        # 如果 akshare 失败，尝试使用 Baostock
        if stock_data is None or float(stock_data.get("总市值", 0)) == 0:
            logger.info("Attempting to fetch data from Baostock...")
            baostock_data = get_market_data_from_baostock(symbol)
            
            if baostock_data:
                # 使用 Baostock 数据填充 stock_data
                stock_data = pd.Series({
                    "总市值": baostock_data.get("market_cap", 0),
                    "流通市值": baostock_data.get("market_cap", 0),  # Baostock返回的就是流通市值
                    "市盈率-动态": baostock_data.get("pe_ratio", 0),
                    "市净率": baostock_data.get("price_to_book", 0)
                })
                logger.info("✓ Using Baostock data as fallback")
        
        # 如果两个数据源都失败，创建默认的 stock_data
        if stock_data is None:
            logger.warning("Both Akshare and Baostock failed, using default values")
            stock_data = pd.Series({
                "总市值": 0,
                "流通市值": 0,
                "市盈率-动态": 0,
                "市净率": 0
            })

        # 获取新浪财务指标
        logger.info("Fetching Sina financial indicators...")
        current_year = datetime.now().year
        financial_data = ak.stock_financial_analysis_indicator(
            symbol=symbol, start_year=str(current_year-1))
        if financial_data is None or financial_data.empty:
            logger.warning("No financial indicator data available")
            return [{}]

        # 按日期排序并获取最新的数据
        financial_data['日期'] = pd.to_datetime(financial_data['日期'])
        financial_data = financial_data.sort_values('日期', ascending=False)
        latest_financial = financial_data.iloc[0] if not financial_data.empty else pd.Series(
        )
        logger.info(
            f"✓ Financial indicators fetched ({len(financial_data)} records)")
        logger.info(f"Latest data date: {latest_financial.get('日期')}")

        # 获取利润表数据（用于计算 price_to_sales）
        logger.info("Fetching income statement...")
        try:
            income_statement = ak.stock_financial_report_sina(
                stock=f"sh{symbol}", symbol="利润表")
            if not income_statement.empty:
                latest_income = income_statement.iloc[0]
                logger.info("✓ Income statement fetched")
            else:
                logger.warning("Failed to get income statement")
                logger.error("No income statement data found")
                latest_income = pd.Series()
        except Exception as e:
            logger.warning("Failed to get income statement")
            logger.error(f"Error getting income statement: {e}")
            latest_income = pd.Series()

        # 构建完整指标数据
        logger.info("Building indicators...")
        try:
            def convert_percentage(value: float) -> float:
                """将百分比值转换为小数"""
                try:
                    return float(value) / 100.0 if value is not None else 0.0
                except:
                    return 0.0

            # 计算 price_to_sales
            # 注意：market_cap 单位是亿元，revenue 单位是元（需要统一单位）
            market_cap_yi = float(stock_data.get("总市值", 0))  # 市值（亿元）
            revenue = float(latest_income.get("营业总收入", 0))  # 营收（元）
            
            # 如果从 Baostock 获取了 price_to_sales，直接使用
            if baostock_data and baostock_data.get("price_to_sales", 0) > 0:
                price_to_sales = baostock_data["price_to_sales"]
            # 否则尝试自己计算（统一单位：都转换为元）
            elif market_cap_yi > 0 and revenue > 0:
                market_cap_yuan = market_cap_yi * 100_000_000  # 转换为元
                price_to_sales = market_cap_yuan / revenue
                logger.debug(f"计算P/S: 市值={market_cap_yi:.2f}亿(元)={market_cap_yuan:.0f}元, 营收={revenue:.0f}元, P/S={price_to_sales:.2f}")
            else:
                price_to_sales = 0
                if market_cap_yi <= 0:
                    logger.warning("市值数据无效，无法计算P/S")
                if revenue <= 0:
                    logger.warning("营收数据无效，无法计算P/S")
            
            all_metrics = {
                # 市场数据（单位：亿元）
                "market_cap": market_cap_yi,  # 使用统一的变量名
                "float_market_cap": float(stock_data.get("流通市值", 0)),

                # 盈利数据
                "revenue": revenue,
                "net_income": float(latest_income.get("净利润", 0)),
                "return_on_equity": convert_percentage(latest_financial.get("净资产收益率(%)", 0)),
                "net_margin": convert_percentage(latest_financial.get("销售净利率(%)", 0)),
                "operating_margin": convert_percentage(latest_financial.get("营业利润率(%)", 0)),

                # 增长指标
                "revenue_growth": convert_percentage(latest_financial.get("主营业务收入增长率(%)", 0)),
                "earnings_growth": convert_percentage(latest_financial.get("净利润增长率(%)", 0)),
                "book_value_growth": convert_percentage(latest_financial.get("净资产增长率(%)", 0)),

                # 财务健康指标
                "current_ratio": float(latest_financial.get("流动比率", 0)),
                "debt_to_equity": convert_percentage(latest_financial.get("资产负债率(%)", 0)),
                "free_cash_flow_per_share": float(latest_financial.get("每股经营性现金流(元)", 0)),
                "earnings_per_share": float(latest_financial.get("加权每股收益(元)", 0)),

                # 估值比率
                "pe_ratio": float(stock_data.get("市盈率-动态", 0)),
                "price_to_book": float(stock_data.get("市净率", 0)),
                "price_to_sales": price_to_sales,
            }

            # 只返回 agent 需要的指标
            agent_metrics = {
                # 市场数据（用于估值分析）
                "market_cap": all_metrics["market_cap"],
                "float_market_cap": all_metrics["float_market_cap"],
                
                # 盈利能力指标
                "return_on_equity": all_metrics["return_on_equity"],
                "net_margin": all_metrics["net_margin"],
                "operating_margin": all_metrics["operating_margin"],

                # 增长指标
                "revenue_growth": all_metrics["revenue_growth"],
                "earnings_growth": all_metrics["earnings_growth"],
                "book_value_growth": all_metrics["book_value_growth"],

                # 财务健康指标
                "current_ratio": all_metrics["current_ratio"],
                "debt_to_equity": all_metrics["debt_to_equity"],
                "free_cash_flow_per_share": all_metrics["free_cash_flow_per_share"],
                "earnings_per_share": all_metrics["earnings_per_share"],

                # 估值比率
                "pe_ratio": all_metrics["pe_ratio"],
                "price_to_book": all_metrics["price_to_book"],
                "price_to_sales": all_metrics["price_to_sales"],
            }

            logger.info("✓ Indicators built successfully")

            # 打印所有获取到的指标数据（用于调试）
            logger.debug("\n获取到的完整指标数据：")
            for key, value in all_metrics.items():
                logger.debug(f"{key}: {value}")

            logger.debug("\n传递给 agent 的指标数据：")
            for key, value in agent_metrics.items():
                logger.debug(f"{key}: {value}")

            return [agent_metrics]

        except Exception as e:
            logger.error(f"Error building indicators: {e}")
            return [{}]

    except Exception as e:
        logger.error(f"Error getting financial indicators: {e}")
        return [{}]


def get_financial_statements(symbol: str) -> Dict[str, Any]:
    """获取财务报表数据"""
    logger.info(f"Getting financial statements for {symbol}...")
    try:
        # 获取资产负债表数据
        logger.info("Fetching balance sheet...")
        try:
            balance_sheet = ak.stock_financial_report_sina(
                stock=f"sh{symbol}", symbol="资产负债表")
            if not balance_sheet.empty:
                latest_balance = balance_sheet.iloc[0]
                previous_balance = balance_sheet.iloc[1] if len(
                    balance_sheet) > 1 else balance_sheet.iloc[0]
                logger.info("✓ Balance sheet fetched")
            else:
                logger.warning("Failed to get balance sheet")
                logger.error("No balance sheet data found")
                latest_balance = pd.Series()
                previous_balance = pd.Series()
        except Exception as e:
            logger.warning("Failed to get balance sheet")
            logger.error(f"Error getting balance sheet: {e}")
            latest_balance = pd.Series()
            previous_balance = pd.Series()

        # 获取利润表数据
        logger.info("Fetching income statement...")
        try:
            income_statement = ak.stock_financial_report_sina(
                stock=f"sh{symbol}", symbol="利润表")
            if not income_statement.empty:
                latest_income = income_statement.iloc[0]
                previous_income = income_statement.iloc[1] if len(
                    income_statement) > 1 else income_statement.iloc[0]
                logger.info("✓ Income statement fetched")
            else:
                logger.warning("Failed to get income statement")
                logger.error("No income statement data found")
                latest_income = pd.Series()
                previous_income = pd.Series()
        except Exception as e:
            logger.warning("Failed to get income statement")
            logger.error(f"Error getting income statement: {e}")
            latest_income = pd.Series()
            previous_income = pd.Series()

        # 获取现金流量表数据
        logger.info("Fetching cash flow statement...")
        try:
            cash_flow = ak.stock_financial_report_sina(
                stock=f"sh{symbol}", symbol="现金流量表")
            if not cash_flow.empty:
                latest_cash_flow = cash_flow.iloc[0]
                previous_cash_flow = cash_flow.iloc[1] if len(
                    cash_flow) > 1 else cash_flow.iloc[0]
                logger.info("✓ Cash flow statement fetched")
            else:
                logger.warning("Failed to get cash flow statement")
                logger.error("No cash flow data found")
                latest_cash_flow = pd.Series()
                previous_cash_flow = pd.Series()
        except Exception as e:
            logger.warning("Failed to get cash flow statement")
            logger.error(f"Error getting cash flow statement: {e}")
            latest_cash_flow = pd.Series()
            previous_cash_flow = pd.Series()

        # 构建财务数据
        line_items = []
        try:
            # 处理最新期间数据
            net_income = float(latest_income.get("净利润", 0))
            operating_revenue = float(latest_income.get("营业总收入", 0))
            operating_cash_flow = float(latest_cash_flow.get("经营活动产生的现金流量净额", 0))
            
            # 尝试获取折旧数据
            depreciation = float(latest_cash_flow.get("固定资产折旧、油气资产折耗、生产性生物资产折旧", 0))
            
            # 如果折旧数据缺失，使用估算值
            if depreciation == 0 and net_income > 0:
                # 方法1：使用经营现金流与净利润的差额作为粗略估计
                # （假设主要差异来自折旧等非现金项目）
                if operating_cash_flow > net_income:
                    estimated_depreciation = (operating_cash_flow - net_income) * 0.6  # 保守估计60%来自折旧
                    depreciation = max(estimated_depreciation, operating_revenue * 0.03)  # 至少为营收的3%
                    logger.warning(f"折旧数据缺失，使用估算值: {depreciation/100000000:.2f}亿元")
                else:
                    # 后备方案：使用营业收入的3-5%作为折旧估算
                    depreciation = operating_revenue * 0.04  # 保守使用4%
                    logger.warning(f"折旧数据缺失且无法从现金流推算，使用营收4%作为估算: {depreciation/100000000:.2f}亿元")
            
            current_item = {
                # 从利润表获取
                "net_income": net_income,
                "operating_revenue": operating_revenue,
                "operating_profit": float(latest_income.get("营业利润", 0)),

                # 从资产负债表计算营运资金
                "working_capital": float(latest_balance.get("流动资产合计", 0)) - float(latest_balance.get("流动负债合计", 0)),

                # 从现金流量表获取
                "depreciation_and_amortization": depreciation,
                "capital_expenditure": abs(float(latest_cash_flow.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0))),
                "free_cash_flow": operating_cash_flow - abs(float(latest_cash_flow.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0)))
            }
            line_items.append(current_item)
            logger.info("✓ Latest period data processed successfully")

            # 处理上一期间数据
            prev_net_income = float(previous_income.get("净利润", 0))
            prev_operating_revenue = float(previous_income.get("营业总收入", 0))
            prev_operating_cash_flow = float(previous_cash_flow.get("经营活动产生的现金流量净额", 0))
            
            # 尝试获取折旧数据
            prev_depreciation = float(previous_cash_flow.get("固定资产折旧、油气资产折耗、生产性生物资产折旧", 0))
            
            # 如果折旧数据缺失，使用估算值（与当期相同的逻辑）
            if prev_depreciation == 0 and prev_net_income > 0:
                if prev_operating_cash_flow > prev_net_income:
                    estimated_prev_depreciation = (prev_operating_cash_flow - prev_net_income) * 0.6
                    prev_depreciation = max(estimated_prev_depreciation, prev_operating_revenue * 0.03)
                else:
                    prev_depreciation = prev_operating_revenue * 0.04
            
            previous_item = {
                "net_income": prev_net_income,
                "operating_revenue": prev_operating_revenue,
                "operating_profit": float(previous_income.get("营业利润", 0)),
                "working_capital": float(previous_balance.get("流动资产合计", 0)) - float(previous_balance.get("流动负债合计", 0)),
                "depreciation_and_amortization": prev_depreciation,
                "capital_expenditure": abs(float(previous_cash_flow.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0))),
                "free_cash_flow": prev_operating_cash_flow - abs(float(previous_cash_flow.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0)))
            }
            line_items.append(previous_item)
            logger.info("✓ Previous period data processed successfully")

        except Exception as e:
            logger.error(f"Error processing financial data: {e}")
            default_item = {
                "net_income": 0,
                "operating_revenue": 0,
                "operating_profit": 0,
                "working_capital": 0,
                "depreciation_and_amortization": 0,
                "capital_expenditure": 0,
                "free_cash_flow": 0
            }
            line_items = [default_item, default_item]

        return line_items

    except Exception as e:
        logger.error(f"Error getting financial statements: {e}")
        default_item = {
            "net_income": 0,
            "operating_revenue": 0,
            "operating_profit": 0,
            "working_capital": 0,
            "depreciation_and_amortization": 0,
            "capital_expenditure": 0,
            "free_cash_flow": 0
        }
        return [default_item, default_item]


def get_stock_industry(symbol: str) -> str:
    """获取股票所属行业信息
    
    Args:
        symbol: 股票代码
        
    Returns:
        str: 行业名称，如果获取失败返回空字符串
    """
    try:
        # 方法1: 尝试从东方财富获取行业信息
        try:
            stock_info = ak.stock_individual_info_em(symbol=symbol)
            if stock_info is not None and not stock_info.empty:
                # 查找行业信息
                industry_row = stock_info[stock_info['item'] == '行业']
                if not industry_row.empty:
                    industry = str(industry_row['value'].iloc[0])
                    logger.info(f"✓ Industry info fetched from Akshare: {industry}")
                    return industry
        except Exception as e:
            logger.debug(f"Failed to get industry from Akshare: {e}")
        
        # 方法2: 尝试从Baostock获取行业信息
        try:
            if ensure_baostock_login():
                bs_code = convert_stock_code_to_baostock(symbol)
                rs = bs.query_stock_industry(code=bs_code)
                
                if rs.error_code == '0':
                    industry_list = []
                    while (rs.error_code == '0') & rs.next():
                        industry_list.append(rs.get_row_data())
                    
                    if industry_list:
                        industry_df = pd.DataFrame(industry_list, columns=rs.fields)
                        if not industry_df.empty and 'industry' in industry_df.columns:
                            industry = str(industry_df.iloc[0]['industry'])
                            logger.info(f"✓ Industry info fetched from Baostock: {industry}")
                            return industry
        except Exception as e:
            logger.debug(f"Failed to get industry from Baostock: {e}")
        
        logger.warning(f"Could not fetch industry information for {symbol}")
        return ""
        
    except Exception as e:
        logger.error(f"Error getting stock industry: {e}")
        return ""


def get_market_data(symbol: str) -> Dict[str, Any]:
    """获取市场数据"""
    try:
        # 获取行业信息
        industry = get_stock_industry(symbol)
        
        # 获取实时行情
        stock_data = None
        try:
            realtime_data = ak.stock_zh_a_spot_em()
            if realtime_data is not None and not realtime_data.empty:
                stock_data_filtered = realtime_data[realtime_data['代码'] == symbol]
                if not stock_data_filtered.empty:
                    stock_data = stock_data_filtered.iloc[0]
                    logger.info(f"✓ Market data fetched from Akshare for {symbol}")
                else:
                    logger.warning(f"No market data found for {symbol}")
            else:
                logger.warning("No real-time quotes data available")
        except Exception as e:
            logger.warning(f"Failed to fetch real-time quotes from Akshare: {e}")
            logger.info("Trying Baostock as fallback...")
        
        # 如果 akshare 失败，尝试使用 Baostock
        if stock_data is None or float(stock_data.get("总市值", 0)) == 0:
            logger.info("Attempting to fetch market data from Baostock...")
            baostock_data = get_market_data_from_baostock(symbol)
            
            if baostock_data:
                # 从 Baostock 获取历史数据来计算52周高低点
                bs_code = convert_stock_code_to_baostock(symbol)
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,close,volume",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3"
                )
                
                high_52w = 0
                low_52w = 0
                volume = 0
                
                if rs.error_code == '0':
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        df = pd.DataFrame(data_list, columns=rs.fields)
                        df['close'] = pd.to_numeric(df['close'], errors='coerce')
                        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
                        high_52w = df['close'].max()
                        low_52w = df['close'].min()
                        volume = df['volume'].iloc[-1] if len(df) > 0 else 0
                
                logger.info("✓ Using Baostock market data as fallback")
                
                # 尝试从 Baostock 获取股票名称
                stock_name = ""
                try:
                    rs_basic = bs.query_stock_basic(code=bs_code)
                    if rs_basic.error_code == '0':
                        basic_list = []
                        while (rs_basic.error_code == '0') & rs_basic.next():
                            basic_list.append(rs_basic.get_row_data())
                        if basic_list:
                            basic_df = pd.DataFrame(basic_list, columns=rs_basic.fields)
                            if not basic_df.empty and 'code_name' in basic_df.columns:
                                stock_name = basic_df.iloc[0].get('code_name', '')
                except Exception as e:
                    logger.warning(f"Failed to fetch stock name from Baostock: {e}")
                
                return {
                    "stock_name": stock_name,
                    "industry": industry,
                    "market_cap": baostock_data.get("market_cap", 0),
                    "volume": volume,
                    "average_volume": volume,  # 使用当前成交量作为平均值
                    "fifty_two_week_high": high_52w,
                    "fifty_two_week_low": low_52w
                }
        
        # 如果有 akshare 数据，使用它
        if stock_data is not None:
            return {
                "stock_name": str(stock_data.get("名称", "")),
                "industry": industry,
                "market_cap": float(stock_data.get("总市值", 0)),
                "volume": float(stock_data.get("成交量", 0)),
                "average_volume": float(stock_data.get("成交量", 0)),
                "fifty_two_week_high": float(stock_data.get("52周最高", 0)),
                "fifty_two_week_low": float(stock_data.get("52周最低", 0))
            }
        
        # 如果两个数据源都失败，返回默认值
        logger.warning("Both Akshare and Baostock failed, using default values for market data")
        return {
            "stock_name": "",
            "industry": industry,
            "market_cap": 0,
            "volume": 0,
            "average_volume": 0,
            "fifty_two_week_high": 0,
            "fifty_two_week_low": 0
        }

    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return {
            "stock_name": "",
            "market_cap": 0,
            "volume": 0,
            "average_volume": 0,
            "fifty_two_week_high": 0,
            "fifty_two_week_low": 0
        }


def get_price_history(symbol: str, start_date: str = None, end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
    """获取历史价格数据

    Args:
        symbol: 股票代码
        start_date: 开始日期，格式：YYYY-MM-DD，如果为None则默认获取过去一年的数据
        end_date: 结束日期，格式：YYYY-MM-DD，如果为None则使用昨天作为结束日期
        adjust: 复权类型，可选值：
               - "": 不复权
               - "qfq": 前复权（默认）
               - "hfq": 后复权

    Returns:
        包含以下列的DataFrame：
        - date: 日期
        - open: 开盘价
        - high: 最高价
        - low: 最低价
        - close: 收盘价
        - volume: 成交量（手）
        - amount: 成交额（元）
        - amplitude: 振幅（%）
        - pct_change: 涨跌幅（%）
        - change_amount: 涨跌额（元）
        - turnover: 换手率（%）

        技术指标：
        - momentum_1m: 1个月动量
        - momentum_3m: 3个月动量
        - momentum_6m: 6个月动量
        - volume_momentum: 成交量动量
        - historical_volatility: 历史波动率
        - volatility_regime: 波动率区间
        - volatility_z_score: 波动率Z分数
        - atr_ratio: 真实波动幅度比率
        - hurst_exponent: 赫斯特指数
        - skewness: 偏度
        - kurtosis: 峰度
    """
    try:
        # 获取当前日期和昨天的日期
        current_date = datetime.now()
        yesterday = current_date - timedelta(days=1)

        # 如果没有提供日期，默认使用昨天作为结束日期
        if not end_date:
            end_date = yesterday  # 使用昨天作为结束日期
        else:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
            # 确保end_date不会超过昨天
            if end_date > yesterday:
                end_date = yesterday

        if not start_date:
            start_date = end_date - timedelta(days=365)  # 默认获取一年的数据
        else:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")

        logger.info(f"\nGetting price history for {symbol}...")
        logger.info(f"Start date: {start_date.strftime('%Y-%m-%d')}")
        logger.info(f"End date: {end_date.strftime('%Y-%m-%d')}")

        def get_and_process_data(start_date, end_date):
            """获取并处理数据，包括重命名列等操作"""
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust=adjust
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # 重命名列以匹配技术分析代理的需求
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change_amount",
                "换手率": "turnover"
            })

            # 确保日期列为datetime类型
            df["date"] = pd.to_datetime(df["date"])
            return df

        # 获取历史行情数据
        df = get_and_process_data(start_date, end_date)

        if df is None or df.empty:
            logger.warning(
                f"Warning: No price history data found for {symbol}")
            return pd.DataFrame()

        # 检查数据量是否足够
        min_required_days = 120  # 至少需要120个交易日的数据
        if len(df) < min_required_days:
            logger.warning(
                f"Warning: Insufficient data ({len(df)} days) for all technical indicators")
            logger.info("Attempting to fetch more data...")

            # 扩大时间范围到2年
            start_date = end_date - timedelta(days=730)
            df = get_and_process_data(start_date, end_date)

            if len(df) < min_required_days:
                logger.warning(
                    f"Warning: Even with extended time range, insufficient data ({len(df)} days)")

        # 计算动量指标
        df["momentum_1m"] = df["close"].pct_change(periods=20)  # 20个交易日约等于1个月
        df["momentum_3m"] = df["close"].pct_change(periods=60)  # 60个交易日约等于3个月
        df["momentum_6m"] = df["close"].pct_change(
            periods=120)  # 120个交易日约等于6个月

        # 计算成交量动量（相对于20日平均成交量的变化）
        df["volume_ma20"] = df["volume"].rolling(window=20).mean()
        df["volume_momentum"] = df["volume"] / df["volume_ma20"]

        # 计算波动率指标
        # 1. 历史波动率 (20日)
        # A股市场：每年交易日约240-250天，使用240进行年化（而不是252）
        A_SHARE_TRADING_DAYS_PER_YEAR = 240
        returns = df["close"].pct_change()
        df["historical_volatility"] = returns.rolling(
            window=20).std() * np.sqrt(A_SHARE_TRADING_DAYS_PER_YEAR)  # 年化（A股市场）

        # 2. 波动率区间 (相对于过去120天的波动率的位置)
        volatility_120d = returns.rolling(window=120).std() * np.sqrt(A_SHARE_TRADING_DAYS_PER_YEAR)
        vol_min = volatility_120d.rolling(window=120).min()
        vol_max = volatility_120d.rolling(window=120).max()
        vol_range = vol_max - vol_min
        df["volatility_regime"] = np.where(
            vol_range > 0,
            (df["historical_volatility"] - vol_min) / vol_range,
            0  # 当范围为0时返回0
        )

        # 3. 波动率Z分数
        vol_mean = df["historical_volatility"].rolling(window=120).mean()
        vol_std = df["historical_volatility"].rolling(window=120).std()
        df["volatility_z_score"] = (
            df["historical_volatility"] - vol_mean) / vol_std

        # 4. ATR比率
        tr = pd.DataFrame()
        tr["h-l"] = df["high"] - df["low"]
        tr["h-pc"] = abs(df["high"] - df["close"].shift(1))
        tr["l-pc"] = abs(df["low"] - df["close"].shift(1))
        tr["tr"] = tr[["h-l", "h-pc", "l-pc"]].max(axis=1)
        df["atr"] = tr["tr"].rolling(window=14).mean()
        df["atr_ratio"] = df["atr"] / df["close"]

        # 计算统计套利指标
        # 1. 赫斯特指数 (使用过去120天的数据)
        def calculate_hurst(series):
            """
            计算Hurst指数。

            Args:
                series: 价格序列

            Returns:
                float: Hurst指数，或在计算失败时返回np.nan
            """
            try:
                series = series.dropna()
                if len(series) < 30:  # 降低最小数据点要求
                    return np.nan

                # 使用对数收益率
                log_returns = np.log(series / series.shift(1)).dropna()
                if len(log_returns) < 30:  # 降低最小数据点要求
                    return np.nan

                # 使用更小的lag范围
                # 减少lag范围到2-10天
                lags = range(2, min(11, len(log_returns) // 4))

                # 计算每个lag的标准差
                tau = []
                for lag in lags:
                    # 计算滚动标准差
                    std = log_returns.rolling(window=lag).std().dropna()
                    if len(std) > 0:
                        tau.append(np.mean(std))

                # 基本的数值检查
                if len(tau) < 3:  # 进一步降低最小要求
                    return np.nan

                # 使用对数回归
                lags_log = np.log(list(lags))
                tau_log = np.log(tau)

                # 计算回归系数
                reg = np.polyfit(lags_log, tau_log, 1)
                hurst = reg[0] / 2.0

                # 只保留基本的数值检查
                if np.isnan(hurst) or np.isinf(hurst):
                    return np.nan

                return hurst

            except Exception as e:
                return np.nan

        # 使用对数收益率计算Hurst指数
        log_returns = np.log(df["close"] / df["close"].shift(1))
        df["hurst_exponent"] = log_returns.rolling(
            window=120,
            min_periods=60  # 要求至少60个数据点
        ).apply(calculate_hurst)

        # 2. 偏度 (20日)
        df["skewness"] = returns.rolling(window=20).skew()

        # 3. 峰度 (20日)
        df["kurtosis"] = returns.rolling(window=20).kurt()

        # 按日期升序排序
        df = df.sort_values("date")

        # 重置索引
        df = df.reset_index(drop=True)

        logger.info(
            f"Successfully fetched price history data ({len(df)} records)")

        # 检查并报告NaN值
        nan_columns = df.isna().sum()
        if nan_columns.any():
            logger.warning(
                "\nWarning: The following indicators contain NaN values:")
            for col, nan_count in nan_columns[nan_columns > 0].items():
                logger.warning(f"- {col}: {nan_count} records")

        return df

    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        return pd.DataFrame()


def prices_to_df(prices):
    """Convert price data to DataFrame with standardized column names"""
    try:
        df = pd.DataFrame(prices)

        # 标准化列名映射
        column_mapping = {
            '收盘': 'close',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'change_percent',
            '涨跌额': 'change_amount',
            '换手率': 'turnover_rate'
        }

        # 重命名列
        for cn, en in column_mapping.items():
            if cn in df.columns:
                df[en] = df[cn]

        # 确保必要的列存在
        required_columns = ['close', 'open', 'high', 'low', 'volume']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0.0  # 使用0填充缺失的必要列

        return df
    except Exception as e:
        logger.error(f"Error converting price data: {str(e)}")
        # 返回一个包含必要列的空DataFrame
        return pd.DataFrame(columns=['close', 'open', 'high', 'low', 'volume'])


def get_price_data(
    ticker: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """获取股票价格数据

    Args:
        ticker: 股票代码
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD

    Returns:
        包含价格数据的DataFrame
    """
    return get_price_history(ticker, start_date, end_date)
