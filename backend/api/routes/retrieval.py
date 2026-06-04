"""
检索 API (MVP).

POST /api/v1/retrieval/search
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend._compat import Annotated as _A  # noqa: F401
from backend.retrieval import SearchHit, search_by_text

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    kb_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=2.0)


class RetrievalResponse(BaseModel):
    query: str
    hits: list[dict]
    count: int


@router.post("/search", response_model=RetrievalResponse, summary="向量检索")
async def search(payload: RetrievalRequest) -> RetrievalResponse:
    hits: list[SearchHit] = await search_by_text(
        payload.query,
        kb_id=payload.kb_id,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
    )
    return RetrievalResponse(
        query=payload.query,
        hits=[h.to_dict() for h in hits],
        count=len(hits),
    )
