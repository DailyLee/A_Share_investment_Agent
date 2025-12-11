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

# 行业P/S倍数参考值（基于A股市场实际估值水平优化）
# A股市场特点：整体估值水平低于成熟市场，更关注PE/PB等传统指标
# P/S倍数应更保守，反映A股市场估值特点
INDUSTRY_PS_RATIOS = {
    "technology": 6.5,        # 科技行业：A股科技股P/S通常低于美股（从8.0降低到6.5）
    "healthcare": 5.0,        # 医药行业：A股医药股估值相对合理（从6.0降低到5.0）
    "consumer": 2.5,          # 消费行业：A股消费股估值相对保守（从3.0降低到2.5）
    "services": 3.5,          # 服务业：A股服务业估值适中（从4.0降低到3.5）
    "manufacturing": 2.0,     # 制造业：A股制造业估值较低（从2.5降低到2.0）
    "utilities": 1.2,         # 公用事业：A股公用事业估值低（从1.5降低到1.2）
    "finance": 1.5,           # 金融行业：A股金融股估值低（从2.0降低到1.5）
    "real_estate": 1.5,       # 房地产：A股地产股估值低（从1.8降低到1.5）
    "heavy_industry": 1.2,    # 重工业：A股重工业估值低（从1.5降低到1.2）
    "default": 2.5            # 默认值（从3.0降低到2.5）
}


