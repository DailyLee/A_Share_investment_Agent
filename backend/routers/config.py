"""
配置相关路由模块

此模块提供设置和获取系统配置的 API 端点
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging
from typing import Optional

from ..models.api_models import ApiResponse

logger = logging.getLogger("config_router")

# 创建路由器
router = APIRouter(prefix="/api/config", tags=["Config"])

# 内存中存储的配置（仅在运行时有效）
_runtime_config = {
    "OPENAI_COMPATIBLE_API_KEY": None,
    "OPENAI_COMPATIBLE_BASE_URL": None,
    "OPENAI_COMPATIBLE_MODEL": None,
}


class ConfigRequest(BaseModel):
    """配置请求模型"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.post("/set", response_model=ApiResponse[dict])
async def set_config(request: ConfigRequest):
    """设置系统配置
    
    设置 OPENAI_COMPATIBLE_API_KEY、OPENAI_COMPATIBLE_BASE_URL 和 OPENAI_COMPATIBLE_MODEL。
    这些配置会在运行时生效，但不会持久化到环境变量文件中。
    """
    try:
        if request.api_key:
            _runtime_config["OPENAI_COMPATIBLE_API_KEY"] = request.api_key
            os.environ["OPENAI_COMPATIBLE_API_KEY"] = request.api_key
            logger.info("OPENAI_COMPATIBLE_API_KEY has been set")
        
        if request.base_url:
            _runtime_config["OPENAI_COMPATIBLE_BASE_URL"] = request.base_url
            os.environ["OPENAI_COMPATIBLE_BASE_URL"] = request.base_url
            logger.info("OPENAI_COMPATIBLE_BASE_URL has been set")
        
        if request.model:
            _runtime_config["OPENAI_COMPATIBLE_MODEL"] = request.model
            os.environ["OPENAI_COMPATIBLE_MODEL"] = request.model
            logger.info("OPENAI_COMPATIBLE_MODEL has been set")
        
        return ApiResponse(
            success=True,
            message="配置已设置",
            data={
                "api_key_set": request.api_key is not None,
                "base_url_set": request.base_url is not None,
                "model_set": request.model is not None,
            }
        )
    except Exception as e:
        logger.error(f"Error setting config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set config: {str(e)}")


@router.get("/get", response_model=ApiResponse[dict])
async def get_config():
    """获取当前系统配置
    
    返回当前设置的配置值（不包含敏感信息如 API Key 的完整值）
    """
    try:
        # 从环境变量或运行时配置获取
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY") or _runtime_config.get("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL") or _runtime_config.get("OPENAI_COMPATIBLE_BASE_URL")
        model = os.getenv("OPENAI_COMPATIBLE_MODEL") or _runtime_config.get("OPENAI_COMPATIBLE_MODEL")
        
        # 隐藏 API Key 的敏感部分
        api_key_display = None
        if api_key:
            if len(api_key) > 8:
                api_key_display = api_key[:4] + "..." + api_key[-4:]
            else:
                api_key_display = "***"
        
        return ApiResponse(
            success=True,
            message="配置获取成功",
            data={
                "api_key": api_key_display,
                "api_key_set": api_key is not None,
                "base_url": base_url,
                "base_url_set": base_url is not None,
                "model": model,
                "model_set": model is not None,
            }
        )
    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")
