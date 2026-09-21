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
})();
