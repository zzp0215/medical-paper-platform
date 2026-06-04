"""
大纲生成 Agent (单 LLM 调用版).

输入: 论文题目 + 类型 + KB 检索结果
输出: PaperOutline (含 sections 列表)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.core import LLMError, logger
from backend.llm import ChatMessage, ChatRequest, LLMRouter
from backend.models.paper import PaperType
from backend.retrieval import search_for_writing

PROMPT_PATH = Path(__file__).parent / "prompts" / "planner.md"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


@dataclass
class OutlineNode:
    """大纲节点."""

    order_index: int
    heading: str
    section_type: str
    description: str
    key_points: list[str] = field(default_factory=list)


@dataclass
class PaperOutline:
    """完整论文大纲."""

    abstract_intent: str
    sections: list[OutlineNode]

    def to_dict(self) -> dict:
        return {
            "abstract_intent": self.abstract_intent,
            "sections": [
                {
                    "order_index": n.order_index,
                    "heading": n.heading,
                    "section_type": n.section_type,
                    "description": n.description,
                    "key_points": n.key_points,
                }
                for n in self.sections
            ],
        }


# 论文类型 → 默认章节结构
DEFAULT_SECTIONS: dict[str, list[dict]] = {
    PaperType.REVIEW.value: [
        ("摘要", "abstract", "概述研究范围与方法"),
        ("引言", "introduction", "背景与研究意义"),
        ("方法", "methods", "文献检索策略与纳入标准"),
        ("结果", "results", "主要发现分类总结"),
        ("讨论", "discussion", "与现有证据对比, 局限性"),
        ("结论", "conclusion", "总结与展望"),
        ("参考文献", "references", ""),
    ],
    PaperType.CLINICAL_TRIAL.value: [
        ("摘要", "abstract", "结构化摘要"),
        ("引言", "introduction", "临床背景与研究假设"),
        ("方法", "methods", "研究设计/对象/干预/终点"),
        ("结果", "results", "基线/主要/次要终点"),
        ("讨论", "discussion", "临床意义与安全性"),
        ("结论", "conclusion", "结论"),
    ],
    PaperType.CASE_REPORT.value: [
        ("摘要", "abstract", "病例要点"),
        ("引言", "introduction", "病例独特性背景"),
        ("病例", "methods", "病史/检查/诊断/治疗"),
        ("结果", "results", "随访与转归"),
        ("讨论", "discussion", "与既往文献比较"),
        ("结论", "conclusion", "经验总结"),
    ],
    PaperType.META_ANALYSIS.value: [
        ("摘要", "abstract", "系统综述结构化摘要"),
        ("引言", "introduction", "PICO 框架"),
        ("方法", "methods", "检索策略/纳入排除/统计模型"),
        ("结果", "results", "文献筛选/特征/合并效应"),
        ("讨论", "discussion", "异质性/敏感性/GRADE"),
        ("结论", "conclusion", "证据等级"),
    ],
    PaperType.BASIC_RESEARCH.value: [
        ("摘要", "abstract", ""),
        ("引言", "introduction", "科学问题与假说"),
        ("材料与方法", "methods", "实验材料/方法"),
        ("结果", "results", "主要发现"),
        ("讨论", "discussion", "机制探讨"),
        ("结论", "conclusion", "总结"),
    ],
    PaperType.OTHER.value: [
        ("摘要", "abstract", ""),
        ("引言", "introduction", ""),
        ("主体", "methods", ""),
        ("结果", "results", ""),
        ("讨论", "discussion", ""),
        ("结论", "conclusion", ""),
    ],
}


def _default_outline(paper_type: str, title: str) -> PaperOutline:
    """LLM 失败时的兜底大纲."""
    sections_data = DEFAULT_SECTIONS.get(paper_type, DEFAULT_SECTIONS[PaperType.OTHER.value])
    return PaperOutline(
        abstract_intent=f"围绕《{title}》展开论述",
        sections=[
            OutlineNode(
                order_index=i + 1,
                heading=h,
                section_type=t,
                description=d or f"本节讨论 {h} 相关内容",
                key_points=[],
            )
            for i, (h, t, d) in enumerate(sections_data)
        ],
    )


async def generate_outline(
    *,
    title: str,
    paper_type: str = PaperType.REVIEW.value,
    target_language: str = "zh",
    kb_id: int | None = None,
) -> PaperOutline:
    """生成论文大纲.

    Args:
        title: 论文题目
        paper_type: 论文类型 (review / clinical_trial / ...)
        target_language: zh / en
        kb_id: 检索用的知识库 ID (None = 跨库)

    Returns:
        PaperOutline
    """
    # 1) 检索参考材料
    context = await search_for_writing(title, kb_id=kb_id, top_k=8)

    # 2) 拼 prompt
    prompt = PROMPT_TEMPLATE.format(
        title=title,
        paper_type=paper_type,
        target_language=("中文" if target_language == "zh" else "English"),
        context_chunks=context[:3000],  # 截断防止超长
    )

    # 3) 调 LLM
    try:
        async with LLMRouter() as router:
            resp = await router.chat(
                request=ChatRequest(
                    messages=[ChatMessage(role="user", content=prompt)],
                    temperature=0.4,
                    max_tokens=2000,
                ),
                scenario="planning",
            )
        return _parse_outline(resp.content, paper_type, title)
    except Exception as e:
        logger.error("大纲生成失败, 用默认大纲兜底 | err={}", e)
        return _default_outline(paper_type, title)


def _parse_outline(content: str, paper_type: str, title: str) -> PaperOutline:
    """解析 LLM 输出的 JSON."""
    # 尝试提取 JSON 块
    json_match = re.search(r"\{[\s\S]*\}", content)
    if not json_match:
        logger.warning("LLM 输出不含 JSON, 用默认大纲")
        return _default_outline(paper_type, title)

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("JSON 解析失败 | err={}", e)
        return _default_outline(paper_type, title)

    abstract = data.get("abstract_intent", f"围绕《{title}》")
    sections_raw = data.get("sections", [])
    if not sections_raw:
        return _default_outline(paper_type, title)

    nodes = []
    for i, s in enumerate(sections_raw):
        nodes.append(
            OutlineNode(
                order_index=s.get("order_index", i + 1),
                heading=s.get("heading", f"第{i+1}节"),
                section_type=s.get("section_type", "introduction"),
                description=s.get("description", ""),
                key_points=s.get("key_points", []),
            )
        )
    return PaperOutline(abstract_intent=abstract, sections=nodes)
