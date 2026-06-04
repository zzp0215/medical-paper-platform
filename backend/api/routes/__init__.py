"""API 路由统一注册."""
from fastapi import APIRouter

from backend.api.routes import chat, export, health, paper, retrieval, upload


def register_routes(app_router: APIRouter) -> None:
    """把所有子路由挂到主 router 上."""
    # health 挂到根 (不挂 v1, 方便 K8s 探针)
    app_router.include_router(health.router)

    # 业务路由全部走 /api/v1 前缀
    app_router.include_router(upload.router, prefix="/api/v1")
    app_router.include_router(retrieval.router, prefix="/api/v1")
    app_router.include_router(paper.router, prefix="/api/v1")
    app_router.include_router(chat.router, prefix="/api/v1")
    app_router.include_router(export.router, prefix="/api/v1")


__all__ = ["register_routes"]
