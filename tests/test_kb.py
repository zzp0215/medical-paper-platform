"""
知识库客户端测试 (Phase 1.2.2).

LocalKBClient: 基础接口 (不依赖外部服务)
RAGFlowClient: 接口存在性 + 未启用行为
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


# ============================================
# LocalKBClient
# ============================================
class TestLocalKB:
    """LocalKB 接口."""

    def test_create_dataset(self) -> None:
        from backend.kb import LocalKBClient

        async def _run() -> None:
            client = LocalKBClient()
            ds_id = await client.create_dataset("test")
            assert ds_id.startswith("ds_")
            assert len(ds_id) > 10

        asyncio.run(_run())

    def test_upload_document_idempotent(self) -> None:
        from backend.kb import LocalKBClient

        async def _run() -> None:
            client = LocalKBClient()
            content = b"hello world"
            doc_id = await client.upload_document("ds_x", content, filename="a.pdf")
            # 同样内容 → 同样 doc_id (sha256 决定)
            doc_id2 = await client.upload_document("ds_x", content, filename="b.pdf")
            assert doc_id == doc_id2

        asyncio.run(_run())

    def test_retrieve_returns_list(self) -> None:
        from backend.kb import LocalKBClient, RetrievalQuery

        async def _run() -> None:
            client = LocalKBClient()
            hits = await client.retrieve(RetrievalQuery(query="test", top_k=3))
            assert isinstance(hits, list)
            # 当前 stub 阶段, 返回占位
            assert len(hits) >= 1

        asyncio.run(_run())

    def test_health_check_structure(self) -> None:
        from backend.kb import LocalKBClient

        async def _run() -> None:
            client = LocalKBClient()
            health = await client.health_check()
            assert "status" in health
            assert health["backend"] == "local"
            assert "components" in health

        asyncio.run(_run())


# ============================================
# RAGFlowClient
# ============================================
class TestRAGFlow:
    """RAGFlow 客户端 (未启用场景)."""

    def test_disabled_raises(self) -> None:
        """RAGFLOW_ENABLED=false (默认) 应抛 NotFoundError."""
        from backend.kb import RAGFlowClient
        from backend.core import NotFoundError

        async def _run() -> None:
            with pytest.raises(NotFoundError, match="RAGFlow 未启用"):
                async with RAGFlowClient() as _:
                    pass

        asyncio.run(_run())

    def test_interface_inherits_base(self) -> None:
        """RAGFlowClient 必须实现 KnowledgeBaseClient 接口."""
        from backend.kb import RAGFlowClient
        from backend.kb.base import KnowledgeBaseClient

        assert issubclass(RAGFlowClient, KnowledgeBaseClient)


# ============================================
# 工厂
# ============================================
class TestFactory:
    """默认客户端工厂."""

    def test_default_returns_local(self) -> None:
        """RAGFLOW_ENABLED=false 时, 工厂返回 LocalKBClient."""
        from backend.kb import get_default_client, LocalKBClient

        client = get_default_client()
        # 默认未启用, 应是 LocalKB
        assert isinstance(client, LocalKBClient)
