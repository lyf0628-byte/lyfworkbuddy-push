"""认证路由：登录 / 登出 / 首页。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..db import get_conn, query_one
from ..security import create_token, verify_password

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "web" / "templates"))


@router.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/chat")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    conn = get_conn()
    user = query_one(conn, "SELECT * FROM users WHERE username = ?", (username,))
    if user is None or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "login.html", {"error": "用户名或密码错误"})
    token = create_token({"uid": user["id"], "role": user["role"]})
    resp = RedirectResponse(url="/chat", status_code=302)
    resp.set_cookie("token", token, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie("token")
    return resp
