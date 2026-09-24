// صفحة الفريق. كل الصلاحيات بتتحقق على السيرفر (accounts.py)؛ هنا بنخبّي الأزرار
// اللي مش ليك بس عشان الصفحة تبقى نضيفة.
(() => {
  const $ = (s) => document.querySelector(s);
  const status = $("#status");
  const companySel = $("#company");
  const labels = Object.fromEntries(window.ROLE_LABELS);
  labels.operator = "مشغّل المنصة";

  const say = (msg, isError = false) => {
    status.textContent = msg;
    status.classList.toggle("status--error", isError);
  };

  async function call(method, url, body) {
    const res = await fetch(url, {
      method, headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `خطأ ${res.status}`);
    return data;
  }

  const companyId = () => (companySel ? Number(companySel.value) : null);

  function showSecret(username, pw) {
    if (!pw) return;
    $("#secret-user").textContent = username;
    $("#secret-pw").textContent = pw;
    $("#secret").hidden = false;
    $("#secret").scrollIntoView({ behavior: "smooth" });
  }
  $("#secret-close").addEventListener("click", () => {
    $("#secret").hidden = true;
    $("#secret-pw").textContent = "";
  });
  $("#secret-copy").addEventListener("click", () =>
    navigator.clipboard?.writeText($("#secret-pw").textContent).then(() => say("اتنسخت")));

  const when = (iso) => (iso ? new Date(iso).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" }) : "—");

  function row(m, isAdmin, me) {
    const tr = document.createElement("tr");
    const active = m.active && m.user_active;
    if (!active) tr.className = "inactive";
    const td = (text) => { const c = document.createElement("td"); c.textContent = text ?? ""; tr.append(c); return c; };
    const name = td(m.display_name || m.username);
    if (m.username === me) { const t = document.createElement("span"); t.className = "tag"; t.textContent = "انت"; name.append(t); }
    td(m.username).dir = "ltr";
    td(m.job_title || "—");
    const roleCell = td("");
    if (isAdmin && active && m.username !== me) {
      const sel = document.createElement("select");
      sel.innerHTML = $("#role-options").innerHTML;
      sel.value = m.role;
      sel.setAttribute("aria-label", `دور ${m.username}`);
      sel.addEventListener("change", async () => {
        try { await call("PATCH", `../api/team/members/${encodeURIComponent(m.username)}`, { company_id: companyId(), role: sel.value }); say("الدور اتغيّر"); }
        catch (e) { say(e.message, true); sel.value = m.role; }
      });
      roleCell.append(sel);
    } else {
      roleCell.textContent = labels[m.role] || m.role;
    }
    td(active ? when(m.last_login_at) : "اتشال من المشروع");
    if (isAdmin) {
      const cell = td("");
      if (m.username !== me) {
        const acts = document.createElement("div");
        acts.className = "actions";
        const btn = (text, cls, fn) => { const b = document.createElement("button"); b.className = `btn ${cls}`; b.textContent = text; b.addEventListener("click", fn); acts.append(b); };
        if (active) {
          btn("كلمة سر جديدة", "", async () => {
            if (!confirm(`كلمة سر مؤقتة جديدة لـ ${m.username}؟ القديمة هتبطل تشتغل.`)) return;
            try { const r = await call("POST", `../api/team/members/${encodeURIComponent(m.username)}/reset`, { company_id: companyId() }); showSecret(m.username, r.temp_password); }
            catch (e) { say(e.message, true); }
          });
          btn("شيل من المشروع", "btn--danger", async () => {
            if (!confirm(`تشيل ${m.username} من المشروع؟ هيبطل يشوف المشاريع. تقدر ترجّعه بعدين.`)) return;
            try { await call("DELETE", `../api/team/members/${encodeURIComponent(m.username)}`, { company_id: companyId() }); say("اتشال"); load(); }
            catch (e) { say(e.message, true); }
          });
        } else {
          btn("رجّعه", "", async () => {
            try { await call("POST", "../api/team/members", { company_id: companyId(), username: m.username, role: m.role }); say("رجع للفريق"); load(); }
            catch (e) { say(e.message, true); }
          });
        }
        cell.append(acts);
      }
    }
    return tr;
  }

  async function load() {
    if (!companySel) return;
    say("بيحمّل…");
    try {
      const data = await call("GET", `../api/team?company_id=${companyId()}`);
      const isAdmin = data.role === "admin" || data.role === "operator";
      document.querySelectorAll(".admin-only").forEach((el) => { el.hidden = !isAdmin; });
      $("#not-admin").hidden = isAdmin;
      $("#rename [name=name]").value = companySel.selectedOptions[0].textContent;
      const body = $("#members");
      body.replaceChildren(...data.members.map((m) => row(m, isAdmin, data.me)));
      say(`${data.members.filter((m) => m.active && m.user_active).length} في الفريق`);
    } catch (e) { say(e.message, true); }
  }

  const formData = (form) => Object.fromEntries(new FormData(form).entries());

  $("#add")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const d = formData(ev.target);
    try {
      const r = await call("POST", "../api/team/members", { ...d, company_id: companyId() });
      ev.target.reset();
      if (r.temp_password) showSecret(d.username, r.temp_password);
      else say(`${d.username} عنده حساب بالفعل — اتضاف للمشروع بكلمة سره الحالية`);
      load();
    } catch (e) { say(e.message, true); }
  });

  $("#rename")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = formData(ev.target).name;
    try {
      await call("POST", "../api/companies/rename", { company_id: companyId(), name });
      companySel.selectedOptions[0].textContent = name;
      say("اسم الشركة اتغيّر");
    } catch (e) { say(e.message, true); }
  });

  $("#new-company")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const d = formData(ev.target);
    try {
      const r = await call("POST", "../api/companies", d);
      ev.target.reset();
      if (companySel) {
        companySel.append(new Option(d.name, r.company_id));
        companySel.value = String(r.company_id);
        load();
      }
      if (r.temp_password) showSecret(d.admin_username, r.temp_password);
      else say(`الشركة اتعملت، و${d.admin_username} مديرها بكلمة سره الحالية`);
    } catch (e) { say(e.message, true); }
  });

  $("#my-password").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await call("POST", "../api/me/password", formData(ev.target)); ev.target.reset(); say("كلمة السر اتغيّرت"); }
    catch (e) { say(e.message, true); }
  });

  companySel?.addEventListener("change", load);
  load();
})();
