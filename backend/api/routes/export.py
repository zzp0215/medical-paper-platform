"""
Word 导出路由 (Phase 6 完善).

骨架阶段
--------
- 接收 paper_id
- 返回占位提示
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend._compat import Annotated
from backend.core import NotFoundError
from backend.db import get_async_session
from backend.models import Paper
from backend.schemas import Ok

router = APIRouter(prefix="/export", tags=["export"])


@router.post(
    "/word",
    response_model=Ok[dict],
    summary="导出 Word 文档 (Phase 6 接入 word_chat)",
)
async def export_word(
    paper_id: int,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[dict]:
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.is_deleted:
        raise NotFoundError(f"Paper {paper_id} not found")

    # TODO Phase 6: 调 word_chat 渲染 AMA 模板
    return Ok(
        data={
            "paper_id": paper_id,
            "status": "placeholder",
            "message": "Word 导出功能 Phase 6 接入, 当前为占位响应",
            "download_url": None,
        }
    )
