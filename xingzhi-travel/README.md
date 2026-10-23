# 行知旅行 · 旅行行程与异常协作（首期试点）交付包

> 范围：**变更影响与通知闭环**。只做检测、提醒与通知闭环；不自主退款、不自主改签、不承诺赔偿。

## 一、交付清单

| # | 交付物 | 文件 | 形态 |
|---|---|---|---|
| 1 | 业务挖掘实验室系统 | `mining-lab/index.html` | 单页 Web 应用（无外部依赖，双击即可打开） |
| 2 | 行业分析（docx 整理） | `industry-analysis/Xingzhi-Travel-Industry-Analysis.docx` | Word 文档，含 11 张表、2 张图 |
| 3 | 两张流程图 | `flowcharts/as-is-flow.html`、`flowcharts/to-be-flow.html` | 泳道图，浏览器打开后可打印 / 导出 PDF |
| 4 | 报价单与设计方案 | `proposal/Xingzhi-Travel-Quotation.xlsx`、`proposal/Xingzhi-Travel-Solution-Design.docx` | Excel 5 个工作表（含公式）；Word 15 章 16 表 |

## 二、目录结构

```
xingzhi-travel/
├─ mining-lab/              业务挖掘实验室（Web）
│  ├─ index.html            入口
│  ├─ lab-data.js           数据层：36 条证据 f00–f55、6 项候选需求、8 个候选切入点
│  └─ lab-app.js            交互层：8 个页签、搜索、评分排序、证据追溯
├─ flowcharts/              流程图
│  ├─ as-is-flow.html       现状：7 泳道 13 步、2 条返工回路
│  ├─ to-be-flow.html       转型后：8 泳道 16 步、5 级审核门、3 条回路
│  ├─ *.data.js             图数据（与页面分离，便于维护）
│  └─ flow-render.js        SVG 泳道图渲染引擎（数据驱动，无手写坐标）
├─ industry-analysis/       行业分析报告（docx）+ 两张图表 PNG
├─ proposal/                解决方案设计说明书（docx）+ 项目报价单（xlsx）
└─ scripts/                 构建与校验脚本（可重复执行）
```

## 三、业务挖掘实验室功能

| 页签 | 内容 |
|---|---|
| 总览 | KPI 现状→目标、瓶颈定位、候选需求分布、四来源收敛状态、建议路径、未达标归因规则 |
| 四来源收敛 | Buyer/Brief/Industry/Operator 四视角状态与缺口；含本期补充的行业证据表 |
| 流程拆解 | 由流程图数据自动生成的 13 步（现状）与 16 步（转型后）步骤明细表 |
| 风险矩阵 | 8 个候选切入点，支持拖动「价值 / 可拦截 / 可恢复」滑块做敏感性分析并实时排序 |
| 候选需求 | REQ-1…REQ-6 的完整推导、不确定处、验证动作与验收出口 |
| 证据库 | 36 条访谈事实，按岗位筛选、全文搜索、点击证据编号可从需求反向追溯 |
| 流程图 | 现状与转型后两张泳道图的内嵌查看 |
| 验证排期 | 6 项验证动作排序 + 8 项试点前待追问事项 |

## 四、口径一致性说明

| 项目 | 数值 | 来源 |
|---|---|---|
| 首期预算 | 120,000 元 | 报告 f03 |
| 报价合计（含税） | 117,500 元 | 报价单 HX-QT-2026-1023 |
| 综合单价 / 总人天 | 1,250 元/人天 · 94 人天 | 同上 |
| 付款节奏 | 30% / 30% / 25% / 15%，绑定 G1 与三个里程碑 | 同上 |
| 验收硬指标 | 覆盖率 100%、遗漏率 14%→<2%、确认耗时 80→20 分钟、审计可重建 | 报告 f00/f02 |
| 实施周期 | 13–18 周（4 阶段） | 报价单交付周期表 |

## 五、重新生成与校验

```bash
# 文档与报价单
python scripts/build_industry_docx.py     # 需要 python-docx、matplotlib
python scripts/build_proposal_docx.py     # 需要 python-docx
python scripts/build_quotation_xlsx.py    # 需要 openpyxl

# 无头校验（不需要浏览器）
node scripts/verify_flowcharts.js         # 校验两张流程图渲染与引用完整性
node scripts/verify_lab.js                # 校验实验室 8 个页签渲染与数据引用
```

## 六、重要声明

本仓库所有内容依据《行知旅行 · 业务需求发现报告》V1.0（2026-10-23）与《项目报价单》HX-QT-2026-1023 编制。
报告明确：访谈基于合成场景，6 项候选需求均为**待验证假设**，不作为验收结论；调查覆盖 36/36 仅表示材料采集范围，不代表验收通过。
所有指标口径须在试点前由运营经理书面签发（分母、排除规则、统计周期三者齐备）。行业分析部分引自公开资料，仅作方向性参照，**不替代本方基线**。
