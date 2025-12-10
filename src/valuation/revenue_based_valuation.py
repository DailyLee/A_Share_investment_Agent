# -*- coding: utf-8 -*-
"""
基于营收的估值方法

适用于成长型公司，特别是当前盈利为负但营收增长的公司：
1. P/S倍数法：使用行业平均P/S倍数
2. 未来盈利能力预测：预测未来何时盈利，然后使用DCF
3. 营收增长率折现：基于营收增长率和未来盈利能力
"""

from typing import Dict, Any, Optional
from src.utils.logging_config import setup_logger

logger = setup_logger('revenue_based_valuation')

# 行业P/S倍数参考值（基于A股市场平均水平）
INDUSTRY_PS_RATIOS = {
    "technology": 8.0,        # 科技行业：高增长，高P/S
    "healthcare": 6.0,        # 医药行业：稳定增长
    "consumer": 3.0,          # 消费行业：稳定
    "services": 4.0,          # 服务业：中等增长
    "manufacturing": 2.5,     # 制造业：成熟行业
    "utilities": 1.5,         # 公用事业：低增长
    "finance": 2.0,           # 金融行业：特殊估值
    "real_estate": 1.8,       # 房地产：周期性
    "heavy_industry": 1.5,    # 重工业：周期性
    "default": 3.0            # 默认值
}


def calculate_revenue_based_valuation(
    operating_revenue: float,
    revenue_growth_rate: float,
    industry_code: str,
    market_cap: float = 0,
    years_to_profitability: int = 3,
    target_profit_margin: float = 0.10
) -> Dict[str, Any]:
    """
    基于营收的估值方法
    
    适用于：
    - 当前盈利为负但营收增长的公司
    - 成长型科技公司
    - 早期阶段的公司
    
    Args:
        operating_revenue: 营业收入（元）
        revenue_growth_rate: 营收增长率（如0.3表示30%）
        industry_code: 行业代码
        market_cap: 当前市值（元），用于计算P/S倍数
        years_to_profitability: 预计几年后盈利（默认3年）
        target_profit_margin: 目标净利润率（默认10%）
    
    Returns:
        Dict包含估值结果
    """
    try:
        if operating_revenue <= 0:
            logger.warning("营业收入为负或为零，无法使用营收估值法")
            return {
                'revenue_value': 0,
                'method': 'revenue_based',
                'error': 'Invalid revenue'
            }
        
        # 方法1：P/S倍数法
        ps_ratio = INDUSTRY_PS_RATIOS.get(industry_code, INDUSTRY_PS_RATIOS["default"])
        
        # 如果提供了市值，使用实际P/S倍数（更准确）
        if market_cap > 0 and operating_revenue > 0:
            actual_ps = market_cap / operating_revenue
            # 如果实际P/S在合理范围内（0.5-20），使用实际值
            if 0.5 <= actual_ps <= 20:
                ps_ratio = actual_ps
                logger.info(f"使用实际P/S倍数: {ps_ratio:.2f}")
            else:
                logger.warning(f"实际P/S倍数异常({actual_ps:.2f})，使用行业平均: {ps_ratio:.2f}")
        
        revenue_value_ps = operating_revenue * ps_ratio
        
        logger.info(f"\n=== Revenue-Based Valuation ===")
        logger.info(f"Operating Revenue: ¥{operating_revenue/100000000:.2f}亿")
        logger.info(f"Revenue Growth Rate: {revenue_growth_rate:.2%}")
        logger.info(f"P/S Ratio: {ps_ratio:.2f}")
        logger.info(f"Valuation (P/S Method): ¥{revenue_value_ps/100000000:.2f}亿")
        
        # 方法2：未来盈利能力预测法
        # 假设公司在years_to_profitability年后开始盈利
        # 使用营收增长预测未来营收，然后应用目标净利润率
        future_revenue = operating_revenue * ((1 + revenue_growth_rate) ** years_to_profitability)
        future_net_income = future_revenue * target_profit_margin
        
        # 使用简化的DCF模型（假设永续增长率为3%）
        # 折现率使用12%（成长型公司风险较高）
        discount_rate = 0.12
        terminal_growth_rate = 0.03
        
        # 计算未来盈利的现值
        # 假设从第years_to_profitability+1年开始盈利，持续5年高增长，然后永续
        future_value = 0
        for year in range(1, 6):  # 5年高增长期
            year_net_income = future_net_income * ((1 + revenue_growth_rate * 0.5) ** year)
            discount_factor = (1 + discount_rate) ** (years_to_profitability + year)
            pv = year_net_income / discount_factor
            future_value += pv
        
        # 永续价值
        terminal_net_income = future_net_income * ((1 + revenue_growth_rate * 0.5) ** 5)
        terminal_value = terminal_net_income * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
        terminal_pv = terminal_value / ((1 + discount_rate) ** (years_to_profitability + 5))
        
        revenue_value_dcf = future_value + terminal_pv
        
        logger.info(f"\nFuture Profitability Method:")
        logger.info(f"  Years to Profitability: {years_to_profitability}")
        logger.info(f"  Target Profit Margin: {target_profit_margin:.0%}")
        logger.info(f"  Future Revenue (Year {years_to_profitability}): ¥{future_revenue/100000000:.2f}亿")
        logger.info(f"  Future Net Income (Year {years_to_profitability}): ¥{future_net_income/100000000:.2f}亿")
        logger.info(f"  Valuation (DCF Method): ¥{revenue_value_dcf/100000000:.2f}亿")
        
        # 使用两种方法的平均值（更保守）
        revenue_value = (revenue_value_ps + revenue_value_dcf) / 2
        
        logger.info(f"\n=== Combined Valuation ===")
        logger.info(f"P/S Method: ¥{revenue_value_ps/100000000:.2f}亿")
        logger.info(f"DCF Method: ¥{revenue_value_dcf/100000000:.2f}亿")
        logger.info(f"Average: ¥{revenue_value/100000000:.2f}亿")
        
        return {
            'revenue_value': revenue_value,
            'revenue_value_ps': revenue_value_ps,
            'revenue_value_dcf': revenue_value_dcf,
            'ps_ratio': ps_ratio,
            'method': 'revenue_based',
            'years_to_profitability': years_to_profitability,
            'target_profit_margin': target_profit_margin
        }
    
    except Exception as e:
        logger.error(f"营收估值计算错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'revenue_value': 0,
            'method': 'revenue_based',
            'error': str(e)
        }
