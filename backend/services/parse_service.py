"""
PDF 解析服务 (MVP 同步版).

职责
----
1. 接收 PDF 字节
2. 调 PDFParser 解析成 Markdown
3. 文本分块
4. 更新 Document.parse_metadata (markdown + chunks)

不上 Celery 的原因: 单篇 PDF 解析 < 5s, MVP 同步可接受
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import NotFoundError, logger
from backend.models import Document, DocumentStatus
from backend.parser import PyMuPDFParser
from backend.parser.base import ParseResult
from backend.services.text_chunker import Chunk, chunk_markdown


async def parse_and_store(
    session: AsyncSession,
    document_id: int,
) -> ParseResult:
    """解析 PDF 并落库.

    Args:
        session: 异步 DB session
        document_id: Document.id

    Returns:
        ParseResult (含 markdown 和原始 blocks)

    Raises:
        NotFoundError: 文档不存在
    """
    # 1) 查文档
    doc = await session.get(Document, document_id)
    if doc is None or doc.is_deleted:
        raise NotFoundError(f"Document {document_id} not found")

    # 2) 更新状态 → PARSING
    doc.status = DocumentStatus.PARSING
    doc.error_message = None
    await session.flush()

    try:
        # 3) 读文件 (从 MinIO, MVP 阶段先假定本地路径或回退)
        file_bytes = await _read_document_bytes(doc)

        # 4) 解析
        parser = PyMuPDFParser(extract_images=False)
        result = await parser.parse(file_bytes, filename=doc.title + ".pdf")

        # 5) 切块
        chunks = chunk_markdown(result.markdown)

        # 6) 落库
        doc.parse_metadata = {
            "markdown": result.markdown,
            "page_count": result.page_count,
            "parser": result.metadata.get("parser"),
            "elapsed_ms": result.metadata.get("elapsed_ms"),
            "chunk_count": len(chunks),
            "chunk_size_avg": sum(c.metadata["char_count"] for c in chunks) // max(len(chunks), 1),
            "parsed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        doc.status = DocumentStatus.PARSED
        await session.flush()

        logger.info(
            "PDF 解析完成 | doc_id={} pages={} chunks={} elapsed={}ms",
            doc.id, result.page_count, len(chunks), int(result.metadata.get("elapsed_ms", 0)),
        )
        return result

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)[:500]
        await session.flush()
        logger.exception("PDF 解析失败 | doc_id={}", doc.id)
        raise


async def _read_document_bytes(doc: Document) -> bytes:
    """读 PDF 字节 (优先 MinIO, 回退本地路径).

    MVP 阶段: 文件可能在 MinIO, 也可能本地测试时直接落盘到 data/uploads/
    """
    import os
    from pathlib import Path

    # 优先 MinIO
    try:
        from minio import Minio

        from backend.core import settings

        client = Minio(
            settings.minio.endpoint,
            access_key=settings.minio.root_user,
            secret_key=settings.minio.root_password,
            secure=settings.minio.secure,
        )
        resp = client.get_object(settings.minio.bucket_pdfs, doc.file_path)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()
    except Exception as e:
        logger.warning("MinIO 读失败, 回退本地路径 | doc_id={} err={}", doc.id, e)

    # 兜底: 本地路径
    local_path = Path("data/uploads") / doc.file_path
    if local_path.exists():
        return local_path.read_bytes()

    # 测试环境: 允许 mock 字节
    if os.getenv("TESTING") == "1":
        return b"%PDF-1.4\n%%EOF\n"

    raise NotFoundError(f"Document file not found: {doc.file_path}")
