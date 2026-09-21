// سجل النشاط (F3). كل الفلترة والصلاحيات على السيرفر (audit.py) — الصفحة دي
// بتعرض اللي السيرفر بيرجّعه بس، فمفيش شركة تانية ممكن تظهر هنا مهما اتعبت بالـ URL.
(() => {
  const $ = (s) => document.querySelector(s);
  const status = $("#status");
  const companySel = $("#company");
  const filters = $("#filters");
  if (!filters) return;                       // شاشة "مش مسموح"

  const say = (msg, isError = false) => {
    status.textContent = msg;
    status.classList.toggle("status--error", isError);
  };

  const companyId = () => (companySel ? Number(companySel.value) : null);

  async function get(url, params) {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== ""));
    const res = await fetch(`${url}?${q}`, { headers: { Accept: "application/json" } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `خطأ ${res.status}`);
    return data;
  }

  const when = (iso) =>
    iso ? new Date(iso).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" }) : "—";

  // الحركات اللي المفروض العين تقع عليها الأول
  const ALERT = new Set(["delete", "login_failed", "role_change", "member_remove", "password_reset"]);
  const AUTH = new Set(["login", "logout", "password_change"]);

  function details(raw) {
    if (!raw) return document.createTextNode("—");
    let data;
    try { data = JSON.parse(raw); } catch { return document.createTextNode(raw); }
    const box = document.createElement("details");
    box.className = "changes";
    const head = document.createElement("summary");
    const changed = data.changed || {};
    const keys = Object.keys(changed);
    head.textContent = keys.length ? `${keys.length} حقل اتغيّر` : "التفاصيل";
    box.append(head);
    const dl = document.createElement("dl");
    const put = (label, node) => {
      const dt = document.createElement("dt"); dt.textContent = label;
      const dd = document.createElement("dd"); dd.append(node);
      dl.append(dt, dd);
    };
    for (const [field, pair] of Object.entries(changed)) {
      const line = document.createElement("span");
      const from = document.createElement("span");
      from.className = "from"; from.textContent = String(pair.from ?? "—");
      const to = document.createElement("span");
      to.className = "to"; to.textContent = String(pair.to ?? "—");
      line.append(from, " ← ", to);
      put(field, line);
    }
    for (const [key, value] of Object.entries(data)) {
      if (key === "changed") continue;
      const text = typeof value === "object" && value !== null
        ? Object.entries(value).map(([k, v]) => `${k}: ${v}`).join("، ")
        : String(value);
      put(key === "new" ? "القيم" : key === "old" ? "كان" : key, document.createTextNode(text));
    }
    box.append(dl);
    return box;
  }

  function fillSelect(select, values, labels) {
    const current = select.value;
    select.innerHTML = '<option value="">الكل</option>';
    for (const v of values) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = (labels && labels[v]) || v;
      select.append(opt);
    }
    if (values.includes(current)) select.value = current;
  }

  async function loadEntries() {
    const form = new FormData(filters);
    const data = await get("../api/activity", {
      company_id: companyId(),
      user: form.get("user"), entity: form.get("entity"),
      action: form.get("action"), q: form.get("q"),
    });
    fillSelect(filters.elements.user, data.filters.users);
    fillSelect(filters.elements.entity, data.filters.entities, data.entity_labels);
    fillSelect(filters.elements.action, data.filters.actions, data.action_labels);

    const body = $("#rows");
    body.textContent = "";
    for (const r of data.rows) {
      const tr = document.createElement("tr");
      const td = (node) => {
        const cell = document.createElement("td");
        cell.append(node instanceof Node ? node : document.createTextNode(node ?? "—"));
        tr.append(cell);
        return cell;
      };
      td(when(r.at)).className = "when";
      td(r.username || "النظام");
      const what = document.createElement("span");
      what.textContent = r.summary
        || `${data.action_labels[r.action] || r.action} — ${data.entity_labels[r.entity] || r.entity}`;
      if (ALERT.has(r.action)) what.className = "what--alert";
      else if (AUTH.has(r.action)) what.className = "what--auth";
      td(what);
      td(r.project_name || "—");
      td(details(r.changes));
      body.append(tr);
    }
    $("#empty").hidden = data.rows.length > 0;
    say(data.rows.length ? `${data.rows.length} حركة` : "");
  }

  async function loadUsage() {
    const days = Number($("#days").value);
    const data = await get("../api/usage", { company_id: companyId(), days });
    $("#usage-head").textContent =
      `${data.active_users} مستخدم نشط في آخر ${data.days} يوم`;
    const body = $("#usage");
    body.textContent = "";
    for (const r of data.rows) {
      const tr = document.createElement("tr");
      const target = r.target ? data.target_labels[r.target] || r.target : "—";
      for (const value of [data.event_labels[r.event] || r.event, target, r.times, r.people]) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      }
      body.append(tr);
    }
  }

  async function refresh() {
    try {
      await Promise.all([loadEntries(), loadUsage()]);
    } catch (e) {
      say(e.message, true);
    }
  }

  filters.addEventListener("submit", (e) => { e.preventDefault(); refresh(); });
  filters.addEventListener("change", () => refresh());
  $("#days").addEventListener("change", () => loadUsage().catch((e) => say(e.message, true)));
  if (companySel) companySel.addEventListener("change", refresh);

  // ?company_id= من الشريط الجانبي في التطبيق
  const wanted = new URLSearchParams(location.search).get("company_id");
  if (wanted && companySel && [...companySel.options].some((o) => o.value === wanted)) {
    companySel.value = wanted;
  }
  refresh();
})();
