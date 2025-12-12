"""
历史报告相关路由模块

此模块提供读取 reports 目录中历史报告文件的 API 端点
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import logging
from typing import List
from datetime import datetime, UTC

from ..models.api_models import ApiResponse

logger = logging.getLogger("reports_router")

# 创建路由器
router = APIRouter(prefix="/reports", tags=["Reports"])


def get_reports_dir():
    """获取 reports 目录路径"""
    # 获取项目根目录
    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(current_file))
    project_root = os.path.dirname(backend_dir)
    reports_dir = os.path.join(project_root, "reports")
    return reports_dir


@router.get("/", response_model=ApiResponse[List[dict]])
async def list_reports():
    """获取所有历史报告文件列表
    
    返回 reports 目录中所有 .md 文件的列表，包含文件名、股票代码和日期信息
    """
    try:
        reports_dir = get_reports_dir()
        
        if not os.path.exists(reports_dir):
            logger.warning(f"Reports directory does not exist: {reports_dir}")
            return ApiResponse(
                success=True,
                message="Reports directory does not exist",
                data=[]
            )
        
        reports = []
        for filename in os.listdir(reports_dir):
            if filename.endswith('.md'):
                # 解析文件名格式: {ticker}_{date}.md
                # 例如: 600330_20251211.md
                name_without_ext = filename[:-3]  # 移除 .md
                parts = name_without_ext.rsplit('_', 1)
                
                ticker = parts[0] if len(parts) > 0 else ''
                date_str = parts[1] if len(parts) > 1 else ''
                
                reports.append({
                    "filename": filename,
                    "ticker": ticker,
                    "date": date_str
                })
        
        # 按文件名倒序排序（最新的在前）
        reports.sort(key=lambda x: x["filename"], reverse=True)
        
        return ApiResponse(
            success=True,
            message=f"Found {len(reports)} reports",
            data=reports
        )
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get("/{filename}", response_model=ApiResponse[dict])
async def get_report(filename: str):
    """获取指定报告文件的内容
    
    参数:
    - filename: 报告文件名，例如: 600330_20251211.md
    """
    try:
        # 安全检查：防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # 确保文件名以 .md 结尾
        if not filename.endswith('.md'):
            raise HTTPException(status_code=400, detail="Only .md files are allowed")
        
        reports_dir = get_reports_dir()
        file_path = os.path.join(reports_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Report file not found: {filename}")
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return ApiResponse(
            success=True,
            message="Report retrieved successfully",
            data={
                "filename": filename,
                "content": content
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading report {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")


@router.get("/{filename}/download")
async def download_report(filename: str):
    """下载指定报告文件
    
    参数:
    - filename: 报告文件名，例如: 600330_20251211.md
    """
    try:
        # 安全检查：防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # 确保文件名以 .md 结尾
        if not filename.endswith('.md'):
            raise HTTPException(status_code=400, detail="Only .md files are allowed")
        
        reports_dir = get_reports_dir()
        file_path = os.path.join(reports_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Report file not found: {filename}")
        
        return FileResponse(
            file_path,
            media_type='text/markdown',
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")
