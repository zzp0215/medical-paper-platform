"""
PyMuPDF4LLM 解析器 (CPU 友好, 基础链路验证).

适用场景
--------
- 验证 PDF→Markdown 基础链路 (Phase 1.2.1)
- 简单中文/英文文献 (无复杂公式/双栏)
- 资源受限环境 (无 GPU, 不想拉 MinerU)

不适用
------
- 复杂学术版式 (双栏/嵌入公式/扫描件) → 用 MinerU
- OCR (扫描件) → MinerU/PaddleOCR
"""
from __future__ import annotations

import asyncio
import io
import time

import pymupdf4llm

from backend.core import logger
from backend.parser.base import Block, ParseResult


class PyMuPDFParser:
    """PyMuPDF4LLM 解析器."""

    def __init__(self, *, extract_images: bool = False) -> None:
        self.extract_images = extract_images

    async def parse(self, file_bytes: bytes, *, filename: str = "document.pdf") -> ParseResult:
        t0 = time.perf_counter()
        logger.info("PDF 解析开始 | file={} size={}B", filename, len(file_bytes))

        # pymupdf4llm 是同步 API, 跑在线程池
        # v1.x: to_markdown() 直接返回完整 markdown 字符串
        def _do_parse() -> tuple[str, list[Block], int]:
            import pymupdf
            # 用 stream 方式打开, 不写临时文件
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            try:
                full_text: str = pymupdf4llm.to_markdown(
                    doc,
                    show_progress=False,
                    extract_images=self.extract_images,
                    image_size_limit=0.05,  # <5% 页面面积的图忽略
                )
                page_count = doc.page_count
            finally:
                doc.close()

            # 按行粗分 block (heading 启发式)
            blocks: list[Block] = []
            for line in full_text.split("\n"):
                if line.strip().startswith("#"):
                    blocks.append(Block(type="heading", content=line.strip(), page=0))
                elif line.strip():
                    blocks.append(Block(type="text", content=line.strip(), page=0))
            return full_text, blocks, page_count

        try:
            markdown, blocks, page_count = await asyncio.to_thread(_do_parse)
        except Exception as e:
            logger.exception("PyMuPDF 解析失败 | file={}", filename)
            raise ParseError(f"PDF 解析失败: {e}") from e

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            "PDF 解析完成 | file={} pages={} blocks={} chars={} elapsed={:.0f}ms",
            filename, page_count, len(blocks), len(markdown), elapsed,
        )

        return ParseResult(
            markdown=markdown,
            blocks=blocks,
            page_count=page_count,
            metadata={"parser": "pymupdf4llm", "elapsed_ms": elapsed, "filename": filename},
        )


from backend.core import ParseError  # 末尾导入避免循环