def calculate_revenue_based_valuation(
    operating_revenue: float,
    revenue_growth_rate: float,
    industry_code: str,
    market_cap: float = 0,
    years_to_profitability: int = 3,
    target_profit_margin: float = 0.10,
    current_net_income: float = 0,
    current_net_margin: float = 0
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
        current_net_income: 当前净利润（如果已盈利）
        current_net_margin: 当前净利润率（如果已盈利）
    
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
        actual_ps = None  # 初始化actual_ps变量
        
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
        
        # 对于已经盈利的公司，P/S方法估值应该更接近市值（市场已经反映了盈利能力）
        # 如果实际P/S在合理范围内，说明市场估值相对合理
        # 但对于成长型公司，即使利润率较低，如果营收增长很快，也不应该过度下调
        if market_cap > 0 and actual_ps is not None and 0.5 <= actual_ps <= 20:
            # 对于已盈利公司，只有在利润率很低且增长也很慢时才下调
            # 如果营收增长率>20%，说明是成长型公司，不应该过度下调P/S估值
            if current_net_margin > 0 and current_net_margin < 0.05:
                # 如果是成长型公司（营收增长>20%），下调幅度更小
                if revenue_growth_rate > 0.20:
                    # 成长型公司：即使利润率低，但增长快，只下调5%
                    adjustment_factor = 0.95
                    revenue_value_ps = revenue_value_ps * adjustment_factor
                    logger.info(f"已盈利成长型公司（利润率{current_net_margin:.1%}，增长{revenue_growth_rate:.1%}），P/S估值小幅下调至: ¥{revenue_value_ps/100000000:.2f}亿")
                else:
                    # 非成长型公司：利润率低且增长慢，下调10-15%
                    adjustment_factor = 0.85 if current_net_margin < 0.03 else 0.90
                    revenue_value_ps = revenue_value_ps * adjustment_factor
                    logger.info(f"已盈利但利润率较低且增长慢({current_net_margin:.1%})，P/S估值下调至: ¥{revenue_value_ps/100000000:.2f}亿")
        
        logger.info(f"\n=== Revenue-Based Valuation ===")
        logger.info(f"Operating Revenue: ¥{operating_revenue/100000000:.2f}亿")
        logger.info(f"Revenue Growth Rate: {revenue_growth_rate:.2%}")
        logger.info(f"P/S Ratio: {ps_ratio:.2f}")
        logger.info(f"Valuation (P/S Method): ¥{revenue_value_ps/100000000:.2f}亿")
        
        # 方法2：未来盈利能力预测法
        # 对于已经盈利的公司，使用当前净利润率；对于亏损公司，假设未来盈利
        is_profitable = current_net_income > 0 and current_net_margin > 0
        
        if is_profitable:
            # 已盈利公司：使用当前净利润率，但考虑未来增长
            # 营收增长率应该衰减（高增长不可持续），但对于成长型公司衰减幅度应该更小
            # 对于A股市场，高增长率通常会快速衰减到行业平均水平
            if revenue_growth_rate > 0.30:
                # 增长率>30%，假设未来5年衰减到20%（保留更多增长潜力）
                adjusted_growth_rate = 0.20
            elif revenue_growth_rate > 0.20:
                # 增长率20-30%，假设未来5年衰减到15%（保留更多增长潜力）
                adjusted_growth_rate = 0.15
            else:
                # 增长率<20%，假设未来5年衰减到8%
                adjusted_growth_rate = min(revenue_growth_rate * 0.6, 0.08)
            
            # 对于成长型公司，假设未来利润率会改善
            # 如果当前利润率<5%但营收增长>20%，假设未来利润率会显著改善
            if current_net_margin < 0.05 and revenue_growth_rate > 0.20:
                # 成长型公司：假设未来利润率会改善到目标利润率的80%（更乐观）
                effective_profit_margin = max(current_net_margin * 1.5, target_profit_margin * 0.8)
            else:
                # 非成长型公司：假设未来利润率小幅改善
                effective_profit_margin = min(current_net_margin * 1.2, target_profit_margin)
            
            # 从当前开始计算，而不是假设未来才开始盈利
            years_to_profitability = 0
            future_revenue = operating_revenue
            future_net_income = operating_revenue * effective_profit_margin
            
            logger.info(f"已盈利公司，当前净利润率: {current_net_margin:.1%}，有效净利润率: {effective_profit_margin:.1%}，调整后增长率: {adjusted_growth_rate:.1%}")
        else:
            # 亏损公司：假设未来盈利
            future_revenue = operating_revenue * ((1 + revenue_growth_rate) ** years_to_profitability)
            future_net_income = future_revenue * target_profit_margin
            adjusted_growth_rate = revenue_growth_rate * 0.5  # 未来增长率衰减
        
        # 使用简化的DCF模型（A股市场永续增长率设为2.5%）
        # 折现率使用12%（成长型公司风险较高，A股市场波动性大）
        discount_rate = 0.12
        terminal_growth_rate = 0.025  # A股市场永续增长率2.5%（从3%降低）
        
        # 计算未来盈利的现值
        # 假设从第years_to_profitability+1年开始盈利，持续5年高增长，然后永续
        future_value = 0
        for year in range(1, 6):  # 5年高增长期
            year_net_income = future_net_income * ((1 + adjusted_growth_rate) ** year)
            discount_factor = (1 + discount_rate) ** (years_to_profitability + year)
            pv = year_net_income / discount_factor
            future_value += pv
        
        # 永续价值
        terminal_net_income = future_net_income * ((1 + adjusted_growth_rate) ** 5)
        terminal_value = terminal_net_income * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
        terminal_pv = terminal_value / ((1 + discount_rate) ** (years_to_profitability + 5))
        
        revenue_value_dcf = future_value + terminal_pv
        
        logger.info(f"\nFuture Profitability Method:")
        logger.info(f"  Years to Profitability: {years_to_profitability}")
        logger.info(f"  Target Profit Margin: {target_profit_margin:.0%}")
        logger.info(f"  Future Revenue (Year {years_to_profitability}): ¥{future_revenue/100000000:.2f}亿")
        logger.info(f"  Future Net Income (Year {years_to_profitability}): ¥{future_net_income/100000000:.2f}亿")
        logger.info(f"  Valuation (DCF Method): ¥{revenue_value_dcf/100000000:.2f}亿")
        
        # 对于已盈利公司，根据成长性调整权重
        # 对于亏损公司，两种方法权重相等
        if is_profitable:
            # 如果是成长型公司（营收增长>20%），更依赖DCF方法（反映未来增长潜力）
            # 如果是非成长型公司，更依赖P/S方法（市场已经反映了盈利能力）
            if revenue_growth_rate > 0.20:
                # 成长型公司：P/S方法权重50%，DCF方法权重50%（平衡两种方法）
                revenue_value = 0.5 * revenue_value_ps + 0.5 * revenue_value_dcf
                logger.info(f"已盈利成长型公司（增长{revenue_growth_rate:.1%}），使用平衡权重（P/S 50% + DCF 50%）")
            else:
                # 非成长型公司：P/S方法权重70%，DCF方法权重30%
                revenue_value = 0.7 * revenue_value_ps + 0.3 * revenue_value_dcf
                logger.info("已盈利非成长型公司，使用加权平均（P/S 70% + DCF 30%）")
        else:
            # 亏损公司：两种方法权重相等
            revenue_value = (revenue_value_ps + revenue_value_dcf) / 2
            logger.info("亏损公司，使用简单平均（P/S 50% + DCF 50%）")
        
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
