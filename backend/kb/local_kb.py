"""
本地知识库 (Phase 1.2.2 验证用).

用平台自带的:
- PostgreSQL (Document/KB 元数据)
- Milvus (向量检索, BGE-M3 → text-embedding-3-small)
- Elasticsearch (倒排索引, BM25 兜底)

优点: 不用额外起 RAGFlow (省 8G 内存), 适合 MVP
缺点: 缺少 DeepDoc 深度文档理解 (RAGFlow 的强项), 公式/表格解析弱
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

from backend.core import LLMError, logger, settings
from backend.kb.base import (
    DocumentChunk,
    KnowledgeBaseClient,
    RetrievalHit,
    RetrievalQuery,
)
from backend.llm import LLMClient


class LocalKBClient(KnowledgeBaseClient):
    """基于 PostgreSQL + Milvus + ES 的轻量 KB.

    注意: 当前实现是 Phase 1.2.2 的骨架版本, 完整功能 (Milvus 索引管理 /
    ES 索引 mapping / 多源融合 / 自反馈) 留到 Phase 3.2 完善.
    """

    def __init__(self) -> None:
        self._llm: LLMClient | None = None

    async def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
            await self._llm.__aenter__()
        return self._llm

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._llm:
            await self._llm.__aexit__(exc_type, exc, tb)
            self._llm = None

    # ============================================
    # 文档管理 (Phase 3.2 完整实现, 当前先存元数据)
    # ============================================
    async def create_dataset(self, name: str, *, description: str = "") -> str:
        """当前简化版: 用 name 的 hash 作为 dataset_id."""
        ds_id = "ds_" + hashlib.sha256(name.encode()).hexdigest()[:16]
        logger.info("LocalKB 创建数据集 (mock) | name={} id={}", name, ds_id)
        return ds_id

    async def upload_document(
        self, dataset_id: str, file_bytes: bytes, *, filename: str
    ) -> str:
        """当前简化版: 只生成 doc_id, 不实际入库."""
        sha = hashlib.sha256(file_bytes).hexdigest()[:24]
        doc_id = f"doc_{sha}"
        logger.info("LocalKB 上传文档 (mock) | filename={} id={}", filename, doc_id)
        return doc_id

    async def wait_parse_complete(self, doc_id: str, *, timeout: float = 300) -> bool:
        """本地版本没有解析流程, 直接返回 True."""
        return True

    async def delete_document(self, doc_id: str) -> None:
        logger.info("LocalKB 删除文档 (mock) | id={}", doc_id)

    # ============================================
    # 检索 (Phase 1.2.2 基础版: 调 LLM 简单匹配)
    # ============================================
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalHit]:
        """简化版检索: 调用 LLM 生成 "假设答案" + 占位命中.

        Phase 3.2 完整版会:
        1. query → embedding (text-embedding-3-small)
        2. Milvus 向量检索 top_k=20
        3. ES 关键词检索 top_k=20
        4. 融合 + 重排 → top_k
        5. 自反馈: LLM 审查结果, 决定是否再检索
        """
        # 当前阶段: 返回一个占位命中, 让上层链路可走通
        logger.warning(
            "LocalKB.retrieve 还在 stub 阶段 (Phase 3.2 完善), "
            "返回占位命中 | query={!r}",
            query.query[:50],
        )
        return [
            RetrievalHit(
                chunk_id="placeholder_1",
                doc_id="placeholder_doc",
                content=f"[LocalKB stub] 检索查询: {query.query}",
                score=0.5,
                metadata={"note": "Phase 3.2 完整实现 Milvus+ES 融合检索"},
            )
        ]

    # ============================================
    # 健康检查
    # ============================================
    async def health_check(self) -> dict:
        """检查 Milvus + ES + LLM 链路."""
        result: dict[str, Any] = {
            "status": "up",
            "backend": "local",
            "components": {},
        }
        # 测 LLM
        try:
            llm = await self._get_llm()
            # ping via models list
            from openai import AsyncOpenAI

            async with AsyncOpenAI(base_url=llm.base_url, api_key=llm.api_key, timeout=5.0) as c:
                await c.models.list()
            result["components"]["litellm"] = "up"
        except Exception as e:
            result["components"]["litellm"] = f"down: {e}"
            result["status"] = "degraded"

        # Milvus / ES 留 Phase 3.2 加 (要连真实服务)
        result["components"]["milvus"] = "not_checked"
        result["components"]["elasticsearch"] = "not_checked"

        return result
