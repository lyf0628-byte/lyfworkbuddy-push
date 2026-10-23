/* 无头校验：在最小 DOM 桩上执行流程图渲染，确认无运行时异常并输出版面尺寸。
 * 运行： node scripts/verify_flowcharts.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..', 'flowcharts');

function makeNode(tag) {
  return {
    tag,
    attrs: {},
    children: [],
    textContent: '',
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { this.children.push(c); return c; }
  };
}

const documentStub = { createElementNS: (_ns, tag) => makeNode(tag) };
const windowStub = { document: documentStub };

const ctx = vm.createContext({ window: windowStub, document: documentStub, console });
const load = (f) => vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });

load('flow-render.js');
const results = [];
for (const [name, key, dataFile] of [
  ['现状流程图', 'AS_IS', 'as-is-flow.data.js'],
  ['转型后流程图', 'TO_BE', 'to-be-flow.data.js']
]) {
  load(dataFile);
  const data = windowStub[key];
  const svg = makeNode('svg');
  windowStub.FlowRender.render(svg, Object.assign({}, data.config, {
    lanes: data.lanes, steps: data.steps, loops: data.loops
  }));
  let nodes = 0, texts = 0, paths = 0;
  (function walk(n) {
    if (n.tag === 'g') nodes++;
    if (n.tag === 'text') texts++;
    if (n.tag === 'path') paths++;
    n.children.forEach(walk);
  })(svg);
  results.push({
    name,
    lanes: data.lanes.length,
    steps: data.steps.length,
    loops: data.loops.length,
    width: Number(svg.getAttribute('width')),
    height: Number(svg.getAttribute('height')),
    nodeGroups: nodes, texts, paths
  });
  // 一致性校验：步骤引用的泳道必须存在；回路引用的步骤必须存在
  const laneIds = new Set(data.lanes.map((l) => l.id));
  data.steps.forEach((s) => {
    if (!laneIds.has(s.lane)) throw new Error(`${name}: 步骤 ${s.code} 引用未知泳道 ${s.lane}`);
  });
  const codes = new Set(data.steps.map((s) => s.code));
  data.loops.forEach((l) => {
    if (!codes.has(l.from) || !codes.has(l.to)) throw new Error(`${name}: 回路 ${l.from}->${l.to} 引用未知步骤`);
  });
}

console.table(results);
console.log('校验通过：泳道引用、回路引用、渲染执行均无异常。');
