from agent.state import AgentState
from tools.mock_api import get_document_by_id, format_status
from tools.policies import verify_document, format_verify_result


def finance_verify_node(state: AgentState) -> AgentState:
    entities = state["entities"]
    doc_id = entities.get("doc_id", "")
    employee_name = entities.get("employee_name", "")

    results = []

    if doc_id:
        doc = get_document_by_id(doc_id)
    elif employee_name:
        from tools.mock_api import get_documents_by_employee
        docs = get_documents_by_employee(employee_name)
        doc = docs[0] if docs else None
    else:
        doc = None

    if doc:
        results.append(format_status(doc))
        results.append("")
        verify_result = verify_document(doc)
        state["verify_result"] = verify_result
        results.append(format_verify_result(verify_result))
    else:
        results.append("请提供单据号（如 BX202609001）来进行财务核对。")

    state["response"] = "\n".join(results)
    state["current_step"] = "verified"
    return state
