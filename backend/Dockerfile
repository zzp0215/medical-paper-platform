# ============================================
# Backend Dockerfile (Phase 1.1.4)
# ============================================
# 构建:  docker build -t medpaper-backend -f backend/Dockerfile .
# 运行:  docker run --rm -p 8000:8000 --env-file .env medpaper-backend
# 依赖:  root requirements.txt (Phase 1-6 全部依赖)
# ============================================

FROM python:3.10-slim AS base

# 环境
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# 系统依赖 (curl 仅健康检查; build-essential 给某些 wheel 备用)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖, 利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 再拷源码 (变更频率低 → 缓存命中率高)
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 非 root 运行
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# 启动 (生产用 4 workers, 镜像默认 1)
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
