"""生成《行知旅行 · 旅行行程与异常协作项目报价单》xlsx
金额口径与《项目报价单》HX-QT-2026-1023 一致：综合单价 1,250 元/人天，94 人天，合计 117,500 元。
运行： python scripts/build_quotation_xlsx.py
"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'proposal', 'Xingzhi-Travel-Quotation.xlsx')

RATE = 1250
MODULES = [
    ('1', '系统集成', '三系统打通 · 主键关联 · 去重与降级', 28, '可运行集成包 + 接口说明文档'),
    ('2', '检测与通知引擎', '变更识别 · 影响面计算 · 回执校验', 20, '引擎服务 + 规则配置文件'),
    ('3', '人工审核与留痕', '5 个审核门 · 转人工四要素 · 审计重建', 10, '审核工作台 + 留痕字段清单'),
    ('4', '隐私与权限控制', '最小可见 · 脱敏 · 90 天留存与删档复核', 8, '权限矩阵 + 留存策略 + 审计日志'),
    ('5', '历史回放与基线测量', '3 个历史团标注 · 字段完整率抽样 · 基线周', 8, '基线报告 + 口径草案'),
    ('6', '培训与十团试点陪跑', '导游 / 协调员 / 服务商 · 4 场培训 · 全程陪跑', 13, '培训材料 + 试点周报'),
    ('7', '项目管理与验收', '周会 · 风险登记 · 验收材料 · 复盘', 7, '项目管理台账 + 验收报告'),
]
PAYMENTS = [
    ('第 1 期 · 签约', 0.30, '合同签订且授权口径通过（G1）'),
    ('第 2 期 · 集成完成', 0.30, '三系统打通并完成版本校验评审'),
    ('第 3 期 · 试点启动', 0.25, '10 团试点开始且回执链路跑通'),
    ('第 4 期 · 验收', 0.15, '达标判定通过并交付验收报告'),
]
SCHEDULE = [
    ('阶段一　口径与权限', '2–3 周', '授权口径草案 · 权限矩阵 · 基线报告', '运营经理签发；安全主管无否决意见'),
    ('阶段二　系统集成', '4–6 周', '集成包 · 接口文档 · 去重降级方案', '三系统状态一致；主键可关联率达约定阈值'),
    ('阶段三　检测与审核', '4–5 周', '检测引擎 · 审核工作台 · 转人工四要素', '建议均附原记录；转人工记录字段完整'),
    ('阶段四　试点验收', '3–4 周', '试点周报 · 达标报告 · 审计重建样例', '覆盖率 100% 且遗漏率 <2%；未触停止条件'),
]
TERMS = [
    ('综合单价', '1,250 元/人天，包含需求梳理、设计、开发、测试、文档五部分工作，不另计差旅。'),
    ('工时口径', '94 人天 ≈ 4.5 个人月；含 5 个审核门的等待时间，不含驳回重走。'),
    ('数据来源', '金额依据《行知旅行 · 业务需求发现报告》f03「首期可用预算 12 万元，包含集成、培训与验证」；报告未给单价与人天拆分，人天为按模块复杂度测算，可据实调整。'),
    ('不含费用', '第三方软件许可与云资源（按实际用量实报实销）· 硬件与终端采购 · 短信/消息通道费 · 超出 10 团的扩展试点 · 现有系统改造。'),
    ('税费', '已按 6% 现代服务业增值税计入；如需专票请提供开票信息。'),
    ('维护费', '不含上线后年度维护费，建议按合同额 12–15%/年另计；不承诺以节省工时折算投资回报。'),
    ('报价有效期', '自 2026-10-23 起 30 日内有效，逾期需重新确认。'),
    ('范围变更', '超出本合同范围的增项按 1,250 元/人天据实结算，须经双方书面确认。'),
    ('需方配合', '提供三系统访问权限、历史团样本、业务口径决策人与安全审核人排期；因需方原因导致的等待按每日 0.5 人天计入工期顺延。'),
    ('知识产权', '定制开发部分著作权归需方；供方保留通用组件与框架的使用权。'),
    ('数据与保密', '试点数据仅在授权范围内使用，遵循最小可见原则；不记录账号口令与不必要个人信息；项目结束后 30 日内销毁或返还全部原始资料，评价记录按 90 天留存并由安全主管复核删档。'),
    ('停止条件', '出现紧急人身安全事件、涉及退款/改签/赔偿、资料缺依据或两版本冲突、关键系统不可用等情形，任一方有权暂停推进并转入人工处置，相关费用按已完成人天结算。'),
    ('质保与维护', '验收后提供 3 个月免费缺陷修复；年度维护服务另议，建议按合同额 12–15%/年。'),
    ('争议解决', '友好协商；协商不成提交需方所在地人民法院。'),
]

THIN = Border(*[Side(style='thin', color='D1D5DB')] * 4)
HEAD_FILL = PatternFill('solid', fgColor='1E293B')
SUB_FILL = PatternFill('solid', fgColor='F1F5F9')
TOTAL_FILL = PatternFill('solid', fgColor='EFF6FF')
FONT_HEAD = Font(name='Microsoft YaHei', size=10.5, bold=True, color='FFFFFF')
FONT_BODY = Font(name='Microsoft YaHei', size=10)
FONT_BOLD = Font(name='Microsoft YaHei', size=10, bold=True)
FONT_TITLE = Font(name='Microsoft YaHei', size=16, bold=True, color='1F2937')
WRAP = Alignment(wrap_text=True, vertical='center')
CENTER = Alignment(horizontal='center', vertical='center')


def style_row(ws, row, cols, font=FONT_BODY, fill=None, align=WRAP, numfmt=None, start_col=1):
    for i in range(start_col, start_col + cols):
        c = ws.cell(row=row, column=i)
        c.font = font
        c.border = THIN
        c.alignment = align
        if fill:
            c.fill = fill
        if numfmt and isinstance(c.value, (int, float)):
            c.number_format = numfmt


def build():
    wb = Workbook()

    # ---- 封面 ----
    ws = wb.active
    ws.title = '报价总览'
    ws.sheet_view.showGridLines = False
    ws['A1'] = '项 目 报 价 单'
    ws['A1'].font = FONT_TITLE
    ws['A2'] = 'PROJECT QUOTATION'
    ws['A2'].font = Font(name='Microsoft YaHei', size=10, bold=True, color='1D4ED8')
    meta = [
        ('项目名称', '旅行行程与异常协作（变更影响与通知闭环 · 首期试点）'),
        ('报价编号', 'HX-QT-2026-1023'),
        ('报价日期', '2026-10-23'),
        ('有效期', '自报价日起 30 日'),
        ('币种', '人民币 CNY · 含税（已按 6% 现代服务业增值税计入）'),
        ('需方单位', '行知旅行（旅行社运营方）'),
        ('需方项目负责人', '顾明岚 · 旅行运营经理'),
        ('验收参与', '傅景（旅行安全主管） · 叶书（目的地服务商）'),
        ('供方单位', '（待填）'),
        ('交付负责人 / 联系方式', '（待填）'),
    ]
    r = 4
    for k, v in meta:
        ws.cell(row=r, column=1, value=k).font = FONT_BOLD
        ws.cell(row=r, column=2, value=v).font = FONT_BODY
        ws.cell(row=r, column=1).fill = SUB_FILL
        ws.cell(row=r, column=1).border = THIN
        ws.cell(row=r, column=2).border = THIN
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='报价合计（含税）').font = Font(name='Microsoft YaHei', size=12, bold=True)
    ws.cell(row=r, column=2, value='=费用明细!F9').font = Font(name='Microsoft YaHei', size=12, bold=True, color='DC2626')
    ws.cell(row=r, column=1).fill = TOTAL_FILL
    ws.cell(row=r, column=2).fill = TOTAL_FILL
    ws.cell(row=r, column=1).border = THIN
    ws.cell(row=r, column=2).border = THIN
    ws.cell(row=r, column=2).number_format = '#,##0'
    r += 1
    ws.cell(row=r, column=1, value='大写').font = FONT_BOLD
    ws.cell(row=r, column=2, value='壹拾壹万柒仟伍佰元整').font = FONT_BODY
    ws.cell(row=r, column=1).border = THIN
    ws.cell(row=r, column=2).border = THIN
    r += 1
    ws.cell(row=r, column=1, value='预算上限 / 结余').font = FONT_BOLD
    ws.cell(row=r, column=2, value='预算上限 120,000 元；结余转入风险金（约占预算 2.1%）').font = FONT_BODY
    ws.cell(row=r, column=1).border = THIN
    ws.cell(row=r, column=2).border = THIN
    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 62
    ws.column_dimensions['C'].width = 46

    # ---- 费用明细 ----
    ws = wb.create_sheet('费用明细')
    ws.sheet_view.showGridLines = False
    head = ['序号', '费用模块', '工作说明', '人天（测算）', '单价（元/人天）', '金额（元）', '交付形态']
    ws.append(head)
    for i, c in enumerate(ws[1], start=1):
        c.font = FONT_HEAD
        c.fill = HEAD_FILL
        c.alignment = CENTER
        c.border = THIN
    start = 2
    for i, (no, name, desc, days, deliver) in enumerate(MODULES):
        row = start + i
        ws.cell(row=row, column=1, value=int(no))
        ws.cell(row=row, column=2, value=name)
        ws.cell(row=row, column=3, value=desc)
        ws.cell(row=row, column=4, value=days)
        ws.cell(row=row, column=5, value=RATE)
        ws.cell(row=row, column=6, value='=D{0}*E{0}'.format(row))
        ws.cell(row=row, column=7, value=deliver)
        style_row(ws, row, 7, numfmt='#,##0')
        ws.cell(row=row, column=1).alignment = CENTER
    last = start + len(MODULES) - 1
    trow = last + 1
    ws.cell(row=trow, column=1, value='小计')
    ws.cell(row=trow, column=2, value='7 个模块')
    ws.cell(row=trow, column=4, value='=SUM(D{0}:D{1})'.format(start, last))
    ws.cell(row=trow, column=6, value='=SUM(F{0}:F{1})'.format(start, last))
    ws.cell(row=trow, column=7, value='—')
    style_row(ws, trow, 7, font=FONT_BOLD, fill=TOTAL_FILL, numfmt='#,##0')
    ws.cell(row=trow, column=1).alignment = CENTER
    brow = trow + 1
    ws.cell(row=brow, column=1, value='预算结余')
    ws.cell(row=brow, column=2, value='预算上限 120,000 元')
    ws.cell(row=brow, column=6, value='=120000-F{0}'.format(trow))
    ws.cell(row=brow, column=7, value='预留作风险金')
    style_row(ws, brow, 7, font=FONT_BODY, fill=SUB_FILL, numfmt='#,##0')
    for col, w in zip('ABCDEFG', [8, 22, 42, 12, 14, 14, 30]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = 'A2'

    # ---- 付款计划 ----
    ws = wb.create_sheet('付款计划')
    ws.sheet_view.showGridLines = False
    ws.append(['期次', '触发条件', '比例', '金额（元）'])
    for c in ws[1]:
        c.font = FONT_HEAD
        c.fill = HEAD_FILL
        c.alignment = CENTER
        c.border = THIN
    for i, (name, pct, cond) in enumerate(PAYMENTS):
        row = 2 + i
        ws.cell(row=row, column=1, value=name)
        ws.cell(row=row, column=2, value=cond)
        ws.cell(row=row, column=3, value=pct)
        ws.cell(row=row, column=4, value='=ROUND(费用明细!F9*C{0},0)'.format(row))
        style_row(ws, row, 4, numfmt='#,##0')
        ws.cell(row=row, column=3).number_format = '0%'
        ws.cell(row=row, column=3).alignment = CENTER
    trow = 2 + len(PAYMENTS)
    ws.cell(row=trow, column=1, value='合计')
    ws.cell(row=trow, column=3, value='=SUM(C2:C{0})'.format(trow - 1))
    ws.cell(row=trow, column=4, value='=SUM(D2:D{0})'.format(trow - 1))
    style_row(ws, trow, 4, font=FONT_BOLD, fill=TOTAL_FILL, numfmt='#,##0')
    ws.cell(row=trow, column=3).number_format = '0%'
    ws.cell(row=trow, column=3).alignment = CENTER
    for col, w in zip('ABCD', [22, 42, 12, 16]):
        ws.column_dimensions[col].width = w

    # ---- 交付周期与验收 ----
    ws = wb.create_sheet('交付与验收')
    ws.sheet_view.showGridLines = False
    ws.append(['阶段', '周期（测算）', '关键交付物', '验收标准'])
    for c in ws[1]:
        c.font = FONT_HEAD
        c.fill = HEAD_FILL
        c.alignment = CENTER
        c.border = THIN
    for i, (name, dur, deliver, acc) in enumerate(SCHEDULE):
        row = 2 + i
        ws.cell(row=row, column=1, value=name)
        ws.cell(row=row, column=2, value=dur)
        ws.cell(row=row, column=3, value=deliver)
        ws.cell(row=row, column=4, value=acc)
        style_row(ws, row, 4)
        ws.cell(row=row, column=2).alignment = CENTER
    row = 2 + len(SCHEDULE) + 1
    ws.cell(row=row, column=1, value='验收硬指标').font = FONT_BOLD
    ws.cell(row=row, column=1).fill = SUB_FILL
    ws.cell(row=row, column=1).border = THIN
    ws.cell(row=row, column=2, value='关键变更确认覆盖率 100% · 通知遗漏率 14% → <2% · 异常确认耗时 80 → 20 分钟 · 审计可完整重建任一笔历史异常处理链')
    ws.cell(row=row, column=2).font = FONT_BOLD
    ws.cell(row=row, column=2).border = THIN
    ws.cell(row=row, column=2).alignment = WRAP
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
    for col, w in zip('ABCD', [22, 16, 44, 44]):
        ws.column_dimensions[col].width = w

    # ---- 计价说明与商务条款 ----
    ws = wb.create_sheet('计价说明与条款')
    ws.sheet_view.showGridLines = False
    ws.append(['项目', '说明'])
    for c in ws[1]:
        c.font = FONT_HEAD
        c.fill = HEAD_FILL
        c.alignment = CENTER
        c.border = THIN
    for i, (k, v) in enumerate(TERMS):
        row = 2 + i
        ws.cell(row=row, column=1, value=k)
        ws.cell(row=row, column=2, value=v)
        style_row(ws, row, 2)
        ws.cell(row=row, column=1).font = FONT_BOLD
    row = 2 + len(TERMS) + 1
    ws.cell(row=row, column=1, value='编制依据')
    ws.cell(row=row, column=2, value='《行知旅行 · 业务需求发现报告》V1.0（36 条访谈事实 f00–f55），其中 f03 给定首期预算总额 12 万元；人天与单价为测算值，最终以双方确认的合同为准。')
    style_row(ws, row, 2)
    ws.cell(row=row, column=1).font = FONT_BOLD
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 96
    for rr in range(2, row + 1):
        ws.row_dimensions[rr].height = 30

    out = os.path.abspath(OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wb.save(out)
    print('已生成：', out)


if __name__ == '__main__':
    build()
