/* 业务挖掘实验室 · 交互层
 * 依赖：lab-data.js、../flowcharts/as-is-flow.data.js、../flowcharts/to-be-flow.data.js
 */
(function () {
  'use strict';
  const D = window.LAB;
  const APP = document.getElementById('app');
  const NAV = document.getElementById('nav');

  const state = { tab: 'overview', q: '', role: 'all', highlight: null, scores: {} };
  D.candidates.forEach((c) => {
    state.scores[c.id] = { value: c.value, intercept: c.intercept, recover: c.recover };
  });

  const TYPE_LABEL = {
    exec: '执行', decision: '判断点', wait: '等待/超时',
    manual: '人工控制', engine: '系统能力', intake: '外部触发'
  };

  const esc = (s) => String(s).replace(/[&<>"]/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  const evInfo = (id) => D.evidence.find((e) => e.id === id) || { id: id, text: '（证据正文未收录）', role: '-' };
  const roleName = (r) => D.roles[r] || r || '—';

  function match(text) {
    if (!state.q) return true;
    return String(text).toLowerCase().indexOf(state.q.toLowerCase()) >= 0;
  }

  function evChip(id) {
    const e = evInfo(id);
    return `<button class="chip ref" data-ev="${id}" title="${esc(e.text)}">${id}</button>`;
  }

  function score(s) {
    return Math.round((s.value * 0.4 + s.intercept * 0.35 + s.recover * 0.25) * 20);
  }

  function decision(s) {
    if (s.intercept <= 2) return { t: '不做 · 设硬约束', c: 'no' };
    if (s.recover <= 2) return { t: '暂缓 · 需先补证据', c: 'hold' };
    return score(s) >= 70 ? { t: '先做 · 最小可验证', c: 'go' } : { t: '候选 · 待补充证据', c: 'hold' };
  }

  /* ---------- 总览 ---------- */
  function renderOverview() {
    const p0 = D.requirements.filter((r) => r.priority === 'P0').length;
    const p1 = D.requirements.filter((r) => r.priority === 'P1').length;
    const p2 = D.requirements.filter((r) => r.priority === 'P2').length;
    return `
      <div class="banner"><b>声明</b>${esc(D.meta.warning)}</div>
      <div class="kpis">
        ${D.kpis.map((k) => `
          <div class="kpi">
            <div class="k">${esc(k.k)}</div>
            <div class="vrow"><span class="now">${esc(k.v)}</span><span class="arw">→</span><span class="tgt">${esc(k.t)}</span></div>
            <div class="hint">${esc(k.hint)}</div>
          </div>`).join('')}
      </div>
      <div class="grid2">
        <section class="card">
          <h3>瓶颈定位</h3>
          <p class="p">瓶颈不在算法而在口径：服务商按“发出通知”计算完成，导游按“对方确认资源可用”计算完成，两套标准并存；叠加 CRM、行程表与供应商消息平台分散且主键不稳定，导致变更通知多版本并存、导游逐个电话确认。</p>
          <ul class="ul">
            <li>可确认瓶颈：多版本并存 → 逐个电话确认 → 遗漏率 14%（目标 2%）存在明确差距 <span class="src">f10 / f30 / f31 / f50</span></li>
            <li>范围边界：只做检测、提醒与通知闭环，不自主退款、改签或承诺赔偿 <span class="src">f52</span></li>
            <li>不可确认项：签证类异常检测流程、审批清单与制度口径、留存最终期限、异常单量与投诉分布 <span class="src">f04 / f41 / f43</span></li>
          </ul>
        </section>
        <section class="card">
          <h3>候选需求分布</h3>
          <div class="bars">
            ${[['P0 · 先定口径与必填字段', p0, '#dc2626'], ['P1 · 规则、授权与指标', p1, '#f97316'], ['P2 · 留存与审计期限', p2, '#64748b']]
              .map(([n, v, c]) => `<div class="bar-row"><div class="bar-name">${n}</div>
                <div class="bar-track"><div class="bar-fill" style="width:${v / 6 * 100}%;background:${c}"></div></div>
                <div class="bar-val">${v} 项</div></div>`).join('')}
          </div>
          <h3 style="margin-top:18px">四来源收敛状态</h3>
          <div class="bars">
            ${D.sources.map((s) => `<div class="bar-row"><div class="bar-name">${s.name.split(' · ')[0]}</div>
              <div class="bar-track"><div class="bar-fill" style="width:${s.status === 'missing' ? 8 : 55}%;background:${s.status === 'missing' ? '#dc2626' : '#0ea5e9'}"></div></div>
              <div class="bar-val">${s.status === 'missing' ? '缺失' : '部分'}</div></div>`).join('')}
          </div>
          <p class="p small">四个视角并未指向同一确认点：<b>Brief 与 Industry 缺失</b>。本期已补入行业证据（见「四来源」页），Industry 从“缺失”转为“部分”，但适用性仍需结合本项目数据与接口差异验证。</p>
        </section>
      </div>
      <div class="grid2">
        <section class="card">
          <h3>建议路径</h3>
          <ol class="ol">
            <li>先定两项 P0：确认回执口径、转人工必填字段</li>
            <li>再做三项 P1：数据关联与版本校验、审批授权清单、试点指标口径</li>
            <li>留存与审计（P2）期限待组织规则确认后推进</li>
            <li>六项均须在试点前书面固定分母、排除规则与统计周期，并由负责人签发</li>
          </ol>
        </section>
        <section class="card">
          <h3>归因规则（未达标时先查什么）</h3>
          <ol class="ol">
            <li>先看<b>覆盖率是否 100%</b>：覆盖不全说明执行没做对，不是方案错</li>
            <li>覆盖达标但遗漏仍超 2%：再查节点耗时与交接责任</li>
            <li>触及停止条件：暂停试点并由负责人复盘</li>
          </ol>
          <p class="p small">来源：f02 / f42 / f44。此规则须事先写进试点方案，事后补写无法追溯。</p>
        </section>
      </div>`;
  }

  /* ---------- 四来源收敛 ---------- */
  function renderSources() {
    return `
      <div class="card">
        <h3>Buyer · Brief · Industry · Operator 四来源核对</h3>
        <p class="p small">用途：回答“谁说要做、哪里真的坏了、范围允许什么、技术是否可行”。四个视角若不指向同一瓶颈，分歧须保留在问题清单而非被抹平。</p>
      </div>
      <div class="grid2">
        ${D.sources.map((s) => `
          <section class="card">
            <div class="card-head">
              <h3>${esc(s.name)}</h3>
              <span class="tag ${s.status === 'missing' ? 'bad' : 'warn'}">${s.status === 'missing' ? '缺失' : '部分采集'}</span>
            </div>
            <div class="meta-row"><span>对应角色</span>${esc(s.who)}</div>
            <div class="meta-row"><span>状态</span>${esc(s.statusText)}</div>
            <div class="meta-row"><span>已采集依据</span>${
              s.evidence.length ? s.evidence.map(evChip).join(' ') : '<span class="muted">暂无</span>'}</div>
            <div class="gaps"><b>缺口 / 待核实</b><ul class="ul">${s.gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul></div>
          </section>`).join('')}
      </div>
      <div class="card">
        <h3>行业实践证据（本期补充 · 补 Industry 缺口）</h3>
        <p class="p small">报告原文标注 Industry 为“待补行业实践”；下列条目为本次补入的可比对证据，均已标注出处与口径差异，不能直接当作本项目的验收基线。</p>
        <table class="tbl">
          <tr><th style="width:110px">主题</th><th style="width:34%">行业发现</th><th style="width:22%">出处</th><th style="width:22%">对本项目的含义</th><th>口径差异 / 风险</th></tr>
          ${D.industry.map((i) => `<tr><td><b>${esc(i.topic)}</b></td><td>${esc(i.finding)}</td>
            <td class="small">${esc(i.source)}</td><td>${esc(i.implication)}</td><td class="small muted">${esc(i.caveat)}</td></tr>`).join('')}
        </table>
      </div>`;
  }

  /* ---------- 流程拆解 ---------- */
  function renderProcess() {
    const asis = window.AS_IS, tobe = window.TO_BE;
    if (!asis) return '<div class="card">未能加载 ../flowcharts/as-is-flow.data.js，请将流程图目录与本页面放在同一仓库结构下。</div>';
    const rows = (d) => d.steps.map((s) => {
      const lane = d.lanes.find((l) => l.id === s.lane);
      return `<tr>
        <td class="mono">${esc(s.code)}</td>
        <td>${esc(lane ? lane.name : s.lane)}</td>
        <td><span class="tag t-${s.type}">${TYPE_LABEL[s.type] || s.type}</span></td>
        <td><b>${esc(s.title)}</b><div class="small muted">${esc(s.note || '')}</div></td>
        <td class="small fail">${s.fail ? '⚠ ' + esc(s.fail) : '<span class="muted">—</span>'}</td>
      </tr>`;
    }).join('');
    const countBy = (d) => Object.keys(TYPE_LABEL).map((t) => {
      const n = d.steps.filter((s) => s.type === t).length;
      return n ? `<span class="tag t-${t}">${TYPE_LABEL[t]} ${n}</span>` : '';
    }).join(' ');
    return `
      <div class="card">
        <h3>流程拆解：先画人工现状泳道，标注触发、输入、步骤、交接与异常</h3>
        <p class="p small">交付链：现状流程 → 失败方式 → 智能体／工具边界 → 校验与人工升级路径。区分判断点与执行点，并按失败方式决定哪些步骤可交给系统。</p>
        <div class="tagline">现状：共 ${asis.steps.length} 步 · ${countBy(asis)}</div>
        <div class="tagline">转型后：共 ${tobe.steps.length} 步 · ${countBy(tobe)}</div>
      </div>
      <div class="card">
        <h3>现状步骤明细</h3>
        <table class="tbl">
          <tr><th style="width:60px">编号</th><th style="width:190px">泳道（角色/系统）</th><th style="width:90px">性质</th><th>动作与说明</th><th style="width:26%">失败方式</th></tr>
          ${rows(asis)}
        </table>
      </div>
      <div class="card">
        <h3>转型后步骤明细</h3>
        <table class="tbl">
          <tr><th style="width:60px">编号</th><th style="width:190px">泳道（角色/系统）</th><th style="width:90px">性质</th><th>动作与说明</th><th style="width:26%">失败方式 / 停止条件</th></tr>
          ${rows(tobe)}
        </table>
      </div>`;
  }

  /* ---------- 结果与不可逆风险矩阵 ---------- */
  function renderMatrix() {
    const list = D.candidates.slice().sort((a, b) => score(state.scores[b.id]) - score(state.scores[a.id]));
    return `
      <div class="card">
        <h3>业务结果与不可逆风险矩阵</h3>
        <p class="p small">评分口径：<b>综合分 = 业务价值×40% + 可拦截性×35% + 可恢复性×25%</b>（各 1–5 分，满分 100）。
        判定规则：可拦截性 ≤2 → 不做并设硬约束；可恢复性 ≤2 → 暂缓待补证据；综合分 ≥70 → 先做最小可验证方案。
        <b>不要把模型置信度等同于业务风险</b>。可拖动滑块做敏感性分析，排序会实时变化。</p>
        <div class="tagline">
          <span class="tag go">先做</span><span class="tag hold">暂缓/候选</span><span class="tag no">不做</span>
          <button class="btn" id="reset">恢复默认评分</button>
        </div>
      </div>
      <div class="card">
        <table class="tbl matrix">
          <tr><th style="width:40px">#</th><th style="width:22%">候选切入点</th><th style="width:150px">综合分</th>
            <th style="width:150px">价值 / 可拦截 / 可恢复</th><th style="width:22%">现状基线</th><th style="width:20%">失败何时被谁看见</th><th style="width:90px">结论</th></tr>
          ${list.map((c, i) => {
            const s = state.scores[c.id], sc = score(s), d = decision(s);
            return `<tr>
              <td class="mono">${i + 1}</td>
              <td><b>${esc(c.name)}</b><div class="small muted">${esc(c.req)} · 投入：${esc(c.effort)}</div></td>
              <td><div class="score-wrap"><div class="score-bar"><div class="score-fill ${d.c}" style="width:${sc}%"></div></div><span class="mono">${sc}</span></div></td>
              <td>
                <label>价值 <input type="range" min="1" max="5" value="${s.value}" data-c="${c.id}" data-k="value"><output>${s.value}</output></label>
                <label>拦截 <input type="range" min="1" max="5" value="${s.intercept}" data-c="${c.id}" data-k="intercept"><output>${s.intercept}</output></label>
                <label>恢复 <input type="range" min="1" max="5" value="${s.recover}" data-c="${c.id}" data-k="recover"><output>${s.recover}</output></label>
              </td>
              <td class="small">${esc(c.baseline)}</td>
              <td class="small">${esc(c.failVisible)}</td>
              <td><span class="tag ${d.c}">${d.t}</span></td>
            </tr>`;
          }).join('')}
        </table>
      </div>`;
  }

  /* ---------- 候选需求清单 ---------- */
  function renderReqs() {
    const groups = ['P0', 'P1', 'P2'].map((p) => {
      const rs = D.requirements.filter((r) => r.priority === p && (match(r.id + r.title + r.problem + r.owner)));
      if (!rs.length) return '';
      return `<h3 class="group">${p} · ${p === 'P0' ? '先定口径与必填字段' : p === 'P1' ? '规则、授权与指标口径' : '留存与审计期限'}</h3>` +
        rs.map((r) => `
          <section class="card">
            <div class="card-head">
              <h3><span class="mono">${r.id}</span> ${esc(r.title)}</h3>
              <span class="tag ${p === 'P0' ? 'bad' : p === 'P1' ? 'warn' : 'grey'}">${p}</span>
            </div>
            <table class="tbl kv">
              <tr><th style="width:120px">待确认负责人</th><td>${esc(r.owner)}</td></tr>
              <tr><th>问题推导</th><td>${esc(r.problem)}</td></tr>
              <tr><th>不确定处</th><td class="muted">${esc(r.uncertainty)}</td></tr>
              <tr><th>下一步验证</th><td>${esc(r.next)}</td></tr>
              <tr><th>验收出口</th><td>${esc(r.acceptance)}</td></tr>
              <tr><th>证据依据</th><td>${r.evidence.map(evChip).join(' ')}</td></tr>
            </table>
          </section>`).join('');
    }).join('');
    const shown = D.requirements.filter((r) => match(r.id + r.title + r.problem + r.owner)).length;
    return `<div class="card small muted">当前显示 ${shown} / ${D.requirements.length} 项候选需求。注意：P0/P1/P2 是<b>验证顺序</b>建议，不等于已完成价值与风险评分。</div>${groups ||
      '<div class="card">没有匹配“' + esc(state.q) + '”的需求。</div>'}`;
  }

  /* ---------- 证据库 ---------- */
  function renderEvidence() {
    const list = D.evidence.filter((e) =>
      (state.role === 'all' || e.role === state.role) &&
      match(e.id + e.text + D.roles[e.role] + e.type));
    const chips = [['all', '全部']].concat(Object.keys(D.roles).map((r) => [r, D.roles[r].split(' · ')[1] + ' · ' + D.roles[r].split(' · ')[0]]));
    return `
      <div class="card">
        <h3>访谈证据库（f00–f55，共 ${D.evidence.length} 条）</h3>
        <div class="tagline">${chips.map(([v, n]) => `<button class="chip ${state.role === v ? 'on' : ''}" data-role="${v}">${esc(n)}</button>`).join('')}</div>
        <div class="small muted">当前显示 ${list.length} 条。证据按岗位分组：f0x 运营经理、f1x 导游、f2x 协调员、f3x 平台工程师、f4x 安全主管、f5x 目的地服务商。</div>
      </div>
      <div class="ev-grid">
        ${list.map((e) => `
          <div class="ev ${state.highlight === e.id ? 'hl' : ''}" id="ev-${e.id}">
            <div class="ev-top"><span class="mono">${e.id}</span><span class="tag grey">${esc(e.type)}</span></div>
            <div class="ev-text">${esc(e.text)}</div>
            <div class="ev-role">${esc(roleName(e.role))}</div>
          </div>`).join('')}
      </div>`;
  }

  /* ---------- 流程图 ---------- */
  function renderFlows() {
    return `
      <div class="card">
        <h3>两张流程图</h3>
        <p class="p small">现状流程来自角色访谈还原，转型后流程引入“变更影响与通知闭环引擎”泳道并完成五级审核门设计。可直接打印或导出 PDF。</p>
        <div class="tagline">
          <a class="btn" href="../flowcharts/as-is-flow.html" target="_blank">在新窗口打开现状图</a>
          <a class="btn" href="../flowcharts/to-be-flow.html" target="_blank">在新窗口打开转型后图</a>
        </div>
      </div>
      <div class="card"><h3>现状：人工主导 · 多版本并存</h3>
        <iframe src="../flowcharts/as-is-flow.html" loading="lazy"></iframe></div>
      <div class="card"><h3>转型后：人机协同 · 回执才算完成</h3>
        <iframe src="../flowcharts/to-be-flow.html" loading="lazy"></iframe></div>`;
  }

  /* ---------- 验证排期 ---------- */
  function renderPlan() {
    const at = D.validations.filter((v) => match(v.action + v.exit + v.req));
    const qs = D.questions.filter((q) => match(q.to + q.q));
    return `
      <div class="card">
        <h3>后续验证动作排序</h3>
        <table class="tbl">
          <tr><th style="width:50px">序号</th><th style="width:30%">验证动作</th><th style="width:34%">目的与出口</th><th style="width:90px">对应需求</th></tr>
          ${at.map((v) => `<tr><td class="mono">${v.no}</td><td>${esc(v.action)}</td><td>${esc(v.exit)}</td><td class="mono">${esc(v.req)}</td></tr>`).join('')}
        </table>
      </div>
      <div class="card">
        <h3>待追问事项（试点方案定稿前须完成核对）</h3>
        <table class="tbl">
          <tr><th style="width:200px">追问对象</th><th>待核实问题</th></tr>
          ${qs.map((q) => `<tr><td>${esc(q.to)}</td><td>${esc(q.q)}</td></tr>`).join('')}
        </table>
        <p class="p small">上述 8 项对应报告“二手转述缺口”：访谈材料集中于安全主管与目的地服务商，导游、协调员、工程师、运营经理的现场细节多为转述，未经本人直接确认。</p>
      </div>`;
  }

  const TABS = [
    { id: 'overview', name: '总览', render: renderOverview },
    { id: 'sources', name: '四来源收敛', render: renderSources },
    { id: 'process', name: '流程拆解', render: renderProcess },
    { id: 'matrix', name: '风险矩阵', render: renderMatrix },
    { id: 'reqs', name: '候选需求', render: renderReqs },
    { id: 'evidence', name: '证据库', render: renderEvidence },
    { id: 'flows', name: '流程图', render: renderFlows },
    { id: 'plan', name: '验证排期', render: renderPlan }
  ];

  function renderNav() {
    NAV.innerHTML = TABS.map((t) => `<button class="nav-item ${state.tab === t.id ? 'on' : ''}" data-tab="${t.id}">${t.name}</button>`).join('');
  }

  function draw() {
    const tab = TABS.find((t) => t.id === state.tab) || TABS[0];
    APP.innerHTML = tab.render();
    if (state.tab === 'matrix') {
      const reset = document.getElementById('reset');
      if (reset) reset.addEventListener('click', () => {
        D.candidates.forEach((c) => { state.scores[c.id] = { value: c.value, intercept: c.intercept, recover: c.recover }; });
        draw();
      });
      APP.querySelectorAll('input[type=range]').forEach((inp) => {
        inp.addEventListener('input', (e) => {
          const id = e.target.dataset.c, k = e.target.dataset.k;
          state.scores[id][k] = Number(e.target.value);
          draw();
        });
      });
    }
    if (state.highlight) {
      const node = document.getElementById('ev-' + state.highlight);
      if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  APP.addEventListener('click', (e) => {
    const chipEv = e.target.closest('[data-ev]');
    if (chipEv) {
      state.tab = 'evidence';
      state.role = 'all';
      state.q = '';
      document.getElementById('q').value = '';
      state.highlight = chipEv.dataset.ev;
      renderNav(); draw();
      setTimeout(() => { state.highlight = null; }, 2600);
      return;
    }
    const chipRole = e.target.closest('[data-role]');
    if (chipRole) {
      state.role = chipRole.dataset.role;
      draw();
    }
  });

  NAV.addEventListener('click', (e) => {
    const b = e.target.closest('[data-tab]');
    if (!b) return;
    state.tab = b.dataset.tab;
    state.highlight = null;
    renderNav(); draw();
  });

  document.getElementById('q').addEventListener('input', (e) => {
    state.q = e.target.value.trim();
    draw();
  });

  const hash = location.hash.replace('#', '');
  if (hash && TABS.some((t) => t.id === hash)) state.tab = hash;
  renderNav();
  draw();
})();
