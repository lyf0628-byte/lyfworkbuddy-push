"""Agent 工具集（Function Calling 规范）+ 业务约束。

六个工具，按"权限由小到大"排列：
    search_policy          只读，查规程条文
    compute_impact         只读，计算变更影响面（按事件类型映射）
    register_event         写库，登记变更事件
    notify_parties         写库，登记通知任务（有副作用，需 G3 人工确认）
    manual_handoff         写库，转人工四要素留痕（G4 红线）
    list_my_events         只读，查当前用户的变更事件

调用顺序约束（**由代码强制，不只写在提示词里**）：
    notify_parties 要求 ctx.state["impact_confirmed"] 为 True（G3 已人工确认）；
    未确认时 notify_parties 直接返回 GATE_G3_REQUIRED。
    manual_handoff 要求四要素齐备；缺一返回 MISSING_HANDOFF_FIELDS。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..db import json_dumps
from ..rag.index import get_index
from . import rules


@dataclass
class ToolContext:
    conn: Any
    user: dict[str, Any]
    session_id: int
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def citations(self) -> list[dict[str, Any]]:
        return self.state.setdefault("citations", [])

    def add_citations(self, rows: list[dict[str, Any]]) -> None:
        seen = {(c["doc"], c["heading"], c["text"][:40]) for c in self.citations}
        for row in rows:
            key = (row["doc"], row["heading"], row["text"][:40])
            if key not in seen:
                seen.add(key)
                self.citations.append(row)


# ---------------------------------------------------------------- 工具实现

def _tool_search_policy(ctx: ToolContext, query: str = "", **_kw: Any) -> dict[str, Any]:
    index = get_index(ctx.conn)
    hits = index.search(query or "", top_k=3)
    ctx.add_citations(hits)
    return {
        "ok": True, "query": query,
        "hits": [
            {"heading": h["heading"], "doc": h["doc"], "doc_title": h.get("doc_title"),
             "score": h["score"], "text": h["text"][:300]}
            for h in hits
        ],
        "hint": "只能依据 hits 里的条文回答；hits 为空则回答'未找到相关规定'。",
    }


def _tool_compute_impact(ctx: ToolContext, event_type: str = "", description: str = "", **_kw: Any) -> dict[str, Any]:
    result = rules.compute_impact(event_type, description)
    ctx.state["impact"] = result
    # 触发红线时，绝不自动进入通知，强制 G4
    result["next_gate"] = result["gate"]
    hits = get_index(ctx.conn).search(f"{event_type} 影响面 通知 回执", top_k=2)
    ctx.add_citations(hits)
    return result


def _tool_register_event(
    ctx: ToolContext,
    tour_no: str = "",
    order_no: str = "",
    version: str = "V1.0",
    event_type: str = "其他",
    description: str = "",
    **_kw: Any,
) -> dict[str, Any]:
    if not tour_no.strip():
        return {"ok": False, "error_code": "TOUR_NO_REQUIRED", "error": "团号必填"}
    if not rules.validate_version(version):
        return {"ok": False, "error_code": "BAD_VERSION", "error": f"版本号「{version}」格式不合法，应为 V主.次"}
    if is_irr := rules.is_irreversible(description):
        # 触发红线：登记但不进入自动流程，强制转人工（G4）
        cur = ctx.conn.execute(
            "INSERT INTO change_events (tour_no, order_no, version, event_type, description, status, created_by)"
            " VALUES (?,?,?,?,?, 'manual', ?)",
            (tour_no, order_no, version, event_type, description, ctx.user["id"]),
        )
        event_id = cur.lastrowid
        ctx.conn.commit()
        ctx.state["irreversible_event"] = event_id
        return {
            "ok": True, "event_id": event_id, "irreversible": True, "gate": "G4",
            "error_code": None,
            "hint": "该事件涉及不可逆动作，已登记为待人工状态，需转人工四要素留痕后由授权审批人处理。",
        }
    cur = ctx.conn.execute(
        "INSERT INTO change_events (tour_no, order_no, version, event_type, description, status, created_by)"
        " VALUES (?,?,?,?,?, 'registered', ?)",
        (tour_no, order_no, version, event_type, description, ctx.user["id"]),
    )
    event_id = cur.lastrowid
    ctx.conn.commit()
    ctx.state["event_id"] = event_id
    return {"ok": True, "event_id": event_id, "irreversible": False, "gate": "G2"}


def _tool_notify_parties(
    ctx: ToolContext,
    event_id: int = 0,
    parties: list[dict[str, Any]] | None = None,
    channel: str = "系统内",
    **_kw: Any,
) -> dict[str, Any]:
    # ---- 闸门：G3 人工确认（影响面建议必须人工确认后才可下发）----
    if not ctx.state.get("impact_confirmed"):
        return {
            "ok": False, "error_code": "GATE_G3_REQUIRED",
            "error": "通知下发前必须经 G3 审核门人工确认影响面建议，禁止系统自主下发。",
            "next": "请先由协调员确认影响面建议（确认后调用 confirm_impact）。",
        }
    if not event_id:
        return {"ok": False, "error_code": "EVENT_REQUIRED", "error": "缺少事件编号"}
    parties = parties or []
    if not parties:
        impact = ctx.state.get("impact") or {}
        for t in impact.get("affected_types", ["tourist"]):
            parties.append({"party_type": t, "party_name": rules.PARTY_TYPE_LABEL.get(t, t)})

    task_ids = []
    for p in parties:
        cur = ctx.conn.execute(
            "INSERT INTO notify_tasks (event_id, channel, status) VALUES (?,?, 'sent')",
            (event_id, channel),
        )
        task_ids.append(cur.lastrowid)
        ctx.conn.execute(
            "INSERT INTO affected_parties (event_id, party_type, party_name) VALUES (?,?,?)",
            (event_id, p.get("party_type", "tourist"), p.get("party_name", "")),
        )
    ctx.conn.execute("UPDATE change_events SET status = 'notified' WHERE id = ?", (event_id,))
    ctx.conn.commit()
    return {
        "ok": True, "event_id": event_id, "task_ids": task_ids,
        "channel": channel, "sent_count": len(task_ids),
        "message": f"已登记 {len(task_ids)} 条通知任务（完成口径以「资源可用回执」为准，非「已发送」）。",
    }


def _tool_manual_handoff(
    ctx: ToolContext,
    trigger_reason: str = "",
    assignee: str = "",
    confirm_time: str = "",
    biz_ref: str = "",
    event_id: int = 0,
    **_kw: Any,
) -> dict[str, Any]:
    fields = {
        "trigger_reason": trigger_reason, "assignee": assignee,
        "confirm_time": confirm_time, "biz_ref": biz_ref,
    }
    ok, missing = rules.handoff_fields_valid(fields)
    if not ok:
        return {
            "ok": False, "error_code": "MISSING_HANDOFF_FIELDS",
            "error": f"转人工四要素不完整，缺少：{'、'.join(missing)}。仅给模糊提醒不予验收。",
            "missing": missing,
        }
    cur = ctx.conn.execute(
        "INSERT INTO manual_handoffs (event_id, trigger_reason, assignee, confirm_time, biz_ref, created_by)"
        " VALUES (?,?,?,?,?,?)",
        (event_id or None, trigger_reason, assignee, confirm_time, biz_ref, ctx.user["id"]),
    )
    ctx.conn.commit()
    if event_id:
        ctx.conn.execute("UPDATE change_events SET status = 'manual' WHERE id = ?", (event_id,))
        ctx.conn.commit()
    return {
        "ok": True, "handoff_id": cur.lastrowid, "gate": "G4",
        "message": "转人工四要素已留痕，责任链可追溯。",
    }


def _tool_list_my_events(ctx: ToolContext, **_kw: Any) -> dict[str, Any]:
    rows = ctx.conn.execute(
        "SELECT id, tour_no, order_no, version, event_type, description, status, created_at"
        " FROM change_events WHERE created_by = ? ORDER BY id DESC LIMIT 20",
        (ctx.user["id"],),
    ).fetchall()
    return {"ok": True, "events": [dict(r) for r in rows], "count": len(rows)}


# ---------------------------------------------------------------- 注册表

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    side_effect: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


TOOLS: dict[str, Tool] = {
    "search_policy": Tool(
        name="search_policy",
        description="检索行知旅行变更协作规程条文。任何关于流程、口径、审核门、权限的结论都必须先调用它。",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "自然语言检索词，例如「转人工四要素」"}},
            "required": ["query"],
        },
        handler=_tool_search_policy,
    ),
    "compute_impact": Tool(
        name="compute_impact",
        description="按变更事件类型计算影响面（受影响对象类型），并判断是否触发不可逆红线。通知下发前必须先调用它。",
        parameters={
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "enum": rules.EVENT_TYPES},
                "description": {"type": "string", "description": "事件描述，用于判断是否触发退款/改签等红线"},
            },
            "required": ["event_type"],
        },
        handler=_tool_compute_impact,
    ),
    "register_event": Tool(
        name="register_event",
        description="登记一次行程变更事件（有副作用）。涉及退款/改签等不可逆动作时自动标记为待人工（G4）。",
        parameters={
            "type": "object",
            "properties": {
                "tour_no": {"type": "string", "description": "团号，如 T2026-001"},
                "order_no": {"type": "string", "description": "订单号"},
                "version": {"type": "string", "description": "资料版本，如 V1.0"},
                "event_type": {"type": "string", "enum": rules.EVENT_TYPES},
                "description": {"type": "string"},
            },
            "required": ["tour_no", "event_type", "description"],
        },
        handler=_tool_register_event,
        side_effect=True,
    ),
    "notify_parties": Tool(
        name="notify_parties",
        description="登记通知任务（有副作用）。前置条件：影响面建议已经 G3 人工确认，否则拒绝执行。",
        parameters={
            "type": "object",
            "properties": {
                "event_id": {"type": "integer"},
                "parties": {"type": "array", "items": {"type": "object"}, "description": "受影响对象列表"},
                "channel": {"type": "string", "description": "通知渠道，默认系统内"},
            },
            "required": ["event_id"],
        },
        handler=_tool_notify_parties,
        side_effect=True,
    ),
    "manual_handoff": Tool(
        name="manual_handoff",
        description="转人工四要素强制留痕（有副作用）。退款/改签/赔偿等不可逆动作一律走此工具，四要素缺一不可。",
        parameters={
            "type": "object",
            "properties": {
                "trigger_reason": {"type": "string", "description": "① 触发原因"},
                "assignee": {"type": "string", "description": "② 接手人"},
                "confirm_time": {"type": "string", "description": "③ 确认时间"},
                "biz_ref": {"type": "string", "description": "④ 业务编号+资料版本"},
                "event_id": {"type": "integer"},
            },
            "required": ["trigger_reason", "assignee", "confirm_time", "biz_ref"],
        },
        handler=_tool_manual_handoff,
        side_effect=True,
    ),
    "list_my_events": Tool(
        name="list_my_events",
        description="查看当前用户登记的变更事件。",
        parameters={"type": "object", "properties": {}},
        handler=_tool_list_my_events,
    ),
}


def tool_schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in TOOLS.values()]


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], int]:
    tool = TOOLS.get(name)
    if tool is None:
        return {"ok": False, "error_code": "UNKNOWN_TOOL", "error": f"未注册的工具：{name}"}, 0
    started = time.perf_counter()
    try:
        result = tool.handler(ctx, **(args or {}))
    except TypeError as exc:
        result = {"ok": False, "error_code": "BAD_ARGUMENTS", "error": f"参数不合法：{exc}"}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error_code": "TOOL_FAILED", "error": f"工具执行失败：{exc}"}
    duration_ms = int((time.perf_counter() - started) * 1000)
    return result, duration_ms


def summarize(result: dict[str, Any], limit: int = 240) -> str:
    text = json.dumps(result, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


__all__ = ["TOOLS", "ToolContext", "run_tool", "tool_schemas", "summarize", "json_dumps"]
