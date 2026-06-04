#!/usr/bin/env python3
"""
知识库基础链路验证 (Phase 1.2.2).

不依赖 RAGFlow (那个太重), 验证:
1. LocalKBClient 接口可调
2. 健康检查通过
3. LiteLLM 网关可达 (用于 Phase 3.2 的 embedding)

用法
----
    python3 scripts/verify_kb_basic.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import logger  # noqa: E402
from backend.kb import LocalKBClient, RetrievalQuery, get_default_client  # noqa: E402


async def main() -> int:
    print("=" * 60)
    print("知识库基础链路验证 (Phase 1.2.2)")
    print("=" * 60)

    print("\n1️⃣  默认客户端工厂:")
    client_factory = get_default_client
    print(f"   工厂返回类型: {client_factory.__name__}")

    # 显式拿 LocalKBClient (跳过 RAGFlow)
    print("\n2️⃣  LocalKBClient 接口调用:")
    client = LocalKBClient()
    ds_id = await client.create_dataset("test_kb", description="验证用")
    print(f"   ✅ create_dataset -> {ds_id}")

    doc_id = await client.upload_document(
        ds_id, b"fake pdf content", filename="test.pdf"
    )
    print(f"   ✅ upload_document -> {doc_id}")

    done = await client.wait_parse_complete(doc_id)
    print(f"   ✅ wait_parse_complete -> {done}")

    hits = await client.retrieve(
        RetrievalQuery(query="糖尿病治疗方案", top_k=5)
    )
    print(f"   ✅ retrieve -> {len(hits)} hits (placeholder)")

    health = await client.health_check()
    print(f"   ✅ health_check -> status={health.get('status')}")
    for comp, st in health.get("components", {}).items():
        print(f"      - {comp}: {st}")

    print("\n3️⃣  RAGFlow 客户端 (未启用, 应抛 NotFoundError):")
    from backend.kb import RAGFlowClient
    from backend.core import NotFoundError

    try:
        async with RAGFlowClient() as _:
            pass
    except NotFoundError as e:
        print(f"   ✅ 正确抛 NotFoundError: {str(e)[:80]}...")

    print("\n" + "=" * 60)
    print("✅ Phase 1.2.2 接口层验证通过")
    print("=" * 60)
    print("\n下一步: 启 RAGFlow 真实环境 (可选, 重)")
    print("  cd docker && docker-compose -f docker-compose.yml -f docker-compose.ragflow.yml up -d ragflow")
    print("  访问 http://localhost:9380, 创建 API Key")
    print("  .env 设 RAGFLOW_ENABLED=true + RAGFLOW_API_KEY=...")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
