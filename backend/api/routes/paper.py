"""
论文路由 (Phase 4 完善).

骨架阶段
--------
- CRUD: 创建/查询/列表/删除
- 章节查询
- 状态机推进 (draft → outlining → ...)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend._compat import Annotated
from backend.core import NotFoundError
from backend.db import get_async_session
from backend.models import Paper, PaperSection, PaperStatus
from backend.schemas import (
    Ok,
    Page,
    PaperCreateRequest,
    PaperListItem,
    PaperResponse,
    PaperUpdateRequest,
    SectionResponse,
)

router = APIRouter(prefix="/papers", tags=["papers"])


# ============================================
# 辅助
# ============================================
async def _get_paper_or_404(session: AsyncSession, paper_id: int) -> Paper:
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.is_deleted:
        raise NotFoundError(f"Paper {paper_id} not found")
    return paper


# ============================================
# CRUD
# ============================================
@router.post(
    "",
    response_model=Ok[PaperResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建论文 (草稿)",
)
async def create_paper(
    payload: PaperCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[PaperResponse]:
    paper = Paper(
        owner_id=1,  # TODO: Phase 5 从 JWT 取
        title=payload.title,
        paper_type=payload.paper_type,
        target_language=payload.target_language,
        outline=payload.outline,
        status=PaperStatus.DRAFT,
    )
    session.add(paper)
    await session.flush()
    await session.refresh(paper)
    return Ok(data=PaperResponse.model_validate(paper))


@router.get(
    "",
    response_model=Ok[Page[PaperListItem]],
    summary="论文列表 (分页)",
)
async def list_papers(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: PaperStatus | None = Query(default=None, alias="status"),
) -> Ok[Page[PaperListItem]]:
    # 总数
    count_q = select(func.count(Paper.id)).where(Paper.deleted_at.is_(None), Paper.owner_id == 1)
    if status_filter:
        count_q = count_q.where(Paper.status == status_filter)
    total = (await session.execute(count_q)).scalar_one()

    # 列表
    offset = (page - 1) * page_size
    list_q = (
        select(Paper)
        .where(Paper.deleted_at.is_(None), Paper.owner_id == 1)
        .order_by(Paper.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if status_filter:
        list_q = list_q.where(Paper.status == status_filter)
    rows = (await session.execute(list_q)).scalars().all()

    items = [PaperListItem.model_validate(r) for r in rows]
    return Ok(data=Page.of(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{paper_id}",
    response_model=Ok[PaperResponse],
    summary="论文详情",
)
async def get_paper(
    paper_id: int,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[PaperResponse]:
    paper = await _get_paper_or_404(session, paper_id)
    return Ok(data=PaperResponse.model_validate(paper))


@router.patch(
    "/{paper_id}",
    response_model=Ok[PaperResponse],
    summary="更新论文 (标题/大纲/元数据)",
)
async def update_paper(
    paper_id: int,
    payload: PaperUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[PaperResponse]:
    paper = await _get_paper_or_404(session, paper_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(paper, field, value)
    await session.flush()
    await session.refresh(paper)
    return Ok(data=PaperResponse.model_validate(paper))


@router.delete(
    "/{paper_id}",
    response_model=Ok[None],
    summary="删除论文 (软删)",
)
async def delete_paper(
    paper_id: int,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[None]:
    paper = await _get_paper_or_404(session, paper_id)
    from datetime import datetime, timezone

    paper.deleted_at = datetime.now(tz=timezone.utc)
    return Ok(data=None)


# ============================================
# 章节
# ============================================
@router.get(
    "/{paper_id}/sections",
    response_model=Ok[list[SectionResponse]],
    summary="论文章节列表",
)
async def list_sections(
    paper_id: int,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Ok[list[SectionResponse]]:
    await _get_paper_or_404(session, paper_id)
    result = await session.execute(
        select(PaperSection)
        .where(PaperSection.paper_id == paper_id)
        .order_by(PaperSection.order_index)
    )
    sections = [SectionResponse.model_validate(s) for s in result.scalars().all()]
    return Ok(data=sections)
