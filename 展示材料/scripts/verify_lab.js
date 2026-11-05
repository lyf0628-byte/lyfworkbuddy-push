/* 无头冒烟校验：在两个 JS 文件的桩环境中跑通「业务挖掘实验室」的每个页签，
 * 确认渲染无运行时异常、每页均有实质输出。
 * 运行： node scripts/verify_lab.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const LAB = path.join(__dirname, '..', 'mining-lab');
const ROOT = path.join(__dirname, '..', 'flowcharts');

function mkEl(tag) {
  const el = {
    tag, _html: '', value: '', dataset: {}, handlers: {},
    addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    querySelectorAll() { return []; },
    scrollIntoView() {},
    closest() { return null; }
  };
  return el;
}

const registry = {};
const documentStub = {
  getElementById(id) { return (registry[id] = registry[id] || mkEl('div#' + id)); }
};
const locationStub = { hash: '' };
const windowStub = { document: documentStub };

const ctx = vm.createContext({ window: windowStub, document: documentStub, location: locationStub, console, setTimeout });
const load = (dir, f) => vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), ctx, { filename: f });

load(LAB, 'lab-data.js');
load(ROOT, 'as-is-flow.data.js');
load(ROOT, 'to-be-flow.data.js');
load(LAB, 'lab-app.js');

const app = registry.app;
const nav = registry.nav;
if (!app || !app._html) throw new Error('初始化失败：#app 未产生内容');

const navClick = (nav.handlers.click || [])[0];
if (!navClick) throw new Error('未注册导航点击事件');

const tabs = ['overview', 'sources', 'process', 'matrix', 'reqs', 'evidence', 'flows', 'plan'];
const report = [];
for (const t of tabs) {
  navClick({ target: { closest: () => ({ dataset: { tab: t } }) } });
  const html = app.innerHTML;
  if (!html || html.length < 300) throw new Error(`页签 ${t} 输出为空或过短`);
  if (html.indexOf('undefined') >= 0) throw new Error(`页签 ${t} 输出中出现 undefined，请检查数据字段`);
  report.push({ tab: t, chars: html.length });
}

// 校验数据完整性：需求引用的证据必须存在
const D = windowStub.LAB;
const ids = new Set(D.evidence.map((e) => e.id));
D.requirements.forEach((r) => r.evidence.forEach((id) => {
  if (!ids.has(id)) throw new Error(`需求 ${r.id} 引用了不存在的证据 ${id}`);
}));
D.sources.forEach((s) => s.evidence.forEach((id) => {
  if (!ids.has(id)) throw new Error(`来源 ${s.id} 引用了不存在的证据 ${id}`);
}));

console.table(report);
console.log(`校验通过：${D.evidence.length} 条证据、${D.requirements.length} 项需求、${D.candidates.length} 个候选切入点，跨引用一致。`);
