"""
文本分块器 (MVP 简化版).

策略
----
- 按段落 (\\n\\n) 切分
- 单块超过 chunk_size 时再按句子切
- 块之间保留少量 overlap (上下文)

不用 LangChain splitter 的原因: 简化依赖, 加快 MVP
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """文本块."""

    text: str
    index: int
    metadata: dict | None = None


def chunk_markdown(
    markdown: str,
    *,
    chunk_size: int = 500,      # 目标块大小 (字符)
    chunk_overlap: int = 50,    # 块间重叠
    min_chunk_size: int = 50,   # 最小块, 过短的丢弃
) -> list[Chunk]:
    """切分 Markdown 文本.

    步骤
    ----
    1. 按 \\n\\n 切段落
    2. 段落过短 (标题/列表项) 合并
    3. 段落过长 (>chunk_size) 按句子切
    4. 添加 overlap
    """
    if not markdown.strip():
        return []

    # 1) 段落粗切
    raw_paragraphs = re.split(r"\n\s*\n", markdown)
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    if not paragraphs:
        return []

    # 2) 短段落合并 (避免单字标题成块)
    merged: list[str] = []
    buffer = ""
    for p in paragraphs:
        if len(p) < min_chunk_size and buffer:
            buffer += "\n\n" + p
        else:
            if buffer:
                merged.append(buffer)
            buffer = p
    if buffer:
        merged.append(buffer)

    # 3) 长段落按句子切 + 累积到 chunk_size
    chunks: list[str] = []
    current = ""
    sentence_end = re.compile(r"(?<=[.。!！?？\n])\s+")

    for p in merged:
        if len(p) <= chunk_size:
            # 短段落直接 append
            if len(current) + len(p) > chunk_size and current:
                chunks.append(current.strip())
                # overlap: 取当前块末尾
                current = current[-chunk_overlap:] + "\n\n" + p
            else:
                current = (current + "\n\n" + p) if current else p
        else:
            # 长段落按句子切
            if current:
                chunks.append(current.strip())
                current = ""
            sentences = sentence_end.split(p)
            for s in sentences:
                if len(current) + len(s) > chunk_size and current:
                    chunks.append(current.strip())
                    current = current[-chunk_overlap:] + " " + s
                else:
                    current = (current + " " + s) if current else s

    if current.strip():
        chunks.append(current.strip())

    # 4) 过滤过短块
    chunks = [c for c in chunks if len(c) >= min_chunk_size]

    return [Chunk(text=c, index=i, metadata={"char_count": len(c)}) for i, c in enumerate(chunks)]
