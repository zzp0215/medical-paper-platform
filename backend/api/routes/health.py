"""
健康检查路由.

- /health       liveness  (进程是否响应)
- /health/ready readiness (依赖是否就绪, 失败 K8s 不接流量)
- /health/info  版本/环境信息

所有依赖检查都设了 2s 超时, 不阻塞响应.
"""
from __future__ import annotations

import asyncio
import time

import asyncpg
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Response, status
from minio import Minio
from pymilvus import connections as milvus_connections
from redis.asyncio import from_url as redis_from_url

from backend import __version__
from backend.core import settings
from backend.schemas import ComponentHealth, HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


# ============================================
# 各组件探活 (带超时)
# ============================================
async def _check_db() -> ComponentHealth:
    """PostgreSQL."""
    t0 = time.perf_counter()
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(
                host=settings.database.host,
                port=settings.database.port,
                user=settings.database.user,
                password=settings.database.password,
                database=settings.database.db,
            ),
            timeout=2.0,
        )
        await conn.execute("SELECT 1")
        await conn.close()
        return ComponentHealth(status="up", latency_ms=(time.perf_counter() - t0) * 1000)
    except Exception as e:
        return ComponentHealth(status="down", detail=f"{type(e).__name__}: {e}")


async def _check_redis() -> ComponentHealth:
    """Redis."""
    t0 = time.perf_counter()
    try:
        client = redis_from_url(settings.redis.url, decode_responses=True)
        try:
            await asyncio.wait_for(client.ping(), timeout=2.0)
            return ComponentHealth(status="up", latency_ms=(time.perf_counter() - t0) * 1000)
        finally:
            await client.aclose()
    except Exception as e:
        return ComponentHealth(status="down", detail=f"{type(e).__name__}: {e}")


async def _check_minio() -> ComponentHealth:
    """MinIO."""
    t0 = time.perf_counter()
    try:
        client = Minio(
            settings.minio.endpoint,
            access_key=settings.minio.root_user,
            secret_key=settings.minio.root_password,
            secure=settings.minio.secure,
        )

        def _ping() -> None:
            # minio-py 是同步的, 跑在线程池
            client.bucket_exists(settings.minio.bucket_pdfs)

        await asyncio.wait_for(asyncio.to_thread(_ping), timeout=2.0)
        return ComponentHealth(status="up", latency_ms=(time.perf_counter() - t0) * 1000)
    except Exception as e:
        return ComponentHealth(status="down", detail=f"{type(e).__name__}: {e}")


async def _check_milvus() -> ComponentHealth:
    """Milvus."""
    t0 = time.perf_counter()
    try:
        # pymilvus 是同步的, 包到线程池
        def _ping() -> None:
            milvus_connections.connect(
                alias="healthcheck",
                host=settings.milvus.host,
                port=str(settings.milvus.port),
                user=settings.milvus.user,
                password=settings.milvus.password,
                db_name=settings.milvus.db_name,
                timeout=2.0,
            )
            milvus_connections.disconnect("healthcheck")

        await asyncio.wait_for(asyncio.to_thread(_ping), timeout=3.0)
        return ComponentHealth(status="up", latency_ms=(time.perf_counter() - t0) * 1000)
    except Exception as e:
        return ComponentHealth(status="down", detail=f"{type(e).__name__}: {e}")


async def _check_es() -> ComponentHealth:
    """Elasticsearch."""
    t0 = time.perf_counter()
    try:
        es = AsyncElasticsearch(
            hosts=[settings.elasticsearch.url],
            basic_auth=(settings.elasticsearch.user, settings.elasticsearch.password),
            request_timeout=2.0,
        )
        try:
            await es.cluster.health()
            return ComponentHealth(status="up", latency_ms=(time.perf_counter() - t0) * 1000)
        finally:
            await es.close()
    except Exception as e:
        return ComponentHealth(status="down", detail=f"{type(e).__name__}: {e}")


# ============================================
# 路由
# ============================================
@router.get("", response_model=HealthStatus, summary="Liveness probe (仅检查进程)")
async def liveness() -> HealthStatus:
    return HealthStatus(
        status="ok",
        version=__version__,
        env=settings.app.env,
        components={},
    )


@router.get("/ready", response_model=HealthStatus, summary="Readiness probe (检查全部依赖)")
async def readiness(response: Response) -> HealthStatus:
    # 并行探活, 总耗时 = max(单个耗时)
    db_task = asyncio.create_task(_check_db())
    redis_task = asyncio.create_task(_check_redis())
    minio_task = asyncio.create_task(_check_minio())
    milvus_task = asyncio.create_task(_check_milvus())
    es_task = asyncio.create_task(_check_es())

    components = {
        "postgres": await db_task,
        "redis": await redis_task,
        "minio": await minio_task,
        "milvus": await milvus_task,
        "elasticsearch": await es_task,
    }
    all_up = all(c.status == "up" for c in components.values())
    degraded = any(c.status == "up" for c in components.values()) and not all_up

    if not all_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthStatus(
        status="ok" if all_up else ("degraded" if degraded else "down"),
        version=__version__,
        env=settings.app.env,
        components=components,
    )


@router.get("/info", summary="服务信息 (版本/环境/路径)")
async def info() -> dict:
    return {
        "name": settings.app.name,
        "version": __version__,
        "env": settings.app.env,
        "debug": settings.app.debug,
        "api_v1_prefix": settings.app.api_v1_prefix,
        "phase": "1.1.4 - FastAPI skeleton",
    }
