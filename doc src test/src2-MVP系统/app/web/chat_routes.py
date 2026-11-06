"""对话路由：SSE 流式问答 + 通知确认（G3 闸门）。"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..agent.engine import AgentEngine, find_pending_notify
from ..config import settings
from ..db import get_conn, query_one

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "web" / "templates"))


def _user_from_request(request: Request):
    from ..security import verify_token
    token = request.cookies.get("token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    conn = get_conn()
    return query_one(conn, "SELECT * FROM users WHERE id = ?", (payload.get("uid"),))


def _ensure_user(request: Request):
    user = _user_from_request(request)
    if user is None:
        return None
    return user


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    user = _user_from_request(request)
    if user is None:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
    # 管理端角色不进入员工聊天页，统一回管理后台
    if user["role"] in ("admin", "ops_manager", "security"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin")
    conn = get_conn()
    sessions = conn.execute(
        "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20", (user["id"],)
    ).fetchall()
    return templates.TemplateResponse(request, "chat.html", {
        "user": dict(user), "sessions": [dict(s) for s in sessions],
    })


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/api/chat")
async def chat_stream(request: Request):
    user = _ensure_user(request)
    if user is None:
        return StreamingResponse(iter([_sse({"type": "error", "message": "未登录"})]),
                                media_type="text/event-stream")
    data = await request.json()
    question = (data.get("message") or "").strip()
    session_id = data.get("session_id") or 0
    if not question:
        return StreamingResponse(iter([_sse({"type": "error", "message": "消息为空"})]),
                                media_type="text/event-stream")

    conn = get_conn()
    if not session_id:
        cur = conn.execute("INSERT INTO sessions (user_id) VALUES (?)", (user["id"],))
        conn.commit()
        session_id = cur.lastrowid

    engine = AgentEngine(conn, user, session_id)

    def gen():
        try:
            for event in engine.run(question):
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/confirm_notify")
async def confirm_notify(request: Request):
    user = _ensure_user(request)
    if user is None:
        return {"ok": False, "error": "未登录"}
    data = await request.json()
    accepted = bool(data.get("accepted"))
    reason = data.get("reason", "")
    session_id = data.get("session_id") or 0

    conn = get_conn()
    engine = AgentEngine(conn, user, session_id)
    return engine.confirm_notify(accepted, reason)


@router.get("/api/pending_notify")
def pending_notify(request: Request):
    user = _ensure_user(request)
    if user is None:
        return {"ok": False, "error": "未登录"}
    session_id = int(request.query_params.get("session_id") or 0)
    conn = get_conn()
    pending = find_pending_notify(conn, session_id)
    return {"ok": True, "pending": pending}
