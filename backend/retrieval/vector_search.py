"""
向量检索 (MVP 简化版).

提供
----
- search_by_text: 给定文本查询, 走 embedding → Milvus
- search_chunks:  给定 embedding 直接搜
- search_for_writing: 写作场景专用 (返回带元数据的 chunk 列表, 给 LLM 拼 prompt)
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.core import logger
from backend.services.embedding_service import embed_query
from backend.services.milvus_service import async_search


@dataclass
class SearchHit:
    """检索命中."""

    chunk_id: int
    doc_id: int
    chunk_index: int
    content: str
    score: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "score": self.score,
        }


async def search_by_text(
    query: str,
    *,
    kb_id: int | None = None,
    top_k: int = 5,
    score_threshold: float = 0.0,
) -> list[SearchHit]:
    """文本查询 → 检索 hits.

    Args:
        query: 查询文本
        kb_id: 限定知识库 (None = 跨库)
        top_k: 返回数
        score_threshold: 相似度阈值 (IP 内积, 0-2, 经验 0.5+)
    """
    if not query.strip():
        return []

    query_emb = await embed_query(query)
    return await search_chunks(
        query_emb, kb_id=kb_id, top_k=top_k, score_threshold=score_threshold
    )


async def search_chunks(
    query_embedding: list[float],
    *,
    kb_id: int | None = None,
    top_k: int = 5,
    score_threshold: float = 0.0,
) -> list[SearchHit]:
    """向量检索 (直接给 embedding)."""
    raw = await async_search(
        query_embedding, kb_id=kb_id, top_k=top_k, score_threshold=score_threshold
    )
    return [
        SearchHit(
            chunk_id=r["id"],
            doc_id=r["doc_id"],
            chunk_index=r["chunk_index"],
            content=r["content"],
            score=r["score"],
        )
        for r in raw
    ]


async def search_for_writing(
    topic: str,
    *,
    kb_id: int | None = None,
    top_k: int = 5,
) -> str:
    """写作场景专用: 检索 + 格式化为给 LLM 用的 prompt 片段.

    返回的字符串可以直接拼到 writer prompt 里, 形如:
        [1] (doc=12, score=0.87)
        内容片段...
    """
    hits = await search_by_text(topic, kb_id=kb_id, top_k=top_k, score_threshold=0.3)
    if not hits:
        return "(无相关文献)"

    blocks: list[str] = []
    for i, h in enumerate(hits, 1):
        snippet = h.content[:500] + ("..." if len(h.content) > 500 else "")
        blocks.append(f"[{i}] (doc={h.doc_id}, score={h.score:.2f})\n{snippet}")
    return "\n\n".join(blocks)
