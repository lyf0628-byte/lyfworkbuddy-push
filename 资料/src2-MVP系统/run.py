"""Web 启动器：依赖自检 + 启动 uvicorn。

用法：
    python run.py                 # 默认 8000 端口
    python run.py --port 8124     # 指定端口
    python run.py --reset         # 重置数据库

云端部署（应用发布平台）：
    平台会注入 PORT 环境变量并要求绑定 0.0.0.0，本启动器自动识别：
    存在 PORT 时优先采用，host 切换为 0.0.0.0，且不自动打开浏览器。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    _env_port = os.environ.get("PORT")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(_env_port) if _env_port else 8000)
    parser.add_argument("--host", default="0.0.0.0" if _env_port else "127.0.0.1")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.reset:
        from app.config import settings
        db = settings.db_path
        if db.exists():
            db.unlink()
            print(f"已删除数据库 {db}")

    # 依赖自检
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import jinja2  # noqa: F401
    except ImportError as e:
        print(f"缺少依赖：{e}")
        print("请先安装：python -m pip install -r requirements.txt")
        sys.exit(1)

    from app.config import settings
    from app.db import init_db
    init_db()

    url = f"http://{args.host}:{args.port}"
    print(f"行知旅行 · 行程变更协作 MVP 已启动：{url}")
    print(f"健康检查：{url}/healthz")
    print("账号：linyizhou/emp123（导游）、admin/admin123（运营经理）")

    if not args.no_browser and not _env_port:
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
