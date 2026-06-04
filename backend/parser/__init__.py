"""PDF 解析器 (Phase 2 完善).

决策 2026-06-04
----------------
- 基础链路验证: 用 pymupdf4llm (PyMuPDF + LLM-friendly Markdown 输出)
  - 优点: CPU 友好, 体积小, 中英文都能解析
  - 缺点: 公式识别弱, 复杂表格需要后处理
- 完整服务化: MinerU 留到 Phase 2.1.1 (需 GPU 才能跑满速度)
  - Docker 镜像: mineru.org:0.10/...
  - API: POST /parse (PDF) → { markdown, blocks, images }
"""
from backend.parser.base import PDFParser, ParseResult
from backend.parser.pymupdf_parser import PyMuPDFParser

# MinerU 留接口, Phase 2.1.1 启用
# from backend.parser.mineru_parser import MinerUParser

__all__ = ["PDFParser", "ParseResult", "PyMuPDFParser"]
