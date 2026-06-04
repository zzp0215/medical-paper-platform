"""
Alembic 环境配置.

要点
----
- 从 .env 读 DATABASE_URL (避免硬编码密码)
- 引入所有 model, autogenerate 才能识别
- offline / online 两种模式都支持
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 alembic 能 import backend.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import settings  # noqa: E402
from backend.db.base import Base  # noqa: E402
from backend import models  # noqa: E402,F401  (触发 model 注册)

config = context.config

# 动态注入数据库 URL (覆盖 alembic.ini 里的 sqlalchemy.url)
config.set_main_option("sqlalchemy.url", settings.database.sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 元数据 target (autogenerate 用)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式: 输出 SQL 不连 DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 命名约定保持一致
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式: 直连 DB 执行迁移."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 兼容 (虽然我们用 PG)
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
