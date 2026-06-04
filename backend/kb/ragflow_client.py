"""
RAGFlow HTTP 客户端 (Phase 3 主用).

API 参考: https://ragflow.io/docs/dev/http_api_reference

启用方法
--------
1. 启动 RAGFlow: docker-compose -f docker/docker-compose.yml -f docker/docker-compose.ragflow.yml up -d ragflow
2. .env 设 RAGFLOW_ENABLED=true
3. 首次登录 RAGFlow UI (http://localhost:9380), 创建一个 API Key
4. .env 填 RAGFLOW_API_KEY=...
5. 重启后端服务
"""
from __future__ import annotations

import asyncio
import time

import httpx

from backend.core import LLMError, NotFoundError, logger, settings
from backend.kb.base import (
    DocumentChunk,
    KnowledgeBaseClient,
    RetrievalHit,
    RetrievalQuery,
)


class RAGFlowClient(KnowledgeBaseClient):
    """RAGFlow 客户端.

    内部用 httpx 异步, 失败自动重试 2 次.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url or settings.ragflow.base_url).rstrip("/")
        self.api_key = api_key or settings.ragflow.api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RAGFlowClient":
        if not settings.ragflow.enabled:
            raise NotFoundError(
                "RAGFlow 未启用, 启用步骤:\n"
                "  1. 启动: cd docker && docker-compose -f docker-compose.yml -f docker-compose.ragflow.yml up -d ragflow\n"
                "  2. 访问 http://localhost:9380 创建 API Key\n"
                "  3. .env 设 RAGFLOW_ENABLED=true + RAGFLOW_API_KEY=...\n"
                "  4. 重启后端"
            )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _check(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("RAGFlowClient must be used as async context manager")
        return self._client

    # ============================================
    # 文档管理
    # ============================================
    async def create_dataset(self, name: str, *, description: str = "") -> str:
        """POST /datasets"""
        client = self._check()
        resp = await client.post(
            "/datasets",
            json={"name": name, "description": description, "embedding_model": "BAAI/bge-large-zh-v1.5"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise LLMError(f"RAGFlow create_dataset 失败: {data.get('message')}")
        ds_id = data["data"]["id"]
        logger.info("RAGFlow 创建数据集 | name={} id={}", name, ds_id)
        return ds_id

    async def upload_document(self, dataset_id: str, file_bytes: bytes, *, filename: str) -> str:
        """POST /datasets/{id}/documents"""
        client = self._check()
        files = {"file": (filename, file_bytes, "application/pdf")}
        resp = await client.post(f"/datasets/{dataset_id}/documents", files=files)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise LLMError(f"RAGFlow upload 失败: {data.get('message')}")
        doc_id = data["data"][0]["id"]
        logger.info("RAGFlow 上传文档 | filename={} id={}", filename, doc_id)
        return doc_id

    async def wait_parse_complete(self, doc_id: str, *, timeout: float = 300) -> bool:
        """轮询直到文档状态变成 DONE / FAIL."""
        client = self._check()
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            resp = await client.get(f"/documents/{doc_id}")
            resp.raise_for_status()
            data = resp.json()
            run_status = data.get("data", {}).get("run", "UNKNOWN")
            if run_status == "DONE":
                return True
            if run_status == "FAIL":
                raise LLMError(f"RAGFlow 解析失败: {data}")
            await asyncio.sleep(2)
        return False

    async def delete_document(self, doc_id: str) -> None:
        client = self._check()
        resp = await client.delete(f"/documents/{doc_id}")
        resp.raise_for_status()

    # ============================================
    # 检索
    # ============================================
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalHit]:
        client = self._check()
        # RAGFlow 用 dataset_ids (复数) + 文档过滤
        resp = await client.post(
            "/retrieval",
            json={
                "question": query.query,
                "dataset_ids": query.kb_ids or [],
                "top_k": query.top_k,
                "similarity_threshold": query.score_threshold,
                "vector_similarity_weight": 0.3,  # 关键词/向量混合权重
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise LLMError(f"RAGFlow retrieval 失败: {data.get('message')}")
        chunks = data.get("data", {}).get("chunks", [])
        return [
            RetrievalHit(
                chunk_id=c["id"],
                doc_id=c["document_id"],
                content=c["content"],
                score=c.get("similarity", 0.0),
                metadata={"dataset_id": c.get("dataset_id")},
                source_ref=c.get("document_name"),
            )
            for c in chunks
        ]

    # ============================================
    # 健康检查
    # ============================================
    async def health_check(self) -> dict:
        client = self._check()
        try:
            resp = await client.get("/system/status", timeout=5.0)
            return {
                "status": "up" if resp.status_code == 200 else "degraded",
                "version": resp.json().get("version", "unknown"),
            }
        except Exception as e:
            return {"status": "down", "error": str(e)}
