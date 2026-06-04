# MVP 验证报告 (Sprint 3 - 2026-06-04)

## 验证目标

确认"上传 PDF → 解析 → 检索 → 大纲 → 写作 → 导出 Word"完整业务链路能跑通。

## 验证方式

`scripts/demo_run.py` 端到端演示 (mocked LLM, 避免外部依赖)。

```bash
python3 scripts/demo_run.py
```

## 验证结果

| 步骤 | 状态 | 输出 | 耗时 |
|------|------|------|------|
| 1. PDF 解析 (9 页 arxiv 论文) | ✅ | 44904 字符 Markdown | ~7800ms |
| 2. 大纲生成 (mocked LLM) | ✅ | 6 节 IMRaD 大纲 | <10ms |
| 3. 逐节写作 (mocked LLM) | ✅ | 581 字符内容 (摘要+引言+方法+结果+讨论+结论) | <10ms |
| 4. Word 导出 | ✅ | 36KB docx 文件 | ~900ms |
| **总计** | ✅ | **36KB 论文** | **8.8s** |

## 测试用例覆盖

| 类型 | 测试文件 | 测试数 | 通过 |
|------|----------|--------|------|
| 通用单元 | `test_health.py` | 5 | 5 |
| LLM 网关 | `test_llm_gateway.py` | 9 | 9 |
| LangGraph | `test_langgraph_hello.py` | 5 | 5 |
| PDF 解析 | `test_parser.py` | 6 | 6 |
| 文本分块 | `test_chunker.py` | 5 | 5 |
| 知识库 | `test_kb.py` | 7 | 7 |
| Agent + Word | `test_agents.py` | 7 | 7 |
| Paper 路由 | `test_paper.py` | 2 (skip 2) | 2 |
| **总计** | 7 个文件 | **46 passed, 2 skipped** | ✅ |

## 已实现端点 (FastAPI 19 路由)

```
GET   /health                  liveness
GET   /health/ready            readiness (5 组件)
GET   /health/info             元信息
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
POST  /api/v1/papers/generate          ← 一键生成
POST  /api/v1/papers/{id}/outline      ← 单独生成大纲
POST  /api/v1/papers/{id}/write        ← 单独写作
GET   /api/v1/papers/{id}/export/word  ← Word 下载
POST  /api/v1/chat
POST  /api/v1/export/word
```

## 简化决策 (vs 原始 TODO)

按 MVP 优先原则砍掉:

| 砍掉 | 简化方案 | 后期补 |
|---|---|---|
| 8 个 LangGraph Agent | 单 LLM 调用 (planner/writer 各 1 次) | Phase 4 |
| Verifier 验证 | 跳过, 信 LLM | Phase 4.5 |
| 自反馈迭代检索 | 单次向量检索 | Phase 3.2.3 |
| Cross-Encoder 重排 | 相似度排序 | Phase 3.2.2 |
| 多源融合 (PubMed/Web) | 只用 Milvus 本地 | Phase 3.2.1 |
| Citation Agent 精排 | 简单 [N] 占位 | Phase 4.6 |
| Celery 异步任务 | 同步执行 (单篇 < 1 分钟可接受) | Phase 2.1.3 |
| Dify/Next.js 前端 | Swagger UI 调试 | Phase 5 |
| word_chat 模板引擎 | python-docx 简单生成 | Phase 6 |

## 已知限制

1. **Mock 模式**: demo_run 用假 LLM 响应, 不能验证真实生成质量
2. **Milvus 未实测**: vectorize_service 在本地没启 Milvus, 没跑过
3. **未真调 DeepSeek**: 路由策略代码 OK, 但没真 key 验证
4. **Word 排版简单**: 标题层级 + 段落, 无图无表格无公式

## 真服务模式 (待执行)

```bash
# 1. 启基础服务
cd docker && docker-compose --env-file .env.docker up -d

# 2. 配置 .env 真实 key
DEEPSEEK_API_KEY=sk-xxx
MiniMax_API_KEY=sk-ant-xxx
VLM_API_KEY=sk-xxx

# 3. 启后端
python -m backend.main

# 4. 启 LiteLLM (另一个终端)
cd docker && docker-compose up -d litellm

# 5. 跑真实 demo (LITELLM_BASE_URL=http://localhost:4000/v1)
LITELLM_BASE_URL=http://localhost:4000/v1 \
  python3 scripts/demo_run.py --real
```

## 风险评估

| 风险 | 缓解 |
|------|------|
| DeepSeek 中文医学写作质量 | 已用 prompt 约束 + IMRaD 模板, 后期加 Verifier |
| 检索召回率低 | 单次 Top-5, 后期加 Cross-Encoder 重排 |
| Word 排版简陋 | python-docx 基础够用, 后期可上 word_chat |
| 同步调用超时 | 单篇 < 1 分钟, 后期可上 Celery |

## 下一步建议

- **真实环境跑通** (用真实 API key)
- **5 种医学 PDF 验证** (临床研究/综述/病例报告/Meta/基础研究)
- **收集生成质量样本**, 决定 Phase 4 完整版的优先级
- **部署到内网测试服**, 让 2-3 个医生试用

## Sprint 时间线

```
2026-06-04 14:00  Sprint 1 开始 (PDF 解析)
2026-06-04 16:30  Sprint 1 完成 (commit 13146f2)
2026-06-04 17:00  Sprint 2 开始 (论文生成)
2026-06-04 18:30  Sprint 2 完成 (commit d40216e)
2026-06-04 19:00  Sprint 3 开始 (端到端)
2026-06-04 19:30  Sprint 3 完成 (本报告)
─────────────────────────────
总耗时: ~5.5 小时 (原计划 14 天)
```
