"""
应用配置 (单例).

设计原则
--------
1. 所有环境变量集中读取, 其它模块只导入 `settings`, 不直接调 os.getenv
2. 嵌套模型按服务分组 (DB / Redis / LLM / MinIO / Milvus / ES / RAGFlow / MinerU)
3. 提供 `get_settings()` 缓存函数, 避免反复读 .env

使用
----
    from backend.core.config import settings
    print(settings.DATABASE_URL)
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================
# 子配置模型 (按服务拆分)
# 重要: 每个字段显式声明 env 别名, 避免与系统环境变量 (PATH/LANG/HOST/...) 冲突
# ============================================


# ============================================
# 子配置模型 (按服务拆分)
# ============================================
class AppSettings(BaseSettings):
    """应用级元信息."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        # 子模型自己控制 env 来源, 主配置不重复读
        env_prefix="APP_",
    )

    name: str = "medical-paper-platform"
    env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    secret_key: str = Field(default="change-me-please-use-openssl-rand-hex-32", validation_alias="APP_SECRET_KEY")
    api_v1_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"])

    # JWT
    jwt_secret: str = Field(default="change-me-please-use-openssl-rand-hex-32", validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, validation_alias="JWT_EXPIRE_MINUTES")

    # 服务地址
    backend_host: str = Field(default="0.0.0.0", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, validation_alias="BACKEND_PORT")
    frontend_url: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_URL")


