# 医学论文自动生成平台 — 开发 TODO

> 关联文档: [最终架构](./README.md) | 当前日期: 2026-06-04

---

## Phase 1: 基础设施与环境搭建 (预计 1-2 周)

### 1.1 开发环境
- [ ] 1.1.1 初始化项目仓库 `medical-paper-platform`，Git 初始化
- [ ] 1.1.2 编写 `.gitignore`、`.env.example`、`requirements.txt`
- [ ] 1.1.3 Docker Compose 基础编排（PostgreSQL + Redis + MinIO + Milvus + ES）
- [ ] 1.1.4 FastAPI 项目骨架搭建（目录结构、路由规划）
- [ ] 1.1.5 配置 LiteLLM 网关，接入 DeepSeek-V3 作为默认模型

### 1.2 依赖安装
- [ ] 1.2.1 部署 MinerU（`pip install -U 'mineru[core]'`），验证 PDF→Markdown 基础链路
- [ ] 1.2.2 部署 RAGFlow（Docker Compose），验证文档入库+基础问答
- [ ] 1.2.3 安装 LangGraph + LangChain，编写 Hello World Agent

---

## Phase 2: PDF 解析管道 (预计 2-3 周)

### 2.1 MinerU 服务化
- [ ] 2.1.1 将 MinerU 封装为 FastAPI 微服务（`POST /parse` 接收 PDF，返回结构化 JSON）
- [ ] 2.1.2 批量解析接口（`POST /parse/batch`，支持 50-100 篇并发解析）
- [ ] 2.1.3 Celery 异步任务集成（PDF 解析放入后台队列，WebSocket 推送进度）
- [ ] 2.1.4 解析结果存入 MinIO（Markdown + JSON + 提取的图表 PNG）

### 2.2 医学 PDF 专项适配
- [ ] 2.2.1 图表提取后处理：调用多模态 LLM（Qwen2.5-VL / GPT-4o）生成图表自然语言描述
- [ ] 2.2.2 表格数据提取：StructEqTable 输出 → 结构化 CSV/JSON（保留行列关系）
- [ ] 2.2.3 统计检验结果识别（p值、置信区间、效应量等）
- [ ] 2.2.4 医学命名实体识别增强（疾病、药物、基因、检验指标标注）

### 2.3 验证
- [ ] 2.3.1 用 5 篇不同类型的医学 PDF 测试解析精度（临床研究、综述、病例报告、Meta分析、基础研究）

---

## Phase 3: 知识库与检索引擎 (预计 3-4 周)

### 3.1 RAGFlow 知识库
- [ ] 3.1.1 配置 DeepDoc 布局分析模型，适配医学论文版式
- [ ] 3.1.2 解析后的结构化文档批量导入 RAGFlow
- [ ] 3.1.3 知识库增量更新接口（用户新增 PDF → 自动解析 → 追加入库）
- [ ] 3.1.4 知识库版本管理（每次更新生成快照，支持回滚）

### 3.2 OpenScholar 架构增强（核心）
- [ ] 3.2.1 实现多源检索融合器
  - 源1: 本地 Milvus 向量检索（用户知识库）
  - 源2: PubMed / Semantic Scholar API 检索
  - 源3: Web 搜索（补充最新文献）
- [ ] 3.2.2 训练/部署医学专用 Cross-Encoder 重排序器
  - 基于 BGE-Reranker 在 PubMed 数据上微调
- [ ] 3.2.3 实现自反馈迭代检索循环
  - 初始检索 → 生成检索摘要 → LLM 自我审查（缺什么？） → 补充检索 → 重复至充分
- [ ] 3.2.4 引用归因验证模块
  - 每条论断 → 回溯到源文献段落 → 验证一致性
- [ ] 3.2.5 集成 MedRAG 医学术语索引

### 3.3 验证
- [ ] 3.3.1 检索精度测试（Top-10 命中率 > 90%）
- [ ] 3.3.2 引用准确性测试（与人工标注对比）

---

## Phase 4: 多Agent论文生成引擎 (预计 4-6 周) ⭐ 核心

