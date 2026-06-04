"""
Milvus 向量库服务 (MVP 简化版).

Collection Schema
----------------
name: medpaper_chunks
fields:
  - id: INT64 auto (主键)
  - doc_id: INT64
  - kb_id: INT64
  - chunk_index: INT64
  - content: VARCHAR(8192)
  - embedding: FLOAT_VECTOR(1536)
  - metadata: JSON (可选)

使用
----
    from backend.services.milvus_service import get_milvus, ensure_collection

    await ensure_collection()
    await insert_chunks(doc_id, kb_id, [(text, embedding, metadata), ...])
    results = await search(query_embedding, kb_id, top_k=5)
"""
from __future__ import annotations

import asyncio
from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from backend.core import logger, settings

# Collection 名 (按 KB 维度分表; MVP 简化: 单一表)
COLLECTION_NAME = "medpaper_chunks"
VECTOR_DIM = 1536  # text-embedding-3-small


def get_milvus() -> Collection:
    """获取 Collection (单例, 首次调用时连接)."""
    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=settings.milvus.host,
            port=str(settings.milvus.port),
            user=settings.milvus.user,
            password=settings.milvus.password,
            db_name=settings.milvus.db_name,
            timeout=10,
        )
    return Collection(COLLECTION_NAME)


def ensure_collection() -> None:
    """确保 Collection 存在 (创建 + 建索引)."""
    if utility.has_collection(COLLECTION_NAME):
        return

    logger.info("创建 Milvus Collection: {}", COLLECTION_NAME)
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="doc_id", dtype=DataType.INT64),
        FieldSchema(name="kb_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
    ]
    schema = CollectionSchema(fields=fields, description="Medical paper chunks (MVP)")
    col = Collection(name=COLLECTION_NAME, schema=schema)

    # 建 IVF_FLAT 索引 (小数据量够用, 数据大时换 HNSW)
    index_params = {
        "metric_type": "IP",  # 内积 (cosine 相似度等价于归一化后内积)
        "index_type": "IVF_FLAT",
        "params": {"nlist": 64},
    }
    col.create_index(field_name="embedding", index_params=index_params)
    logger.info("Milvus Collection 创建完成 | index=IVF_FLAT nlist=64")


def insert_chunks(
    doc_id: int,
    kb_id: int,
    items: list[dict[str, Any]],  # [{"chunk_index": int, "content": str, "embedding": list[float]}]
) -> list[int]:
    """插入 chunks. 返回插入的 ID 列表.

    同步 (pymilvus 同步 API), 业务层用 asyncio.to_thread 包装.
    """
    if not items:
        return []
    ensure_collection()
    col = get_milvus()
    col.load()

    data = [
        [doc_id] * len(items),
        [kb_id] * len(items),
        [it["chunk_index"] for it in items],
        [it["content"][:8000] for it in items],  # 截断防止超 VARCHAR
        [it["embedding"] for it in items],
    ]
    result = col.insert(data)
    col.flush()
    logger.info("Milvus 插入 | doc_id={} chunks={}", doc_id, len(items))
    return result.primary_keys


def search(
    query_embedding: list[float],
    *,
    kb_id: int | None = None,
    top_k: int = 5,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """向量检索.

    Returns:
        [{"id", "doc_id", "chunk_index", "content", "score"}, ...]
    """
    ensure_collection()
    col = get_milvus()
    col.load()

    expr = f"kb_id == {kb_id}" if kb_id is not None else None
    search_params = {"metric_type": "IP", "params": {"nprobe": 16}}

    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["doc_id", "chunk_index", "content"],
    )

    hits: list[dict[str, Any]] = []
    if results and results[0]:
        for hit in results[0]:
            score = float(hit.score)
            if score < score_threshold:
                continue
            entity = hit.entity
            hits.append(
                {
                    "id": hit.id,
                    "doc_id": entity.get("doc_id"),
                    "chunk_index": entity.get("chunk_index"),
                    "content": entity.get("content", ""),
                    "score": score,
                }
            )
    return hits


def delete_by_doc(doc_id: int) -> int:
    """删除某文档的所有 chunks. 返回删除数."""
    ensure_collection()
    col = get_milvus()
    col.load()
    expr = f"doc_id == {doc_id}"
    result = col.delete(expr)
    col.flush()
    logger.info("Milvus 删除 | doc_id={} count={}", doc_id, result.delete_count)
    return result.delete_count


# ============================================
# 异步包装 (业务层用 await)
# ============================================
async def async_insert_chunks(
    doc_id: int, kb_id: int, items: list[dict[str, Any]]
) -> list[int]:
    return await asyncio.to_thread(insert_chunks, doc_id, kb_id, items)


async def async_search(
    query_embedding: list[float],
    *,
    kb_id: int | None = None,
    top_k: int = 5,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(search, query_embedding, kb_id=kb_id, top_k=top_k, score_threshold=score_threshold)


async def async_delete_by_doc(doc_id: int) -> int:
    return await asyncio.to_thread(delete_by_doc, doc_id)


def health_check() -> dict:
    """同步健康检查 (供 /health/ready 调)."""
    try:
        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=settings.milvus.host,
                port=str(settings.milvus.port),
                user=settings.milvus.user,
                password=settings.milvus.password,
                db_name=settings.milvus.db_name,
                timeout=5,
            )
        # list collections 试通
        utility.list_collections()
        return {"status": "up"}
    except Exception as e:
        return {"status": "down", "error": str(e)}
