# 行知旅行 · 行程变更与异常协作 MVP（可运行后端系统）

> 对应任务：`src: 2、MVP 项目：工程架构、Agent 框架、知识库，至少 3 处人工确认/审核点`

本目录是一个**真实可运行**的后端系统（对标报销助手智能体的完整度），不再是纯前端演示。
离线模式零依赖、无需 API Key 即可跑通全链路。

## 一、工程架构（六层）

| 层 | 模块 | 职责 |
|---|---|---|
| 接入层 | `app/web/` | 登录、员工端对话（SSE 流式）、管理后台 |
| 应用层 | `app/main.py` | FastAPI 应用、异常处理、路由装配 |
| Agent 层 | `app/agent/` | 规则引擎 + 工具集 + 5 轮工具循环 |
| 检索层 | `app/rag/index.py` | BM25 + 特征哈希向量 + RRF 融合 + 相关性门禁 |
| 数据层 | `app/db.py` | SQLite 13 张表（变更事件/通知/转人工/审核门/审计日志） |
| 安全层 | `app/security.py` `app/privacy.py` | pbkdf2 口令 + HS256 JWT + 日志脱敏 |

## 二、Agent 框架

- **双脑设计**：`HeuristicBrain`（离线确定性，无需 Key）+ `LLMBrain`（真实 Function Calling，配 Key 自动切换）。
- **5 轮工具循环**：意图识别 → 工具调用 → 结果回填 → 再决策，每轮写 `agent_logs`。
- **六工具**：search_policy（查规程）、compute_impact（影响面）、register_event（登记事件）、notify_parties（通知）、manual_handoff（转人工）、list_my_events。

## 三、知识库

- 检索：bigram 分词 + BM25 + 特征哈希向量 + RRF 融合 + 相关性门禁 + 域外弃答。
- 语料：`data/policies/` 下《行程变更协作规程》《访谈证据要点》两份 Markdown，切片落库可追溯。

## 四、三处人工确认/审核点（对应需求 G1/G3/G4）

| # | 审核点 | 触发场景 | 代码位置 |
|---|---|---|---|
| 1 | G1 口径与授权签发 | 事件接入前确认口径已签发 | 规程第四条 + Agent 提示词 |
| 2 | G3 建议发布确认 | 通知下发前，AI 影响面建议须人工确认 | `engine.confirm_notify` 闸门：未确认 `notify_parties` 返回 `GATE_G3_REQUIRED` |
| 3 | G4 不可逆动作审批 | 退款/改签/赔偿一律转人工 | `rules.is_irreversible` + `manual_handoff` 四要素强制留痕 |

## 五、快速验证

```bash
python quickstart.py              # 控制台 3 场景演示（零依赖）
python evals/run_eval.py          # 30 条评测，当前 30/30
python run.py --port 8000         # Web 版（员工端 + 管理后台）
```

### 真实执行测试（对标报销助手 run_tests.py）

对隔离实例跑五类 HTTP 用例，输出 `Test/_runtime/results.json`：

```bash
python run.py --port 8130 --no-browser                      # 终端 1：启动隔离实例
python Test/_scripts/run_tests.py --base http://127.0.0.1:8130   # 终端 2：跑测试
```

当前 **39/39 通过**：正常 12、边界 5、对抗 9、权限 7、故障 6。

账号：`linyizhou`/`emp123`（导游 林亦舟）、`admin`/`admin123`（运营经理 顾明岚）。

## 六、核心业务逻辑（与需求方案一致）

- **完成口径**：以「资源可用回执」而非「通知发出」判定闭环完成（P0-①）。
- **转人工四要素**：触发原因 / 接手人 / 确认时间 / 业务编号+版本，缺一不可（P0-②）。
- **不可逆红线**：退款/改签/赔偿/发车/入住/旅客资料，系统不自主执行（G4）。
- **超时升级**：通知 30/60 分钟未回执两级升级。

## 七、技术栈与依赖

后端 FastAPI + 原生标准库（SQLite、urllib、hashlib）。Web 依赖见 `requirements.txt`；
控制台演示与评测**纯标准库零依赖**。
