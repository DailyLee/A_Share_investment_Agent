# -*- coding: utf-8 -*-
"""
行业特定的估值参数配置

根据不同行业的特点，设置不同的估值参数：
- 资本密集型行业（如电力、钢铁）：降低要求回报率，提高永续增长率，降低安全边际
- 轻资产行业（如软件、咨询）：维持较高的要求回报率
- 周期性行业（如房地产、汽车）：提高折现率，降低永续增长率
- 成长型行业（如科技、医药）：允许更高的增长率
"""

from typing import Dict, Any

# 行业关键词映射（用于匹配行业分类）
INDUSTRY_KEYWORDS = {
    "utilities": ["电力", "水务", "燃气", "公用事业", "能源"],
    "heavy_industry": ["钢铁", "水泥", "化工", "有色金属", "煤炭", "石油"],
    "technology": ["软件", "互联网", "计算机", "电子", "通信", "半导体", "芯片", "IT"],
    "finance": ["银行", "证券", "保险", "金融"],
    "consumer": ["食品", "饮料", "零售", "纺织", "家电", "消费"],
    "healthcare": ["医药", "医疗", "生物制药", "医疗器械"],
    "real_estate": ["房地产", "建筑", "工程"],
    "manufacturing": ["机械", "汽车", "电气设备", "制造"],
    "services": ["传媒", "教育", "旅游", "文化", "娱乐"],
}

# 默认估值参数（用于未分类行业）
DEFAULT_PARAMS = {
    "owner_earnings": {
        "required_return": 0.10,      # 要求回报率 10%（调整：从12%降低到10%，提高估值合理性）
        "margin_of_safety": 0.15,     # 安全边际 15%（调整：从20%降低到15%，适度保守）
        "terminal_growth_factor": 0.4, # 永续增长率 = growth_rate * 0.4
        "terminal_growth_cap": 0.03,   # 永续增长率上限 3%
        "use_maintenance_capex": False, # 是否只扣除维持性资本支出
        "maintenance_capex_ratio": 0.5, # 维持性资本支出占比（当use_maintenance_capex=True时）
        "use_declining_growth": True,  # 是否使用递减增长率模型
    },
    "dcf": {
        "discount_rate": 0.10,         # 折现率 10%
        "terminal_growth_factor": 0.4, # 永续增长率 = growth_rate * 0.4
        "terminal_growth_cap": 0.03,   # 永续增长率上限 3%
    }
}

# 公用事业行业（电力、水务等）- 现金流稳定，资本密集
UTILITIES_PARAMS = {
    "owner_earnings": {
        "required_return": 0.085,      # 降低要求回报率（现金流稳定，调整：从10%降低到8.5%）
        "margin_of_safety": 0.12,      # 降低安全边际（蓝筹股风险较低，调整：从15%降低到12%）
        "terminal_growth_factor": 0.6, # 提高永续增长率系数
        "terminal_growth_cap": 0.04,   # 永续增长率上限提高到 4%
        "use_maintenance_capex": True, # 只扣除维持性资本支出
        "maintenance_capex_ratio": 0.4, # 维持性资本支出约占总资本支出的40%
        "use_declining_growth": False, # 不使用递减增长率（现金流稳定）
    },
    "dcf": {
        "discount_rate": 0.08,         # 降低折现率（风险较低）
        "terminal_growth_factor": 0.6,
        "terminal_growth_cap": 0.04,
    }
}

# 重工业（钢铁、化工等）- 资本密集，周期性强
HEAVY_INDUSTRY_PARAMS = {
    "owner_earnings": {
        "required_return": 0.13,       # 提高要求回报率（周期性风险）
        "margin_of_safety": 0.25,      # 提高安全边际（周期性风险）
        "terminal_growth_factor": 0.3, # 降低永续增长率
        "terminal_growth_cap": 0.02,   # 永续增长率上限 2%
        "use_maintenance_capex": True, # 只扣除维持性资本支出
        "maintenance_capex_ratio": 0.5,
        "use_declining_growth": True,  # 使用递减增长率（周期性行业）
    },
    "dcf": {
        "discount_rate": 0.11,
        "terminal_growth_factor": 0.3,
        "terminal_growth_cap": 0.02,
    }
}

# 科技行业（软件、互联网等）- 轻资产，高成长
TECHNOLOGY_PARAMS = {
    "owner_earnings": {
        "required_return": 0.15,       # 提高要求回报率（高风险高回报）
        "margin_of_safety": 0.20,      # 标准安全边际
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.05,   # 允许更高的永续增长率 5%
        "use_maintenance_capex": False, # 轻资产，全部扣除资本支出
        "maintenance_capex_ratio": 0.3,
        "use_declining_growth": False,  # 不使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.12,         # 提高折现率（风险较高）
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.05,
    }
}

