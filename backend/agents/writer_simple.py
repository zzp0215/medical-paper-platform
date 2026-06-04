"""
写作 Agent (单 LLM 调用版).

- write_section: 写一节
- write_all_sections: 顺序写完全部章节
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from backend.agents.planner_simple import OutlineNode, PaperOutline
from backend.core import LLMError, logger
from backend.llm import ChatMessage, ChatRequest, LLMRouter
from backend.retrieval import search_for_writing

PROMPT_PATH = Path(__file__).parent / "prompts" / "writer.md"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


async def write_section(
    *,
    title: str,           # 论文题目
    paper_type: str,
    section: OutlineNode,
    kb_id: int | None = None,
    target_language: str = "zh",
) -> str:
    """写一个章节.

    Returns:
        Markdown 文本
    """
    # 1) 检索本节相关参考材料
    query = f"{section.heading} {section.description} {' '.join(section.key_points)}"
    context = await search_for_writing(query, kb_id=kb_id, top_k=5)

    # 2) 拼 prompt
    prompt = PROMPT_TEMPLATE.format(
        title=title,
        paper_type=paper_type,
        heading=section.heading,
        section_type=section.section_type,
        key_points="\n".join(f"- {p}" for p in section.key_points) or "(无)",
        description=section.description,
        context_chunks=context[:2500],
    )

    # 3) 调 LLM
    async with LLMRouter() as router:
        resp = await router.chat(
            request=ChatRequest(
                messages=[ChatMessage(role="user", content=prompt)],
                temperature=0.5,
                max_tokens=1500,
            ),
            scenario="writing",
        )
    return resp.content.strip()


async def write_all_sections(
    *,
    title: str,
    paper_type: str,
    outline: PaperOutline,
    kb_id: int | None = None,
    target_language: str = "zh",
    skip_types: list[str] | None = None,
) -> dict[int, str]:
    """顺序写完全部章节 (MVP: 串行, 后期可并行).

    Args:
        skip_types: 跳过的 section_type (如 ['references'] 由 Citation Agent 后期处理)
        target_language: zh / en

    Returns:
        {order_index: markdown_content}
    """
    skip_types = skip_types or ["references"]
    results: dict[int, str] = {}

    for node in outline.sections:
        if node.section_type in skip_types:
            logger.info("跳过章节 | type={} heading={}", node.section_type, node.heading)
            results[node.order_index] = ""  # 占位
            continue

        logger.info(
            "写作 | [{}/{}] {} ({})",
            node.order_index, len(outline.sections), node.heading, node.section_type,
        )
        try:
            content = await write_section(
                title=title,
                paper_type=paper_type,
                section=node,
                kb_id=kb_id,
                target_language=target_language,
            )
            results[node.order_index] = content
        except Exception as e:
            logger.error("章节写作失败 | heading={} err={}", node.heading, e)
            results[node.order_index] = f"(写作失败: {e})"

    return results
