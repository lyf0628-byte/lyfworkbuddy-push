from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.intent import analyze_query_node
from agent.nodes.policy_query import query_policy_node
from agent.nodes.doc_status import query_document_node
from agent.nodes.finance_check import finance_verify_node


def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyze_query_node)
    workflow.add_node("policy_query", query_policy_node)
    workflow.add_node("document_status", query_document_node)
    workflow.add_node("finance_verify", finance_verify_node)
    workflow.add_node("finalize", finalize_response_node)

    workflow.set_entry_point("analyze")

    workflow.add_conditional_edges(
        "analyze",
        route_by_intent,
        {
            "policy": "policy_query",
            "document": "document_status",
            "verify": "finance_verify",
            "chat": "finalize",
        },
    )

    workflow.add_edge("policy_query", "finalize")
    workflow.add_edge("document_status", "finalize")
    workflow.add_edge("finance_verify", END)

    workflow.add_edge("finalize", END)

    return workflow.compile()


def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent", "general_chat")

    mapping = {
        "policy_query": "policy",
        "document_status": "document",
        "finance_verify": "verify",
        "general_chat": "chat",
    }

    return mapping.get(intent, "chat")


POLICY_TEMPLATES = {
    "差旅": """好的，关于{topic}的问题，我为您查阅了公司报销制度：

{content}

💡 温馨提示：如果您有具体场景需要我帮您判断是否合规，可以告诉我更多细节，我会结合制度帮您分析。""",

    "招待": """好的，关于{topic}的问题，我为您查阅了公司招待费用管理规定：

{content}

💡 温馨提示：招待费需提前申请并说明招待对象和目的，超出标准需特别审批。""",

    "流程": """好的，关于{topic}的问题，我为您整理了公司报销流程：

{content}

💡 温馨提示：所有报销单据须在费用发生后30个工作日内提交，逾期不予受理。""",

    "default": """好的，关于{topic}的问题，我为您查阅了相关制度：

{content}

💡 如果您有更具体的问题，可以继续问我，我会帮您找到对应的制度条款。""",
}


def finalize_response_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "general_chat")
    policy_context = state.get("policy_context", "")
    document_info = state.get("document_info", "")

    if intent == "policy_query":
        template = POLICY_TEMPLATES["default"]
        for keyword in ["差旅", "招待", "流程"]:
            if keyword in policy_context or keyword in state.get("user_input", ""):
                template = POLICY_TEMPLATES[keyword]
                break

        response = template.format(
            topic="报销制度",
            content=policy_context if policy_context else "暂无相关制度条款",
        )
        state["response"] = response

    elif intent == "document_status":
        state["response"] = document_info if document_info else "未找到相关单据信息。"

    else:
        state["response"] = (
            "您好！我是青禾报销助手-lyf智能体，很高兴为您服务 🤖\n\n"
            "我可以帮您：\n"
            "  📖 查询报销制度（差旅费标准、招待费规定、报销流程等）\n"
            "  📋 查看单据状态（如'查一下 BX202609001 的状态'）\n"
            "  ✅ 进行财务核对（帮您检查单据是否符合制度）\n\n"
            "请问有什么可以帮到您？"
        )

    state["current_step"] = "done"
    return state


agent_graph = build_agent_graph()


def query_agent(user_input: str) -> str:
    initial_state = AgentState(
        user_input=user_input,
        intent="",
        entities={},
        policy_context="",
        document_info="",
        verify_result={},
        response="",
        current_step="start",
    )

    result = agent_graph.invoke(initial_state)
    return result.get("response", "抱歉，我暂时无法处理您的问题。")


if __name__ == "__main__":
    test_queries = [
        "差旅费住宿标准是多少？",
        "查一下 BX202609001 的状态",
        "帮我核对一下 BX202609005 这张单据",
        "你好",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"用户: {q}")
        print(f"{'='*60}")
        response = query_agent(q)
        print(f"\n助手:\n{response}")
