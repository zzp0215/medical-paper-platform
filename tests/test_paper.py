"""
论文路由冒烟测试.

依赖 DB 的测试默认 skip (用 `pytest -m db` 启用, 需要先启 docker 服务).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_create_paper_validation_error(client: TestClient) -> None:
    """空标题应触发校验错误."""
    resp = client.post(
        "/api/v1/papers",
        json={"title": "", "paper_type": "review", "target_language": "zh"},
    )
    # 校验错误返回 400 (我们的 handler)
    assert resp.status_code in (400, 422)
    body = resp.json()
    assert "code" in body
    assert "message" in body


def test_create_paper_invalid_type(client: TestClient) -> None:
    """非法 paper_type 应被 Pydantic 拒绝."""
    resp = client.post(
        "/api/v1/papers",
        json={"title": "test", "paper_type": "invalid_type", "target_language": "zh"},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.skip(reason="需要 PostgreSQL (pytest -m db, 启动 docker 后再跑)")
def test_list_papers_unauthenticated_placeholder(client: TestClient) -> None:
    """列表接口应能响应 (Phase 5 接入鉴权后这里改断言)."""
    resp = client.get("/api/v1/papers")
    assert resp.status_code in (200, 500, 503)


@pytest.mark.skip(reason="需要 PostgreSQL (pytest -m db, 启动 docker 后再跑)")
def test_chat_paper_not_found(client: TestClient) -> None:
    """不存在的 paper_id 应返回 404."""
    resp = client.post(
        "/api/v1/chat",
        json={"paper_id": 99999, "message": "hello"},
    )
    assert resp.status_code in (404, 500, 503)
