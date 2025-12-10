# -*- coding: utf-8 -*-
"""
改进的所有者收益法估值模型（巴菲特方法）

所有者收益（Owner Earnings）是巴菲特提出的概念，代表股东实际可以提取的现金流。

所有者收益 = 净利润 + 折旧摊销 - 维持性资本支出 - 营运资金增加

关键改进：
1. 更准确地估算维持性资本支出（vs 扩张性资本支出）
2. 考虑营运资金的实际变化
3. 使用三阶段增长模型
4. 包含安全边际
"""

import numpy as np
from typing import Dict, Any, List, Tuple
from src.utils.logging_config import setup_logger

logger = setup_logger('owner_earnings')


def estimate_maintenance_capex(
    depreciation_history: List[float],
    capex_history: List[float],
    revenue_history: List[float],
    industry_type: str = 'default'
) -> Tuple[float, float]:
    """
    估算维持性资本支出
    
    方法1: 维持性资本支出 ≈ 折旧摊销（用于维持现有产能）
    方法2: 使用历史平均的折旧/资本支出比率
    方法3: 使用行业标准比率
    
    Args:
        depreciation_history: 历史折旧摊销
        capex_history: 历史资本支出
        revenue_history: 历史营收
        industry_type: 行业类型
    
    Returns:
        Tuple[float, float]: (维持性资本支出, 维持性资本支出占总资本支出比率)
    """
    try:
        if not depreciation_history or not capex_history:
            logger.warning("Insufficient data for maintenance capex estimation")
            return 0, 0.5
        
        # 行业标准比率
        industry_ratios = {
            'utilities': 0.7,        # 公用事业：资本支出主要用于维持
            'heavy_industry': 0.6,   # 重工业：较高的维持性支出
            'technology': 0.3,       # 科技：大部分支出用于扩张
            'finance': 0.4,          # 金融：较低的资本支出
            'consumer': 0.5,         # 消费：平衡
            'healthcare': 0.4,       # 医药：较多研发支出（非资本支出）
            'real_estate': 0.5,      # 房地产：平衡
            'manufacturing': 0.6,    # 制造业：较高维持性支出
            'services': 0.4,         # 服务业：较低资本支出
            'default': 0.5
        }
        
        industry_ratio = industry_ratios.get(industry_type, 0.5)
        
        # 方法1: 使用最近一期的折旧作为维持性资本支出的估算
        latest_depreciation = depreciation_history[0] if depreciation_history else 0
        latest_capex = capex_history[0] if capex_history else 0
        
        # 方法2: 计算历史平均比率
        historical_ratios = []
        for dep, capex in zip(depreciation_history, capex_history):
            if capex > 0:
                ratio = dep / capex
                if 0 < ratio <= 1.5:  # 合理范围（有时折旧可能略高于维持性资本支出）
                    historical_ratios.append(ratio)
        
        avg_historical_ratio = np.median(historical_ratios) if historical_ratios else industry_ratio
        
        # 综合方法：使用历史比率和行业比率的加权平均
        # 如果历史数据充足，更多依赖历史数据
        if len(historical_ratios) >= 4:
            final_ratio = 0.7 * avg_historical_ratio + 0.3 * industry_ratio
        else:
            final_ratio = 0.3 * avg_historical_ratio + 0.7 * industry_ratio
        
        # 确保比率在合理范围内
        final_ratio = max(0.2, min(final_ratio, 1.0))
        
        # 计算维持性资本支出
        if latest_capex > 0:
            maintenance_capex = latest_capex * final_ratio
        else:
            maintenance_capex = latest_depreciation  # 后备方案
        
        logger.info(f"Maintenance Capex Estimation:")
        logger.info(f"  Latest Depreciation: ¥{latest_depreciation/100000000:.2f}亿")
        logger.info(f"  Latest Capex: ¥{latest_capex/100000000:.2f}亿")
        logger.info(f"  Historical Avg Ratio: {avg_historical_ratio:.2%}")
        logger.info(f"  Industry Standard Ratio: {industry_ratio:.2%}")
        logger.info(f"  Final Ratio: {final_ratio:.2%}")
        logger.info(f"  Estimated Maintenance Capex: ¥{maintenance_capex/100000000:.2f}亿")
        
        return maintenance_capex, final_ratio
    
    except Exception as e:
        logger.error(f"Error estimating maintenance capex: {e}")
        return 0, 0.5


