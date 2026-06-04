"""
Python 兼容性垫片.

目的
----
在 Python < 3.9 时, `typing.Annotated` 不存在. 用 `typing_extensions.Annotated` 兜底.
FastAPI 0.95+ / Pydantic 2.x 都强依赖 Annotated, 写代码时统一从这里导入.
"""
from __future__ import annotations

# typing.Annotated 在 Python 3.9+ 才有, 老版本用 typing_extensions 兜底
try:
    from typing import Annotated  # noqa: F401
except ImportError:  # Python < 3.9
    from typing_extensions import Annotated  # noqa: F401

__all__ = ["Annotated"]