### 4.1 LangGraph 状态图
- [ ] 4.1.1 定义 `PaperState` TypedDict（论文标题、大纲、各节内容、验证报告、引用列表、用户反馈等）
- [ ] 4.1.2 实现 Supervisor Agent（任务分解、Agent调度、状态管理）
- [ ] 4.1.3 实现条件路由逻辑（验证通过→继续 / 不通过→重写 / 用户否决→回到大纲）

### 4.2 Retriever Agent（检索）
- [ ] 4.2.1 Prompt: 根据写作需求+已知上下文，构建检索查询
- [ ] 4.2.2 Tool: 调用 Phase 3 的多源检索+自反馈接口
- [ ] 4.2.3 输出: 带引用标记的文段 + 置信度评分

### 4.3 Planner Agent（大纲）
- [ ] 4.3.1 Prompt: 参照 STORM，根据论文题目+检索摘要生成 IMRaD 大纲
- [ ] 4.3.2 医学论文结构模板库（临床研究/Meta分析/病例报告/综述等）
- [ ] 4.3.3 为每个大纲节点绑定支持性引用
- [ ] 4.3.4 Human-in-Loop: 呈现大纲给用户确认/修改

### 4.4 Writer Agent（写作）
- [ ] 4.4.1 Prompt: IMRaD 风格中文医学写作（引言/方法/结果/讨论/结论）
- [ ] 4.4.2 多章节并行写作（不同 Writer 实例处理不同节）
- [ ] 4.4.3 引用标记插入（正文[N]格式，对应参考文献列表）
- [ ] 4.4.4 待填充数据占位符标记（患者数/统计值等需人工确认）

### 4.5 Verifier Agent（验证）
- [ ] 4.5.1 Prompt: 逐句比对原始文献，标记可疑断言
- [ ] 4.5.2 数据准确性检查（数值、统计量是否与源文献一致）
- [ ] 4.5.3 引用一致性检查（引用标记是否对应正确文献段落）
- [ ] 4.5.4 逻辑矛盾检测（前后文数据是否矛盾）
- [ ] 4.5.5 返回: 通过/小修（自动改）/大修（打回Writer重写）

### 4.6 Citation Agent（引用）
- [ ] 4.6.1 提取全文中所有引用标记
- [ ] 4.6.2 在知识库中验证每条引用的存在性和准确性
- [ ] 4.6.3 引用格式化为 AMA / Vancouver 风格
- [ ] 4.6.4 去重 + 标记缺失引用

### 4.7 Human Node（用户审核点）
- [ ] 4.7.1 大纲确认节点（生成后暂停，等待用户批准）
- [ ] 4.7.2 章节审核节点（每节写完后可选审核）
- [ ] 4.7.3 全文审核节点（生成完成后整体审核）
- [ ] 4.7.4 用户修改指令解析（"改这段数据"→精确定位→重写）

### 4.8 验证
- [ ] 4.8.1 用 3 个不同医学主题测试完整生成流程
- [ ] 4.8.2 医学专家审核生成论文质量

---

## Phase 5: 多轮对话界面 (预计 2-3 周)

### 5.1 Dify 集成
- [ ] 5.1.1 Dify 部署 + 连接 RAGFlow 知识库
- [ ] 5.1.2 文档上传界面（拖拽 PDF → 触发 MinerU 解析 → 入库）
- [ ] 5.1.3 基础问答界面（"这篇文献的样本量是多少？"等检索式问题）

### 5.2 Next.js 论文编辑界面
- [ ] 5.2.1 论文大纲确认页面（IMRaD 树形结构，支持拖拽调整）
- [ ] 5.2.2 章节审核页面（Markdown 渲染 + 引用标注高亮）
- [ ] 5.2.3 对话式修改面板（Chat UI，流式输出）
- [ ] 5.2.4 diff 视图（修改前后对比）
- [ ] 5.2.5 Word 下载按钮

---

## Phase 6: Word 生成与排版 (预计 2-3 周)

### 6.1 word_chat 集成
- [ ] 6.1.1 医学论文模板设计（IMRaD 格式、字体/字号/行距）
- [ ] 6.1.2 论文内容→模板映射（章节名→Heading样式，表格→三线表，公式→OOXML）
- [ ] 6.1.3 参考文献列表自动排版
- [ ] 6.1.4 交叉引用生成（正文引用 ↔ 参考文献锚点）

