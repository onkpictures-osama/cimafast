"""مكوّنين المتصفح لطاولة التقطيع (st.components.v2): نص المشهد، ورسمة المكان.

البيانات بتوصل JSON وبتترسم بـ textContent بس (مفيش innerHTML لأي نص جاي من
المستخدم أو الـ AI). المتصفح بيرجّع حاجة واحدة لبايثون وقت ما المستخدم يدوس
زرار (trigger)، مش مع كل سحبة — عشان الصفحة ماتعملش rerun مع كل حركة.
"""

import streamlit as st

# ---------------------------------------------------------------- نص المشهد

SCRIPT_CSS = """
.cf-sc { font-family: inherit; color: var(--st-text-color); }
.cf-sc-bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
.cf-sc-bar button, .cf-sc-bar select {
  font: inherit; font-size: 0.85rem; padding: 4px 10px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.18); background: transparent; color: inherit; }
.cf-sc-bar button.on { background: var(--st-primary-color); color: #111; border-color: transparent; }
.cf-sc-bar button.go { background: var(--st-primary-color); color: #111; border-color: transparent; font-weight: 600; }
.cf-sc-bar button:disabled { opacity: 0.45; cursor: default; }
.cf-sc-body { max-height: 560px; overflow-y: auto; padding-inline-end: 4px; }
.cf-sc-row { display: flex; gap: 8px; align-items: stretch; cursor: pointer; border-radius: 6px; }
.cf-sc-row:hover { background: rgba(255,255,255,0.04); }
.cf-sc-row.sel { background: rgba(255, 200, 40, 0.16); outline: 1px solid rgba(255, 200, 40, 0.55); }
.cf-sc-row.dim { opacity: 0.35; }
.cf-sc-lanes { display: flex; gap: 3px; flex: 0 0 auto; }
.cf-sc-lane { width: 14px; position: relative; }
.cf-sc-lane i { position: absolute; inset-block: 0; inset-inline-start: 5px; width: 4px; border-radius: 2px; }
.cf-sc-lane b { position: absolute; top: 0; inset-inline-start: 0; font-size: 0.66rem; font-style: normal;
  line-height: 1; padding: 1px 2px; border-radius: 3px; color: #111; }
.cf-sc-text { padding: 6px 4px; line-height: 1.7; flex: 1; text-align: start; }
.cf-sc-text.dlg { padding-inline-start: 28px; }
.cf-sc-who { display: block; font-weight: 700; font-size: 0.85rem; opacity: 0.85; }
.cf-sc-empty { opacity: 0.7; padding: 12px 4px; }
.cf-sc-hint { font-size: 0.8rem; opacity: 0.7; margin-top: 6px; }
"""

