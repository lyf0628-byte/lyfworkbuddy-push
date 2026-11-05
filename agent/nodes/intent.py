import re
from agent.state import AgentState
from tools.mock_api import get_document_by_id, get_documents_by_employee, get_employee_info
from tools.policies import verify_document, format_verify_result

INTENT_KEYWORDS = {
    "policy_query": [
        "制度", "规定", "标准", "政策", "规则", "条款",
        "报销标准", "怎么报销", "如何报销", "能报多少", "上限",
        "差旅费标准", "住宿费标准", "招待费标准", "餐补标准",
        "谁能报", "报不了", "能报吗", "可不可以报",
        "流程", "怎么弄", "怎么申请", "时限", "期限",
    ],
    "document_status": [
        "状态", "查到了吗", "到哪了", "批了没", "批了吗",
        "审核", "进度", "付款", "驳回", "通过",
        "我的单据", "我的报销", "我的单子", "查一下",
        "单据", "单号", "编号",
    ],
    "finance_verify": [
        "核对", "检查", "审核一下", "帮我看看", "对不对",
        "合规", "超标", "问题", "有问题", "帮我查",
    ],
}


def identify_intent(user_input: str) -> str:
    input_lower = user_input.lower()

    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in input_lower)
        scores[intent] = score

    max_intent = max(scores, key=scores.get)
    if scores[max_intent] == 0:
        return "general_chat"

    return max_intent


def extract_doc_id(user_input: str) -> str:
    match = re.search(r'BX\d+', user_input.upper())
    if match:
        return match.group(0)
    return ""


def extract_employee_name(user_input: str) -> str:
    known_employees = ["张军", "李明", "王芳", "赵强"]
    for name in known_employees:
        if name in user_input:
            return name
    return ""


def analyze_query_node(state: AgentState) -> AgentState:
    user_input = state["user_input"]

    intent = identify_intent(user_input)
    doc_id = extract_doc_id(user_input)
    employee_name = extract_employee_name(user_input)

    if not employee_name:
        employee_name = "张军"

    state["intent"] = intent
    state["entities"] = {
        "doc_id": doc_id,
        "employee_name": employee_name,
    }
    state["current_step"] = "analyzed"

    return state