# 金融行业（银行、保险等）- 特殊估值逻辑
FINANCE_PARAMS = {
    "owner_earnings": {
        "required_return": 0.11,
        "margin_of_safety": 0.20,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
        "use_maintenance_capex": False,
        "maintenance_capex_ratio": 0.2, # 金融行业资本支出较少
    },
    "dcf": {
        "discount_rate": 0.09,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
    }
}

# 消费行业（食品饮料、零售等）- 稳定增长
CONSUMER_PARAMS = {
    "owner_earnings": {
        "required_return": 0.11,
        "margin_of_safety": 0.18,      # 降低安全边际（需求稳定）
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.04,
        "use_maintenance_capex": False,
        "maintenance_capex_ratio": 0.4,
        "use_declining_growth": False,  # 不使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.09,
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.04,
    }
}

# 医药健康（医药、医疗器械等）- 高成长，高壁垒
HEALTHCARE_PARAMS = {
    "owner_earnings": {
        "required_return": 0.13,
        "margin_of_safety": 0.20,
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.05,
        "use_maintenance_capex": False,
        "maintenance_capex_ratio": 0.3,
        "use_declining_growth": False,  # 不使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.11,
        "terminal_growth_factor": 0.5,
        "terminal_growth_cap": 0.05,
    }
}

# 房地产（房地产、建筑等）- 高杠杆，周期性强
REAL_ESTATE_PARAMS = {
    "owner_earnings": {
        "required_return": 0.14,       # 高要求回报率（高杠杆风险）
        "margin_of_safety": 0.30,      # 高安全边际（周期性、政策风险）
        "terminal_growth_factor": 0.3,
        "terminal_growth_cap": 0.02,
        "use_maintenance_capex": False,
        "maintenance_capex_ratio": 0.3,
        "use_declining_growth": True,  # 使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.12,
        "terminal_growth_factor": 0.3,
        "terminal_growth_cap": 0.02,
    }
}

# 制造业（机械、汽车等）- 中等资本密集，周期性
MANUFACTURING_PARAMS = {
    "owner_earnings": {
        "required_return": 0.12,
        "margin_of_safety": 0.22,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
        "use_maintenance_capex": True,
        "maintenance_capex_ratio": 0.5,
        "use_declining_growth": True,  # 使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.10,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
    }
}

# 服务业（传媒、教育等）- 轻资产
SERVICES_PARAMS = {
    "owner_earnings": {
        "required_return": 0.13,
        "margin_of_safety": 0.20,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
        "use_maintenance_capex": False,
        "maintenance_capex_ratio": 0.3,
        "use_declining_growth": False,  # 不使用递减增长率
    },
    "dcf": {
        "discount_rate": 0.11,
        "terminal_growth_factor": 0.4,
        "terminal_growth_cap": 0.03,
    }
}

# 行业参数映射
INDUSTRY_PARAMS = {
    "utilities": UTILITIES_PARAMS,
    "heavy_industry": HEAVY_INDUSTRY_PARAMS,
    "technology": TECHNOLOGY_PARAMS,
    "finance": FINANCE_PARAMS,
    "consumer": CONSUMER_PARAMS,
    "healthcare": HEALTHCARE_PARAMS,
    "real_estate": REAL_ESTATE_PARAMS,
    "manufacturing": MANUFACTURING_PARAMS,
    "services": SERVICES_PARAMS,
    "default": DEFAULT_PARAMS,
}


def classify_industry(industry_name: str) -> str:
    """
    根据行业名称分类到预定义的行业类别
    
    Args:
        industry_name: 行业名称（中文）
        
    Returns:
        str: 行业类别代码
    """
    if not industry_name:
        return "default"
    
    industry_name = industry_name.strip()
    
    # 遍历关键词映射
    for industry_code, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in industry_name:
                return industry_code
    
    return "default"


def get_valuation_params(industry_name: str) -> Dict[str, Any]:
    """
    获取指定行业的估值参数
    
    Args:
        industry_name: 行业名称（中文）
        
    Returns:
        Dict: 包含 owner_earnings 和 dcf 参数的字典
    """
    industry_code = classify_industry(industry_name)
    params = INDUSTRY_PARAMS.get(industry_code, DEFAULT_PARAMS)
    
    return {
        "industry_code": industry_code,
        "industry_name": industry_name,
        **params
    }


def get_industry_description(industry_code: str) -> str:
    """获取行业类别的中文描述"""
    descriptions = {
        "utilities": "公用事业（电力/水务/燃气）",
        "heavy_industry": "重工业（钢铁/化工/有色）",
        "technology": "科技行业（软件/互联网/电子）",
        "finance": "金融行业（银行/证券/保险）",
        "consumer": "消费行业（食品/零售/家电）",
        "healthcare": "医药健康（医药/医疗器械）",
        "real_estate": "房地产（地产/建筑）",
        "manufacturing": "制造业（机械/汽车/电气）",
        "services": "服务业（传媒/教育/旅游）",
        "default": "综合/其他行业"
    }
    return descriptions.get(industry_code, "未分类")
