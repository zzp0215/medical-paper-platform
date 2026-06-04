"""
PDF 解析器测试 (Phase 1.2.1).

测试数据
--------
- 英文: tests/test_pdfs/sample.pdf (arxiv 公开 PDF, 9 页)
- 中文: tests/test_pdfs/sample_zh.pdf (程序生成, 2 页)

不依赖任何外部服务.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pymupdf
import pytest

pytestmark = pytest.mark.unit

# 测试 PDF 路径
PDF_DIR = Path(__file__).parent / "test_pdfs"
SAMPLE_EN = PDF_DIR / "sample.pdf"
SAMPLE_ZH = PDF_DIR / "sample_zh.pdf"


@pytest.fixture(scope="module")
def sample_en_bytes() -> bytes:
    """英文测试 PDF (arxiv Docling 报告, 9 页)."""
    if not SAMPLE_EN.exists():
        pytest.skip(f"测试 PDF 不存在: {SAMPLE_EN} (curl -L -o {SAMPLE_EN} https://arxiv.org/pdf/2408.09869)")
    return SAMPLE_EN.read_bytes()


@pytest.fixture(scope="module")
def sample_zh_bytes() -> bytes:
    """中文测试 PDF (程序生成, 2 页)."""
    if not SAMPLE_ZH.exists():
        # 兜底: 用 pymupdf 现生成
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "医学论文自动生成平台", fontsize=20, fontname="china-s")
        page.insert_text((50, 100), "中文解析测试", fontsize=12, fontname="china-s")
        doc.new_page().insert_text((50, 50), "第二页", fontsize=12, fontname="china-s")
        doc.save(str(SAMPLE_ZH))
        doc.close()
    return SAMPLE_ZH.read_bytes()


# ============================================
# 基础功能
# ============================================
class TestPyMuPDFParser:
    """PyMuPDF4LLM 解析器."""

    def test_parse_english_pdf(self, sample_en_bytes: bytes) -> None:
        """英文 PDF 应能解析出 Markdown."""
        from backend.parser import PyMuPDFParser

        async def _run() -> None:
            parser = PyMuPDFParser()
            result = await parser.parse(sample_en_bytes, filename="sample.pdf")
            assert result.page_count > 0
            assert len(result.markdown) > 1000
            assert result.metadata.get("parser") == "pymupdf4llm"
            # 解析耗时 (metadata 记录)
            assert "elapsed_ms" in result.metadata

        asyncio.run(_run())

    def test_parse_chinese_pdf(self, sample_zh_bytes: bytes) -> None:
        """中文 PDF 应能解析且保留中文."""
        from backend.parser import PyMuPDFParser

        async def _run() -> None:
            parser = PyMuPDFParser()
            result = await parser.parse(sample_zh_bytes, filename="sample_zh.pdf")
            assert result.page_count >= 2
            # 必须包含中文字符
            assert any("一" <= ch <= "鿿" for ch in result.markdown)
            # 关键词应能识别
            assert "医学" in result.markdown or "中文" in result.markdown

        asyncio.run(_run())

    def test_parse_blocks_classification(self, sample_zh_bytes: bytes) -> None:
        """Block 分类: heading vs text."""
        from backend.parser import PyMuPDFParser

        async def _run() -> None:
            parser = PyMuPDFParser()
            result = await parser.parse(sample_zh_bytes, filename="sample_zh.pdf")
            # 至少有一个 heading
            assert any(b.type == "heading" for b in result.blocks)
            # text 块应更多
            text_blocks = [b for b in result.blocks if b.type == "text"]
            assert len(text_blocks) > 0

        asyncio.run(_run())

    def test_invalid_pdf_raises(self) -> None:
        """非法 PDF 应抛 ParseError."""
        from backend.parser import PyMuPDFParser
        from backend.core import ParseError

        async def _run() -> None:
            parser = PyMuPDFParser()
            with pytest.raises(ParseError):
                await parser.parse(b"not a pdf", filename="invalid.pdf")

        asyncio.run(_run())


# ============================================
# MinerU 接口
# ============================================
class TestMinerUInterface:
    """MinerU 接口存在性 + 默认禁用行为."""

    def test_mineru_disabled_raises(self) -> None:
        """MinerU 未启用时调用应抛 NotFoundError."""
        from backend.parser.mineru_service import MinerUParser
        from backend.core import NotFoundError

        async def _run() -> None:
            parser = MinerUParser()
            with pytest.raises(NotFoundError):
                await parser.parse(b"%PDF-1.4\n...", filename="test.pdf")

        asyncio.run(_run())

    def test_base_interface_compatible(self) -> None:
        """两个实现都应满足 PDFParser 接口."""
        from backend.parser import PyMuPDFParser
        from backend.parser.mineru_service import MinerUParser

        for cls in (PyMuPDFParser, MinerUParser):
            assert hasattr(cls, "parse")
            import inspect

            assert inspect.iscoroutinefunction(cls.parse)
