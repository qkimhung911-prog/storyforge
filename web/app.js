/* Phần dùng chung của các trang app: đọc Supabase (chỉ đọc) và dựng khung trang. */
(function () {
  const cfg = window.STORYFORGE || {};

  const STEPS = [
    { id: 'kich-ban', label: 'Kịch bản' },
    { id: 'bible', label: 'Bible' },
    { id: 'storyboard', label: 'Storyboard' },
    { id: 'tien-trinh', label: 'Tiến trình' },
    { id: 'timeline', label: 'Timeline' },
  ];
  const AVAILABLE = new Set(['bible', 'storyboard', 'timeline']);

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const configured = () => !!(cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY && !cfg.SUPABASE_ANON_KEY.startsWith('DAN_'));

  async function query(path) {
    const headers = { apikey: cfg.SUPABASE_ANON_KEY };
    if (cfg.SUPABASE_ANON_KEY.startsWith('eyJ')) headers.Authorization = `Bearer ${cfg.SUPABASE_ANON_KEY}`;
    const res = await fetch(`${cfg.SUPABASE_URL}/rest/v1/${path}`, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.message || `Lỗi ${res.status}`);
    }
    return res.json();
  }

  async function loadProject() {
    const id = new URLSearchParams(location.search).get('project');
    const rows = await query(id
      ? `projects?id=eq.${encodeURIComponent(id)}&select=*`
      : 'projects?select=*&order=created_at.desc&limit=1');
    if (!rows.length) throw new Error('Chưa có project nào trong Supabase.');
    return rows[0];
  }

  function statusBadge(status) {
    const map = { pending: ['Chờ duyệt', 'pending'], approved: ['Đã duyệt', 'approved'], failed: ['Lỗi', 'failed'] };
    const [label, cls] = map[status] || [status, 'pending'];
    return `<span class="badge ${cls}"><i></i>${esc(label)}</span>`;
  }

  function heroHtml({ active, step, title, sub }) {
    const nav = STEPS.map((s) => {
      const on = s.id === active;
      const done = STEPS.findIndex((x) => x.id === active) > STEPS.indexOf(s);
      const text = `${done ? '✓ ' : ''}${s.label}`;
      if (on) return `<span class="pill on" aria-current="page">${text}</span>`;
      if (AVAILABLE.has(s.id)) return `<a class="pill" href="${s.id}.html${location.search}">${text}</a>`;
      return `<span class="pill off" title="Sắp có">${text}</span>`;
    }).join('');
    return `
      <div class="app-bg" aria-hidden="true"></div>
      <div class="topbar">
        <a class="logo" href="./" aria-label="StoryForge, trang chủ">
          <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="7" fill="#111"/><path d="M9.5 7.5v9l7-4.5z" fill="#fff"/></svg>
          StoryForge
        </a>
        <nav class="steps mono" aria-label="5 bước">${nav}</nav>
        <span class="badge-mock mono">Chế độ mock · $0.00</span>
      </div>
      <div class="page-hero">
        <div class="mono eyebrow">Bước ${step} / 5</div>
        <h1>${title}</h1>
        <p>${sub}</p>
      </div>`;
  }

  async function boot(opts, render) {
    document.getElementById('hero').innerHTML = heroHtml(opts);
    document.title = `${opts.pageTitle} | StoryForge`;
    const root = document.getElementById('content');
    if (!configured()) {
      root.innerHTML = '<div class="card note-box">Chưa có <code>web/config.js</code> hoặc chưa điền khóa công khai Supabase.</div>';
      return;
    }
    try {
      const project = await loadProject();
      await render(project, root);
    } catch (e) {
      root.innerHTML = `<div class="card note-box err">Không tải được dữ liệu: ${esc(e.message)}</div>`;
    }
  }

  window.SF = { esc, query, boot, statusBadge };
})();
