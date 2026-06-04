"""
SQLAlchemy 声明性基类 + 通用 Mixin.

约定
----
- 所有 Model 必须显式声明 `__tablename__`
- 时间戳字段 (created_at / updated_at) 由 TimestampMixin 提供
- 软删除字段 (deleted_at) 由 SoftDeleteMixin 提供
- 不要在 Model 写业务逻辑, 放到 schemas 或 services
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# 命名约束: 让 Alembic 迁移时能正确引用
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # 通用类型注解
    type_annotation_map: dict[type, Any] = {}

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        """默认表名: 类名转 snake_case + 复数化 (简化版: 直接加 s)."""
        name = cls.__name__
        # CamelCase -> snake_case
        import re

        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return f"{snake}s"


# ============================================
# Mixin
# ============================================
class TimestampMixin:
    """自动维护 created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )


class SoftDeleteMixin:
    """软删除 (deleted_at IS NULL 表示未删除)."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="删除时间 (软删)",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
