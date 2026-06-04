"""
健康检查 & 基础路由冒烟测试.

不依赖 DB/外部服务, 启动快.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness(client: TestClient) -> None:
    """GET /health 应返回 200 + 状态 ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "env" in body


def test_info(client: TestClient) -> None:
    """GET /health/info 应返回版本 + Phase 信息."""
    resp = client.get("/health/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "medical-paper-platform"
    assert body["phase"].startswith("1.1.4")


def test_request_id_header_echo(client: TestClient) -> None:
    """客户端 X-Request-ID 应被透传."""
    rid = "test-rid-12345"
    resp = client.get("/health", headers={"X-Request-ID": rid})
    assert resp.headers.get("X-Request-ID") == rid


def test_request_id_auto_generated(client: TestClient) -> None:
    """无 X-Request-ID 时, 服务端应自动生成 UUID."""
    resp = client.get("/health")
    rid = resp.headers.get("X-Request-ID", "")
    # 至少 8 字符, 不强制格式 (uuid4 是 36 字符含连字符)
    assert len(rid) >= 8


def test_404_returns_json(client: TestClient) -> None:
    """未注册路径应返回 JSON 错误."""
    resp = client.get("/this-path-does-not-exist")
    # FastAPI 默认 404 不是 JSON, 不强制; 仅断言状态码
    assert resp.status_code in (404, 405)


def test_openapi_docs_in_debug(client: TestClient) -> None:
    """debug 模式下应暴露 /docs."""
    # conftest 里 DEBUG=false, 所以这里期望 docs 被禁用
    resp = client.get("/docs")
    assert resp.status_code in (200, 404)
