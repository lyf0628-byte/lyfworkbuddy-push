# 行知旅行 · 旅行行程与异常协作

本仓库为「行知旅行 · 旅行行程与异常协作（首期试点）」项目的交付与答辩材料，作者：刘语锋（f24011130）。

## 仓库内容

| 目录/文件 | 说明 |
|---|---|
| `00-答辩打开顺序.md` | 答辩展示指引（上台顺序、口径、故障备选） |
| `展示材料/` | 完整交付包，见下方明细 |
| `xingzhi-travel/` | 早期版本的交付包（内容与 `展示材料/` 基本一致） |
| `main.py` + `agent/` + `tools/` + `data/` | 「青禾报销助手」智能体（LangGraph + FastAPI），可运行 |
| `templates/`、`static/` | 报销助手前端页面与静态资源 |

## 展示材料明细

| # | 交付物 | 位置 |
|---|---|---|
| 1 | 业务挖掘实验室系统 | `展示材料/mining-lab/index.html`（双击即可打开） |
| 2 | 行业分析 | `展示材料/industry-analysis/Xingzhi-Travel-Industry-Analysis.docx` |
| 3 | 现状 / 转型后流程图 | `展示材料/flowcharts/as-is-flow.html`、`to-be-flow.html` |
| 4 | 解决方案设计说明书 | `展示材料/proposal/Xingzhi-Travel-Solution-Design.docx` |
| 5 | 项目报价单 | `展示材料/proposal/Xingzhi-Travel-Quotation.xlsx` |

## 如何开始答辩展示

1. 打开 `展示材料/mining-lab/index.html`（主要展示页面，无需服务器或登录）。
2. 按 `00-答辩打开顺序.md` 的指引顺序演示各页签。
3. 备用资料：行业分析 docx、方案设计 docx、报价单 xlsx。

## 重要声明

本仓库内容依据《行知旅行 · 业务需求发现报告》V1.0（2026-10-23）与《项目报价单》HX-QT-2026-1023 编制。报告明确：访谈基于合成场景，候选需求均为待验证假设，不作为验收结论；所有指标口径须在试点前由运营经理书面签发。

---

## 「青禾报销助手」智能体（附加原型）

一个基于 **LangGraph + FastAPI** 的智能报销助手，支持三类能力：报销制度查询、单据状态查询、财务合规核对。

### 环境要求

- Python 3.10+

### 安装与运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务（默认 http://127.0.0.1:8000）
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 首页（报销单据看板） |
| GET | `/api/health` | 健康检查 |
| GET | `/api/documents` | 单据列表 |
| GET | `/api/documents/{doc_id}` | 单据详情 |
| GET | `/api/documents/employee/{name}` | 按员工查询单据 |
| POST | `/api/chat` | 智能体对话（制度查询 / 状态查询） |
| POST | `/api/verify` | 财务合规核对 |

### 对话示例

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"差旅费住宿标准是多少？"}'
```

### 目录结构

```
├─ main.py                 FastAPI 入口
├─ agent/                  LangGraph 智能体
│  ├─ graph.py             状态图与节点编排
│  ├─ state.py             状态定义
│  └─ nodes/               各业务节点（意图识别 / 制度查询 / 单据状态 / 财务核对）
├─ tools/                  工具层（mock 数据、报销制度校验）
├─ data/                   模拟数据（mock_db.json、expense_policies.md）
└─ templates/ + static/    前端页面与静态资源
```
