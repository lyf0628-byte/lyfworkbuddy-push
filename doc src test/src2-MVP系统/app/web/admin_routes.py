"""管理后台路由：知识库 / 变更事件 / 通知任务 / 转人工记录 / 审核门日志。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..db import get_conn

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "web" / "templates"))


def _admin_user(request: Request):
    from ..security import verify_token
    from ..db import query_one
    token = request.cookies.get("token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    conn = get_conn()
    user = query_one(conn, "SELECT * FROM users WHERE id = ?", (payload.get("uid"),))
    if user is None or user["role"] not in ("admin", "ops_manager", "security"):
        return None
    return user


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = _admin_user(request)
    if user is None:
        return RedirectResponse(url="/login")
    conn = get_conn()
    events = conn.execute("SELECT * FROM change_events ORDER BY id DESC LIMIT 50").fetchall()
    notify = conn.execute("SELECT * FROM notify_tasks ORDER BY id DESC LIMIT 50").fetchall()
    handoffs = conn.execute("SELECT * FROM manual_handoffs ORDER BY id DESC LIMIT 50").fetchall()
    gates = conn.execute("SELECT * FROM gate_logs ORDER BY id DESC LIMIT 50").fetchall()
    docs = conn.execute("SELECT id, title, version, status, updated_at FROM policy_docs ORDER BY id").fetchall()

    # ---- 看板统计指标（口径与 rules.key_metrics 一致）----
    stats = {
        "event_total": conn.execute("SELECT COUNT(*) c FROM change_events").fetchone()["c"],
        "event_closed": conn.execute(
            "SELECT COUNT(*) c FROM change_events WHERE status = 'closed'").fetchone()["c"],
        "event_notified": conn.execute(
            "SELECT COUNT(*) c FROM change_events WHERE status = 'notified'").fetchone()["c"],
        "notify_pending": conn.execute(
            "SELECT COUNT(*) c FROM notify_tasks WHERE status IN ('pending','sent')").fetchone()["c"],
        "notify_confirmed": conn.execute(
            "SELECT COUNT(*) c FROM notify_tasks WHERE status = 'confirmed'").fetchone()["c"],
        "handoff_total": conn.execute("SELECT COUNT(*) c FROM manual_handoffs").fetchone()["c"],
        "gate_total": conn.execute("SELECT COUNT(*) c FROM gate_logs").fetchone()["c"],
        "gate_passed": conn.execute(
            "SELECT COUNT(*) c FROM gate_logs WHERE result = 'passed'").fetchone()["c"],
        "user_total": conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
    }

    return templates.TemplateResponse(request, "admin_dashboard.html", {
        "user": dict(user),
        "events": [dict(e) for e in events],
        "notify": [dict(n) for n in notify],
        "handoffs": [dict(h) for h in handoffs],
        "gates": [dict(g) for g in gates],
        "docs": [dict(d) for d in docs],
        "stats": stats,
    })


@router.get("/admin/events", response_class=HTMLResponse)
def admin_events(request: Request):
    user = _admin_user(request)
    if user is None:
        return RedirectResponse(url="/login")
    conn = get_conn()
    events = conn.execute("SELECT * FROM change_events ORDER BY id DESC LIMIT 200").fetchall()
    return templates.TemplateResponse(request, "admin_events.html", {
        "user": dict(user), "events": [dict(e) for e in events],
    })
