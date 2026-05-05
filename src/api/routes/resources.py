"""资源下载状态 API。"""
from fastapi import APIRouter
from src.model_download import resources_ready, start_download, get_download_state

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/status")
def resource_status():
    """返回资源就绪状态和下载进度。"""
    state = get_download_state()
    return {
        "ready": resources_ready(),
        "downloading": state["downloading"],
        "progress": state["progress"],
        "total": state["total"],
        "error": state["error"],
    }


@router.post("/download")
def trigger_download():
    """触发资源下载（后台执行）。"""
    if resources_ready():
        return {"message": "资源已就绪", "ready": True}
    start_download()
    return {"message": "下载已开始", "ready": False}
