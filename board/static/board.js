// جدول التصوير — سحب وإفلات، والحفظ بيحصل لوحده بعد كل حركة.
// كل النصوص اللي جاية من البيانات بتتحط بـ textContent، عمرها ما بتدخل innerHTML.
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const INT_EXT = { INT: "داخلي", EXT: "خارجي" };

  let projectId = null;
  let data = null;               // {scenes, days, unscheduled}
  let saveTimer = null;
  let sortables = [];

  // --- الشبكة ----------------------------------------------------------------
  async function api(method, path, body) {
    const opts = { method, headers: {}, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 401) { location.reload(); throw new Error("signed out"); }
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
    return json;
  }

  function status(text, error = false) {
    const s = $("#status");
    s.textContent = text;
    s.classList.toggle("status--error", error);
  }

  // --- البيانات ----------------------------------------------------------------
  async function load() {
    status("بيحمّل…");
    data = await api("GET", `api/board?project_id=${projectId}`);
    render();
    status("");
    if ($("#dood-panel").open) loadDood();
  }

  function layoutFromDom() {
    return [...document.querySelectorAll(".day[data-day-id]")].map(col => ({
      day_id: Number(col.dataset.dayId),
      scene_ids: [...col.querySelectorAll(".strip")].map(s => Number(s.dataset.sceneId)),
    }));
  }

  function scheduleSave() {
    status("بيحفظ…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        await api("PUT", "api/board", { project_id: projectId, days: layoutFromDom() });
        status("✓ اتحفظ");
        refreshStats();
        if ($("#dood-panel").open) loadDood();
      } catch (e) {
        status(`ماتحفظش: ${e.message} — بيرجّع آخر نسخة محفوظة`, true);
        await load();
      }
    }, 350);
  }

  // --- الرسم ------------------------------------------------------------------
  function stripClass(s) {
    return `strip strip--${s.int_ext === "EXT" ? "ext" : "int"}-${s.night ? "night" : "day"}`;
  }

  function stripNode(s) {
    const node = $("#tpl-strip").content.firstElementChild.cloneNode(true);
    node.className = stripClass(s);
    node.dataset.sceneId = s.id;
    $(".strip__no", node).textContent = s.label;
    $(".strip__place", node).textContent = s.location || "مكان غير محدد";
    const meta = [INT_EXT[s.int_ext] || s.int_ext, s.day_night].filter(Boolean);
    if (s.episode) meta.push(`حلقة ${s.episode}`);
    $(".strip__meta", node).textContent = meta.join(" · ");
    $(".strip__cast", node).textContent = s.cast.length ? `👥 ${s.cast.length}` : "";
    node.title = `مشهد ${s.label} — ${s.location || ""}\n${s.cast.map(c => c.name).join("، ") || "من غير شخصيات"}`;
    node.setAttribute("aria-label", `مشهد ${s.label}، ${s.location || ""}، ${meta.join("، ")}`);
    return node;
  }

  function column({ title, dayId = null, sceneIds, day = null }) {
    const col = el("section", dayId ? "day" : "day day--pool");
    if (dayId) col.dataset.dayId = dayId;
    const head = el("header", "day__head");
    const row = el("div", "day__row");
    row.append(el("h2", "day__title", title));
    if (dayId) {
      const del = el("button", "day__del", "×");
      del.type = "button";
      del.title = "امسح اليوم (مشاهده بترجع «مش متجدولة»)";
      del.setAttribute("aria-label", `امسح ${title}`);
      del.addEventListener("click", () => removeDay(dayId, title));
      row.append(del);
    }
    head.append(row);
    head.append(el("div", "day__stats"));
    head.append(el("div", "day__warn"));
    if (dayId) {
      const date = el("input", "day__date");
      date.type = "date";
      date.value = day.shoot_date || "";
      date.disabled = !data.can_edit;
      date.setAttribute("aria-label", `تاريخ ${title}`);
      date.addEventListener("change", () =>
        api("PATCH", `api/days/${dayId}`, { project_id: projectId, shoot_date: date.value, notes: day.notes })
          .then(() => status("✓ اتحفظ التاريخ")).catch(e => status(e.message, true)));
      head.append(date);
    }
    col.append(head);
    const list = el("ul", "day__list");
    sceneIds.forEach(id => data.scenes[id] && list.append(stripNode(data.scenes[id])));
    col.append(list);
    return col;
  }

  function render() {
    // مشاهدة فقط: الجدول بيتقري بس — السيرفر بيرفض أي تعديل برضو
    document.body.classList.toggle("readonly", !data.can_edit);
    sortables.forEach(s => s.destroy());
    sortables = [];
    const board = $("#board");
    board.replaceChildren();
    board.append(column({ title: "مش متجدولة", sceneIds: data.unscheduled }));
    data.days.forEach(d => board.append(column({ title: `اليوم ${d.day_number}`, dayId: d.id,
                                                 sceneIds: d.scene_ids, day: d })));
    board.querySelectorAll(".day__list").forEach(list => {
      sortables.push(new Sortable(list, {
        group: "board", animation: 120, direction: "vertical", disabled: !data.can_edit,
        ghostClass: "sortable-ghost", chosenClass: "sortable-chosen",
        onEnd: e => { if (e.from !== e.to || e.oldIndex !== e.newIndex) scheduleSave(); },
      }));
    });
    refreshStats();
  }

  function refreshStats() {
    let scheduled = 0;
    document.querySelectorAll(".day").forEach(col => {
      const strips = [...col.querySelectorAll(".strip")].map(n => data.scenes[n.dataset.sceneId]);
      const sites = new Set(strips.map(s => s.site));
      const cast = new Set(strips.flatMap(s => s.cast.map(c => c.id)));
      const hasNight = strips.some(s => s.night), hasDay = strips.some(s => !s.night);
      const pool = col.classList.contains("day--pool");
      if (!pool) scheduled += strips.length;
      $(".day__stats", col).textContent = strips.length
        ? `${strips.length} مشهد` + (pool ? "" : ` · ${sites.size} موقع · ${cast.size} ممثل`)
        : "";
      const warn = [];
      if (!pool && sites.size > 1) warn.push(`تنقّل بين ${sites.size} مواقع`);
      if (!pool && hasNight && hasDay) warn.push("نهار وليل في نفس اليوم");
      $(".day__warn", col).textContent = warn.join(" · ");
      const list = $(".day__list", col);
      let empty = $(".day__empty", col);
      if (!strips.length && !empty) {
        empty = el("li", "day__empty", pool ? "كل المشاهد اتجدولت" : "اسحب مشاهد هنا");
        list.append(empty);
      } else if (strips.length && empty) empty.remove();
    });
    const total = Object.keys(data.scenes).length;
    const s = $("#summary");
    s.replaceChildren();
    const b1 = el("strong", null, String(data.days.length)), b2 = el("strong", null, String(scheduled));
    s.append(b1, " يوم تصوير · ", b2, ` مشهد متجدول من ${total}`,
             total - scheduled ? ` · ${total - scheduled} لسه` : " · كل المشاهد اتجدولت");
  }

  // --- أفعال -------------------------------------------------------------------
  async function removeDay(dayId, title) {
    if (!confirm(`تمسح ${title}؟ المشاهد اللي فيه هترجع «مش متجدولة».`)) return;
    try {
      await api("DELETE", `api/days/${dayId}`, { project_id: projectId });
      await load();
      status(`✓ ${title} اتمسح`);
    } catch (e) { status(e.message, true); }
  }

  $("#add-day").addEventListener("click", async () => {
    try {
      const r = await api("POST", "api/days", { project_id: projectId });
      await load();
      status(`✓ اليوم ${r.day_number} اتضاف`);
      $("#board").scrollTo({ left: -$("#board").scrollWidth });
    } catch (e) { status(e.message, true); }
  });

  $("#suggest").addEventListener("click", async () => {
    const perDay = Number($("#per-day").value) || 8;
    const sitesPerDay = Number($("#sites-per-day").value) || 2;
    if (data.days.length &&
        !confirm(`ده هيمسح الـ ${data.days.length} يوم الحاليين ويعمل جدول جديد من الأول. تكمل؟`)) return;
    try {
      status("بيقترح…");
      const r = await api("POST", "api/suggest", { project_id: projectId, per_day: perDay, sites_per_day: sitesPerDay });
      await load();
      status(`✓ اتعمل ${r.days} يوم — نهار أو ليل، لحد ${sitesPerDay} موقع في نفس المدينة. عدّل بالسحب.`);
    } catch (e) { status(e.message, true); }
  });

  // تحريك بالكيبورد: مشهد مختار + Alt + سهم = ينقل لليوم اللي جنبه.
  document.addEventListener("keydown", e => {
    const strip = document.activeElement;
    if (!e.altKey || !strip?.classList?.contains("strip")) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const cols = [...document.querySelectorAll(".day")];
    const i = cols.indexOf(strip.closest(".day"));
    // RTL: اليوم اللي بعده على الشمال
    const j = e.key === "ArrowLeft" ? i + 1 : i - 1;
    if (j < 0 || j >= cols.length) return;
    e.preventDefault();
    $(".day__list", cols[j]).append(strip);
    strip.focus();
    scheduleSave();
  });

  // --- أيام شغل الممثلين --------------------------------------------------------
  async function loadDood() {
    const d = await api("GET", `api/dood?project_id=${projectId}`);
    const wrap = $("#dood");
    wrap.replaceChildren();
    if (!d.rows.length) { wrap.append(el("p", "hint", "لسه مفيش أيام فيها ممثلين.")); return; }
    const table = el("table");
    const head = el("tr");
    head.append(el("th", null, "الشخصية"));
    d.days.forEach(n => head.append(el("th", null, String(n))));
    head.append(el("th", null, "شغل"), el("th", null, "انتظار"));
    table.append(head);
    d.rows.forEach(r => {
      const tr = el("tr");
      tr.append(el("td", null, r.name));
      r.codes.forEach(c => tr.append(el("td", c ? `c-${c}` : null, c)));
      tr.append(el("td", null, String(r.work_days)), el("td", null, String(r.hold_days)));
      table.append(tr);
    });
    wrap.append(table);
  }
  $("#dood-panel").addEventListener("toggle", e => { if (e.target.open) loadDood(); });

  // --- البداية -------------------------------------------------------------------
  const picker = $("#project");
  const wanted = new URLSearchParams(location.search).get("project") || localStorage.getItem("cf-board-project");
  if (wanted && [...picker.options].some(o => o.value === wanted)) picker.value = wanted;
  projectId = Number(picker.value);
  picker.addEventListener("change", () => {
    projectId = Number(picker.value);
    localStorage.setItem("cf-board-project", picker.value);
    load().catch(e => status(e.message, true));
  });
  if (projectId) load().catch(e => status(e.message, true));
  else status("مفيش مشاريع لسه", true);
})();
