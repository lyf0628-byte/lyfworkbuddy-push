from agent.state import AgentState
from tools.mock_api import (
    get_document_by_id,
    get_documents_by_employee,
    format_status,
)


def query_document_node(state: AgentState) -> AgentState:
    entities = state["entities"]
    doc_id = entities.get("doc_id", "")
    employee_name = entities.get("employee_name", "")

    results = []

    if doc_id:
        doc = get_document_by_id(doc_id)
        if doc:
            results.append(format_status(doc))
        else:
            results.append(f"未找到单据号为 {doc_id} 的报销单，请确认单号是否正确。")
    elif employee_name:
        docs = get_documents_by_employee(employee_name)
        if docs:
            results.append(f"📋 共找到 {len(docs)} 张报销单，以下是单据状态汇总：\n")
            for doc in docs:
                status_icon = {
                    "待审核": "⏳",
                    "财务核对中": "🔍",
                    "总经理审批中": "👤",
                    "已付款": "✅",
                    "已驳回": "❌",
                }.get(doc.status, "📄")
                results.append(
                    f"{status_icon} {doc.doc_id} | {doc.type} | ¥{doc.amount:,.0f} | {doc.status}"
                )
            results.append("\n需要查看某张单据的详细信息吗？")
        else:
            results.append(f"未找到 {employee_name} 的报销记录。")

    if not results:
        results.append("请提供单据号（如 BX202609001）或员工姓名来查询单据状态。")

    state["document_info"] = "\n".join(results)
    state["current_step"] = "document_ready"
    return state