def calculate_owner_earnings(
    net_income: float,
    depreciation: float,
    capex: float,
    working_capital_change: float,
    maintenance_capex_ratio: float = 0.5
) -> float:
    """
    计算所有者收益
    
    所有者收益 = 净利润 + 折旧摊销 - 维持性资本支出 - 营运资金增加
    
    Args:
        net_income: 净利润
        depreciation: 折旧摊销
        capex: 资本支出
        working_capital_change: 营运资金变化（正值表示增加，需要扣除）
        maintenance_capex_ratio: 维持性资本支出占总资本支出的比率
    
    Returns:
        float: 所有者收益
    """
    try:
        # 计算维持性资本支出
        maintenance_capex = capex * maintenance_capex_ratio
        
        # 计算所有者收益
        owner_earnings = (net_income + 
                         depreciation - 
                         maintenance_capex - 
                         working_capital_change)
        
        logger.info(f"Owner Earnings Calculation:")
        logger.info(f"  Net Income: ¥{net_income/100000000:.2f}亿")
        logger.info(f"  + Depreciation: ¥{depreciation/100000000:.2f}亿")
        logger.info(f"  - Maintenance Capex: ¥{maintenance_capex/100000000:.2f}亿")
        logger.info(f"  - Working Capital Change: ¥{working_capital_change/100000000:.2f}亿")
        logger.info(f"  = Owner Earnings: ¥{owner_earnings/100000000:.2f}亿")
        
        return owner_earnings
    
    except Exception as e:
        logger.error(f"Error calculating owner earnings: {e}")
        return 0


def calculate_three_stage_owner_earnings_value(
    initial_owner_earnings: float,
    high_growth_rate: float,
    transition_growth_rate: float,
    terminal_growth_rate: float,
    required_return: float,
    high_growth_years: int = 5,
    transition_years: int = 5,
    margin_of_safety: float = 0.25,
    total_debt: float = 0,
    cash_and_equivalents: float = 0
) -> Dict[str, Any]:
    """
    使用三阶段模型计算所有者收益法估值
    
    阶段1（高增长期）: 5年，使用较高的增长率
    阶段2（过渡期）: 5年，增长率线性下降
    阶段3（永续期）: 永续，使用稳定的永续增长率
    
    内在价值 = (阶段1现值 + 阶段2现值 + 阶段3现值) × (1 - 安全边际)
    
    Args:
        initial_owner_earnings: 初始所有者收益
        high_growth_rate: 高增长期增长率
        transition_growth_rate: 过渡期起始增长率
        terminal_growth_rate: 永续增长率
        required_return: 要求回报率
        high_growth_years: 高增长期年数
        transition_years: 过渡期年数
        margin_of_safety: 安全边际（0.25表示75%的价值）
        total_debt: 总债务（用于计算企业价值）
        cash_and_equivalents: 现金及现金等价物
    
    Returns:
        Dict包含估值结果和详细信息
    """
    try:
        if initial_owner_earnings <= 0:
            logger.warning("Initial owner earnings is non-positive, cannot perform valuation")
            return {
                'intrinsic_value': 0,
                'intrinsic_value_with_margin': 0,
                'stage1_value': 0,
                'stage2_value': 0,
                'stage3_value': 0,
                'margin_of_safety': margin_of_safety,
                'error': 'Invalid initial owner earnings'
            }
        
        if required_return <= terminal_growth_rate:
            logger.warning(f"Required return ({required_return:.2%}) must be greater than terminal growth rate ({terminal_growth_rate:.2%})")
            required_return = terminal_growth_rate + 0.05  # 至少大5个百分点
        
        logger.info("\n=== Three-Stage Owner Earnings Valuation ===")
        logger.info(f"Initial Owner Earnings: ¥{initial_owner_earnings/100000000:.2f}亿")
        logger.info(f"Required Return: {required_return:.2%}")
        logger.info(f"Margin of Safety: {margin_of_safety:.0%}")
        
        # 阶段1：高增长期
        stage1_oe = []
        stage1_pv = []
        current_oe = initial_owner_earnings
        
        logger.info(f"\nStage 1: High Growth Period ({high_growth_years} years, {high_growth_rate:.2%} growth)")
        for year in range(1, high_growth_years + 1):
            current_oe = current_oe * (1 + high_growth_rate)
            discount_factor = (1 + required_return) ** year
            pv = current_oe / discount_factor
            stage1_oe.append(current_oe)
            stage1_pv.append(pv)
            logger.info(f"  Year {year}: OE = ¥{current_oe/100000000:.2f}亿, PV = ¥{pv/100000000:.2f}亿")
        
        stage1_value = sum(stage1_pv)
        logger.info(f"  Stage 1 Total PV: ¥{stage1_value/100000000:.2f}亿")
        
        # 阶段2：过渡期（增长率线性递减）
        stage2_oe = []
        stage2_pv = []
        
        # 计算每年增长率递减的幅度
        growth_decline_per_year = (transition_growth_rate - terminal_growth_rate) / transition_years
        
        logger.info(f"\nStage 2: Transition Period ({transition_years} years)")
        logger.info(f"  Growth rate declines from {transition_growth_rate:.2%} to {terminal_growth_rate:.2%}")
        
        current_growth = transition_growth_rate
        for year in range(1, transition_years + 1):
            current_oe = current_oe * (1 + current_growth)
            discount_factor = (1 + required_return) ** (high_growth_years + year)
            pv = current_oe / discount_factor
            stage2_oe.append(current_oe)
            stage2_pv.append(pv)
            logger.info(f"  Year {high_growth_years + year}: OE = ¥{current_oe/100000000:.2f}亿 (growth {current_growth:.2%}), PV = ¥{pv/100000000:.2f}亿")
            current_growth -= growth_decline_per_year
            current_growth = max(current_growth, terminal_growth_rate)
        
        stage2_value = sum(stage2_pv)
        logger.info(f"  Stage 2 Total PV: ¥{stage2_value/100000000:.2f}亿")
        
        # 阶段3：永续期
        # 永续价值 = OE(n+1) / (required_return - terminal_growth_rate)
        terminal_oe = current_oe * (1 + terminal_growth_rate)
        terminal_value = terminal_oe / (required_return - terminal_growth_rate)
        
        # 折现到现在
        total_years = high_growth_years + transition_years
        stage3_pv = terminal_value / ((1 + required_return) ** total_years)
        
        logger.info(f"\nStage 3: Terminal Value")
        logger.info(f"  Terminal OE: ¥{terminal_oe/100000000:.2f}亿")
        logger.info(f"  Terminal Value: ¥{terminal_value/100000000:.2f}亿")
        logger.info(f"  Terminal Value PV: ¥{stage3_pv/100000000:.2f}亿")
        
        # 计算内在价值（企业价值）
        intrinsic_value = stage1_value + stage2_value + stage3_pv
        
        logger.info(f"\n=== Valuation Summary ===")
        logger.info(f"Stage 1 PV: ¥{stage1_value/100000000:.2f}亿 ({stage1_value/intrinsic_value:.1%})")
        logger.info(f"Stage 2 PV: ¥{stage2_value/100000000:.2f}亿 ({stage2_value/intrinsic_value:.1%})")
        logger.info(f"Stage 3 PV: ¥{stage3_pv/100000000:.2f}亿 ({stage3_pv/intrinsic_value:.1%})")
        logger.info(f"Intrinsic Value (before margin): ¥{intrinsic_value/100000000:.2f}亿")
        
        # 应用安全边际
        intrinsic_value_with_margin = intrinsic_value * (1 - margin_of_safety)
        logger.info(f"Margin of Safety ({margin_of_safety:.0%}): -¥{intrinsic_value * margin_of_safety/100000000:.2f}亿")
        logger.info(f"Intrinsic Value (with margin): ¥{intrinsic_value_with_margin/100000000:.2f}亿")
        
        # 计算股权价值（如果提供了债务和现金信息）
        equity_value = intrinsic_value_with_margin
        if total_debt > 0 or cash_and_equivalents > 0:
            equity_value = intrinsic_value_with_margin + cash_and_equivalents - total_debt
            logger.info(f"+ Cash: ¥{cash_and_equivalents/100000000:.2f}亿")
            logger.info(f"- Debt: ¥{total_debt/100000000:.2f}亿")
            logger.info(f"= Equity Value: ¥{equity_value/100000000:.2f}亿")
        
        return {
            'intrinsic_value': intrinsic_value,
            'intrinsic_value_with_margin': intrinsic_value_with_margin,
            'equity_value': equity_value,
            'stage1_value': stage1_value,
            'stage2_value': stage2_value,
            'stage3_value': stage3_pv,
            'stage1_oe': stage1_oe,
            'stage2_oe': stage2_oe,
            'terminal_oe': terminal_oe,
            'margin_of_safety': margin_of_safety,
            'required_return': required_return,
            'high_growth_rate': high_growth_rate,
            'terminal_growth_rate': terminal_growth_rate
        }
    
    except Exception as e:
        logger.error(f"Error in three-stage owner earnings valuation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'intrinsic_value': 0,
            'intrinsic_value_with_margin': 0,
            'equity_value': 0,
            'stage1_value': 0,
            'stage2_value': 0,
            'stage3_value': 0,
            'margin_of_safety': margin_of_safety,
            'error': str(e)
        }


