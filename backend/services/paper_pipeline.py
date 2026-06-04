"""
论文生成完整流水线 (MVP 一键).

流程
----
1. 创建 Paper (status=DRAFT)
2. 检索 KB, 生成大纲 → 存 Paper.outline, status=OUTLINE_READY
3. 用户确认大纲 (Human-in-Loop) → status=WRITING
4. 顺序写每节 → 存 PaperSection.content_md, status=REVIEWING
5. 拼装, 状态 COMPLETED
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents import (
    OutlineNode,
    PaperOutline,
    generate_outline,
    write_all_sections,
    write_section,
)
from backend.core import NotFoundError, logger
from backend.models import Paper, PaperSection, PaperStatus


async def create_paper_with_outline(
    session: AsyncSession,
    *,
    owner_id: int,
    title: str,
    paper_type: str = "review",
    target_language: str = "zh",
    kb_id: int | None = None,
) -> Paper:
    """创建论文 + 生成大纲.

    Args:
        session: DB session
        owner_id: 用户 ID (MVP 写死 1)
        title: 论文题目
        paper_type: 类型
        target_language: zh / en
        kb_id: 检索用的知识库 (None = 跨库)

    Returns:
        Paper (status=OUTLINE_READY)
    """
    # 1) 建论文
    paper = Paper(
        owner_id=owner_id,
        title=title,
        paper_type=paper_type,
        target_language=target_language,
        status=PaperStatus.OUTLINING,
    )
    session.add(paper)
    await session.flush()
    logger.info("Paper 创建 | id={} title={!r}", paper.id, title[:30])

    # 2) 生成大纲
    outline = await generate_outline(
        title=title, paper_type=paper_type,
        target_language=target_language, kb_id=kb_id,
    )

    # 3) 存大纲到 Paper
    paper.outline = outline.to_dict()
    paper.status = PaperStatus.OUTLINE_READY
    paper.progress = 20  # 大纲生成 20%
    await session.flush()

    # 4) 创建 Section 记录 (空内容, 等写作填充)
    for node in outline.sections:
        section = PaperSection(
            paper_id=paper.id,
            order_index=node.order_index,
            heading=node.heading,
            section_type=node.section_type,
            content_md=None,
            word_count=0,
        )
        session.add(section)
    await session.flush()

    logger.info("Paper 大纲就绪 | id={} sections={}", paper.id, len(outline.sections))
    return paper


async def write_paper_sections(
    session: AsyncSession,
    paper_id: int,
) -> Paper:
    """对已确认大纲的 Paper 写全部章节.

    Args:
        session: DB session
        paper_id: Paper.id (status=OUTLINE_READY)

    Returns:
        Paper (status=COMPLETED, sections 全部填好)
    """
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.is_deleted:
        raise NotFoundError(f"Paper {paper_id} not found")
    if paper.status != PaperStatus.OUTLINE_READY:
        raise ValueError(f"Paper {paper_id} 状态 {paper.status} 不允许写作 (需 OUTLINE_READY)")

    # 1) 切到 WRITING
    paper.status = PaperStatus.WRITING
    paper.progress = 30
    await session.flush()

    # 2) 反序列化大纲
    if not paper.outline:
        raise ValueError(f"Paper {paper_id} 大纲为空")
    sections_data = paper.outline.get("sections", [])
    nodes = [
        OutlineNode(
            order_index=s["order_index"],
            heading=s["heading"],
            section_type=s["section_type"],
            description=s.get("description", ""),
            key_points=s.get("key_points", []),
        )
        for s in sections_data
    ]
    outline = PaperOutline(
        abstract_intent=paper.outline.get("abstract_intent", ""),
        sections=nodes,
    )

    # 3) 拿 KB ID (从 metadata 或第一篇文档反查, MVP 简化: 用 None 跨库检索)
    kb_id = (paper.metadata_json or {}).get("kb_id")

    # 4) 写所有章节
    section_results = await write_all_sections(
        title=paper.title,
        paper_type=paper.paper_type.value if hasattr(paper.paper_type, "value") else str(paper.paper_type),
        outline=outline,
        kb_id=kb_id,
        target_language=paper.target_language,
    )

    # 5) 落库
    sections = (
        await session.execute(
            select(PaperSection)
            .where(PaperSection.paper_id == paper_id)
            .order_by(PaperSection.order_index)
        )
    ).scalars().all()

    for sec in sections:
        content = section_results.get(sec.order_index, "")
        sec.content_md = content
        # 中文字数 (按字符) + 英文按词
        sec.word_count = len(content) if paper.target_language == "zh" else len(content.split())

    # 6) 状态推进
    paper.status = PaperStatus.COMPLETED
    paper.progress = 100
    await session.flush()

    logger.info("Paper 写作完成 | id={} sections={}", paper.id, len(sections))
    return paper


async def generate_full_paper(
    session: AsyncSession,
    *,
    owner_id: int,
    title: str,
    paper_type: str = "review",
    target_language: str = "zh",
    kb_id: int | None = None,
    auto_confirm: bool = True,
) -> Paper:
    """一键生成完整论文 (大纲 + 写作).

    Args:
        auto_confirm: True=跳过 Human-in-Loop, 直接写; False=只生成大纲
    """
    paper = await create_paper_with_outline(
        session,
        owner_id=owner_id,
        title=title,
        paper_type=paper_type,
        target_language=target_language,
        kb_id=kb_id,
    )

    if auto_confirm:
        paper = await write_paper_sections(session, paper.id)

    return paper
