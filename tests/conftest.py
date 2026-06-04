"""
pytest 全局 fixture.

- 设置测试环境变量 (覆盖 .env)
- 提供 in-memory / mock 客户端
"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# 测试环境: 用 SQLite 内存 + 关闭外部依赖
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",  # 仅做格式占位, 真实测试需 aiosqlite
)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """FastAPI TestClient (同步接口, 但内部跑异步)."""
    from backend.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """生成一个最小有效 PDF 字节流 (仅用于上传测试)."""
    # 最简 PDF: %PDF-1.4 + 1 页 + EOF
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000100 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%%EOF\n"
    )
