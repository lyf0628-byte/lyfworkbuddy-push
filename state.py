from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    user_input: str
    intent: str
    entities: dict
    policy_context: str
    document_info: str
    verify_result: dict
    response: str
    current_step: str


def merge_dict(a: dict, b: dict) -> dict:
    merged = a.copy()
    merged.update(b)
    return merged