SCRIPT_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const L = data.labels;
  let root = parentElement.querySelector('.cf-sc');
  if (!root) { root = document.createElement('div'); root.className = 'cf-sc'; parentElement.appendChild(root); }
  root.setAttribute('dir', data.dir || 'rtl');
  const sig = JSON.stringify([data.scene_id, data.coverage, data.shots.map(s => [s.id, s.blocks])]);
  if (!root.__st || root.__st.sig !== sig) {
    const prev = root.__st;
    const st = { sig, filter: prev ? prev.filter : 'all', target: 'new', sel: new Set() };
    if (prev && prev.target !== 'new' && data.shots.some(s => String(s.id) === prev.target)) st.target = prev.target;
    const cur = data.shots.find(s => String(s.id) === st.target);
    if (cur) st.sel = new Set(cur.blocks);
    root.__st = st;
  }
  const st = root.__st;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  function render() {
    const keep = root.__scroll || 0;
    root.textContent = '';
    const bar = el('div', 'cf-sc-bar');
    [['all', L.all], ['dialogue', L.dialogue], ['action', L.action]].forEach(([k, lbl]) => {
      const b = el('button', st.filter === k ? 'on' : '', lbl);
      b.onclick = () => { st.filter = k; render(); };
      bar.appendChild(b);
    });
    if (data.editable) {
      const pick = el('select');
      const o0 = el('option', null, L.for_new); o0.value = 'new'; pick.appendChild(o0);
      data.shots.forEach(s => { const o = el('option', null, L.for_shot + ' ' + s.number); o.value = String(s.id); pick.appendChild(o); });
      pick.value = st.target;
      pick.onchange = () => {
        st.target = pick.value;
        const s = data.shots.find(s => String(s.id) === st.target);
        st.sel = new Set(s ? s.blocks : []);
        render();
      };
      bar.appendChild(pick);
      const go = el('button', 'go', st.target === 'new' ? (L.make_shot + ' (' + st.sel.size + ')') : L.save_cover);
      go.disabled = st.target === 'new' && st.sel.size === 0;
      go.onclick = () => setTriggerValue('pick', { target: st.target, ids: Array.from(st.sel).sort((a, b) => a - b), n: Date.now() });
      bar.appendChild(go);
      if (st.sel.size) { const c = el('button', '', L.clear); c.onclick = () => { st.sel = new Set(); render(); }; bar.appendChild(c); }
    }
    root.appendChild(bar);

    const body = el('div', 'cf-sc-body');
    if (!data.blocks.length) body.appendChild(el('div', 'cf-sc-empty', L.no_text));
    const lanes = data.shots.slice(0, 12);
    const covers = (i, n) => (data.coverage[String(i)] || []).includes(n);
    data.blocks.forEach((b, idx) => {
      const dim = st.filter !== 'all' && st.filter !== b.kind;
      const row = el('div', 'cf-sc-row' + (st.sel.has(b.i) ? ' sel' : '') + (dim ? ' dim' : ''));
      const ln = el('div', 'cf-sc-lanes');
      lanes.forEach(s => {
        const lane = el('div', 'cf-sc-lane');
        if (covers(b.i, s.number)) {
          const line = el('i'); line.style.background = s.color; lane.appendChild(line);
          if (!(idx > 0 && covers(data.blocks[idx - 1].i, s.number))) {
            const tag = el('b', null, String(s.number)); tag.style.background = s.color; lane.appendChild(tag);
          }
        }
        ln.appendChild(lane);
      });
      row.appendChild(ln);
      const tx = el('div', 'cf-sc-text' + (b.kind === 'dialogue' ? ' dlg' : ''));
      if (b.kind === 'dialogue') tx.appendChild(el('span', 'cf-sc-who', b.speaker));
      tx.appendChild(el('span', null, b.text));
      row.appendChild(tx);
      if (data.editable) row.onclick = () => { st.sel.has(b.i) ? st.sel.delete(b.i) : st.sel.add(b.i); render(); };
      body.appendChild(row);
    });
    root.appendChild(body);
    if (data.editable && data.blocks.length) root.appendChild(el('div', 'cf-sc-hint', L.hint));
    body.scrollTop = keep;
    body.onscroll = () => { root.__scroll = body.scrollTop; };
  }
  render();
}
"""

# ---------------------------------------------------------------- رسمة المكان

PLAN_CSS = """
.cf-pl { color: var(--st-text-color); font-family: inherit; }
.cf-pl-bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }
.cf-pl-bar button, .cf-pl-bar input {
  font: inherit; font-size: 0.82rem; padding: 3px 9px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.18); background: transparent; color: inherit; }
