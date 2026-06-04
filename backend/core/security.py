"""
安全工具 (JWT + 密码哈希).

现状
----
Phase 1.1.4 阶段只搭骨架, 实际鉴权在 Phase 5 完善:
- /api/v1/auth/login 接口
- OAuth2PasswordBearer 依赖
- refresh_token 机制
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import settings
from backend.core.exceptions import UnauthorizedError

# 密码哈希 (bcrypt, 成本因子 12 兼顾安全/性能)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ============================================
# 密码
# ============================================
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ============================================
# JWT
# ============================================
def create_access_token(
    subject: str | int,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """签发 access token.

    Args:
        subject: 用户标识 (写进 sub claim)
        expires_minutes: 过期分钟数, 默认从 settings 读
        extra_claims: 额外声明 (role, scope 等)
    """
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=expires_minutes or settings.app.jwt_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.app.jwt_secret, algorithm=settings.app.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """解码并校验 token, 失败抛 UnauthorizedError."""
    try:
        return jwt.decode(token, settings.app.jwt_secret, algorithms=[settings.app.jwt_algorithm])
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {e}") from e


# ============================================
# 工具
# ============================================
def generate_api_key(length: int = 32) -> str:
    """生成安全随机 API Key."""
    return secrets.token_urlsafe(length)


def fingerprint(content: str | bytes) -> str:
    """计算内容指纹 (用于 PDF 去重)."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
