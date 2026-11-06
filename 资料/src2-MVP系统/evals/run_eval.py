"""评测脚本：跑 30 条用例，检查回答是否命中期望关键词。

零依赖，直接调用 AgentEngine（离线大脑）。
用法：python evals/run_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db  # noqa: E402
from app.agent.engine import AgentEngine  # noqa: E402


def run_answer(conn, user, session_id, question):
    engine = AgentEngine(conn, user, session_id)
    answer = None
    for ev in engine.run(question):
        if ev["type"] == "token":
            answer = (answer or "") + ev["text"]
        elif ev["type"] == "confirm_required":
            answer = (answer or "") + " [确认闸门]"
    return answer or ""


def main():
    conn = init_db()
    user = conn.execute("SELECT * FROM users WHERE username='linyizhou'").fetchone()
    cases = json.loads(Path(__file__).parent.joinpath("cases.json").read_text(encoding="utf-8"))
    cur = conn.execute("INSERT INTO sessions (user_id) VALUES (?)", (user["id"],))
    conn.commit()
    sid = cur.lastrowid

    passed = 0
    results = []
    for i, case in enumerate(cases, 1):
        ans = run_answer(conn, user, sid, case["q"])
        ok = any(k in ans for k in case["expect"])
        if ok:
            passed += 1
        results.append({
            "id": i, "kind": case["kind"], "q": case["q"],
            "expect": case["expect"], "ok": ok, "answer": ans[:120],
        })
        print(f"[{'✓' if ok else '✗'}] {i:2d} {case['kind']:12s} {case['q']}")

    total = len(cases)
    print(f"\n结果：{passed}/{total} 通过（{passed/total*100:.1f}%）")

    # 写报告
    out = {"passed": passed, "total": total, "results": results}
    Path(__file__).parent.joinpath("report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写入 evals/report.json")


if __name__ == "__main__":
    main()
