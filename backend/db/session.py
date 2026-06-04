"""
异步数据库 Session 工厂.

用法 (FastAPI 依赖)
--------------------
    from backend.db.session import get_async_session

    @router.get("/users")
    async def list_users(session: AsyncSession = Depends(get_async_session)):
        ...

用法 (Celery / 脚本)
---------------------
    from backend.db.session import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(...)
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings

# ============================================
# 引擎
# ============================================
engine: AsyncEngine = create_async_engine(
    settings.database.async_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_pre_ping=True,  # 防 stale connection
    echo=settings.database.echo_sql,
    future=True,
)

# ============================================
# Session 工厂
# ============================================
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ============================================
# FastAPI 依赖
# ============================================
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 路由依赖: 每次请求一个 Session, 结束自动关闭."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
