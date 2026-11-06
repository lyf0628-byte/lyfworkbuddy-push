"""行知旅行「行程变更与异常协作」业务规则引擎。

核心立场（与需求方案一致）：
    **口径、红线、超时、影响面由这里判定，不由 LLM 判定。**
LLM 只负责"把规程讲清楚"，避免模型把"已发送"说成"已完成"这类事故。
所有规则都标注依据，便于回答里回链原文。

业务红线（需求方案 1.2）：
    不可逆动作（发车、入住、接待、对外承诺、资产变更、旅客资料访问、
    退款、改签、赔偿）一律强制人工审批，系统不得自主执行。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# ---------------------------------------------------------------- 变更类型

EVENT_TYPES = ["航班延误", "酒店变更", "车队调整", "天气影响", "其他"]

# 事件类型 → 默认影响对象类型
EVENT_IMPACT_MAP = {
    "航班延误": ["hotel", "fleet", "tourist"],
    "酒店变更": ["tourist", "fleet"],
    "车队调整": ["tourist", "hotel"],
    "天气影响": ["tourist", "hotel", "fleet"],
    "其他": ["tourist"],
}

PARTY_TYPE_LABEL = {
    "hotel": "酒店", "fleet": "车队", "tourist": "游客", "vendor": "服务商",
}


# ---------------------------------------------------------------- 完成口径（P0-①）

# 回执类型：read=已读（只知对方看到）；resource_available=资源可用（真正可执行）
RECEIPT_READ = "read"
RECEIPT_RESOURCE = "resource_available"

# 完成口径：只有「资源可用」回执才算闭环完成；「已读」只算中间态
def is_closed_receipt(receipt_type: str) -> bool:
    return receipt_type == RECEIPT_RESOURCE


# ---------------------------------------------------------------- 超时升级规则

# 超时阈值（分钟）：两级升级
ESCALATE_L1_MINUTES = 30  # 一级：通知 30 分钟未回执 → 提醒
ESCALATE_L2_MINUTES = 60  # 二级：60 分钟未回执 → 升级至接手人


def escalation_level(elapsed_minutes: float) -> int:
    if elapsed_minutes >= ESCALATE_L2_MINUTES:
        return 2
    if elapsed_minutes >= ESCALATE_L1_MINUTES:
        return 1
    return 0


# ---------------------------------------------------------------- 转人工红线（P0-② / G4）

# 不可逆动作清单：命中即强制转人工，系统不得自主执行
IRREVERSIBLE_ACTIONS = [
    "退款", "改签", "赔偿", "发车", "入住", "接待", "对外承诺", "资产变更",
    "旅客资料", "旅客名单", "退团", "换团", "签转",
]


def is_irreversible(text: str) -> bool:
    return any(word in (text or "") for word in IRREVERSIBLE_ACTIONS)


# 转人工四要素：缺一不可
HANDOFF_REQUIRED_FIELDS = ["trigger_reason", "assignee", "confirm_time", "biz_ref"]


def handoff_fields_valid(fields: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = [f for f in HANDOFF_REQUIRED_FIELDS if not (fields.get(f) or "").strip()]
    return (not missing), missing


# ---------------------------------------------------------------- 五道审核门（G1-G5）

GATES = {
    "G1": "口径与授权签发（运营经理）",
    "G2": "数据与主键校验（平台工程师）",
    "G3": "建议发布确认（行程协调员）",
    "G4": "不可逆动作审批（授权审批人/安全主管）",
    "G5": "试点放行与复盘（运营经理+安全主管）",
}


def gate_required_for(action: str) -> str | None:
    """某个动作该走哪道审核门。不可逆动作→G4；通知下发→G3；事件接入→G2。"""
    if is_irreversible(action):
        return "G4"
    if action in ("notify", "下发通知", "通知"):
        return "G3"
    if action in ("register", "接入", "登记"):
        return "G2"
    return None


# ---------------------------------------------------------------- 影响面计算（P2-⑥）

def compute_impact(event_type: str, description: str = "") -> dict[str, Any]:
    """按事件类型返回受影响对象类型 + 是否触发红线。

    返回结构供 Agent 使用；真正的对象名单需依赖三系统主键关联（P1-④ 数据地基），
    MVP 阶段用事件类型映射的默认影响对象类型替代。
    """
    types = EVENT_IMPACT_MAP.get(event_type, ["tourist"])
    return {
        "ok": True,
        "event_type": event_type,
        "affected_types": types,
        "affected_labels": [PARTY_TYPE_LABEL[t] for t in types],
        "irreversible": is_irreversible(description),
        "gate": "G4" if is_irreversible(description) else "G3",
        "hint": "影响面为按事件类型的默认映射，正式环境需按主键关联（团号+订单号+版本）精确计算。",
    }


# ---------------------------------------------------------------- 版本校验（P1-④）

def validate_version(version: str) -> bool:
    """版本号格式校验：V主版本.次版本，如 V1.0、V3.2。"""
    v = (version or "").strip().upper()
    if not v.startswith("V"):
        return False
    parts = v[1:].split(".")
    if len(parts) != 2:
        return False
    return all(p.isdigit() for p in parts)


# ---------------------------------------------------------------- 指标口径（P1-⑤）

# 遗漏率、覆盖率、耗时的定义，写死为常量，供问答与报表一致引用
BASELINE_MISS_RATE = "14%"
TARGET_MISS_RATE = "2%"
BASELINE_CONFIRM_MINUTES = 80
TARGET_CONFIRM_MINUTES = 20
COVERAGE_TARGET = "100%"


def key_metrics() -> dict[str, str]:
    return {
        "遗漏率": f"{BASELINE_MISS_RATE} → {TARGET_MISS_RATE}",
        "异常确认耗时": f"{BASELINE_CONFIRM_MINUTES} 分钟 → {TARGET_CONFIRM_MINUTES} 分钟",
        "关键变更覆盖率": COVERAGE_TARGET,
    }
