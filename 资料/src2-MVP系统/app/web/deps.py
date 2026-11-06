"""Web 依赖：从 Cookie 解析当前用户。"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from ..db import get_conn, query_one
from ..security import verify_token


def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    conn = get_conn()
    user = query_one(conn, "SELECT * FROM users WHERE id = ?", (payload.get("uid"),))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_admin(user=Depends(get_current_user)):
    if user["role"] not in ("admin", "ops_manager", "security"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
