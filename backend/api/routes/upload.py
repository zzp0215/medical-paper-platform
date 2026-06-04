"""
PDF 上传路由 (Phase 2 完善).

骨架阶段
--------
- 接收 multipart 文件
- 写 MinIO (medpaper-pdfs bucket)
- 计算 SHA-256
- 创建 Document 记录 (status=UPLOADED)
- 后续: 触发 Celery 解析任务 (Phase 2.1.3)
"""
from __future__ import annotations

import io
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend._compat import Annotated
from backend.core import NotFoundError, StorageError, fingerprint, logger, settings
from backend.db import get_async_session
from backend.models import Document, DocumentStatus, KnowledgeBase
from backend.schemas import BatchUploadResponse, KnowledgeBaseCreate, KnowledgeBaseResponse, UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])


# ============================================
# MinIO 客户端 (Phase 1.1.4 用单例; Phase 2 改为连接池)
# ============================================
def _get_minio() -> Minio:
    return Minio(
        settings.minio.endpoint,
        access_key=settings.minio.root_user,
        secret_key=settings.minio.root_password,
        secure=settings.minio.secure,
    )


# ============================================
# 知识库管理
# ============================================
@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建知识库",
)
async def create_kb(
    payload: KnowledgeBaseCreate,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> KnowledgeBase:
    # TODO: owner_id 暂时写死 1, Phase 5 从 JWT 取
    kb = KnowledgeBase(
        owner_id=1,
        name=payload.name,
        description=payload.description,
        specialty=payload.specialty,
    )
    session.add(kb)
    await session.flush()
    await session.refresh(kb)
    return kb


@router.get(
    "/knowledge-bases",
    response_model=list[KnowledgeBaseResponse],
    summary="知识库列表",
)
async def list_kbs(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[KnowledgeBase]:
    result = await session.execute(select(KnowledgeBase).where(KnowledgeBase.deleted_at.is_(None)))
    return list(result.scalars().all())


# ============================================
# 单文件上传
# ============================================
@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上传单个 PDF",
)
async def upload_pdf(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    file: Annotated[UploadFile, File(description="PDF 文件, ≤50MB")],
    kb_id: Annotated[int, Query(description="目标知识库 ID")] = ...,
) -> UploadResponse:
    # 1) 校验 KB
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.is_deleted:
        raise NotFoundError(f"KnowledgeBase {kb_id} not found")

    # 2) 读全文 + 算哈希
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise StorageError("File too large (limit 50MB)")
    sha = fingerprint(content)

    # 3) 去重检查
    dup = await session.execute(select(Document).where(Document.file_sha256 == sha))
    if existing := dup.scalar_one_or_none():
        logger.info("PDF 重复上传 | sha={} → 复用 doc_id={}", sha[:12], existing.id)
        return UploadResponse(
            document_id=existing.id,
            filename=file.filename or "untitled.pdf",
            size=existing.file_size,
            sha256=sha,
            status=existing.status,
            is_duplicate=True,
        )

    # 4) 写 MinIO
    minio = _get_minio()
    object_key = f"{kb_id}/{sha[:2]}/{sha}.pdf"
    try:
        if not minio.bucket_exists(settings.minio.bucket_pdfs):
            minio.make_bucket(settings.minio.bucket_pdfs)
        minio.put_object(
            settings.minio.bucket_pdfs,
            object_key,
            io.BytesIO(content),
            length=len(content),
            content_type="application/pdf",
        )
    except Exception as e:
        raise StorageError(f"MinIO upload failed: {e}") from e

    # 5) 落库
    doc = Document(
        kb_id=kb_id,
        uploader_id=1,  # TODO: 替换为真实用户
        title=(file.filename or "untitled.pdf").rsplit(".", 1)[0],
        file_path=object_key,
        file_size=len(content),
        file_sha256=sha,
        status=DocumentStatus.UPLOADED,
    )
    session.add(doc)
    await session.flush()
    await session.refresh(doc)

    logger.info("PDF 上传成功 | doc_id={} kb_id={} size={}B sha={}", doc.id, kb_id, len(content), sha[:12])

    # TODO Phase 2.1.3: dispatch celery 解析任务
    return UploadResponse(
        document_id=doc.id,
        filename=file.filename or "untitled.pdf",
        size=doc.file_size,
        sha256=sha,
        status=doc.status,
        is_duplicate=False,
        task_id=None,
    )


# ============================================
# 批量上传
# ============================================
@router.post(
    "/batch",
    response_model=BatchUploadResponse,
    summary="批量上传 PDF (≤50 个/批)",
)
async def upload_batch(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    files: Annotated[list[UploadFile], File(description="PDF 文件列表")],
    kb_id: Annotated[int, Query()] = ...,
) -> BatchUploadResponse:
    if not 1 <= len(files) <= 50:
        raise StorageError("Batch size must be 1-50")
    items: list[UploadResponse] = []
    accepted = duplicates = rejected = 0
    for f in files:
        try:
            r = await upload_pdf(session=session, file=f, kb_id=kb_id)
            items.append(r)
            if r.is_duplicate:
                duplicates += 1
            else:
                accepted += 1
        except Exception as e:
            rejected += 1
            logger.warning("批量上传单文件失败 | filename={} err={}", f.filename, e)
    return BatchUploadResponse(
        total=len(files),
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        items=items,
    )
