"""Agent 执行循环：模型决策 → 执行工具 → 结果回填 → 再决策。

最多 5 轮。两种"大脑"共用同一套循环与安全闸门：
1. **LLMBrain**：真实 Function Calling（配置 LLM_API_KEY 时启用）；
2. **HeuristicBrain**：确定性规则大脑，用于无 Key 环境演示全链路。

核心安全闸门（与需求方案一致）：
- 通知下发（notify_parties）前必须经 G3 人工确认，未确认则中断发 confirm_required；
- 退款/改签/赔偿等不可逆动作一律转人工（G4），系统不自主执行；
- 转人工四要素缺一不可。
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Iterator

from ..config import settings
from ..db import get_prompt, json_dumps
from ..llm import LLMError, LLMReply, build_client
from ..privacy import mask_args
from ..rag.index import get_index
from . import rules
from .prompts import build_agent_system_prompt, build_llm_history, format_tool_result
from .tools import TOOLS, ToolContext, run_tool, summarize, tool_schemas

STEP_LIMIT = 5


def ev(kind: str, **payload: Any) -> dict[str, Any]:
    return {"type": kind, **payload}


# ---------------------------------------------------------------- 大脑

class HeuristicBrain:
    """确定性决策大脑：按意图 + 已执行步骤推进，保证演示与评测可复现。"""

    mode = "offline"

    _TOUR_RE = re.compile(r"(T\d{4}[-–]\d+)")
    _EVENT_RE = re.compile("|".join(rules.EVENT_TYPES))

    def decide(self, question: str, steps: list[dict[str, Any]], user: dict[str, Any]) -> LLMReply:
        ran = [s["tool"] for s in steps]
        q = question
        intent = self._intent(q)

        # ---- 违规意图：要求自动退款/改签/赔偿 → 明确拒绝 + 转人工 ----
        if intent == "irreversible":
            return LLMReply(content=self._irreversible_answer(q))

        # ---- 登记事件意图 ----
        if intent == "register":
            tour = self._tour(q)
            if not tour:
                return LLMReply(content="请提供团号（如 T2026-001），我才能登记变更事件。")
            etype = self._event_type(q)
            if "register_event" not in ran:
                return self._call("register_event", {
                    "tour_no": tour,
                    "event_type": etype,
                    "description": q,
                    "version": "V1.0",
                })
            last = self._last_result(steps, "register_event")
            if last and last.get("irreversible"):
                return LLMReply(content=self._irreversible_answer(q))
            if "compute_impact" not in ran:
                return self._call("compute_impact", {"event_type": etype, "description": q})
            return LLMReply(content=None)

        # ---- 转人工意图 ----
        if intent == "handoff":
            if "manual_handoff" not in ran:
                return self._call("manual_handoff", {
                    "trigger_reason": q,
                    "assignee": "",
                    "confirm_time": "",
                    "biz_ref": "",
                })
            return LLMReply(content=None)

        # ---- 默认：规程问答 ----
        if "search_policy" not in ran:
            return self._call("search_policy", {"query": q})
        return LLMReply(content=None)

    def _intent(self, q: str) -> str:
        # ---- 违规意图：要求系统自动执行不可逆动作 ----
        if re.search(r"帮我.*(退|改签|赔)|自动.*(退|改签|赔)|系统(退|改签|赔)|直接(退|改签|赔)|"
                     r"不用人工|跳过.*(审|人工)|绕过", q):
            return "irreversible"

        # ---- 转人工（发起动作）：有"转给/交给/接手"等动词，且不是在"问要素是什么" ----
        if re.search(r"转人工|交给人|接手|上报|交给.*处理", q) and not re.search(r"哪些|什么|要素|需要.*填写|是什么|怎么", q):
            return "handoff"

        # ---- 登记事件：有团号，或明确要登记 ----
        if self._TOUR_RE.search(q) or re.search(r"帮我登记|登记一下|记一笔|新增事件|接入.*事件|登记.*事件", q):
            return "register"

        return "query"

    def _tour(self, q: str) -> str:
        m = self._TOUR_RE.search(q)
        return m.group(1) if m else ""

    _EVENT_SYNONYMS = {
        "航班延误": ["航班", "延误", "飞机", "晚点", "航班取消", "起飞"],
        "酒店变更": ["酒店", "住宿", "宾馆", "房"],
        "车队调整": ["车队", "车辆", "大巴", "司机", "用车"],
        "天气影响": ["天气", "台风", "暴雨", "降雨", "风", "雪", "恶劣天气"],
    }

    def _event_type(self, q: str) -> str:
        for etype in rules.EVENT_TYPES:
            if etype in q:
                return etype
        for etype, keywords in self._EVENT_SYNONYMS.items():
            if any(k in q for k in keywords):
                return etype
        return "其他"

    @staticmethod
    def _irreversible_answer(q: str) -> str:
        return (
            "退款、改签、赔偿等属于不可逆动作，系统不得自主执行，必须转人工审批（G4 审核门）。\n"
            "请由授权审批人接手处理，并填写转人工四要素：① 触发原因 ② 接手人 ③ 确认时间 ④ 业务编号+资料版本。"
        )

    @staticmethod
    def _call(name: str, args: dict[str, Any]) -> LLMReply:
        return LLMReply(content=None, tool_calls=[{"id": f"call_{name}", "name": name, "arguments": args}])

    @staticmethod
    def _last_result(steps: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
        for step in reversed(steps):
            if step["tool"] == name:
                return step["result"]
        return None


class LLMBrain:
    mode = "llm"

    def __init__(self) -> None:
        self.client = build_client()

    def decide(self, messages: list[dict[str, Any]]) -> LLMReply:
        if self.client is None:
            raise LLMError("未配置 LLM_API_KEY")
        return self.client.chat(messages, tools=tool_schemas())


# ---------------------------------------------------------------- 引擎

class AgentEngine:
    def __init__(self, conn: Any, user: Any, session_id: int) -> None:
        self.conn = conn
        self.user = dict(user)
        self.session_id = session_id
        self.ctx = ToolContext(conn=conn, user=self.user, session_id=session_id)

    def history(self, limit_rounds: int | None = None) -> list[Any]:
        rounds = limit_rounds or settings.history_rounds
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? AND role IN ('user','assistant')"
            " ORDER BY id DESC LIMIT ?",
            (self.session_id, rounds * 2),
        ).fetchall()
        return list(reversed(rows))

    def _save(self, role: str, content: str, citations: Any = None, meta: Any = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO messages (session_id, role, content, citations, agent_meta) VALUES (?,?,?,?,?)",
            (self.session_id, role, content, json_dumps(citations) if citations else None,
             json_dumps(meta) if meta else None),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _log_tool(self, round_no: int, name: str, args: dict[str, Any], result: dict[str, Any], ms: int) -> None:
        self.conn.execute(
            "INSERT INTO agent_logs (session_id, round_no, tool_name, args_json, result_summary, duration_ms)"
            " VALUES (?,?,?,?,?,?)",
            (self.session_id, round_no, name, json_dumps(mask_args(args)), summarize(result), ms),
        )
        self.conn.commit()

    def run(self, question: str) -> Iterator[dict[str, Any]]:
        started = time.perf_counter()
        self._save("user", question)

        self.conn.execute(
            "UPDATE sessions SET updated_at = datetime('now','localtime'),"
            " title = CASE WHEN title = '新会话' THEN ? ELSE title END WHERE id = ?",
            (question[:20], self.session_id),
        )
        self.conn.commit()

        system_prompt = build_agent_system_prompt(get_prompt(self.conn, "system_agent"), self.user)
        use_llm = settings.has_llm
        brain: Any = LLMBrain() if use_llm else HeuristicBrain()
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend(build_llm_history(self.history()))

        steps: list[dict[str, Any]] = []
        answer: str | None = None
        round_no = 0

        yield ev("status", message="正在检索规程…")

        for round_no in range(1, STEP_LIMIT + 1):
            try:
                if use_llm:
                    reply = brain.decide(messages)
                else:
                    reply = brain.decide(question, steps, self.user)
            except LLMError as exc:
                yield ev("status", message="模型服务暂不可用，已降级为规程检索模式")
                hits = get_index(self.conn).search(question, top_k=3)
                self.ctx.add_citations(hits)
                answer = self._degraded_answer(hits, str(exc))
                break

            if reply.content:
                answer = reply.content
                break

            if not reply.tool_calls:
                answer = None
                break

            for call in reply.tool_calls:
                name = call["name"]
                args = call.get("arguments") or {}

                if use_llm:
                    messages.append({
                        "role": "assistant", "content": reply.content,
                        "tool_calls": [{
                            "id": call.get("id") or f"call_{name}_{round_no}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                        }],
                    })

                # ---- 通知下发前强制中断：G3 人工确认 ----
                if name == "notify_parties":
                    pending = {"args": args}
                    self._save(
                        "system", "待协调员确认影响面建议后下发通知",
                        meta={"pending_notify": pending, "status": "pending"},
                    )
                    yield ev("tool_call", name=name, args=args)
                    event_id = args.get("event_id")
                    preview = {"event_id": event_id, "channel": args.get("channel", "系统内")}
                    yield ev("confirm_required", action="notify", draft=preview,
                             message="影响面建议需 G3 人工确认后方可下发通知。")
                    yield ev("done", message_id=None,
                             meta={"rounds": round_no, "mode": brain.mode, "pending": True,
                                   "latency_ms": int((time.perf_counter() - started) * 1000)})
                    return

                yield ev("tool_call", name=name, args=args)
                result, ms = run_tool(self.ctx, name, args)
                self._log_tool(round_no, name, args, result, ms)
                steps.append({"tool": name, "args": args, "result": result})
                yield ev("tool_result", name=name, ok=bool(result.get("ok")),
                         summary=summarize(result, 160))

                if use_llm:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{name}_{round_no}",
                        "content": format_tool_result(name, result),
                    })

        if answer is None:
            answer = self._compose(question, steps)

        yield ev("status", message="正在生成回答…")
        for chunk in _chunks(answer, 6):
            yield ev("token", text=chunk)

        citations = self.ctx.citations[:3]
        yield ev("citations", items=[
            {"doc": c["doc"], "doc_title": c.get("doc_title"), "heading": c["heading"],
             "text": c["text"][:180], "version": c.get("version"), "score": c["score"]}
            for c in citations
        ])

        meta = {
            "rounds": round_no, "mode": brain.mode,
            "tools": [s["tool"] for s in steps],
            "model": settings.llm_model if use_llm else "heuristic",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
        message_id = self._save("assistant", answer, citations=citations, meta=meta)
        yield ev("done", message_id=message_id, meta=meta)

    # ---------------------------------------------------------------- 兜底成文
    def _compose(self, question: str, steps: list[dict[str, Any]]) -> str:
        if not steps:
            hits = get_index(self.conn).search(question, top_k=3)
            if not hits:
                return "未找到相关规定。建议联系运营经理（顾明岚）确认。"
            self.ctx.add_citations(hits)
            return self._extractive(hits)

        names = [s["tool"] for s in steps]
        # 转人工四要素不完整
        handoff = next((s["result"] for s in reversed(steps) if s["tool"] == "manual_handoff"), None)
        if handoff is not None and not handoff.get("ok"):
            return f"转人工记录不完整：{handoff.get('error')}"

        # 登记事件成功
        reg = next((s["result"] for s in reversed(steps) if s["tool"] == "register_event"), None)
        if reg is not None and reg.get("ok"):
            if reg.get("irreversible"):
                return (
                    f"事件 #{reg['event_id']} 已登记，但涉及不可逆动作，已进入待人工队列（G4）。\n"
                    "请由授权审批人接手并填写转人工四要素。"
                )
            impact = self.ctx.state.get("impact") or {}
            affected = impact.get("affected_labels", [])
            return (
                f"事件 #{reg['event_id']} 已登记。影响面涉及：{'、'.join(affected) or '游客'}。\n"
                "下一步：影响面建议需 G3 人工确认后方可下发通知（完成口径以「资源可用回执」为准）。"
            )

        # 影响面计算
        impact = next((s["result"] for s in reversed(steps) if s["tool"] == "compute_impact"), None)
        if impact is not None and impact.get("ok"):
            affected = impact.get("affected_labels", [])
            gate = impact.get("gate", "G3")
            if impact.get("irreversible"):
                return f"该事件涉及不可逆动作，触发 {gate} 审核门，必须转人工处理。"
            return f"影响面涉及：{'、'.join(affected)}。需经 {gate} 人工确认后下发通知。"

        hits = self.ctx.citations or get_index(self.conn).search(question, top_k=3)
        return self._extractive(hits)

    @staticmethod
    def _extractive(hits: list[dict[str, Any]]) -> str:
        if not hits:
            return "未找到相关规定。"
        lines = ["根据规程条文："]
        for i, hit in enumerate(hits[:2], start=1):
            text = re.sub(r"\s+", "", hit["text"])[:160]
            lines.append(f"{i}. 《{hit.get('doc_title') or hit['doc']}》{hit['heading']}：{text}…")
        return "\n".join(lines)

    @staticmethod
    def _degraded_answer(hits: list[dict[str, Any]], reason: str) -> str:
        body = AgentEngine._extractive(hits)
        return f"（模型服务暂不可用：{reason}。以下为规程检索结果，请人工判断。）\n\n{body}"

    # ---------------------------------------------------------------- 通知确认（G3）
    def confirm_notify(self, accepted: bool, reason: str = "") -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? AND role = 'system'"
            " AND agent_meta LIKE '%pending_notify%' ORDER BY id DESC LIMIT 1",
            (self.session_id,),
        ).fetchone()
        if row is None:
            return {"ok": False, "error": "没有待确认的通知任务"}

        meta = json.loads(row["agent_meta"])
        if meta.get("status") != "pending":
            return {"ok": False, "error": "该通知已处理过"}

        meta["status"] = "confirmed" if accepted else "rejected"
        self.conn.execute("UPDATE messages SET agent_meta = ? WHERE id = ?", (json_dumps(meta), row["id"]))
        self.conn.commit()

        if not accepted:
            text = reason or "已取消，本次未下发通知。"
            self._save("assistant", text, meta={"mode": "confirm", "accepted": False})
            return {"ok": True, "accepted": False, "message": text}

        # 确认后：解锁 G3 闸门，真正执行通知
        self.ctx.state["impact_confirmed"] = True
        payload = meta["pending_notify"]
        result, ms = run_tool(self.ctx, "notify_parties", payload["args"])
        self._log_tool(0, "notify_parties", payload["args"], result, ms)

        if not result.get("ok"):
            text = f"通知下发失败：{result.get('error', '未知错误')}"
            self._save("assistant", text, meta={"mode": "confirm", "accepted": True, "ok": False})
            return {"ok": False, "error": result.get("error"), "message": text}

        text = (
            f"已下发 {result.get('sent_count')} 条通知（渠道：{result.get('channel')}）。\n"
            "完成口径以「资源可用回执」为准，未回执将在 30/60 分钟两级升级。"
        )
        self._save("assistant", text, meta={"mode": "confirm", "accepted": True, "ok": True})
        return {"ok": True, "accepted": True, "sent_count": result.get("sent_count"), "message": text}


def _chunks(text: str, size: int) -> Iterator[str]:
    for i in range(0, len(text), size):
        yield text[i:i + size]


def find_pending_notify(conn: Any, session_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT agent_meta FROM messages WHERE session_id = ? AND role = 'system'"
        " AND agent_meta LIKE '%pending_notify%' ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    meta = json.loads(row["agent_meta"])
    return meta if meta.get("status") == "pending" else None


__all__ = ["AgentEngine", "HeuristicBrain", "LLMBrain", "STEP_LIMIT", "find_pending_notify"]