### 6.2 Paper-Refiner 集成
- [ ] 6.2.1 段落级 AI 润色接口（选择性改写，人工勾选采纳）
- [ ] 6.2.2 表格/公式/图片自动跳过保护

### 6.3 验证
- [ ] 6.3.1 Word 打开正确性验证（格式/样式/引用/公式渲染）

---

## Phase 7: 医学翻译引擎 (预计 3-4 周)

### 7.1 翻译模型
- [ ] 7.1.1 部署 MMed-Llama3-8B（本地推理或 API）
- [ ] 7.1.2 fanyi 工具链集成（批量翻译 + 多引擎备选）

### 7.2 医学术语库
- [ ] 7.2.1 构建医学中英术语映射库（UMLS + 自定义）
- [ ] 7.2.2 翻译后术语一致性校验（同一术语全文统一翻译）
- [ ] 7.2.3 缩写管理（首次出现全称+缩写，后续统一缩写）

### 7.3 验证
- [ ] 7.3.1 医学专家审核翻译准确性（术语 + 表达）

---

## Phase 8: 校对与去AI化引擎 (预计 3-4 周) ⚠️ 自研

### 8.1 AI特征检测
- [ ] 8.1.1 收集 AI 写作 vs 人类写作的医学论文对照语料
- [ ] 8.1.2 训练/设计 AI 特征检测器（句式模板化、过度连贯、缺乏个人观点等）
- [ ] 8.1.3 标注工具（标记疑似 AI 段落 → 人工验证）

### 8.2 风格改写
- [ ] 8.2.1 AMA Manual of Style 规范 Prompt 约束
- [ ] 8.2.2 医学写作风格迁移（被动语态比例、专业术语密度、句式变化）
- [ ] 8.2.3 学术写作"人性化"特征注入（适度保留局限性讨论、研究展望的谨慎语气）

### 8.3 验证
- [ ] 8.3.1 AI检测工具（GPTZero/Originality）对比测试
- [ ] 8.3.2 医学专家盲审（AI改写版 vs 纯AI版 vs 人类版）

---

## Phase 9: 集成测试与部署 (预计 2-3 周)

### 9.1 端到端测试
- [ ] 9.1.1 全流程测试：上传50篇PDF → 输入题目 → 生成大纲 → 确认 → 生成初稿 → 修改 → 翻译 → 去AI化 → Word输出
- [ ] 9.1.2 边界测试：只传1篇PDF、传100篇PDF、各类型混合文献
- [ ] 9.1.3 性能测试：PDF并发解析、论文生成耗时

### 9.2 部署
- [ ] 9.2.1 Docker Compose 生产配置（资源限制、GPU分配、健康检查）
- [ ] 9.2.2 Nginx 反向代理 + HTTPS
- [ ] 9.2.3 监控告警（Prometheus + Grafana，LLM调用量/延迟/错误率）

---

## 进度总览

| Phase | 内容 | 预计周期 | 状态 | 依赖 |
|-------|------|---------|------|------|
| 1 | 基础设施与环境搭建 | 1-2周 | ⬜ 待开始 | - |
| 2 | PDF解析管道 | 2-3周 | ⬜ 待开始 | Phase 1 |
| 3 | 知识库与检索引擎 | 3-4周 | ⬜ 待开始 | Phase 2 |
| 4 | 多Agent论文生成引擎 ⭐ | 4-6周 | ⬜ 待开始 | Phase 3 |
| 5 | 多轮对话界面 | 2-3周 | ⬜ 待开始 | Phase 4 |
| 6 | Word生成与排版 | 2-3周 | ⬜ 待开始 | Phase 4 |
| 7 | 医学翻译引擎 | 3-4周 | ⬜ 待开始 | Phase 4 |
| 8 | 校对与去AI化引擎 | 3-4周 | ⬜ 待开始 | Phase 7 |
| 9 | 集成测试与部署 | 2-3周 | ⬜ 待开始 | Phase 5-8 |
| **总计** | | **22-31周** | | |

> **MVP 建议**：Phase 1-4 完成后（约 10-15 周）即可跑通「PDF→知识库→论文初稿」核心闭环，可先内部试用验证。

---

## 开发目录结构

