"""
上下文管理器模块

提供各种API相关的上下文管理器
"""

from contextlib import contextmanager
import logging

from ..state import api_state

logger = logging.getLogger("context_managers")


@contextmanager
def workflow_run(run_id: str):
    """
    工作流运行上下文管理器

    用法:
    with workflow_run(run_id):
        # 执行工作流
    """
    logger.info(f"🔵 workflow_run 上下文管理器：注册运行 {run_id}")
    api_state.register_run(run_id)
    logger.info(f"✅ workflow_run 上下文管理器：运行已注册 {run_id}")
    try:
        logger.info(f"🟢 workflow_run 上下文管理器：进入 yield，准备执行工作流 {run_id}")
        yield
        logger.info(f"🟡 workflow_run 上下文管理器：yield 返回，工作流执行完成 {run_id}")
        api_state.complete_run(run_id, "completed")
        logger.info(f"✅ workflow_run 上下文管理器：运行状态已更新为 completed {run_id}")
    except Exception as e:
        logger.error(f"❌ workflow_run 上下文管理器：捕获异常 {run_id}: {type(e).__name__}: {str(e)}")
        api_state.complete_run(run_id, "error")
        logger.info(f"⚠️ workflow_run 上下文管理器：运行状态已更新为 error {run_id}")
        raise
