"""知识库抽象接口."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    """文档块 (检索 + 生成的最小单位)."""

    chunk_id: str
    doc_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class RetrievalQuery:
    """检索请求."""

    query: str
    kb_ids: list[str] = field(default_factory=list)
    top_k: int = 20
    score_threshold: float = 0.3
    filters: dict = field(default_factory=dict)
    # 是否走自反馈 (OpenScholar 架构, Phase 3.2.3)
    use_self_feedback: bool = False


@dataclass
class RetrievalHit:
    """检索命中."""

    chunk_id: str
    doc_id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    # 引用归因: 哪一段对应哪条引用
    source_ref: str | None = None


class KnowledgeBaseClient(ABC):
    """知识库客户端抽象.

    所有实现必须提供 4 类操作: 文档管理 / 检索 / 反馈 / 健康检查
    """

    # ---------- 文档管理 ----------
    @abstractmethod
    async def create_dataset(self, name: str, *, description: str = "") -> str:
        """创建数据集 (KB). 返回 dataset_id."""

    @abstractmethod
    async def upload_document(
        self, dataset_id: str, file_bytes: bytes, *, filename: str
    ) -> str:
        """上传文档, 返回 doc_id."""

    @abstractmethod
    async def wait_parse_complete(self, doc_id: str, *, timeout: float = 300) -> bool:
        """等待文档解析完成."""

    @abstractmethod
    async def delete_document(self, doc_id: str) -> None:
        """删除文档."""

    # ---------- 检索 ----------
    @abstractmethod
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalHit]:
        """单次检索."""

    async def self_feedback_retrieve(
        self, query: RetrievalQuery, *, max_rounds: int = 3
    ) -> list[RetrievalHit]:
        """自反馈迭代检索 (默认实现: 单次)."""
        return await self.retrieve(query)

    # ---------- 健康检查 ----------
    @abstractmethod
    async def health_check(self) -> dict:
        """返回组件状态."""