class DatabaseSettings(BaseSettings):
    """PostgreSQL 关系数据库."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", case_sensitive=False, extra="ignore")

    user: str = "medpaper"
    password: str = "change-me-in-prod"
    db: str = "medpaper"
    host: str = "localhost"
    port: int = 5432

    pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    echo_sql: bool = Field(default=False, validation_alias="DB_ECHO_SQL")

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Redis 缓存 + Celery Broker."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", case_sensitive=False, extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = "change-me-in-prod"

    celery_broker_db: int = 1
    celery_backend_db: int = 2

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    @property
    def celery_broker_url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.celery_broker_db}"

    @property
    def celery_backend_url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.celery_backend_db}"


class MinIOSettings(BaseSettings):
    """MinIO 对象存储."""

    model_config = SettingsConfigDict(env_prefix="MINIO_", case_sensitive=False, extra="ignore")

    root_user: str = "medpaper"
    root_password: str = "change-me-in-prod"
    endpoint: str = "localhost:9000"
    secure: bool = False
    bucket_pdfs: str = "medpaper-pdfs"
    bucket_figures: str = "medpaper-figures"
    bucket_exports: str = "medpaper-exports"

    @property
    def base_url(self) -> str:
        proto = "https" if self.secure else "http"
        return f"{proto}://{self.endpoint}"


class MilvusSettings(BaseSettings):
    """Milvus 向量数据库."""

    model_config = SettingsConfigDict(env_prefix="MILVUS_", case_sensitive=False, extra="ignore")

    host: str = "localhost"
    port: int = 19530
    user: str = "root"
    password: str = "Milvus"
    db_name: str = "medpaper"


class ESSettings(BaseSettings):
    """Elasticsearch 全文检索."""

    model_config = SettingsConfigDict(env_prefix="ES_", case_sensitive=False, extra="ignore")

    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"
    user: str = "elastic"
    password: str = "change-me-in-prod"
    index_papers: str = "medpaper_papers"
    index_chunks: str = "medpaper_chunks"

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


class LLMSettings(BaseSettings):
    """LLM 网关配置 (Phase 1.1.5 简化版: 仅云端 API).

    决策 (2026-06-04): 暂不接入本地模型, 只用 DeepSeek + MiniMax
    - DeepSeek-V3 主力: 论文写作 / Planner / Verifier / 翻译
    - MiniMax Claude Sonnet 4.6 备用: 质量敏感场景
    - OpenAI text-embedding-3-small 嵌入 (Phase 3 启用)
    """

    # 显式指定 alias, 避免 LLM_/LLM 命名混乱
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # ---------- DeepSeek-V3 主力 ----------
    deepseek_api_key: str = Field(default="sk-your-deepseek-key", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")

    # ---------- MiniMax (Claude 兼容) 备用 ----------
    anthropic_api_key: str = Field(default="sk-ant-your-anthropic-key", validation_alias="MiniMax_API_KEY")
    anthropic_base_url: str = Field(default="https://api.MiniMax.com", validation_alias="MiniMax_BASE_URL")
    anthropic_model: str = Field(default="MiniMax-sonnet-4-6", validation_alias="MiniMax_MODEL")

    # ---------- OpenAI 嵌入 (text-embedding-3-small) ----------
    openai_api_key: str = Field(default="sk-your-openai-key", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    embedding_model: str = Field(default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1536, validation_alias="EMBEDDING_DIM")

    # ---------- LiteLLM Proxy 自身 ----------
    litellm_base_url: str = Field(default="http://litellm:4000/v1", validation_alias="LITELLM_BASE_URL")
    litellm_master_key: str = Field(default="sk-litellm-change-me", validation_alias="LITELLM_MASTER_KEY")

    # ---------- 路由策略 ----------
    router_strategy: Literal["cost_first", "quality_first", "manual"] = "cost_first"
    default_temperature: float = 0.3
    max_tokens: int = 4096


class EmbeddingSettings(BaseSettings):
    """Embedding & Reranker 配置.

    决策 (2026-06-04): 暂不引入本地 BGE-M3 / BGE-Reranker
    - Phase 3 起步用 OpenAI text-embedding-3-small (云端, 便宜)
    - Rerank 用 LiteLLM 调 DeepSeek (LLM-as-rerank) 或暂不做
    - 后续评估效果再决定是否引入本地模型
    """

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", case_sensitive=False, extra="ignore")

    # 主嵌入 (云端)
    model: str = "text-embedding-3-small"
    dim: int = 1536

    # 备用本地模型 (暂未启用, 留接口)
    local_model: str = "BAAI/bge-m3"
    local_dim: int = 1024
    use_local: bool = False   # 一键切换

    batch_size: int = 8
    retrieval_top_k: int = 20
    rerank_top_k: int = 8


class RAGFlowSettings(BaseSettings):
    """RAGFlow 知识库 (Phase 3)."""

    model_config = SettingsConfigDict(env_prefix="RAGFLOW_", case_sensitive=False, extra="ignore")

    enabled: bool = False
    api_key: str = "your-ragflow-api-key"
    base_url: str = "http://localhost:9380/api/v1"
    knowledge_base_id: str = ""


class MinerUSettings(BaseSettings):
    """MinerU PDF 解析服务 (Phase 2)."""

    # 显式 alias 避免与系统 LANG 冲突
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    enabled: bool = Field(default=False, validation_alias="MINERU_ENABLED")
    api_base: str = Field(default="http://localhost:8000", validation_alias="MINERU_API_BASE")
    parse_method: Literal["auto", "txt", "ocr"] = Field(default="auto", validation_alias="MINERU_PARSE_METHOD")
    lang: Literal["ch", "en", "korean", "japan"] = Field(default="ch", validation_alias="MINERU_LANG")
    device: Literal["cpu", "cuda"] = Field(default="cpu", validation_alias="MINERU_DEVICE")


class LangGraphSettings(BaseSettings):
    """LangGraph 状态图 (Phase 4)."""

    model_config = SettingsConfigDict(env_prefix="LANGGRAPH_", case_sensitive=False, extra="ignore")

    checkpoint_dir: str = "./langgraph_checkpoints"
    max_iterations: int = 5
    enable_human_loop: bool = True
    writer_parallel_workers: int = 4


class LogSettings(BaseSettings):
    """日志配置."""

    model_config = SettingsConfigDict(env_prefix="LOG_", case_sensitive=False, extra="ignore")

    level: str = "INFO"
    rotation: str = "100 MB"
    retention: str = "30 days"
    rate_limit_per_minute: int = 60


# ============================================
# 主配置
# ============================================
class Settings(BaseSettings):
    """聚合所有子配置, 单例导入用.

    注意: 各子配置自己声明 env_prefix, 主配置不再加 env_nested_delimiter.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    milvus: MilvusSettings = Field(default_factory=MilvusSettings)
    elasticsearch: ESSettings = Field(default_factory=ESSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    ragflow: RAGFlowSettings = Field(default_factory=RAGFlowSettings)
    mineru: MinerUSettings = Field(default_factory=MinerUSettings)
    langgraph: LangGraphSettings = Field(default_factory=LangGraphSettings)
    log: LogSettings = Field(default_factory=LogSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存配置实例 (避免反复解析 .env)."""
    return Settings()


# 全局单例 — 业务代码统一从此导入
settings = get_settings()
