"""
Embedding 服务 (调 LiteLLM /embeddings).

当前: text-embedding-3-small (1536 维, OpenAI 兼容)
后期: 可切换 BGE-M3 (本地) 通过 settings.embedding.use_local
"""
from __future__ import annotations

import asyncio
from typing import Iterable

from backend.core import logger, settings
from backend.llm.client import LLMClient
from backend.llm.models import EmbeddingRequest


async def embed_texts(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """批量文本 → 向量.

    Args:
        texts: 文本列表
        model: 模型名 (None = 用 settings)

    Returns:
        与 texts 等长的向量列表

    Note:
        OpenAI 单次最多 2048 个输入, 大批量自动分批
    """
    if not texts:
        return []

    model = model or settings.llm.embedding_model
    batch_size = settings.embedding.batch_size * 10  # embedding 一次可吃更多

    all_embeddings: list[list[float]] = []

    async with LLMClient() as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                resp = await client.embed(
                    EmbeddingRequest(model=model, input=batch, encoding_format="float")
                )
                # 按 index 排序
                sorted_data = sorted(resp.data, key=lambda d: d.index)
                all_embeddings.extend([d.embedding for d in sorted_data])
            except Exception as e:
                logger.error("Embedding 失败 | batch={}..{} | err={}", i, i + len(batch), e)
                # 失败兜底: 用零向量占位 (后续检索会过滤)
                all_embeddings.extend([[0.0] * settings.llm.embedding_dim] * len(batch))

    logger.info("Embedding 完成 | texts={} dim={}", len(texts), settings.llm.embedding_dim)
    return all_embeddings


async def embed_query(query: str, *, model: str | None = None) -> list[float]:
    """单 query → 向量."""
    embeddings = await embed_texts([query], model=model)
    return embeddings[0] if embeddings else [0.0] * settings.llm.embedding_dim
