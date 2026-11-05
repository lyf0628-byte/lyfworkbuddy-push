import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

DATA_DIR = Path(__file__).parent.parent / "data"


class DocumentItem(BaseModel):
    category: str
    amount: float
    desc: str


class ReimbursementDocument(BaseModel):
    doc_id: str
    employee: str
    department: str
    type: str
    amount: float
    status: str
    submit_date: str
    items: list[DocumentItem]
    reject_reason: Optional[str] = None


class Employee(BaseModel):
    name: str
    level: str
    department: str
    phone: str


def load_mock_db() -> dict:
    db_path = DATA_DIR / "mock_db.json"
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_document_by_id(doc_id: str) -> Optional[ReimbursementDocument]:
    db = load_mock_db()
    for doc in db["documents"]:
        if doc["doc_id"] == doc_id.upper():
            return ReimbursementDocument(**doc)
    return None


def get_documents_by_employee(employee_name: str) -> list[ReimbursementDocument]:
    db = load_mock_db()
    results = []
    for doc in db["documents"]:
        if doc["employee"] == employee_name:
            results.append(ReimbursementDocument(**doc))
    return results


def get_employee_info(employee_name: str) -> Optional[Employee]:
    db = load_mock_db()
    for emp in db["employees"]:
        if emp["name"] == employee_name:
            return Employee(**emp)
    return None


STATUS_FLOW = [
    "待审核",
    "财务核对中",
    "总经理审批中",
    "已付款",
]

STATUS_DESC = {
    "待审核": "单据已提交，等待部门负责人审核",
    "财务核对中": "部门已通过，正在进行财务合规性核对",
    "总经理审批中": "财务核对通过，等待总经理最终审批",
    "已付款": "所有审批完成，款项已支付",
    "已驳回": "单据被驳回，请查看驳回原因",
}


def format_status(doc: ReimbursementDocument) -> str:
    desc = STATUS_DESC.get(doc.status, doc.status)
    base = f"【{doc.doc_id}】{doc.employee} 的{doc.type}报销单\n"
    base += f"提交日期: {doc.submit_date}\n"
    base += f"报销金额: ¥{doc.amount:,.2f}\n"
    base += f"当前状态: {doc.status} - {desc}\n"
    if doc.reject_reason:
        base += f"驳回原因: {doc.reject_reason}\n"
    base += "\n明细:\n"
    for item in doc.items:
        base += f"  - {item.category}: ¥{item.amount:,.2f} ({item.desc})\n"
    return base
