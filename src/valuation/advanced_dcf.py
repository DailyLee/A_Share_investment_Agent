# -*- coding: utf-8 -*-
"""
改进的DCF估值模型

基于市场原则的DCF模型实现：
1. 三阶段增长模型（高增长期 -> 过渡期 -> 永续期）
2. WACC（加权平均资本成本）计算
3. 更准确的自由现金流预测
4. 敏感性分析
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from src.utils.logging_config import setup_logger

logger = setup_logger('advanced_dcf')


def calculate_wacc(
    risk_free_rate: float,
    market_risk_premium: float,
    beta: float,
    total_debt: float,
    total_equity: float,
    cost_of_debt: float,
    tax_rate: float
) -> float:
    """
    计算加权平均资本成本（WACC）
    
    WACC = (E/V) × Re + (D/V) × Rd × (1 - Tc)
    
    其中：
    - E = 权益市值
    - D = 债务价值
    - V = E + D（企业总价值）
    - Re = 权益成本（使用CAPM: Re = Rf + β × MRP）
    - Rd = 债务成本
    - Tc = 企业税率
    
    Args:
        risk_free_rate: 无风险利率（中国10年期国债收益率，约2.5-3%）
        market_risk_premium: 市场风险溢价（约6-8%）
        beta: 贝塔系数（如无法获取，使用行业平均beta）
        total_debt: 总债务
        total_equity: 股东权益
        cost_of_debt: 债务成本（如无法获取，使用市场平均利率）
        tax_rate: 有效税率
    
    Returns:
        float: WACC
    """
    try:
        # 计算权益成本（CAPM）
        cost_of_equity = risk_free_rate + beta * market_risk_premium
        
        # 计算企业总价值
        total_value = total_debt + total_equity
        
        if total_value <= 0:
            logger.warning("Invalid total value, using default WACC of 10%")
            return 0.10
        
        # 计算权重
        equity_weight = total_equity / total_value
        debt_weight = total_debt / total_value
        
        # 计算WACC
        wacc = (equity_weight * cost_of_equity + 
                debt_weight * cost_of_debt * (1 - tax_rate))
        
        # 确保WACC在合理范围内（5%-20%）
        wacc = max(0.05, min(wacc, 0.20))
        
        logger.info(f"WACC Calculation:")
        logger.info(f"  Cost of Equity: {cost_of_equity:.2%}")
        logger.info(f"  Cost of Debt (after tax): {cost_of_debt * (1 - tax_rate):.2%}")
        logger.info(f"  Equity Weight: {equity_weight:.2%}")
        logger.info(f"  Debt Weight: {debt_weight:.2%}")
        logger.info(f"  WACC: {wacc:.2%}")
        
        return wacc
    
    except Exception as e:
        logger.error(f"Error calculating WACC: {e}")
        return 0.10  # 默认返回10%


def estimate_growth_rates(
    historical_fcf: List[float],
    historical_revenue: List[float],
    historical_ebit: List[float],
    industry_growth: float = 0.05
) -> Tuple[float, float, float]:
    """
    估算三阶段增长率
    
    Args:
        historical_fcf: 历史自由现金流（从最新到最早）
        historical_revenue: 历史营收（从最新到最早）
        historical_ebit: 历史EBIT（从最新到最早）
        industry_growth: 行业平均增长率
    
    Returns:
        Tuple[float, float, float]: (高增长期增长率, 过渡期起始增长率, 永续增长率)
    """
    try:
        # 计算历史增长率
        fcf_growth_rates = []
        revenue_growth_rates = []
        ebit_growth_rates = []
        
        # 计算各指标的年化增长率
        for i in range(len(historical_fcf) - 1):
            if historical_fcf[i+1] > 0:
                fcf_gr = (historical_fcf[i] / historical_fcf[i+1]) ** (1/1) - 1
                if -0.5 < fcf_gr < 1.0:  # 过滤异常值
                    fcf_growth_rates.append(fcf_gr)
            
            if historical_revenue[i+1] > 0:
                rev_gr = (historical_revenue[i] / historical_revenue[i+1]) ** (1/1) - 1
                if -0.3 < rev_gr < 0.5:  # 过滤异常值
                    revenue_growth_rates.append(rev_gr)
            
            if historical_ebit[i+1] > 0:
                ebit_gr = (historical_ebit[i] / historical_ebit[i+1]) ** (1/1) - 1
                if -0.5 < ebit_gr < 1.0:  # 过滤异常值
                    ebit_growth_rates.append(ebit_gr)
        
        # 计算平均增长率（使用中位数减少异常值影响）
        avg_fcf_growth = np.median(fcf_growth_rates) if fcf_growth_rates else industry_growth
        avg_revenue_growth = np.median(revenue_growth_rates) if revenue_growth_rates else industry_growth
        avg_ebit_growth = np.median(ebit_growth_rates) if ebit_growth_rates else industry_growth
        
        # 高增长期增长率：使用历史增长率的加权平均，但不超过30%
        # 权重：营收增长率 40%，EBIT增长率 30%，FCF增长率 30%
        high_growth_rate = (0.4 * avg_revenue_growth + 
                           0.3 * avg_ebit_growth + 
                           0.3 * avg_fcf_growth)
        high_growth_rate = max(0, min(high_growth_rate, 0.30))  # 限制在0-30%
        
        # 如果历史增长率过低或为负，使用行业增长率
        if high_growth_rate < 0.03:
            high_growth_rate = max(industry_growth, 0.05)
        
        # 过渡期起始增长率：高增长期的70%
        transition_growth_rate = high_growth_rate * 0.7
        
        # 永续增长率：使用中国GDP长期增长率（约3-4%）
        terminal_growth_rate = 0.03
        
        logger.info(f"Growth Rate Estimation:")
        logger.info(f"  Historical FCF Growth: {avg_fcf_growth:.2%}")
        logger.info(f"  Historical Revenue Growth: {avg_revenue_growth:.2%}")
        logger.info(f"  Historical EBIT Growth: {avg_ebit_growth:.2%}")
        logger.info(f"  High Growth Rate (Stage 1): {high_growth_rate:.2%}")
        logger.info(f"  Transition Growth Rate (Stage 2 start): {transition_growth_rate:.2%}")
        logger.info(f"  Terminal Growth Rate (Stage 3): {terminal_growth_rate:.2%}")
        
        return high_growth_rate, transition_growth_rate, terminal_growth_rate
    
    except Exception as e:
        logger.error(f"Error estimating growth rates: {e}")
        return 0.08, 0.05, 0.03  # 默认值


def calculate_three_stage_dcf(
    initial_fcf: float,
    high_growth_rate: float,
    transition_growth_rate: float,
    terminal_growth_rate: float,
    wacc: float,
    high_growth_years: int = 5,
    transition_years: int = 5,
    total_debt: float = 0,
    cash_and_equivalents: float = 0,
    shares_outstanding: float = 0
) -> Dict[str, Any]:
    """
    三阶段DCF估值模型
    
    阶段1（高增长期）: 5年，使用较高的增长率
    阶段2（过渡期）: 5年，增长率线性下降
    阶段3（永续期）: 永续，使用稳定的永续增长率
    
    企业价值 = 阶段1现值 + 阶段2现值 + 阶段3现值
    股权价值 = 企业价值 + 现金 - 债务
    每股价值 = 股权价值 / 总股本
    
    Args:
        initial_fcf: 初始自由现金流（最近一期）
        high_growth_rate: 高增长期增长率
        transition_growth_rate: 过渡期起始增长率
        terminal_growth_rate: 永续增长率
        wacc: 加权平均资本成本
        high_growth_years: 高增长期年数
        transition_years: 过渡期年数
        total_debt: 总债务
        cash_and_equivalents: 现金及现金等价物
        shares_outstanding: 总股本
    
    Returns:
        Dict包含估值结果和详细信息
    """
    try:
        if initial_fcf <= 0:
            logger.warning("Initial FCF is non-positive, cannot perform DCF valuation")
            return {
                'enterprise_value': 0,
                'equity_value': 0,
                'value_per_share': 0,
                'stage1_value': 0,
                'stage2_value': 0,
                'stage3_value': 0,
                'error': 'Invalid initial FCF'
            }
        
        if wacc <= terminal_growth_rate:
            logger.warning(f"WACC ({wacc:.2%}) must be greater than terminal growth rate ({terminal_growth_rate:.2%})")
            wacc = terminal_growth_rate + 0.03  # 至少大3个百分点
        
        logger.info("\n=== Three-Stage DCF Valuation ===")
        logger.info(f"Initial FCF: ¥{initial_fcf/100000000:.2f}亿")
        logger.info(f"WACC: {wacc:.2%}")
        
        # 阶段1：高增长期
        stage1_fcf = []
        stage1_pv = []
        current_fcf = initial_fcf
        
        logger.info(f"\nStage 1: High Growth Period ({high_growth_years} years, {high_growth_rate:.2%} growth)")
        for year in range(1, high_growth_years + 1):
            current_fcf = current_fcf * (1 + high_growth_rate)
            discount_factor = (1 + wacc) ** year
            pv = current_fcf / discount_factor
            stage1_fcf.append(current_fcf)
            stage1_pv.append(pv)
            logger.info(f"  Year {year}: FCF = ¥{current_fcf/100000000:.2f}亿, PV = ¥{pv/100000000:.2f}亿")
        
        stage1_value = sum(stage1_pv)
        logger.info(f"  Stage 1 Total PV: ¥{stage1_value/100000000:.2f}亿")
        
        # 阶段2：过渡期（增长率线性递减）
        stage2_fcf = []
        stage2_pv = []
        
        # 计算每年增长率递减的幅度
        growth_decline_per_year = (transition_growth_rate - terminal_growth_rate) / transition_years
        
        logger.info(f"\nStage 2: Transition Period ({transition_years} years)")
        logger.info(f"  Growth rate declines from {transition_growth_rate:.2%} to {terminal_growth_rate:.2%}")
        
        current_growth = transition_growth_rate
        for year in range(1, transition_years + 1):
            current_fcf = current_fcf * (1 + current_growth)
            discount_factor = (1 + wacc) ** (high_growth_years + year)
            pv = current_fcf / discount_factor
            stage2_fcf.append(current_fcf)
            stage2_pv.append(pv)
            logger.info(f"  Year {high_growth_years + year}: FCF = ¥{current_fcf/100000000:.2f}亿 (growth {current_growth:.2%}), PV = ¥{pv/100000000:.2f}亿")
            current_growth -= growth_decline_per_year
            current_growth = max(current_growth, terminal_growth_rate)  # 不低于永续增长率
        
        stage2_value = sum(stage2_pv)
        logger.info(f"  Stage 2 Total PV: ¥{stage2_value/100000000:.2f}亿")
        
        # 阶段3：永续期
        # 永续价值 = FCF(n+1) / (WACC - g)
        # FCF(n+1) = 最后一期FCF × (1 + terminal_growth_rate)
        terminal_fcf = current_fcf * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (wacc - terminal_growth_rate)
        
        # 折现到现在
        total_years = high_growth_years + transition_years
        stage3_pv = terminal_value / ((1 + wacc) ** total_years)
        
        logger.info(f"\nStage 3: Terminal Value")
        logger.info(f"  Terminal FCF: ¥{terminal_fcf/100000000:.2f}亿")
        logger.info(f"  Terminal Value: ¥{terminal_value/100000000:.2f}亿")
        logger.info(f"  Terminal Value PV: ¥{stage3_pv/100000000:.2f}亿")
        
        # 计算企业价值
        enterprise_value = stage1_value + stage2_value + stage3_pv
        
        logger.info(f"\n=== Valuation Summary ===")
        logger.info(f"Stage 1 PV: ¥{stage1_value/100000000:.2f}亿 ({stage1_value/enterprise_value:.1%})")
        logger.info(f"Stage 2 PV: ¥{stage2_value/100000000:.2f}亿 ({stage2_value/enterprise_value:.1%})")
        logger.info(f"Stage 3 PV: ¥{stage3_pv/100000000:.2f}亿 ({stage3_pv/enterprise_value:.1%})")
        logger.info(f"Enterprise Value: ¥{enterprise_value/100000000:.2f}亿")
        
        # 计算股权价值
        equity_value = enterprise_value + cash_and_equivalents - total_debt
        logger.info(f"+ Cash: ¥{cash_and_equivalents/100000000:.2f}亿")
        logger.info(f"- Debt: ¥{total_debt/100000000:.2f}亿")
        logger.info(f"= Equity Value: ¥{equity_value/100000000:.2f}亿")
        
        # 计算每股价值
        value_per_share = 0
        if shares_outstanding > 0:
            value_per_share = equity_value / shares_outstanding
            logger.info(f"Shares Outstanding: {shares_outstanding/100000000:.2f}亿股")
            logger.info(f"Value Per Share: ¥{value_per_share:.2f}")
        
        return {
            'enterprise_value': enterprise_value,
            'equity_value': equity_value,
            'value_per_share': value_per_share,
            'stage1_value': stage1_value,
            'stage2_value': stage2_value,
            'stage3_value': stage3_pv,
            'stage1_fcf': stage1_fcf,
            'stage2_fcf': stage2_fcf,
            'terminal_fcf': terminal_fcf,
            'wacc': wacc,
            'high_growth_rate': high_growth_rate,
            'terminal_growth_rate': terminal_growth_rate
        }
    
    except Exception as e:
        logger.error(f"Error in three-stage DCF calculation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'enterprise_value': 0,
            'equity_value': 0,
            'value_per_share': 0,
            'stage1_value': 0,
            'stage2_value': 0,
            'stage3_value': 0,
            'error': str(e)
        }


def calculate_dcf_with_sensitivity(
    initial_fcf: float,
    high_growth_rate: float,
    transition_growth_rate: float,
    terminal_growth_rate: float,
    wacc: float,
    high_growth_years: int = 5,
    transition_years: int = 5,
    total_debt: float = 0,
    cash_and_equivalents: float = 0,
    shares_outstanding: float = 0,
    sensitivity_range: float = 0.01
) -> Dict[str, Any]:
    """
    带敏感性分析的DCF估值
    
    Args:
        sensitivity_range: 敏感性分析的范围（如0.01表示±1%）
    
    Returns:
        Dict包含基准估值和敏感性分析结果
    """
    # 基准估值
    base_valuation = calculate_three_stage_dcf(
        initial_fcf, high_growth_rate, transition_growth_rate, terminal_growth_rate,
        wacc, high_growth_years, transition_years, total_debt, cash_and_equivalents, shares_outstanding
    )
    
    # WACC敏感性分析
    wacc_sensitivity = {}
    for delta in [-0.02, -0.01, 0, 0.01, 0.02]:
        adjusted_wacc = wacc + delta
        if adjusted_wacc > terminal_growth_rate:
            result = calculate_three_stage_dcf(
                initial_fcf, high_growth_rate, transition_growth_rate, terminal_growth_rate,
                adjusted_wacc, high_growth_years, transition_years, total_debt, cash_and_equivalents, shares_outstanding
            )
            wacc_sensitivity[f"{adjusted_wacc:.2%}"] = result['equity_value']
    
    # 增长率敏感性分析
    growth_sensitivity = {}
    for delta in [-0.02, -0.01, 0, 0.01, 0.02]:
        adjusted_growth = high_growth_rate + delta
        if 0 < adjusted_growth < 0.5:
            adjusted_transition = transition_growth_rate + delta * 0.7
            result = calculate_three_stage_dcf(
                initial_fcf, adjusted_growth, adjusted_transition, terminal_growth_rate,
                wacc, high_growth_years, transition_years, total_debt, cash_and_equivalents, shares_outstanding
            )
            growth_sensitivity[f"{adjusted_growth:.2%}"] = result['equity_value']
    
    logger.info("\n=== Sensitivity Analysis ===")
    logger.info("WACC Sensitivity:")
    for wacc_val, eq_val in wacc_sensitivity.items():
        logger.info(f"  WACC {wacc_val}: Equity Value = ¥{eq_val/100000000:.2f}亿")
    
    logger.info("\nGrowth Rate Sensitivity:")
    for growth_val, eq_val in growth_sensitivity.items():
        logger.info(f"  Growth {growth_val}: Equity Value = ¥{eq_val/100000000:.2f}亿")
    
    base_valuation['sensitivity'] = {
        'wacc': wacc_sensitivity,
        'growth': growth_sensitivity
    }
    
    return base_valuation
