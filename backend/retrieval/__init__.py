"""Retrieval 包 (向量检索 + 简化重排).

MVP 简化:
- 单次向量检索 (无 Cross-Encoder 重排)
- 无自反馈迭代
- 无多源融合 (只用 Milvus)
"""
from backend.retrieval.vector_search import (
    SearchHit,
    search_by_text,
    search_chunks,
    search_for_writing,
)

__all__ = ["SearchHit", "search_by_text", "search_chunks", "search_for_writing"]
