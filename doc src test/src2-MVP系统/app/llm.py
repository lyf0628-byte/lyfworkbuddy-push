"""OpenAI 兼容 LLM 客户端（零第三方依赖，用 urllib）。

只有配置了 LLM_API_KEY 时才真正联网；否则走 HeuristicBrain 离线模式。
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .config import settings


class LLMError(Exception):
    pass


@dataclass
class LLMReply:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def build_client():
    """无 Key 时返回 None，由上层切 HeuristicBrain。"""
    if not settings.has_llm:
        return None
    return OpenAICompatClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        temperature=settings.llm_temperature,
    )


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout: int = 60, temperature: float = 0.2) -> None:
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMReply:
        url = self.base_url + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"LLM 调用失败：{exc}") from exc

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        reply = LLMReply(content=msg.get("content"))
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            reply.tool_calls.append({
                "id": tc.get("id"),
                "name": fn.get("name"),
                "arguments": args,
            })
        return reply
