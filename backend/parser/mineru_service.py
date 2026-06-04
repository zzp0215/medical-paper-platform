"""
MinerU 解析器 (Phase 2.1.1 完整服务化).

当前状态
--------
- 接口已定义 (PDFParser 子类)
- MinerU 部署验证推迟到 GPU 可用时
- CPU 跑 MinerU 极慢, MVP 阶段用 PyMuPDF4LLM 够用

后续启用
--------
1. GPU 服务器到位后:  pip install 'mineru[core]'
2. 启动 MinerU 微服务: docker run mineru-api
3. 改 settings.mineru.enabled = True, 这里切到 MinerU 客户端
"""
from __future__ import annotations

import io

from backend.core import NotFoundError, logger, settings
from backend.parser.base import Block, ParseResult


class MinerUParser:
    """MinerU 解析器 (HTTP 客户端)."""

    def __init__(self, api_base: str | None = None, timeout: float = 120.0) -> None:
        self.api_base = api_base or settings.mineru.api_base
        self.timeout = timeout
        if not settings.mineru.enabled:
            logger.warning(
                "MinerU 未启用 (settings.mineru.enabled=false), "
                "如需切换: 启用服务后改 .env 的 MINERU_ENABLED=true"
            )

    async def parse(self, file_bytes: bytes, *, filename: str = "document.pdf") -> ParseResult:
        if not settings.mineru.enabled:
            raise NotFoundError(
                "MinerU 未启用, 当前用 PyMuPDF4LLM. "
                "切换方法: .env 设 MINERU_ENABLED=true 并部署 MinerU 服务"
            )

        import httpx

        # TODO Phase 2.1.1: 实际 HTTP 调用
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     files = {"file": (filename, io.BytesIO(file_bytes), "application/pdf")}
        #     params = {"method": settings.mineru.parse_method, "lang": settings.mineru.lang}
        #     resp = await client.post(f"{self.api_base}/parse", files=files, params=params)
        #     resp.raise_for_status()
        #     data = resp.json()

        raise NotImplementedError("Phase 2.1.1 完整实现")
