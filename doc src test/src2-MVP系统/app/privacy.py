"""日志脱敏：旅客手机号、身份证号等个人信息在写入 agent_logs 前打码。

对应需求红线：全链路留痕「不记录账号口令与不必要个人信息」（证据 f45）。
"""
from __future__ import annotations

import re

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
_IDCARD = re.compile(r"(?<!\d)(\d{6})(\d{8})(\d{3}[\dXx])(?!\d)")


def mask_phone(text: str) -> str:
    return _PHONE.sub(r"\1****\3", text)


def mask_idcard(text: str) -> str:
    return _IDCARD.sub(r"\1********\3", text)


def mask_args(data: dict) -> dict:
    """对工具入参做浅层脱敏（只处理字符串值）。"""
    out: dict = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = mask_idcard(mask_phone(v))
        elif isinstance(v, list):
            out[k] = [mask_idcard(mask_phone(x)) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out