.cf-pl-bar input { width: 64px; cursor: text; }
.cf-pl-bar input.lbl { width: 130px; }
.cf-pl-bar button.on { background: var(--st-primary-color); color: #111; border-color: transparent; }
.cf-pl-bar button.go { background: var(--st-primary-color); color: #111; border-color: transparent; font-weight: 600; }
.cf-pl-bar .sep { width: 1px; align-self: stretch; background: rgba(255,255,255,0.15); margin: 0 2px; }
.cf-pl-bar .cap { font-size: 0.8rem; opacity: 0.75; }
.cf-pl svg { width: 100%; height: auto; display: block; background: #10131f; border-radius: 10px; touch-action: none; user-select: none; }
.cf-pl-dirty { font-size: 0.8rem; color: var(--st-primary-color); }
"""

PLAN_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const L = data.labels, NS = 'http://www.w3.org/2000/svg';
  let root = parentElement.querySelector('.cf-pl');
  if (!root) { root = document.createElement('div'); root.className = 'cf-pl'; parentElement.appendChild(root); }
  root.setAttribute('dir', data.dir || 'rtl');
  const sig = JSON.stringify([data.scene_id, data.plan, data.blocking, data.rev]);
  if (!root.__st || root.__st.sig !== sig) {
    root.__st = { sig, mode: root.__st ? root.__st.mode : 'block', plan: JSON.parse(JSON.stringify(data.plan)),
                  bl: JSON.parse(JSON.stringify(data.blocking)), sel: null, pen: false, dirtyPlan: false, dirtyBl: false };
  }
  const S = root.__st;
  const P = S.plan, B = S.bl;
  const M = Math.round(0.2 * Math.max(P.w, P.h));
  const U = () => Math.max(P.w, P.h) / 500;   // حجم النقط والكتابة بيكبر مع المكان
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const sv = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const redraw = () => draw();
  let dragging = null;
  const charById = id => data.chars.find(c => c.id === id);
  const shotById = id => data.shots.find(s => s.id === id);

  function toolbar() {
    const bar = el('div', 'cf-pl-bar');
    const tab = (k, lbl) => { const b = el('button', S.mode === k ? 'on' : '', lbl); b.onclick = () => { S.mode = k; S.sel = null; S.pen = false; redraw(); }; return b; };
    bar.appendChild(tab('block', L.mode_block));
    if (data.can_edit_plan) bar.appendChild(tab('decor', L.mode_decor));
    if (data.editable) {
      const save = el('button', 'go', L.save); save.onclick = () => {
        setTriggerValue('save', { plan: S.plan, blocking: S.bl, plan_dirty: S.dirtyPlan, n: Date.now() });
      };
      bar.appendChild(save);
      if (S.dirtyPlan || S.dirtyBl) bar.appendChild(el('span', 'cf-pl-dirty', L.unsaved));
    }
    barBox.appendChild(bar);
    if (!data.editable) return;
    const bar2 = el('div', 'cf-pl-bar');
    if (S.mode === 'decor') {
      data.kinds.forEach(([k, lbl]) => { const b = el('button', '', '+ ' + lbl); b.onclick = () => addItem(k, lbl); bar2.appendChild(b); });
      bar2.appendChild(el('span', 'sep'));
      const pen = el('button', S.pen ? 'on' : '', L.pen); pen.onclick = () => { S.pen = !S.pen; S.sel = null; redraw(); }; bar2.appendChild(pen);
      if (P.strokes.length) { const u = el('button', '', L.undo_stroke); u.onclick = () => { P.strokes.pop(); S.dirtyPlan = true; redraw(); }; bar2.appendChild(u); }
      bar2.appendChild(el('span', 'sep'));
      bar2.appendChild(el('span', 'cap', L.room));
      ['w', 'h'].forEach(k => { const i = el('input'); i.type = 'number'; i.min = 100; i.max = 2000; i.step = 50; i.value = P[k];
        i.onchange = () => { P[k] = Math.max(100, Math.min(2000, Number(i.value) || P[k])); S.dirtyPlan = true; redraw(); }; bar2.appendChild(i); });
    } else {
      const placedC = new Set(B.chars.map(c => c.id)), placedS = new Set(B.cams.map(c => c.shot_id));
      const freeC = data.chars.filter(c => !placedC.has(c.id)), freeS = data.shots.filter(s => !placedS.has(s.id));
      // كل واحد جديد بيتحط جنب اللي قبله مش فوقه
      const spot = (n) => 0.25 + 0.12 * (n % 5);
      if (freeC.length) {
        bar2.appendChild(el('span', 'cap', L.place_chars));
        freeC.forEach(c => { const b = el('button', '', '● ' + c.name); b.style.borderColor = c.color;
          b.onclick = () => { B.chars.push({ id: c.id, x: Math.round(P.w * spot(B.chars.length)), y: Math.round(P.h / 2), f: 0 });
            S.sel = { t: 'char', id: c.id }; S.dirtyBl = true; redraw(); }; bar2.appendChild(b); });
      } else if (!data.chars.length) bar2.appendChild(el('span', 'cap', L.no_chars));
      barBox.appendChild(bar2);
      // الكاميرات: سطر لوحده - كاميرا لكل لقطة، بتتحط جوه المكان تحت وباصّة لفوق
      const barC = el('div', 'cf-pl-bar');
      if (!data.shots.length) barC.appendChild(el('span', 'cap', L.no_shots));
      else if (freeS.length) {
        barC.appendChild(el('span', 'cap', L.place_cams));
        freeS.forEach(s => { const b = el('button', '', '🎥 ' + L.cam_of_shot + ' ' + s.number); b.style.borderColor = s.color;
          b.onclick = () => { B.cams.push({ shot_id: s.id, x: Math.round(P.w * spot(B.cams.length)), y: Math.round(P.h - 0.1 * P.h), r: -90 });
            S.sel = { t: 'cam', id: s.id }; S.dirtyBl = true; redraw(); }; barC.appendChild(b); });
      } else barC.appendChild(el('span', 'cap', L.all_cams_placed));
      barBox.appendChild(barC);
    }
    if (S.mode === 'decor') barBox.appendChild(bar2);
    const selObj = selected();
    if (selObj) {
      const bar3 = el('div', 'cf-pl-bar');
      bar3.appendChild(el('span', 'cap', selObj.title));
      const rot = (d) => { const b = el('button', '', d > 0 ? '⟳' : '⟲'); b.onclick = () => { selObj.rotate(d); redraw(); }; return b; };
      bar3.appendChild(rot(-15)); bar3.appendChild(rot(15));
      if (selObj.resize) { ['−', '+'].forEach((s, i) => { const b = el('button', '', s); b.onclick = () => { selObj.resize(i ? 1.15 : 1 / 1.15); redraw(); }; bar3.appendChild(b); });
        ['↔', '↕'].forEach((s, i) => { const b = el('button', '', s + '+'); b.onclick = () => { selObj.stretch(i); redraw(); }; bar3.appendChild(b); }); }
      if (selObj.label !== undefined) { const i = el('input', 'lbl'); i.value = selObj.label; i.placeholder = L.label;
        i.onchange = () => { selObj.setLabel(i.value); redraw(); }; bar3.appendChild(i); }
      if (selObj.move) { const b = el('button', selObj.hasMove ? 'on' : '', L.move); b.onclick = () => { selObj.move(); redraw(); }; bar3.appendChild(b); }
      const del = el('button', '', L.remove); del.onclick = () => { selObj.remove(); S.sel = null; redraw(); }; bar3.appendChild(del);
      barBox.appendChild(bar3);
    }
  }

  function selected() {
    if (!S.sel || !data.editable) return null;
    if (S.sel.t === 'item') {
      const it = P.items[S.sel.i]; if (!it) return null;
      return { title: it.label || L.item, label: it.label,
        rotate: d => { it.r = (it.r + d) % 360; S.dirtyPlan = true; },
        resize: f => { it.w = Math.max(5, Math.round(it.w * f)); it.h = Math.max(3, Math.round(it.h * f)); S.dirtyPlan = true; },
        stretch: axis => { if (axis) it.h = Math.round(it.h * 1.2); else it.w = Math.round(it.w * 1.2); S.dirtyPlan = true; },
        setLabel: v => { it.label = v.slice(0, 40); S.dirtyPlan = true; },
        remove: () => { P.items.splice(S.sel.i, 1); S.dirtyPlan = true; } };
    }
    if (S.sel.t === 'char') {
      const c = B.chars.find(c => c.id === S.sel.id); if (!c) return null;
      return { title: (charById(c.id) || {}).name || '', rotate: d => { c.f = (c.f + d) % 360; S.dirtyBl = true; },
        hasMove: c.tx != null,
        move: () => { if (c.tx != null) { delete c.tx; delete c.ty; } else { c.tx = Math.min(P.w, c.x + 80); c.ty = c.y; } S.dirtyBl = true; },
        remove: () => { B.chars = B.chars.filter(x => x.id !== c.id); S.dirtyBl = true; } };
    }
    if (S.sel.t === 'cam') {
      const c = B.cams.find(c => c.shot_id === S.sel.id); if (!c) return null;
      return { title: L.shot + ' ' + ((shotById(c.shot_id) || {}).number || ''), rotate: d => { c.r = (c.r + d) % 360; S.dirtyBl = true; },
        remove: () => { B.cams = B.cams.filter(x => x.shot_id !== c.shot_id); S.dirtyBl = true; } };
    }
    return null;
  }

  function addItem(k, lbl) {
    const size = data.kind_sizes[k] || [60, 40];
    P.items.push({ k, x: P.w / 2, y: P.h / 2, w: size[0], h: size[1], r: 0, label: k === 'block' ? '' : lbl });
    S.sel = { t: 'item', i: P.items.length - 1 }; S.dirtyPlan = true; redraw();
  }

  function svgPoint(svg, evt) {
    const pt = svg.createSVGPoint(); pt.x = evt.clientX; pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function drawItem(g, it, idx, active) {
    const grp = sv('g', { transform: 'translate(' + it.x + ' ' + it.y + ') rotate(' + it.r + ')' });
    const sel = S.sel && S.sel.t === 'item' && S.sel.i === idx;
    const stroke = sel ? '#ffc828' : 'rgba(255,255,255,0.55)';
    const hw = it.w / 2, hh = it.h / 2;
    if (it.k === 'plant') grp.appendChild(sv('circle', { r: Math.max(hw, hh), fill: 'rgba(90,170,110,0.35)', stroke }));
    else if (it.k === 'wall') grp.appendChild(sv('rect', { x: -hw, y: -hh, width: it.w, height: it.h, fill: 'rgba(230,230,240,0.85)', stroke }));
    else if (it.k === 'window') { grp.appendChild(sv('rect', { x: -hw, y: -hh, width: it.w, height: it.h, fill: 'rgba(120,190,255,0.35)', stroke }));
      grp.appendChild(sv('line', { x1: -hw, y1: 0, x2: hw, y2: 0, stroke: 'rgba(120,190,255,0.9)' })); }
    else if (it.k === 'door') { grp.appendChild(sv('rect', { x: -hw, y: -hh, width: it.w, height: it.h, fill: 'rgba(200,150,90,0.55)', stroke }));
      grp.appendChild(sv('path', { d: 'M ' + (-hw) + ' ' + hh + ' A ' + it.w + ' ' + it.w + ' 0 0 0 ' + hw + ' ' + (hh - it.w), fill: 'none', stroke: 'rgba(200,150,90,0.8)', 'stroke-dasharray': '4 4' })); }
    else grp.appendChild(sv('rect', { x: -hw, y: -hh, width: it.w, height: it.h, rx: it.k === 'car' || it.k === 'sofa' ? 8 : 3,
      fill: 'rgba(160,170,200,0.22)', stroke }));
    if (it.label) { const t = sv('text', { x: 0, y: 5 * U(), 'text-anchor': 'middle', 'font-size': 15 * U(), fill: 'rgba(255,255,255,0.9)', 'pointer-events': 'none' }); t.textContent = it.label; grp.appendChild(t); }
    if (active) makeDrag(grp, it, () => { S.dirtyPlan = true; }, { t: 'item', i: idx });
    else grp.setAttribute('opacity', '0.6');
    g.appendChild(grp);
  }

  function makeDrag(node, obj, onMove, selKey, keys) {
    if (!data.editable) return;
    node.style.cursor = 'grab';
    node.addEventListener('pointerdown', ev => {
      if (S.pen) return;
      ev.stopPropagation();
      const p = svgPoint(svg, ev);
      const kx = keys ? keys[0] : 'x', ky = keys ? keys[1] : 'y';
      dragging = { obj, kx, ky, dx: obj[kx] - p.x, dy: obj[ky] - p.y, onMove };
      S.sel = selKey; svg.setPointerCapture(ev.pointerId);
    });
  }

  // الـ svg نفسه بيتعمل مرة في كل تشغيل للمكوّن (عشان السحب يفضل ماسك فيه)،
  // واللي جواه بس هو اللي بيترسم تاني
  root.textContent = '';
  const barBox = el('div'); root.appendChild(barBox);
  const svg = sv('svg', {}); root.appendChild(svg);
  const capBox = el('div', 'cf-pl-bar'); root.appendChild(capBox);
  let stroke = null;
  svg.addEventListener('pointerdown', ev => {
    if (!data.editable) return;
    if (S.pen && S.mode === 'decor') { const p = svgPoint(svg, ev); stroke = { pts: [[Math.round(p.x), Math.round(p.y)]] }; P.strokes.push(stroke);
      svg.setPointerCapture(ev.pointerId); S.dirtyPlan = true; return; }
    if (!dragging && S.sel) { S.sel = null; draw(); }
  });
  svg.addEventListener('pointermove', ev => {
    const p = svgPoint(svg, ev);
    if (stroke) { const x = Math.max(0, Math.min(P.w, Math.round(p.x))), y = Math.max(0, Math.min(P.h, Math.round(p.y)));
      const last = stroke.pts[stroke.pts.length - 1];
      if (Math.abs(last[0] - x) + Math.abs(last[1] - y) > 4) { stroke.pts.push([x, y]); drawLive(); } return; }
    if (!dragging) return;
    const lo = dragging.obj.k ? 0 : -M;
    dragging.obj[dragging.kx] = Math.round(Math.max(lo, Math.min(P.w - lo, p.x + dragging.dx)));
    dragging.obj[dragging.ky] = Math.round(Math.max(lo, Math.min(P.h - lo, p.y + dragging.dy)));
    dragging.onMove(); drawLive();
  });
  const end = () => { if (stroke) { if (stroke.pts.length < 2) P.strokes.pop(); stroke = null; draw(); }
    if (dragging) { dragging = null; draw(); } };
  svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);

  function draw() {
    barBox.textContent = '';
    toolbar();
    drawSvg();
    capBox.textContent = '';
    capBox.appendChild(el('span', 'cap', S.mode === 'decor' ? L.hint_decor : L.hint_block));
  }

  function drawSvg() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute('viewBox', (-M) + ' ' + (-M) + ' ' + (P.w + 2 * M) + ' ' + (P.h + 2 * M));
    svg.appendChild(sv('rect', { x: 0, y: 0, width: P.w, height: P.h, fill: 'rgba(255,255,255,0.03)', stroke: 'rgba(255,255,255,0.8)', 'stroke-width': 4 }));
    for (let gx = 100; gx < P.w; gx += 100) svg.appendChild(sv('line', { x1: gx, y1: 0, x2: gx, y2: P.h, stroke: 'rgba(255,255,255,0.05)' }));
    for (let gy = 100; gy < P.h; gy += 100) svg.appendChild(sv('line', { x1: 0, y1: gy, x2: P.w, y2: gy, stroke: 'rgba(255,255,255,0.05)' }));
    const decor = sv('g', {}); svg.appendChild(decor);
    const decorActive = S.mode === 'decor' && data.can_edit_plan;
    P.items.forEach((it, i) => drawItem(decor, it, i, decorActive));
    P.strokes.forEach(s => decor.appendChild(sv('polyline', { points: s.pts.map(p => p.join(',')).join(' '), fill: 'none',
      stroke: 'rgba(255,255,255,' + (decorActive ? 0.8 : 0.45) + ')', 'stroke-width': 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })));
    const blockActive = S.mode === 'block';
    // الكاميرات
    B.cams.forEach(c => {
      const s = shotById(c.shot_id); if (!s) return;
      const on = data.active_shot === c.shot_id || (S.sel && S.sel.t === 'cam' && S.sel.id === c.shot_id);
      const fov = s.fov * Math.PI / 180, len = Math.max(P.w, P.h) * 0.35;
      const g = sv('g', { transform: 'translate(' + c.x + ' ' + c.y + ') rotate(' + c.r + ')', opacity: blockActive ? 1 : 0.5 });
      g.appendChild(sv('path', { d: 'M 0 0 L ' + (len * Math.cos(fov / 2)) + ' ' + (len * Math.sin(fov / 2)) + ' L ' + (len * Math.cos(fov / 2)) + ' ' + (-len * Math.sin(fov / 2)) + ' Z',
        fill: s.color, 'fill-opacity': on ? 0.28 : 0.12, stroke: s.color, 'stroke-opacity': 0.7 }));
      const u = U();
      g.appendChild(sv('rect', { x: -20 * u, y: -14 * u, width: 32 * u, height: 28 * u, rx: 5 * u, fill: s.color, stroke: on ? '#fff' : 'none', 'stroke-width': 2 * u }));
      g.appendChild(sv('path', { d: 'M ' + 12 * u + ' ' + -7 * u + ' L ' + 22 * u + ' ' + -14 * u + ' L ' + 22 * u + ' ' + 14 * u + ' L ' + 12 * u + ' ' + 7 * u + ' Z', fill: s.color }));
      svg.appendChild(g);
      const t = sv('text', { x: c.x, y: c.y + 6 * U(), 'text-anchor': 'middle', 'font-size': 17 * U(), 'font-weight': 700, fill: '#111', 'pointer-events': 'none' }); t.textContent = String(s.number);
      svg.appendChild(t);
      if (blockActive) makeDrag(g, c, () => { S.dirtyBl = true; }, { t: 'cam', id: c.shot_id });
    });
    // الشخصيات
    B.chars.forEach(c => {
      const info = charById(c.id); if (!info) return;
      const sel = S.sel && S.sel.t === 'char' && S.sel.id === c.id;
      if (c.tx != null) {
        svg.appendChild(sv('line', { x1: c.x, y1: c.y, x2: c.tx, y2: c.ty, stroke: info.color, 'stroke-width': 3 * U(), 'stroke-dasharray': (10 * U()) + ' ' + (8 * U()), opacity: 0.8 }));
        const head = sv('circle', { cx: c.tx, cy: c.ty, r: 11 * U(), fill: 'none', stroke: info.color, 'stroke-width': 3 * U() });
        svg.appendChild(head);
        if (blockActive) makeDrag(head, c, () => { S.dirtyBl = true; }, { t: 'char', id: c.id }, ['tx', 'ty']);
      }
      const g = sv('g', { transform: 'translate(' + c.x + ' ' + c.y + ')', opacity: blockActive ? 1 : 0.55 });
      const u = U();
      const face = sv('g', { transform: 'rotate(' + c.f + ')' });
      face.appendChild(sv('path', { d: 'M ' + 18 * u + ' ' + -9 * u + ' L ' + 33 * u + ' 0 L ' + 18 * u + ' ' + 9 * u + ' Z', fill: info.color }));
      g.appendChild(face);
      g.appendChild(sv('circle', { r: 17 * u, fill: info.color, stroke: sel ? '#fff' : 'rgba(0,0,0,0.4)', 'stroke-width': (sel ? 3 : 1.5) * u }));
      const n = sv('text', { y: 5 * u, 'text-anchor': 'middle', 'font-size': 15 * u, 'font-weight': 700, fill: '#111', 'pointer-events': 'none' }); n.textContent = info.short; g.appendChild(n);
      const nm = sv('text', { y: 40 * u, 'text-anchor': 'middle', 'font-size': 17 * u, fill: '#fff', 'paint-order': 'stroke', stroke: '#10131f', 'stroke-width': 4 * u, 'pointer-events': 'none' }); nm.textContent = info.name; g.appendChild(nm);
      svg.appendChild(g);
      if (blockActive) makeDrag(g, c, () => { S.dirtyBl = true; }, { t: 'char', id: c.id });
    });
  }
  // أثناء السحب: نرسم اللي جوه الـ SVG بس، مرة لكل فريم
  let pending = false;
  function drawLive() { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; drawSvg(); }); }
  draw();
}
"""

_script = None
_plan = None


def script_panel(data, key):
    global _script
    if _script is None:
        _script = st.components.v2.component("cf_decoupage_script", css=SCRIPT_CSS, js=SCRIPT_JS)
    return _script(data=data, key=key, on_pick_change=lambda: None)


def plan_editor(data, key):
    global _plan
    if _plan is None:
        _plan = st.components.v2.component("cf_decoupage_plan", css=PLAN_CSS, js=PLAN_JS)
    return _plan(data=data, key=key, on_save_change=lambda: None)
