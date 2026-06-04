"""
FastAPI 应用工厂.

使用
----
    from backend.api.main import create_app
    app = create_app()
    # uvicorn backend.api.main:app --reload

设计原则
--------
- 工厂模式: 方便测试时创建独立 app 实例 (e.g. 覆盖 DB session)
- lifespan 管理: 启动/关闭钩子里初始化/释放资源
- 路由/中间件集中注册, 不在工厂里写业务
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from backend import __version__
from backend.api.middleware import access_log_middleware, register_error_handlers
from backend.api.routes import register_routes
from backend.core import logger, settings, setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期: 启动 → 运行 → 关闭."""
    # 启动
    setup_logging(settings)
    logger.info("🚀 启动 {name} v{version} | env={env}", name=settings.app.name, version=__version__, env=settings.app.env)

    # TODO Phase 1.1.5: 初始化 LiteLLM 网关
    # TODO Phase 2.x:  启动 Celery worker (worker 进程独立, 这里只做健康检查)
    # TODO Phase 4.x:  预热 LangGraph 状态图

    yield

    # 关闭
    logger.info("🛑 关闭 {name}", name=settings.app.name)
    # TODO: 关闭 HTTP client / DB engine / Redis pool


def create_app() -> FastAPI:
    """应用工厂."""
    app = FastAPI(
        title="Medical Paper Platform API",
        version=__version__,
        description="医学论文自动生成平台 - 后端 API",
        docs_url="/docs" if settings.app.debug else None,  # 生产关 Swagger
        redoc_url="/redoc" if settings.app.debug else None,
        openapi_url="/openapi.json" if settings.app.debug else None,
        default_response_class=ORJSONResponse,  # 比 json 快 2-3x
        lifespan=lifespan,
    )

    # ---------- 中间件 (顺序敏感) ----------
    # CORS 必须放最前
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # 错误处理 (含 request_id 注入)
    register_error_handlers(app)
    # 访问日志
    app.middleware("http")(access_log_middleware)

    # ---------- 路由 ----------
    register_routes(app)

    return app


# 入口实例 (uvicorn backend.api.main:app)
app = create_app()