def calculate_normalized_owner_earnings(
    owner_earnings_history: List[float],
    normalization_years: int = 5
) -> float:
    """
    计算正常化的所有者收益
    
    对于周期性行业，使用多年平均值更合理
    
    Args:
        owner_earnings_history: 历史所有者收益（从最新到最早）
        normalization_years: 用于正常化的年数
    
    Returns:
        float: 正常化的所有者收益
    """
    try:
        if not owner_earnings_history:
            return 0
        
        # 使用最近N年的平均值
        recent_oe = owner_earnings_history[:normalization_years]
        
        # 过滤掉异常值（负值或极端值）
        valid_oe = [oe for oe in recent_oe if oe > 0]
        
        if not valid_oe:
            logger.warning("No valid owner earnings in history")
            return 0
        
        # 使用中位数（对异常值更稳健）
        normalized_oe = np.median(valid_oe)
        
        logger.info(f"Normalized Owner Earnings:")
        logger.info(f"  Using {len(valid_oe)} periods")
        logger.info(f"  Normalized OE: ¥{normalized_oe/100000000:.2f}亿")
        
        return normalized_oe
    
    except Exception as e:
        logger.error(f"Error normalizing owner earnings: {e}")
        return owner_earnings_history[0] if owner_earnings_history else 0
