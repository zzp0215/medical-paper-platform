"""知识库管理 (Phase 3 完善).

策略 (2026-06-04)
-----------------
- 优先 RAGFlow (知识库地基, DeepDoc 解析)
- 备选 LocalKB (用平台自带的 PostgreSQL + Milvus + ES, 轻量)

业务层只调用 KnowledgeBaseClient 抽象接口, 切换后端不影响上层.
"""
from backend.kb.base import (
    DocumentChunk,
    KnowledgeBaseClient,
    RetrievalHit,
    RetrievalQuery,
)
from backend.kb.local_kb import LocalKBClient
from backend.kb.ragflow_client import RAGFlowClient

# 工厂: 根据 settings 自动选实现
def get_default_client() -> KnowledgeBaseClient:
    """根据 settings.ragflow.enabled 返回对应实现."""
    from backend.core import settings

    if settings.ragflow.enabled:
        return RAGFlowClient()
    return LocalKBClient()


__all__ = [
    "KnowledgeBaseClient",
    "DocumentChunk",
    "RetrievalQuery",
    "RetrievalHit",
    "RAGFlowClient",
    "LocalKBClient",
    "get_default_client",
]
