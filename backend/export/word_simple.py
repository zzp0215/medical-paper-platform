"""
Word 导出 (MVP 简化版).

用 python-docx 生成 IMRaD 格式 Word.
样式: 标题层级 / 正文 / 引用列表
"""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt, RGBColor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import NotFoundError, logger
from backend.models import Paper, PaperSection


async def export_paper_to_docx(
    session: AsyncSession,
    paper_id: int,
) -> bytes:
    """生成 Word 文档字节流.

    Args:
        session: DB session
        paper_id: Paper.id

    Returns:
        docx 文件字节

    Raises:
        NotFoundError: 论文不存在
    """
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.is_deleted:
        raise NotFoundError(f"Paper {paper_id} not found")

    # 拿所有 sections
    sections = (
        await session.execute(
            select(PaperSection)
            .where(PaperSection.paper_id == paper_id)
            .order_by(PaperSection.order_index)
        )
    ).scalars().all()

    # 创建 docx
    doc = Document()

    # ---------- 标题 ----------
    title_para = doc.add_heading(paper.title, level=0)
    title_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    # 元信息
    meta = doc.add_paragraph()
    meta.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    meta_run = meta.add_run(
        f"生成时间: {datetime.now().strftime('%Y-%m-%d')}  |  "
        f"类型: {paper.paper_type}  |  "
        f"语言: {paper.target_language}"
    )
    meta_run.font.size = Pt(9)
    meta_run.font.color.rgb = RGBColor(128, 128, 128)

    doc.add_paragraph()  # 空行

    # ---------- 摘要意图 (如有) ----------
    if paper.outline and paper.outline.get("abstract_intent"):
        intent = paper.outline["abstract_intent"]
        p = doc.add_paragraph()
        run = p.add_run(f"摘要意图: {intent}")
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(100, 100, 100)

    # ---------- 章节 ----------
    for sec in sections:
        # 跳过空内容 (如 references 留后期处理)
        if not sec.content_md:
            continue

        # 标题
        if sec.section_type == "abstract":
            doc.add_heading(sec.heading, level=1)
        elif sec.section_type in ("introduction", "methods", "results", "discussion", "conclusion"):
            doc.add_heading(f"{sec.order_index}. {sec.heading}", level=1)
        else:
            doc.add_heading(sec.heading, level=2)

        # 内容 (按段落切)
        for paragraph_text in sec.content_md.split("\n\n"):
            paragraph_text = paragraph_text.strip()
            if not paragraph_text:
                continue
            # 处理 Markdown 标记
            if paragraph_text.startswith("### "):
                doc.add_heading(paragraph_text[4:], level=3)
            elif paragraph_text.startswith("## "):
                doc.add_heading(paragraph_text[3:], level=2)
            elif paragraph_text.startswith("# "):
                doc.add_heading(paragraph_text[2:], level=1)
            elif paragraph_text.startswith("- "):
                # 列表
                p = doc.add_paragraph(paragraph_text[2:], style="List Bullet")
            else:
                p = doc.add_paragraph(paragraph_text)
                # 段落格式
                for run in p.runs:
                    run.font.size = Pt(11)

    # ---------- 落款 ----------
    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    footer_run = footer.add_run("—— 完 ——")
    footer_run.font.size = Pt(10)
    footer_run.font.color.rgb = RGBColor(128, 128, 128)

    # 序列化为字节
    buf = io.BytesIO()
    doc.save(buf)
    doc_bytes = buf.getvalue()
    buf.close()

    logger.info(
        "Word 导出完成 | paper_id={} sections={} size={}KB",
        paper_id, len(sections), len(doc_bytes) // 1024,
    )
    return doc_bytes
