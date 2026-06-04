"""
多轮对话修改路由 (Phase 4 / 5 完善).

骨架阶段
--------
- 接收用户消息 + 论文 ID
- 返回占位响应 (Phase 4 接入 LangGraph Supervisor)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend._compat import Annotated
from backend.core import NotFoundError
from backend.db import get_async_session
from backend.models import Paper
from backend.schemas import ChatRequest, ChatResponse, Ok

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=Ok[ChatResponse],
    summary="对话式修改 (Phase 4 接入 LangGraph)",
)
async def chat(
    payload: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[ChatResponse]:
    paper = await session.get(Paper, payload.paper_id)
    if paper is None or paper.is_deleted:
        raise NotFoundError(f"Paper {payload.paper_id} not found")

    # TODO Phase 4: 调用 LangGraph supervisor graph
    return Ok(
        data=ChatResponse(
            paper_id=payload.paper_id,
            reply=(
                f"已收到您对论文《{paper.title}》的修改指令: {payload.message!r}。\n"
                "LangGraph 引擎尚未接入 (Phase 4), 当前为占位响应。"
            ),
            diff=None,
            sections_updated=[],
        )
    )
