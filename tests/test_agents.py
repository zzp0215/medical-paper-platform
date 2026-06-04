"""
Word 导出 + Agent 单元测试.
"""
from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document

pytestmark = pytest.mark.unit


# ============================================
# Planner
# ============================================
class TestPlanner:
    """大纲生成 (单 LLM)."""

    def test_default_outline_fallback(self) -> None:
        from backend.agents.planner_simple import _default_outline

        outline = _default_outline("review", "测试题目")
        assert len(outline.sections) >= 5
        # 第一个 section 应该是 abstract
        assert outline.sections[0].section_type == "abstract"

    def test_parse_outline_valid_json(self) -> None:
        from backend.agents.planner_simple import _parse_outline

        content = """{
  "abstract_intent": "本综述聚焦...",
  "sections": [
    {"order_index": 1, "heading": "引言", "section_type": "introduction", "description": "背景", "key_points": ["a", "b"]}
  ]
}"""
        outline = _parse_outline(content, "review", "测试")
        assert len(outline.sections) == 1
        assert outline.sections[0].heading == "引言"

    def test_parse_outline_invalid_falls_back(self) -> None:
        from backend.agents.planner_simple import _parse_outline

        # 无 JSON
        outline = _parse_outline("just plain text", "review", "测试")
        # 兜底大纲
        assert len(outline.sections) >= 5


# ============================================
# Writer
# ============================================
class TestWriter:
    """写作 (单 LLM)."""

    @pytest.mark.asyncio
    async def test_write_section_returns_content(self) -> None:
        from backend.agents import OutlineNode, write_section
        from backend.llm import ChatResponse, TokenUsage

        with patch("backend.agents.writer_simple.LLMRouter") as MockRouter:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            mock.chat = AsyncMock(
                return_value=ChatResponse(
                    id="r1", model="deepseek-chat",
                    content="这是引言内容 [1]",
                    usage=TokenUsage(total_tokens=20, model="deepseek-chat"),
                )
            )
            MockRouter.return_value = mock

            with patch("backend.agents.writer_simple.search_for_writing", new=AsyncMock(return_value="[1] 内容")):
                content = await write_section(
                    title="test",
                    paper_type="review",
                    section=OutlineNode(
                        order_index=1,
                        heading="引言",
                        section_type="introduction",
                        description="背景",
                        key_points=["a", "b"],
                    ),
                )
            assert "引言" in content or "内容" in content

    @pytest.mark.asyncio
    async def test_write_all_sections_skips_references(self) -> None:
        from backend.agents import OutlineNode, PaperOutline, write_all_sections
        from backend.llm import ChatResponse, TokenUsage

        with patch("backend.agents.writer_simple.LLMRouter") as MockRouter:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            mock.chat = AsyncMock(
                return_value=ChatResponse(
                    id="r1", model="deepseek-chat", content="ok",
                    usage=TokenUsage(total_tokens=10, model="deepseek-chat"),
                )
            )
            MockRouter.return_value = mock

            with patch("backend.agents.writer_simple.search_for_writing", new=AsyncMock(return_value="ref")):
                outline = PaperOutline(
                    abstract_intent="x",
                    sections=[
                        OutlineNode(1, "引言", "introduction", "desc", []),
                        OutlineNode(2, "参考文献", "references", "", []),
                    ],
                )
                results = await write_all_sections(
                    title="test", paper_type="review", outline=outline,
                )
            # 2 个 section, references (order_index=2) 应为空
            assert len(results) == 2
            assert results[2] == ""  # references 跳过
            # chat 只调用 1 次 (引言)
            assert mock.chat.await_count == 1


# ============================================
# Word 导出
# ============================================
class TestWordExport:
    """Word 文档生成 (不连真 DB, mock session)."""

    def test_export_with_mock_sections(self) -> None:
        """用 mock session 测 export_paper_to_docx."""
        from backend.export.word_simple import export_paper_to_docx

        # Mock Paper
        paper = type("Paper", (), {
            "id": 1,
            "title": "测试论文",
            "paper_type": "review",
            "target_language": "zh",
            "outline": {"abstract_intent": "test"},
            "is_deleted": False,
        })()
        section1 = type("S", (), {
            "order_index": 1, "heading": "引言", "section_type": "introduction",
            "content_md": "这是引言内容。", "word_count": 8,
        })()
        section2 = type("S", (), {
            "order_index": 2, "heading": "方法", "section_type": "methods",
            "content_md": "## 实验设计\n\n样本量 100.", "word_count": 10,
        })()

        # mock session
        async def mock_get(model, id):
            if id == 1:
                return paper
            return None

        class MockResult:
            def __init__(self, rows): self._rows = rows
            def scalars(self): return self
            def all(self): return self._rows

        async def mock_execute(stmt):
            return MockResult([section1, section2])

        class MockSession:
            async def get(self, model, id): return await mock_get(model, id)
            async def execute(self, stmt): return await mock_execute(stmt)

        async def _run():
            return await export_paper_to_docx(MockSession(), 1)

        docx_bytes = asyncio.run(_run())
        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 1000
        # docx 是 zip 格式, 前 2 字节是 PK
        assert docx_bytes[:2] == b"PK"
        # 用 python-docx 反向解析验证
        doc = Document(BytesIO(docx_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "测试论文" in text
        assert "引言" in text

    def test_export_paper_not_found(self) -> None:
        from backend.export.word_simple import export_paper_to_docx
        from backend.core import NotFoundError

        class MockSession:
            async def get(self, model, id): return None

        async def _run():
            await export_paper_to_docx(MockSession(), 999)

        with pytest.raises(NotFoundError):
            asyncio.run(_run())
