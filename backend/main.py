"""
本地开发启动入口.

用法
----
    python -m backend.main                  # 直接启动
    python -m backend.main --reload          # 热重载
    uvicorn backend.api.main:app --reload   # 等价

生产
----
    uvicorn backend.api.main:app \
        --host 0.0.0.0 --port 8000 \
        --workers 4 --proxy-headers
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path (支持 `python -m backend.main` 运行)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Medical Paper Platform backend")
    parser.add_argument("--host", default=os.getenv("BACKEND_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BACKEND_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--workers", type=int, default=1, help="生产 workers (与 --reload 互斥)")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_config=None,  # 用我们自己的 loguru
        access_log=False,  # 关闭 uvicorn 自带, 用我们中间件
    )


if __name__ == "__main__":
    main()
