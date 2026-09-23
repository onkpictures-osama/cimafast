// الصفحة الرئيسية: البحث في كل المشاريع، ومشروع جديد. النصوص اللي جاية من البيانات
// بتتحط بـ textContent بس.
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const API = "../board/api/";

  // --- البحث ---
  const q = $("#q"), results = $("#results");
  let timer = null, seq = 0;
  const hide = () => { results.hidden = true; results.replaceChildren(); };
  q.addEventListener("input", () => {
    clearTimeout(timer);
    const text = q.value.trim();
    if (text.length < 2) return hide();
    timer = setTimeout(async () => {
      const mine = ++seq;
      const res = await fetch(`${API}search?q=${encodeURIComponent(text)}`, { credentials: "same-origin" });
      if (mine !== seq) return;                 // a newer query already went out
      const data = await res.json().catch(() => ({ results: [] }));
      const items = (data.results || []).map((r) => {
        const li = document.createElement("li"), a = document.createElement("a");
        a.href = r.href;
        const k = document.createElement("span"); k.className = "kind"; k.textContent = r.kind;
        const l = document.createElement("span"); l.textContent = r.label;
        const p = document.createElement("span"); p.className = "proj"; p.textContent = r.project;
        a.append(k, l, p); li.append(a); return li;
      });
      if (!items.length) {
        const li = document.createElement("li"); li.className = "muted"; li.style.padding = "8px 10px";
        li.textContent = "مفيش نتايج"; items.push(li);
      }
      results.replaceChildren(...items); results.hidden = false;
    }, 220);
  });
  q.addEventListener("keydown", (e) => { if (e.key === "Escape") { q.value = ""; hide(); } });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search")) hide(); });

  // --- مشروع جديد ---
  const toggle = $("#new-toggle"), form = $("#new-project");
  toggle?.addEventListener("click", () => {
    form.hidden = !form.hidden;
    toggle.setAttribute("aria-expanded", String(!form.hidden));
    if (!form.hidden) form.querySelector("[name=name]").focus();
  });
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = $("#new-status");
    const body = Object.fromEntries(new FormData(form).entries());
    status.textContent = "بينشئ…";
    const res = await fetch(`${API}projects`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { status.textContent = data.error || `خطأ ${res.status}`; status.classList.add("status--error"); return; }
    location.href = data.href;                  // straight to "add screenplay" for the new project
  });

  // --- H4: جرس التنبيهات ---
  // بيسأل كل ٣٠ ثانية عشان التغيير يوصل من غير refresh. فتح اللوحة = "شفتهم".
  const nBtn = $("#notif-btn"), nPanel = $("#notif-panel"), nList = $("#notif-list"), nCount = $("#notif-count");
  if (nBtn) {
    let latest = 0;
    const showCount = (n) => {
      nCount.hidden = !n;
      nCount.textContent = n > 99 ? "99+" : String(n || "");
      nBtn.setAttribute("aria-label", n ? `التنبيهات: ${n} جديد` : "التنبيهات");
    };
    const render = (data) => {
      latest = data.latest_id || 0;
      showCount(data.unread || 0);
      const items = (data.items || []).map((it) => {
        const li = document.createElement("li"), a = document.createElement("a");
        a.href = it.href; if (it.unread) a.className = "is-new";
        const t = document.createElement("span"); t.className = "notif__text"; t.textContent = it.text;
        const m = document.createElement("span"); m.className = "notif__meta";
        m.textContent = [it.who, it.project, it.ago].filter(Boolean).join(" · ");
        a.append(t, m); li.append(a); return li;
      });
      if (!items.length) {
        const li = document.createElement("li"); li.className = "muted"; li.style.padding = "8px 10px";
        li.textContent = "مفيش تغييرات جديدة في مشاريعك آخر أسبوعين."; items.push(li);
      }
      nList.replaceChildren(...items);
    };
    const load = async () => {
      try {
        const res = await fetch(`${API}notifications`, { credentials: "same-origin" });
        if (res.ok) render(await res.json());
      } catch (_) { /* الشبكة وقعت: نجرّب تاني بعد ٣٠ ثانية */ }
    };
    const close = () => { nPanel.hidden = true; nBtn.setAttribute("aria-expanded", "false"); };
    nBtn.addEventListener("click", async () => {
      if (!nPanel.hidden) return close();
      nPanel.hidden = false; nBtn.setAttribute("aria-expanded", "true");
      if (!latest) return;
      try {
        const res = await fetch(`${API}notifications/seen`, {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ up_to: latest }) });
        if (res.ok) showCount((await res.json()).unread || 0);
      } catch (_) { /* مش مهم: هتتعلّم مقروءة المرة الجاية */ }
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".notif")) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !nPanel.hidden) { close(); nBtn.focus(); } });
    load();
    setInterval(load, 30000);
  }
})();
