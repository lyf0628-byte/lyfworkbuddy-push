"""SQLite 数据访问层：建表、初始化数据、轻量查询助手。

行知旅行「行程变更与异常协作」的业务数据模型：
变更事件 → 影响面 → 通知任务 → 回执确认 → 超时升级 → 转人工留痕。
核心红线：退款/改签/赔偿等不可逆动作一律转人工，系统不自主执行。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .config import settings
from .security import hash_password

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. 用户：协调员/导游/运营经理/安全主管/平台工程师/服务商，角色决定权限
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('coordinator', 'guide', 'ops_manager', 'security', 'engineer', 'vendor', 'admin')),
    department    TEXT NOT NULL DEFAULT '运营部',
    employee_no   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 2. 会话
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT '新会话',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at DESC);

-- 3. 消息
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content       TEXT NOT NULL,
    citations     TEXT,
    agent_meta    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

-- 4. 制度/规程文档（含版本，支撑"当时按哪版判的"）
CREATE TABLE IF NOT EXISTS policy_docs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    filename       TEXT NOT NULL,
    title          TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT 'V1.0',
    effective_date TEXT NOT NULL DEFAULT (date('now')),
    content        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    uploaded_by    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 5. 制度切片
CREATE TABLE IF NOT EXISTS policy_chunks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id   INTEGER NOT NULL REFERENCES policy_docs(id) ON DELETE CASCADE,
    ord      INTEGER NOT NULL,
    heading  TEXT NOT NULL,
    text     TEXT NOT NULL,
    n_chars  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON policy_chunks(doc_id, ord);

-- 6. 变更事件（主键：团号 + 订单号 + 版本号，对应 P1-④ 主键关联）
CREATE TABLE IF NOT EXISTS change_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tour_no     TEXT NOT NULL,               -- 团号
    order_no    TEXT,                        -- 订单号
    version     TEXT NOT NULL DEFAULT 'V1.0',-- 资料版本
    event_type  TEXT NOT NULL,               -- 航班延误/酒店变更/车队调整/天气影响
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'registered'
                CHECK (status IN ('registered', 'impact_computed', 'notified', 'closed', 'escalated', 'manual')),
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_tour ON change_events(tour_no, version);

-- 7. 受影响对象（影响面计算结果）
CREATE TABLE IF NOT EXISTS affected_parties (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   INTEGER NOT NULL REFERENCES change_events(id) ON DELETE CASCADE,
    party_type TEXT NOT NULL CHECK (party_type IN ('hotel', 'fleet', 'tourist', 'vendor')),
    party_name TEXT NOT NULL,
    contact    TEXT,
    confirmed  INTEGER NOT NULL DEFAULT 0,   -- 0=未确认 1=已读 2=资源可用
    confirmed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_affected_event ON affected_parties(event_id);

-- 8. 通知任务
CREATE TABLE IF NOT EXISTS notify_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES change_events(id) ON DELETE CASCADE,
    channel       TEXT NOT NULL DEFAULT '系统内',  -- 系统内/短信/企微/电话
    sent_at       TEXT,
    receipt_at    TEXT,                       -- 回执时间（关键：完成口径）
    receipt_type  TEXT,                       -- read / resource_available
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'sent', 'received', 'confirmed', 'escalated')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_notify_event ON notify_tasks(event_id);

-- 9. 转人工记录（四要素强制留痕：触发原因/接手人/确认时间/业务编号+版本）
CREATE TABLE IF NOT EXISTS manual_handoffs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER REFERENCES change_events(id) ON DELETE SET NULL,
    trigger_reason TEXT NOT NULL,
    assignee      TEXT NOT NULL,
    confirm_time  TEXT NOT NULL,
    biz_ref       TEXT NOT NULL,              -- 业务编号 + 资料版本
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 10. 审核门记录（G1 口径签发 / G2 数据校验 / G3 建议确认 / G4 不可逆审批 / G5 试点放行）
CREATE TABLE IF NOT EXISTS gate_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER REFERENCES change_events(id) ON DELETE SET NULL,
    gate          TEXT NOT NULL CHECK (gate IN ('G1','G2','G3','G4','G5')),
    result        TEXT NOT NULL DEFAULT 'pending' CHECK (result IN ('pending','passed','rejected','escalated')),
    actor         TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 11. Agent 决策日志
CREATE TABLE IF NOT EXISTS agent_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id     INTEGER,
    round_no       INTEGER NOT NULL,
    tool_name      TEXT NOT NULL,
    args_json      TEXT,
    result_summary TEXT,
    duration_ms    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_agent_logs_session ON agent_logs(session_id, id);

-- 12. 提示词模板
CREATE TABLE IF NOT EXISTS prompt_templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    content    TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 13. 对话审计
CREATE TABLE IF NOT EXISTS audit_flags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    reason     TEXT NOT NULL,
    flagged_by TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def get_conn(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_all(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def query_one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(params)).fetchone()


def execute(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur


# ---------------------------------------------------------------- 初始化

DEFAULT_PROMPTS = {
    "system_qa": (
        "你是行知旅行的行程变更协作助手，只根据提供的规程条文与访谈证据回答，"
        "不确定时明确说'未找到相关规定'，回答末尾附引用来源，不得编造流程、口径或权限。\n"
        "回答要简洁、给数字、给依据；涉及遗漏率、耗时、口径一律按规程原文。"
    ),
    "system_agent": (
        "你是行知旅行「行程变更与异常协作」助手 Agent。你可以调用工具完成：查规程、"
        "计算变更影响面、登记通知任务、转人工留痕。\n"
        "硬性规则：\n"
        "1) 任何流程/口径/权限结论必须先 search_policy 取到依据，不得凭记忆回答；\n"
        "2) 通知下发前必须 compute_impact 且经人工确认（G3），未确认禁止 notify；\n"
        "3) 退款/改签/赔偿等不可逆动作一律转人工（G4），系统不得自主执行；\n"
        "4) 转人工必须四要素齐备（触发原因/接手人/确认时间/业务编号+版本），缺一不可；\n"
        "5) 规程里没有的内容，明确说'未找到'，不要推断。"
    ),
}


def _seed_users(conn: sqlite3.Connection) -> None:
    rows = [
        (settings.seed_employee_user, hash_password(settings.seed_employee_pwd), "林亦舟（导游）", "guide", "导游部", "G2001"),
        (settings.seed_admin_user, hash_password(settings.seed_admin_pwd), "顾明岚（运营经理）", "ops_manager", "运营部", "E0001"),
    ]
    for row in rows:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role, department, employee_no)"
            " VALUES (?,?,?,?,?,?) ON CONFLICT(username) DO NOTHING",
            row,
        )
    conn.commit()


def _seed_prompts(conn: sqlite3.Connection) -> None:
    for key, name in (("system_qa", "问答系统提示词"), ("system_agent", "Agent 系统提示词")):
        conn.execute(
            "INSERT INTO prompt_templates (key, name, content) VALUES (?,?,?)"
            " ON CONFLICT(key) DO NOTHING",
            (key, name, DEFAULT_PROMPTS[key]),
        )
    conn.commit()


def _seed_policies(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS c FROM policy_docs").fetchone()["c"]
    if existing:
        return
    from .rag.index import chunk_document

    for path in sorted(settings.policies_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title = path.stem
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        cur = conn.execute(
            "INSERT INTO policy_docs (filename, title, version, effective_date, content, status, uploaded_by)"
            " VALUES (?,?,?,?,?, 'active', 'system')",
            (path.name, title, "V1.0", "2026-11-06", content),
        )
        doc_id = cur.lastrowid
        chunks = chunk_document(content, doc_title=title)
        conn.executemany(
            "INSERT INTO policy_chunks (doc_id, ord, heading, text, n_chars) VALUES (?,?,?,?,?)",
            [(doc_id, i, c["heading"], c["text"], len(c["text"])) for i, c in enumerate(chunks)],
        )
    conn.commit()


def rebuild_chunks(conn: sqlite3.Connection, doc_id: int) -> int:
    from .rag.index import chunk_document

    row = conn.execute("SELECT title, content FROM policy_docs WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return 0
    conn.execute("DELETE FROM policy_chunks WHERE doc_id = ?", (doc_id,))
    chunks = chunk_document(row["content"], doc_title=row["title"])
    conn.executemany(
        "INSERT INTO policy_chunks (doc_id, ord, heading, text, n_chars) VALUES (?,?,?,?,?)",
        [(doc_id, i, c["heading"], c["text"], len(c["text"])) for i, c in enumerate(chunks)],
    )
    conn.commit()
    return len(chunks)


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    _seed_users(conn)
    _seed_prompts(conn)
    _seed_policies(conn)
    return conn


def get_prompt(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT content FROM prompt_templates WHERE key = ?", (key,)).fetchone()
    if row:
        return row["content"]
    return DEFAULT_PROMPTS.get(key, "")


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
