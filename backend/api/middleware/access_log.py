"""访问日志中间件."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request

from backend.core import logger


async def access_log_middleware(request: Request, call_next: Callable[[Request], Awaitable]) -> Awaitable:
    """记录每个请求的耗时 + 状态码."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    request_id = getattr(request.state, "request_id", "-")
    # 跳过高频健康检查日志 (降噪)
    if request.url.path in ("/health", "/health/", "/api/v1/health", "/api/v1/health/"):
        return response

    logger.info(
        "{method} {path} | {status} | {elapsed:.1f}ms | {client} | rid={rid}",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed=elapsed_ms,
        client=request.client.host if request.client else "-",
        rid=request_id,
    )
    return response
