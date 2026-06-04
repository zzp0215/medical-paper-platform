"""
向量化编排: 文档 chunks → embedding → 入 Milvus.

触发点
------
- Document 状态变 PARSED 后自动向量化
- 用户手动重新触发 (KB 重建)
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import logger
from backend.models import Document, DocumentStatus
from backend.services import milvus_service, parse_service
from backend.services.embedding_service import embed_texts
from backend.services.text_chunker import chunk_markdown


async def vectorize_document(
    session: AsyncSession,
    document_id: int,
) -> int:
    """对已解析文档做向量化并入库.

    Args:
        session: DB session
        document_id: Document.id

    Returns:
        入库 chunk 数

    流程
    ----
    1. 读 Document.parse_metadata.markdown
    2. 文本分块 (与 parse_service 保持一致)
    3. 批量 embedding
    4. 入 Milvus
    5. 更新 Document.status = READY
    """
    doc = await session.get(Document, document_id)
    if doc is None or doc.is_deleted:
        from backend.core import NotFoundError

        raise NotFoundError(f"Document {document_id} not found")

    if doc.status not in (DocumentStatus.PARSED, DocumentStatus.READY):
        raise ValueError(f"Document {document_id} 状态 {doc.status} 不允许向量化 (需要 PARSED/READY)")

    markdown = (doc.parse_metadata or {}).get("markdown", "")
    if not markdown:
        raise ValueError(f"Document {document_id} 解析内容为空")

    # 1) 分块
    chunks = chunk_markdown(markdown)
    if not chunks:
        logger.warning("Document {} 切块为空, 跳过", document_id)
        return 0

    # 2) embedding
    texts = [c.text for c in chunks]
    embeddings = await embed_texts(texts)

    # 3) 入库 Milvus
    items = [
        {
            "chunk_index": c.index,
            "content": c.text,
            "embedding": emb,
        }
        for c, emb in zip(chunks, embeddings, strict=True)
    ]
    ids = await milvus_service.async_insert_chunks(
        doc_id=doc.id, kb_id=doc.kb_id, items=items
    )

    # 4) 更新状态
    doc.status = DocumentStatus.READY
    # 把 chunk_ids 存到 metadata 便于溯源
    doc.parse_metadata = {
        **(doc.parse_metadata or {}),
        "milvus_ids": ids,
        "vectorized_at": __import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ).isoformat(),
    }
    # 更新 KB 统计
    await _update_kb_stats(session, doc.kb_id)

    logger.info("Document {} 向量化完成 | chunks={} ids={}", doc.id, len(ids), ids[:3])
    return len(ids)


async def _update_kb_stats(session: AsyncSession, kb_id: int) -> None:
    """更新知识库的 doc_count / chunk_count."""
    from sqlalchemy import func, select

    from backend.models import Document, KnowledgeBase

    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None:
        return

    doc_count = await session.scalar(
        select(func.count(Document.id)).where(
            Document.kb_id == kb_id, Document.deleted_at.is_(None)
        )
    )
    kb.doc_count = doc_count or 0
    # chunk_count 近似为: 文档数 * 平均 chunk
    # 准确做法: Milvus SQL count(*), 但慢. MVP 简单累加
    kb.chunk_count = sum(
        (d.parse_metadata or {}).get("chunk_count", 0)
        for d in (await session.execute(
            select(Document).where(Document.kb_id == kb_id, Document.deleted_at.is_(None))
        )).scalars().all()
    )


async def full_pipeline(
    session: AsyncSession,
    document_id: int,
) -> dict:
    """完整流程: 解析 + 向量化.

    失败回滚: 任一步失败, 文档状态置 FAILED
    """
    from backend.core import ParseError

    doc = await session.get(Document, document_id)
    if doc is None:
        from backend.core import NotFoundError

        raise NotFoundError(f"Document {document_id} not found")

    try:
        await parse_service.parse_and_store(session, document_id)
        chunk_count = await vectorize_document(session, document_id)
        return {"doc_id": document_id, "chunks": chunk_count, "status": "ready"}
    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)[:500]
        await session.flush()
        raise ParseError(f"Pipeline failed: {e}") from e
