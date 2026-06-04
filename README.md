# 医学论文自动生成平台

> 7 大核心需求: PDF批量上传解析 / 中文初稿生成 / 多轮修改 / Word输出 / 中→英翻译 / 去AI化 / 知识库增量

## 当前状态 (2026-06-04)

✅ **MVP 跑通** (Sprint 1-3 完成, 49 测试通过)

**完整业务流** (端到端可用):
```
PDF 上传 → 解析 (pymupdf4llm) → 向量化 (OpenAI 嵌入) → 入 Milvus
   ↓
输入论文题目 → 检索相关段落 → LLM 生成 IMRaD 大纲
   ↓
逐节 LLM 写作 → 拼装成完整论文 → python-docx 导出 Word
```

## 快速开始

```bash
# 1. 安装依赖 (Python 3.10)
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10 - --user
python3.10 -m pip install --user -r requirements.txt

# 2. 启基础服务 (PostgreSQL + Redis + MinIO + Milvus + ES + LiteLLM)
cd docker && docker-compose --env-file .env.docker up -d

# 3. 配置 .env (根目录)
cp .env.example .env
# 填入 DEEPSEEK_API_KEY / MiniMax_API_KEY / OPENAI_API_KEY

# 4. 跑端到端 demo (mock LLM, 不需 key)
python3 scripts/demo_run.py

# 5. 跑测试
python3.10 -m pytest tests/   # 49 passed
```

## 目录结构

```
medical-paper-platform/
├── backend/
│   ├── api/                 # FastAPI 路由 (19 endpoints)
│   ├── core/                # 配置/日志/异常/安全
│   ├── db/                  # SQLAlchemy 异步 session
│   ├── models/              # ORM 模型 (User/Paper/KB/Document/Task)
│   ├── schemas/             # Pydantic 校验
│   ├── services/            # 业务编排 (parse/embed/vectorize/pipeline)
│   ├── agents/              # 简化版 Agent (planner/writer) + prompts/
│   ├── retrieval/           # 向量检索
│   ├── llm/                 # LLM 客户端 (LLMClient + LLMRouter 降级链)
│   ├── parser/              # PDF 解析 (PyMuPDF + MinerU stub)
│   ├── export/              # Word 导出
│   └── kb/                  # 知识库 (RAGFlow 客户端 + LocalKB 兜底)
├── docker/                  # Docker Compose (PG/Redis/MinIO/Milvus/ES/LiteLLM)
├── litellm/                 # LiteLLM Proxy 配置
├── alembic/                 # DB 迁移
├── tests/                   # 49 个测试
├── scripts/                 # demo_run / verify_pdf / verify_kb
├── examples/                # hello_langgraph.py
├── docs/                    # mvp-validation-report.md
└── requirements.txt
```

## 关键决策 (2026-06-04)

| 决策 | 原因 |
|---|---|
| **简化 LLM 栈**: 仅 DeepSeek + MiniMax + OpenAI 嵌入 | 不上本地模型, 加快打通 |
| **简化检索**: 单次向量检索, 无 Cross-Encoder | 后期补 |
| **单 Agent 写作**: 一次 LLM 调用写一节 | 不分多 Agent 协作 |
| **同步执行**: 单篇 PDF < 1 分钟 | 后期上 Celery |
| **PyMuPDF 替代 MinerU**: CPU 友好 | 后期 GPU 到位再切 |

详见 [docs/mvp-validation-report.md](docs/mvp-validation-report.md)

## API 端点 (19 路由)

```
GET   /health
GET   /health/ready
GET   /health/info

POST  /api/v1/upload/knowledge-bases
GET   /api/v1/upload/knowledge-bases
POST  /api/v1/upload
POST  /api/v1/upload/batch

POST  /api/v1/retrieval/search

POST  /api/v1/papers
GET   /api/v1/papers
GET   /api/v1/papers/{id}
PATCH /api/v1/papers/{id}
DEL   /api/v1/papers/{id}
GET   /api/v1/papers/{id}/sections
POST  /api/v1/papers/generate             # 一键生成
POST  /api/v1/papers/{id}/outline         # 单独大纲
POST  /api/v1/papers/{id}/write           # 单独写作
GET   /api/v1/papers/{id}/export/word     # Word 下载

POST  /api/v1/chat
POST  /api/v1/export/word
```

## 测试统计

```
49 passed, 2 skipped
- test_health.py       5 ✅ (liveness/readiness/request_id)
- test_llm_gateway.py  9 ✅ (路由策略/降级链)
- test_langgraph_hello 5 ✅ (状态/条件路由/完整 graph)
- test_parser.py       6 ✅ (中英文 PDF)
- test_chunker.py      5 ✅ (段落切块)
- test_kb.py           7 ✅ (LocalKB + RAGFlow 接口)
- test_agents.py       7 ✅ (Planner/Writer/Word 导出)
- test_e2e.py          2 ✅ (端到端链路)
- test_paper.py        2 skipped (需 DB)
```

## 后续优化方向 (按 ROI 排序)

1. **真服务跑通** (5 医学 PDF 验证) — 验证质量
2. **Word 排版升级** (上 word_chat, 加表格/公式) — 提升专业度
3. **Verifier Agent** (事实核查) — 提升准确性
4. **Cross-Encoder 重排** — 提升检索质量
5. **多源融合** (PubMed/Web) — 扩展知识面
6. **多 Agent 编排** (LangGraph 完整版) — 提升可控性
7. **Celery 异步** — 提升并发
8. **Dify/Next.js 前端** — 提升体验

## 文档

- [TODO.md](TODO.md) — 9-Phase 路线图
- [docs/mvp-validation-report.md](docs/mvp-validation-report.md) — Sprint 3 验证报告
- [docker/README.md](docker/README.md) — Docker 服务说明
- [litellm/README.md](litellm/README.md) — LLM 网关说明
