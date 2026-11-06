"""提示词组装：系统提示词 + 历史拼接 + 工具结果格式化 + 引用渲染。"""
from __future__ import annotations

import json
from typing import Any


def build_agent_system_prompt(template: str, user: dict[str, Any]) -> str:
    role_label = user.get("role", "employee")
    return (
        f"{template}\n\n"
        f"当前用户：{user.get('display_name', '')}，角色：{role_label}，部门：{user.get('department', '')}。\n"
        "回答请用简体中文，简洁、给数字、给依据。"
    )


def build_llm_history(rows: list[Any]) -> list[dict[str, Any]]:
    """把 DB 里的消息行转成 OpenAI messages（只取 user/assistant，system 跳过）。"""
    msgs: list[dict[str, Any]] = []
    for r in rows:
        role = r["role"]
        if role not in ("user", "assistant"):
            continue
        msgs.append({"role": role, "content": r["content"]})
    return msgs


def format_tool_result(name: str, result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)


def render_citations(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return ""
    lines = ["\n\n依据："]
    for i, c in enumerate(citations[:3], start=1):
        lines.append(f"{i}. 《{c.get('doc_title') or c.get('doc')}》{c.get('heading', '')}")
    return "\n".join(lines)
