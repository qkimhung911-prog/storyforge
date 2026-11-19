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
  const AVAILABLE = new Set(['kich-ban', 'bible', 'storyboard', 'tien-trinh', 'timeline']);

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

  // Tiêu đề vùng: dải màu đặc (biểu tượng, tên, nhiệm vụ, số lượng), cùng ngôn ngữ với Canvas và demo trang chủ.
  const ZICON = {
    char: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    prop: '<path d="M12 3l8 6-8 12L4 9z"/><path d="M4 9h16"/>',
    loc: '<path d="M3 19l6-9 4 6 3-4 5 7z"/><circle cx="17" cy="7" r="2"/>',
    shot: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M8 5v14M16 5v14"/>',
    film: '<circle cx="12" cy="12" r="9"/><path d="M10 8.5v7l6-3.5z"/>',
  };
  function zoneHead(kind, title, sub, count) {
    return `<div class="zhead" style="--zc:var(--c-${kind})"><span class="zi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ZICON[kind]}</svg></span><span class="zt"><b>${esc(title)}</b>${sub ? `<i>${esc(sub)}</i>` : ''}</span>${count !== undefined && count !== null ? `<em>${esc(count)}</em>` : ''}</div>`;
  }

  // Thanh điều hướng bên trái dùng chung (cả trang Canvas): mỗi mục một biểu tượng và nhãn ngắn.
  const NAV = [
    { id: 'kich-ban', label: 'Kịch bản', ic: '<path d="M6 3h9l4 4v14H6z"/><path d="M9 12h7M9 16h7"/>' },
    { id: 'bible', label: 'Bible', ic: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>' },
    { id: 'storyboard', label: 'Storyboard', ic: '<rect x="3" y="4" width="8" height="7" rx="1.5"/><rect x="13" y="4" width="8" height="7" rx="1.5"/><rect x="3" y="13" width="8" height="7" rx="1.5"/><rect x="13" y="13" width="8" height="7" rx="1.5"/>' },
    { id: 'canvas', label: 'Canvas', ic: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="12" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8.5 6h4a3 3 0 0 1 3 3v1M8.5 18h4a3 3 0 0 0 3-3v-1"/>' },
    { id: 'goi-shot', label: 'Gói shot', ic: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M8 6l2-3h4l2 3"/>' },
    { id: 'tien-trinh', label: 'Tiến trình', ic: '<path d="M4 12h4l3-7 4 14 3-7h2"/>' },
    { id: 'timeline', label: 'Timeline', ic: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M8 5v14"/>' },
  ];

  function railHtml(active) {
    const items = NAV.map((n) => `<a class="${n.id === active ? 'on' : ''}" href="${n.id}.html${location.search}" title="${n.label}" ${n.id === active ? 'aria-current="page"' : ''}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${n.ic}</svg>${n.label}</a>`).join('');
    return `<nav class="rail" aria-label="Điều hướng"><a class="logo" href="./" aria-label="StoryForge, trang chủ" title="Trang chủ"></a>${items}</nav>`;
  }

  function heroHtml({ active, step, title, sub }) {
    return `
      ${railHtml(active)}
      <div class="apphead">
        <div class="ah-main">
          <div class="mono eyebrow">${step ? `Bước ${step} / 5` : 'StoryForge'}</div>
          <h1>${title}</h1>
          <p>${sub}</p>
        </div>
        <span class="badge-mock mono">Chế độ mock · $0.00</span>
      </div>`;
  }

  async function boot(opts, render) {
    document.body.classList.add('app');
    document.getElementById('hero').innerHTML = heroHtml(opts);
    document.title = `${opts.pageTitle} | StoryForge`;
    const root = document.getElementById('content');
    if (opts.noProject) { await render(null, root); return; }
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

  window.SF = { esc, query, boot, statusBadge, railHtml, zoneHead };
})();
