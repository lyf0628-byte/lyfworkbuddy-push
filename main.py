from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from agent.graph import query_agent
from tools.mock_api import (
    get_document_by_id,
    get_documents_by_employee,
    format_status,
    load_mock_db,
)
from tools.policies import verify_document, format_verify_result

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="青禾报销助手-lyf智能体",
    description="基于LangGraph的智能报销助手，支持制度查询、单据状态查询和财务核对",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jinja_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str
    entities: dict


class VerifyRequest(BaseModel):
    doc_id: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = load_mock_db()
    docs = db["documents"]

    total_amount = sum(d["amount"] for d in docs)
    pending_count = sum(1 for d in docs if d["status"] in ("待审核", "财务核对中", "总经理审批中"))
    paid_count = sum(1 for d in docs if d["status"] == "已付款")
    rejected_count = sum(1 for d in docs if d["status"] == "已驳回")

    template = jinja_env.get_template("index.html")
    html = template.render(
        documents=docs,
        total_docs=len(docs),
        total_amount=total_amount,
        pending_count=pending_count,
        paid_count=paid_count,
        rejected_count=rejected_count,
    )
    return HTMLResponse(content=html)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    from agent.nodes.intent import identify_intent, extract_doc_id, extract_employee_name

    response = query_agent(request.message)
    intent = identify_intent(request.message)
    entities = {
        "doc_id": extract_doc_id(request.message),
        "employee_name": extract_employee_name(request.message) or "张军",
    }
    return ChatResponse(response=response, intent=intent, entities=entities)


@app.get("/api/documents")
async def list_documents():
    db = load_mock_db()
    docs_summary = []
    for doc in db["documents"]:
        docs_summary.append({
            "doc_id": doc["doc_id"],
            "employee": doc["employee"],
            "department": doc.get("department", ""),
            "type": doc["type"],
            "amount": doc["amount"],
            "status": doc["status"],
            "submit_date": doc["submit_date"],
        })
    return {"total": len(docs_summary), "documents": docs_summary}


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = get_document_by_id(doc_id)
    if not doc:
        return {"error": f"单据 {doc_id} 未找到"}
    return {
        "doc_id": doc.doc_id,
        "employee": doc.employee,
        "department": doc.department,
        "type": doc.type,
        "amount": doc.amount,
        "status": doc.status,
        "submit_date": doc.submit_date,
        "reject_reason": doc.reject_reason,
        "items": [item.model_dump() for item in doc.items],
        "formatted": format_status(doc),
    }


@app.get("/api/documents/employee/{name}")
async def get_employee_documents(name: str):
    docs = get_documents_by_employee(name)
    if not docs:
        return {"total": 0, "documents": [], "message": f"未找到 {name} 的报销记录"}
    return {
        "employee": name,
        "total": len(docs),
        "documents": [
            {
                "doc_id": d.doc_id,
                "type": d.type,
                "amount": d.amount,
                "status": d.status,
                "submit_date": d.submit_date,
            }
            for d in docs
        ],
    }


@app.post("/api/verify")
async def verify_doc(request: VerifyRequest):
    doc = get_document_by_id(request.doc_id)
    if not doc:
        return {"error": f"单据 {request.doc_id} 未找到"}
    result = verify_document(doc)
    result["formatted"] = format_verify_result(result)
    return result


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "青禾报销助手-lyf智能体"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
