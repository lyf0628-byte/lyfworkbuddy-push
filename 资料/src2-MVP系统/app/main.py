"""FastAPI 应用入口：健康检查 + 认证 + 对话（SSE）+ 通知确认。

尽量保持接口精简，员工端核心就是 /chat 与 /confirm_notify。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .db import init_db

app = FastAPI(title="行知旅行 · 行程变更与异常协作 MVP", version="1.0.0")

# 启动时初始化数据库（幂等）
_conn = init_db()


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "app": "行知旅行行程变更与异常协作 MVP",
        "llm": "online" if settings.has_llm else "offline",
        "version": "1.0.0",
    }


from .web import auth_routes, chat_routes, admin_routes  # noqa: E402  # 延迟导入，避免循环依赖

app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(admin_routes.router)


@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"ok": False, "error": f"服务器错误：{exc}"})