```
/home/r720/disk4/yixue_lin/medical-paper-platform/
│
├── README.md                    # 架构文档 (本文件)
├── TODO.md                      # 开发任务 (本文件)
│
├── docker/                      # Docker 编排
│   ├── docker-compose.yml       # 基础服务
│   ├── docker-compose.prod.yml  # 生产配置
│   └── nginx/                   # Nginx 配置
│
├── backend/                     # 后端服务
│   ├── api/                     # FastAPI 主服务
│   │   ├── main.py              # 入口
│   │   ├── routes/              # 路由
│   │   │   ├── upload.py        # PDF上传
│   │   │   ├── paper.py         # 论文生成
│   │   │   ├── chat.py          # 对话接口
│   │   │   └── export.py        # Word导出
│   │   └── middleware/          # 中间件
│   │
│   ├── agents/                  # LangGraph Agent (核心)
│   │   ├── supervisor.py        # Supervisor Agent
│   │   ├── retriever.py         # 检索 Agent
│   │   ├── planner.py           # 大纲 Agent
│   │   ├── writer.py            # 写作 Agent
│   │   ├── verifier.py          # 验证 Agent
│   │   ├── citation.py          # 引用 Agent
│   │   ├── translator.py        # 翻译 Agent
│   │   ├── polisher.py          # 润色 Agent
│   │   ├── formatter.py         # 排版 Agent
│   │   ├── state.py             # PaperState 定义
│   │   └── graph.py             # 状态图编排
│   │
│   ├── retrieval/               # 检索引擎
│   │   ├── multi_source.py      # 多源融合检索
│   │   ├── reranker.py          # Cross-Encoder 重排序
│   │   ├── self_feedback.py     # 自反馈迭代
│   │   └── citation_verify.py   # 引用归因验证
│   │
│   ├── parser/                  # PDF解析服务
│   │   ├── mineru_service.py    # MinerU 封装
│   │   ├── chart_extractor.py   # 图表提取
│   │   └── table_extractor.py   # 表格提取
│   │
│   ├── translation/             # 翻译引擎
│   │   ├── mmedlm_service.py    # MMedLM 服务
│   │   ├── fanyi_toolkit.py     # fanyi 工具
│   │   └── glossary.py          # 术语库
│   │
│   ├── export/                  # 输出引擎
│   │   ├── word_generator.py    # word_chat 集成
│   │   ├── template_engine.py   # 模板引擎
│   │   └── styles.py            # 样式定义
│   │
│   ├── kb/                      # 知识库管理
│   │   ├── ragflow_client.py    # RAGFlow API 封装
│   │   └── index_manager.py     # 索引管理
│   │
│   └── tasks/                   # Celery 异步任务
│       ├── parse_task.py        # PDF解析任务
│       ├── generate_task.py     # 论文生成任务
│       └── export_task.py       # Word导出任务
│
├── frontend/                    # 前端
│   ├── nextjs/                  # Next.js 论文编辑界面
│   │   ├── pages/
│   │   ├── components/
│   │   │   ├── OutlineEditor    # 大纲编辑器
│   │   │   ├── SectionReview    # 章节审核
│   │   │   ├── ChatPanel        # 对话修改面板
│   │   │   └── DiffViewer       # 差异对比
│   │   └── api/                 # API 调用
│   │
│   └── dify/                    # Dify 配置导出
│       └── app_export.yml       # Dify 应用配置
│
├── models/                      # 模型文件 (gitignored)
│   ├── reranker/                # 医学重排序器权重
│   └── mmedlm/                  # MMedLM 模型
│
├── data/                        # 数据文件 (gitignored)
│   ├── glossary/                # 术语库
│   ├── templates/               # Word 模板
│   └── test_pdfs/               # 测试用 PDF
│
├── tests/                       # 测试
│   ├── test_parser.py
│   ├── test_retrieval.py
│   ├── test_agents.py
│   └── test_e2e.py
│
└── docs/                        # 额外文档
    ├── prompts/                 # Agent Prompt 模板
    │   ├── retriever.md
    │   ├── planner.md
    │   ├── writer.md
    │   ├── verifier.md
    │   ├── translator.md
    │   └── polisher.md
    └── architecture/            # 架构决策记录
        └── adr-001-ragflow-openscholar.md
```
