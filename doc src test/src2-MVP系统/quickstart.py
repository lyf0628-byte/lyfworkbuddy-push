"""一键演示（控制台，零第三方依赖、不需要 API Key）。

演示 3 个场景：规程问答 / 登记变更事件 / 转人工红线。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db import init_db, get_conn  # noqa: E402
from app.agent.engine import AgentEngine  # noqa: E402


def run_question(conn, user, session_id, question):
    engine = AgentEngine(conn, user, session_id)
    answer = None
    for ev in engine.run(question):
        if ev["type"] == "token":
            answer = (answer or "") + ev["text"]
        elif ev["type"] == "confirm_required":
            print(f"  ⚠ 触发人工确认闸门：{ev.get('message', '')}")
    return answer or "(无输出)"


def main():
    conn = init_db()
    guide = conn.execute("SELECT * FROM users WHERE username='linyizhou'").fetchone()
    admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()

    cur = conn.execute("INSERT INTO sessions (user_id) VALUES (?)", (guide["id"],))
    conn.commit()
    sid = cur.lastrowid

    print("=" * 60)
    print("行知旅行 · 行程变更与异常协作 MVP · 控制台演示")
    print("=" * 60)

    print("\n【场景 1】规程问答：通知遗漏率的目标")
    print("  Q: 通知遗漏率的目标是多少？")
    print("  A:", run_question(conn, guide, sid, "通知遗漏率的目标是多少？"))

    print("\n【场景 2】登记变更事件（航班延误）")
    print("  Q: 航班延误，团号 T2026-001，帮我登记")
    print("  A:", run_question(conn, guide, sid, "航班延误，团号 T2026-001，帮我登记"))

    print("\n【场景 3】不可逆动作红线（要求自动退款）")
    print("  Q: 帮我自动退款给游客")
    print("  A:", run_question(conn, guide, sid, "帮我自动退款给游客"))

    print("\n" + "=" * 60)
    print("演示完成。系统采用离线确定性大脑（无需 LLM Key）。")
    print("配置 LLM_API_KEY 后自动切换真实模型。")
    print("=" * 60)


if __name__ == "__main__":
    main()
