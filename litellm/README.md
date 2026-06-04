# LiteLLM 网关

> 关联: [项目 TODO](../TODO.md) Phase 1.1.5 | [架构文档](../README.md)

## 简化版 v0 (2026-06-04)

**只用云端 API, 不上本地模型** — 加快 MVP 闭环:

| 角色 | 模型 | 用途 | 备注 |
|------|------|------|------|
| 主力 | DeepSeek-V3 | 写作/Planner/Verifier/翻译 | 便宜, 64K context, 中文强 |
| 备用 | MiniMax Claude Sonnet 4.6 | 质量敏感场景 | 贵, 备用 |
| 嵌入 | OpenAI text-embedding-3-small | 文档向量化 (Phase 3) | 1536 维, $0.02/1M tok |

> 翻译/嵌入/重排一律走云端, 后续 Phase 8 评估效果再决定是否引入 MMed-Llama3 / BGE-Reranker 本地模型。

## 启动

```bash
# 1. 配置密钥
cp litellm/.env.example litellm/.env
vim litellm/.env   # 填 DEEPSEEK_API_KEY / MiniMax_API_KEY / OPENAI key

# 2. 启动 (依赖 docker-compose.yml 的 litellm 服务)
cd docker
docker-compose --env-file .env.docker up -d litellm

# 3. 健康检查
curl http://localhost:4000/health/liveliness
curl -H "Authorization: Bearer sk-litellm-master-dev-key-change-in-prod" \
     http://localhost:4000/v1/models
```

## 后端调用

业务代码只用 `backend.llm.LLMRouter`, **不直接 import openai**:

```python
from backend.llm import LLMRouter, ChatMessage, ChatRequest

async with LLMRouter() as router:
    resp = await router.chat(
        request=ChatRequest(
            messages=[ChatMessage(role="user", content="写一段医学摘要")],
        ),
        scenario="writing",   # 自动选 deepseek -> claude 降级链
    )
    print(resp.content)
    print(f"tokens={resp.usage.total_tokens} cost=${resp.usage.cost_usd:.4f}")
```

## 路由策略

`backend.llm.router.resolve_model_chain` 决定降级顺序:

| strategy | writing/planning/verification | polish |
|----------|-------------------------------|--------|
| cost_first (默认) | deepseek → claude | claude → deepseek |
| quality_first | claude → deepseek | claude → deepseek |
| manual | 调用方传 `request.model` | 同左 |

`scenario` 是业务层语义, 不同任务有不同优先级 (polish 走贵模型保质量)。

## 端口/服务

- **4000** — LiteLLM API (OpenAI 兼容)
- **4000/ui** — Web UI (看 usage / keys)
- **health** — `/health/liveliness` `/health/readiness`

## 数据持久化

- `medpaper_litellm` 数据库 — LiteLLM 自动建表, 存 usage / audit
- Redis — 缓存 + 限流 (复用平台主 Redis)

## 下一步

- Phase 1.2.3: LangGraph Hello World 用 `LLMRouter` 跑通
- Phase 2.x: PDF 解析 + 检索 (用 deepseek-chat 抽取, text-embedding-3-small 向量化)
- Phase 3.x: 引入 RAGFlow, LiteLLM 缓存省 token
- Phase 4: 8 个 Agent 全部走 `LLMRouter` (业务层 0 关心密钥)
