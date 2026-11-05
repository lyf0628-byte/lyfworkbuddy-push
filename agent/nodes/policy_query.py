from pathlib import Path
from agent.state import AgentState

POLICY_DIR = Path(__file__).parent.parent.parent / "data"


POLICY_SECTIONS = {
    "travel": {
        "keywords": ["差旅", "出差", "交通", "住宿", "酒店", "伙食", "餐补", "高铁", "飞机", "机票"],
        "section": "第二章 差旅费报销制度",
    },
    "entertainment": {
        "keywords": ["招待", "请客", "客户", "宴请", "吃饭"],
        "section": "第三章 招待费用报销",
    },
    "office": {
        "keywords": ["办公", "耗材", "用品", "文具", "通讯", "话费", "补贴"],
        "section": "第四章 办公用品及日常费用",
    },
    "process": {
        "keywords": ["流程", "审批", "怎么报", "步骤", "时限", "多久", "期限", "发票"],
        "section": "第五章 报销流程",
    },
    "violation": {
        "keywords": ["违规", "虚报", "造假", "处罚", "处理", "驳回"],
        "section": "第六章 违规处理",
    },
}


def split_policy_content(content: str) -> dict[str, str]:
    sections = {}
    lines = content.split("\n")
    current_section = "总则"
    current_content = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or (stripped.startswith("第") and "章" in stripped):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = stripped.replace("#", "").strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "\n".join(current_content)

    return sections


def query_policy_node(state: AgentState) -> AgentState:
    user_input = state["user_input"]

    policy_file = POLICY_DIR / "expense_policies.md"
    with open(policy_file, "r", encoding="utf-8") as f:
        content = f.read()

    sections = split_policy_content(content)

    relevant_sections = []
    query_lower = user_input.lower()

    for section_name, section_content in sections.items():
        score = 0
        for rule in POLICY_SECTIONS.values():
            if rule["section"] in section_name:
                for kw in rule["keywords"]:
                    if kw.lower() in query_lower:
                        score += 2

        for kw in ["制度", "规定", "标准"]:
            if kw in query_lower and kw in section_content.lower():
                score += 1

        if score > 0:
            relevant_sections.append((section_name, section_content, score))

    relevant_sections.sort(key=lambda x: x[2], reverse=True)

    if relevant_sections:
        top_sections = relevant_sections[:2]
        state["policy_context"] = "\n\n".join(
            f"## {name}\n{content}" for name, content, _ in top_sections
        )
    else:
        all_parts = []
        for name, content in list(sections.items())[:3]:
            all_parts.append(f"## {name}\n{content}")
        state["policy_context"] = "\n\n".join(all_parts)

    state["current_step"] = "policy_ready"
    return state
