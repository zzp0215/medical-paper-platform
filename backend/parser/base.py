"""PDF 解析器抽象接口."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Block:
    """解析后的内容块."""

    type: str  # "text" | "heading" | "image" | "table" | "formula" | "code"
    content: str
    page: int = 0
    bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)
    metadata: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    """PDF 解析统一结果."""

    markdown: str
    blocks: list[Block] = field(default_factory=list)
    page_count: int = 0
    metadata: dict = field(default_factory=dict)
    # 图片 (key=相对路径, value=字节)
    images: dict[str, bytes] = field(default_factory=dict)
    # 错误信息 (非致命)
    warnings: list[str] = field(default_factory=list)


class PDFParser(ABC):
    """PDF 解析器基类.

    所有实现必须返回标准 ParseResult, 上层业务只依赖这个接口.
    """

    @abstractmethod
    async def parse(self, file_bytes: bytes, *, filename: str = "document.pdf") -> ParseResult:
        """解析 PDF 文件.

        Args:
            file_bytes: PDF 二进制
            filename: 用于日志/元数据, 不参与解析逻辑

        Returns:
            标准化 ParseResult
        """
