/* 泳道流程图渲染引擎：由数据驱动生成 SVG，避免手写坐标。
 * 用法：FlowRender.render(svgElement, config)
 * config = { lanes, steps, loops, laneWidth, title, meta, sources }
 */
(function (global) {
  'use strict';

  const TYPE_STYLE = {
    exec:     { label: '执行',       fill: '#ffffff', stroke: '#94a3b8', bar: '#64748b' },
    decision: { label: '判断点',     fill: '#fff7ed', stroke: '#fb923c', bar: '#f97316' },
    wait:     { label: '等待/超时',  fill: '#f1f5f9', stroke: '#94a3b8', bar: '#94a3b8' },
    manual:   { label: '人工控制',   fill: '#fef2f2', stroke: '#f87171', bar: '#ef4444' },
    engine:   { label: '系统能力',   fill: '#eff6ff', stroke: '#60a5fa', bar: '#2563eb' },
    intake:   { label: '外部触发',   fill: '#f5f3ff', stroke: '#a78bfa', bar: '#7c3aed' }
  };

  const LANE_PALETTE = ['#e2e8f0', '#eef2f6', '#e8eef7', '#f2eef9', '#eef7f1', '#fdf3ea', '#f6f0ec'];

  // 中文按 1 字宽、ASCII 按 0.58 字宽估算换行
  function textWidth(str, fontSize) {
    let w = 0;
    for (const ch of str) w += (/[\x00-\xff]/.test(ch) ? 0.58 : 1) * fontSize;
    return w;
  }

  function wrap(str, maxPx, fontSize) {
    const lines = [];
    let line = '';
    for (const ch of str) {
      const next = line + ch;
      if (textWidth(next, fontSize) > maxPx && line) {
        lines.push(line);
        line = ch;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function el(tag, attrs, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function measureNode(step, laneWidth) {
    const padX = 12;
    const inner = laneWidth - 2 * padX;
    const c = TYPE_STYLE[step.type] || TYPE_STYLE.exec;
    const titleLines = wrap(step.title, inner - 14, 13.5);
    const noteLines = step.note ? wrap(step.note, inner, 11.5) : [];
    const failLines = step.fail ? wrap(step.fail, inner, 11) : [];
    const h = 16 + titleLines.length * 18 + (noteLines.length ? 6 + noteLines.length * 15 : 0) +
              (failLines.length ? 6 + failLines.length * 14 : 0) + 12;
    return { titleLines, noteLines, failLines, height: h, style: c };
  }

  function drawNode(parent, step, x, y, w) {
    const m = measureNode(step, w);
    const c = m.style;
    const g = el('g', { transform: `translate(${x},${y})` });
    g.appendChild(el('rect', {
      x: 0, y: 0, width: w, height: m.height, rx: 8, ry: 8,
      fill: c.fill, stroke: c.stroke, 'stroke-width': 1.2
    }));
    // 左侧类型色条
    g.appendChild(el('rect', { x: 0, y: 0, width: 4, height: m.height, rx: 2, fill: c.bar }));
    // 编号徽标
    g.appendChild(el('circle', { cx: 18, cy: 17, r: 9, fill: c.bar, opacity: 0.12 }));
    g.appendChild(el('text', {
      x: 18, y: 21, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': '700', fill: c.bar
    }, step.code.replace(/^[A-Z]/, '')));
    let ty = 22;
    m.titleLines.forEach((ln, i) => {
      g.appendChild(el('text', { x: i === 0 ? 32 : 12, y: ty + i * 18, 'font-size': 13.5, 'font-weight': '600', fill: '#0f172a' }, ln));
    });
    ty += m.titleLines.length * 18 + 6;
    m.noteLines.forEach((ln, i) => {
      g.appendChild(el('text', { x: 12, y: ty + i * 15, 'font-size': 11.5, fill: '#475569' }, ln));
    });
    ty += m.noteLines.length * 15 + 6;
    m.failLines.forEach((ln, i) => {
      g.appendChild(el('text', { x: 12, y: ty + i * 14, 'font-size': 11, 'font-style': 'italic', fill: '#b91c1c' }, (i === 0 ? '⚠ ' : '') + ln));
    });
    parent.appendChild(g);
    return m.height;
  }

  function arrowPath(a, b) {
    // a: 起点(x,y) 从源节点底部出；b: 终点(x,y) 从目标节点顶部入
    const dy = Math.max(28, (b.y - a.y) / 2);
    const c1 = { x: a.x, y: a.y + dy };
    const c2 = { x: b.x, y: b.y - dy };
    return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
  }

  function render(svg, cfg) {
    svg.innerHTML = '';
    const laneWidth = cfg.laneWidth || 178;
    const gapX = 10;
    const marginL = 16, marginT = 108;
    const lanes = cfg.lanes;
    const laneIndex = {};
    lanes.forEach((l, i) => (laneIndex[l.id] = i));

    const totalW = marginL * 2 + lanes.length * laneWidth + (lanes.length - 1) * gapX;

    // 纵向排布：每个步骤独占一行，行高随内容自适应
    let y = marginT + 34;
    const positions = [];
    cfg.steps.forEach((s) => {
      const h = measureNode(s, laneWidth).height;
      const x = marginL + laneIndex[s.lane] * (laneWidth + gapX);
      positions.push({ x, y, h, step: s });
      y += h + 26;
    });
    const totalH = y + 70;

    svg.setAttribute('viewBox', `0 0 ${totalW} ${totalH}`);
    svg.setAttribute('width', totalW);
    svg.setAttribute('height', totalH);

    // 标题区
    const head = el('g', {});
    head.appendChild(el('text', { x: 16, y: 30, 'font-size': 19, 'font-weight': '700', fill: '#0f172a' }, cfg.title));
    if (cfg.subtitle) {
      head.appendChild(el('text', { x: 16, y: 52, 'font-size': 12.5, fill: '#475569' }, cfg.subtitle));
    }
    head.appendChild(el('rect', { x: 16, y: 64, width: totalW - 32, height: 34, rx: 6, fill: '#f8fafc', stroke: '#e2e8f0' }));
    (cfg.meta || []).forEach((kv, i) => {
      const x = 26 + i * ((totalW - 40) / (cfg.meta.length || 1));
      head.appendChild(el('text', { x: x, y: 79, 'font-size': 11, fill: '#64748b' }, kv.k));
      head.appendChild(el('text', { x: x, y: 93, 'font-size': 13, 'font-weight': '700', fill: '#0f172a' }, kv.v));
    });
    // 图例
    const legend = Object.keys(TYPE_STYLE);
    let lx = totalW - 16;
    for (let i = legend.length - 1; i >= 0; i--) {
      const c = TYPE_STYLE[legend[i]];
      const w = textWidth(c.label, 11) + 26;
      lx -= w + 8;
      head.appendChild(el('rect', { x: lx, y: 38, width: w, height: 18, rx: 4, fill: c.fill, stroke: c.stroke }));
      head.appendChild(el('rect', { x: lx, y: 38, width: 4, height: 18, fill: c.bar }));
      head.appendChild(el('text', { x: lx + 10, y: 51, 'font-size': 11, fill: '#334155' }, c.label));
    }
    svg.appendChild(head);

    // 泳道背景与表头
    lanes.forEach((l, i) => {
      const x = marginL + i * (laneWidth + gapX);
      svg.appendChild(el('rect', {
        x: x, y: marginT, width: laneWidth, height: totalH - marginT - 54,
        fill: LANE_PALETTE[i % LANE_PALETTE.length], opacity: 0.55, rx: 6
      }));
      svg.appendChild(el('rect', { x: x, y: marginT, width: laneWidth, height: 30, fill: '#1e293b', rx: 6 }));
      svg.appendChild(el('text', {
        x: x + laneWidth / 2, y: marginT + 20, 'text-anchor': 'middle',
        'font-size': 12.5, 'font-weight': '700', fill: '#ffffff'
      }, l.name));
    });

    // 连接线
    const defs = el('defs', {});
    [['ah', '#475569'], ['ah-fail', '#dc2626']].forEach(([id, color]) => {
      const marker = el('marker', {
        id: id, viewBox: '0 0 10 10', refX: 9, refY: 5,
        markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse'
      });
      marker.appendChild(el('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: color }));
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    for (let i = 0; i < positions.length - 1; i++) {
      const a = positions[i], b = positions[i + 1];
      const p = el('path', {
        d: arrowPath({ x: a.x + laneWidth / 2, y: a.y + a.h }, { x: b.x + laneWidth / 2, y: b.y }),
        fill: 'none', stroke: '#475569', 'stroke-width': 1.4, 'marker-end': 'url(#ah)'
      });
      svg.appendChild(p);
    }

    // 返工 / 升级回路
    (cfg.loops || []).forEach((lp) => {
      const from = positions.find((p) => p.step.code === lp.from);
      const to = positions.find((p) => p.step.code === lp.to);
      if (!from || !to) return;
      const start = { x: from.x + laneWidth - 6, y: from.y + from.h / 2 };
      const end = { x: to.x + 6, y: to.y + to.h / 2 };
      const off = Math.min(laneWidth * 0.9, 120) * (end.x > start.x ? -1 : 1);
      const d = `M ${start.x} ${start.y} C ${start.x - off} ${start.y}, ${end.x + off} ${end.y}, ${end.x} ${end.y}`;
      svg.appendChild(el('path', {
        d: d, fill: 'none', stroke: '#dc2626', 'stroke-width': 1.3,
        'stroke-dasharray': '5 4', 'marker-end': 'url(#ah-fail)'
      }));
      const mx = (start.x + end.x) / 2 - off * 0.55;
      const my = (start.y + end.y) / 2 - 8;
      svg.appendChild(el('rect', { x: mx - 46, y: my - 12, width: 92, height: 18, rx: 9, fill: '#fee2e2', stroke: '#fca5a5' }));
      svg.appendChild(el('text', {
        x: mx, y: my + 1.5, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': '600', fill: '#b91c1c'
      }, lp.label));
    });

    // 节点
    positions.forEach((p) => drawNode(svg, p.step, p.x, p.y, laneWidth));

    // 页脚来源说明
    if (cfg.sources) {
      svg.appendChild(el('text', { x: 16, y: totalH - 34, 'font-size': 11, fill: '#64748b' }, cfg.sources));
    }
  }

  global.FlowRender = { render: render };
})(window);
