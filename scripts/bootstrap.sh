#!/usr/bin/env bash
# ============================================
# 首次启动脚本 (开发环境)
# ============================================
# 1. 创建 .env (从 .env.example 复制, 如不存在)
# 2. 创建虚拟环境 (uv / venv)
# 3. 安装依赖
# 4. 创建数据目录
# ============================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 项目根: $PROJECT_ROOT"

# ---------- 1. .env ----------
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "✅ 已创建 .env (从 .env.example, 请填入真实密钥)"
else
    echo "⏭  .env 已存在, 跳过"
fi

# ---------- 2. 虚拟环境 ----------
if [[ ! -d .venv ]]; then
    echo "🔧 创建虚拟环境 .venv ..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# ---------- 3. 依赖 ----------
echo "📦 升级 pip + 安装依赖 ..."
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# ---------- 4. 数据目录 ----------
mkdir -p data/{uploads,tmp,outputs} logs langgraph_checkpoints tests/test_pdfs
echo "✅ 数据目录已创建"

echo ""
echo "🎉 引导完成! 下一步:"
echo "   1. 编辑 .env 填入 DeepSeek/Anthropic 等 API Key"
echo "   2. cd docker && make up  (启动基础服务)"
echo "   3. alembic upgrade head   (初始化数据库表)"
echo "   4. python -m backend.main --reload  (启动 API)"
