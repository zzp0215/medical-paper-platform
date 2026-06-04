"""
统一错误处理中间件.

设计
----
- 业务异常 (MedPaperError) → 解析 code/message/status_code 后返回 JSON
- Pydantic 校验异常 (RequestValidationError) → 400 + 详细字段错误
- SQLAlchemy 异常 → 500 + 隐藏堆栈 (记日志)
- 未捕获异常 → 500 + 通用消息, 真实错误进日志
- 每个响应附 `X-Request-ID` 便于追踪
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.core import MedPaperError, logger


def _error_payload(
    code: str,
    message: str,
    status_code: int,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "request_id": request_id,
    }


async def _business_error_handler(request: Request, exc: MedPaperError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.warning(
        "业务异常 | code={} status={} path={} request_id={} message={}",
        exc.code, exc.status_code, request.url.path, request_id, exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message, exc.status_code, request_id, exc.details),
        headers={"X-Request-ID": request_id},
    )


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    # 提取字段路径 + 错误信息
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    logger.info("参数校验失败 | path={} request_id={} errors={}", request.url.path, request_id, errors)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_payload(
            "validation_error",
            "Request validation failed",
            400,
            request_id,
            {"errors": errors},
        ),
        headers={"X-Request-ID": request_id},
    )


async def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("数据库异常 | path={} request_id={}", request.url.path, request_id)

    # 唯一约束冲突 → 409
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=409,
            content=_error_payload("conflict", "Database integrity violation", 409, request_id),
            headers={"X-Request-ID": request_id},
        )

    return JSONResponse(
        status_code=500,
        content=_error_payload("database_error", "Database error", 500, request_id),
        headers={"X-Request-ID": request_id},
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("未捕获异常 | path={} request_id={} type={}", request.url.path, request_id, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=_error_payload("internal_error", "Internal server error", 500, request_id),
        headers={"X-Request-ID": request_id},
    )


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable]
) -> Awaitable:
    """每个请求分配 request_id (header 透传或生成)."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def register_error_handlers(app: FastAPI) -> None:
    """注册所有异常处理器."""
    app.add_exception_handler(MedPaperError, _business_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, _sqlalchemy_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
    app.middleware("http")(request_id_middleware)
