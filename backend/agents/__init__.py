"""Agents (MVP 简化版).

只保留: planner_simple + writer_simple
复杂多 Agent 编排 (Phase 4 完整版) 留到交付优化阶段.
"""
from backend.agents.planner_simple import (
    generate_outline,
    OutlineNode,
    PaperOutline,
)
from backend.agents.writer_simple import write_section, write_all_sections

__all__ = [
    "generate_outline",
    "OutlineNode",
    "PaperOutline",
    "write_section",
    "write_all_sections",
]
