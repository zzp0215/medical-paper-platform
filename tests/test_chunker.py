"""
文本分块器测试.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestChunker:
    def test_simple_paragraphs(self) -> None:
        from backend.services.text_chunker import chunk_markdown

        text = "# Title\n\nFirst paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
        chunks = chunk_markdown(text, min_chunk_size=10)
        assert len(chunks) >= 1
        # 标题被合并 (短)
        assert any("Title" in c.text for c in chunks)

    def test_long_paragraph_split(self) -> None:
        from backend.services.text_chunker import chunk_markdown

        # 造一个 ~3000 字符的段落
        long_text = ("This is sentence number xxxx. " * 100).strip()
        assert len(long_text) > 2500, f"造的长文应该 > 2500 字符, 实际 {len(long_text)}"
        chunks = chunk_markdown(long_text, chunk_size=400, min_chunk_size=50)
        # 应该切成多块
        assert len(chunks) > 1, f"应该被切分, 实际只有 1 块"
        # 每块不超过 chunk_size 太多 (允许 overlap)
        for c in chunks:
            assert len(c.text) <= 600, f"块太大: {len(c.text)}"

    def test_empty_text(self) -> None:
        from backend.services.text_chunker import chunk_markdown

        assert chunk_markdown("") == []
        assert chunk_markdown("   \n\n  ") == []

    def test_short_blocks_filtered(self) -> None:
        from backend.services.text_chunker import chunk_markdown

        # 单字标题应该被合并, 不独立成块
        text = "A\n\nB\n\nThis is a real paragraph with enough content to survive."
        chunks = chunk_markdown(text, min_chunk_size=20)
        # 至少包含那个有内容的段落
        assert any("real paragraph" in c.text for c in chunks)
        # 不应有过短的独立块
        assert all(len(c.text) >= 20 for c in chunks)

    def test_chinese_text(self) -> None:
        from backend.services.text_chunker import chunk_markdown

        text = "## 摘要\n\n本研究纳入 100 例 2 型糖尿病患者, 随机分组.\n\n## 方法\n\n采用双盲随机对照试验."
        chunks = chunk_markdown(text, min_chunk_size=20)
        assert len(chunks) >= 1
        assert any("糖尿病" in c.text for c in chunks)
