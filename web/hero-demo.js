// Hero demo của Landing: một cửa sổ Canvas chạy vòng lặp 5 nhịp, mỗi chuyển động có nguyên nhân (con trỏ).
// Nhịp: 1 dán kịch bản, 2 tách tài sản, 3 chọn một shot, 4 có clip, 5 ghép phim, rồi quay về đầu.
(function () {
  const root = document.getElementById('demo');
  if (!root) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const SHOTS = [
    { id: '1-1', label: 'Shot 1.1 · wide', clip: false },
    { id: '1-2', label: 'Shot 1.2 · close-up', clip: true },
    { id: '2-1', label: 'Shot 2.1 · medium', clip: true },
    { id: '2-2', label: 'Shot 2.2 · insert', clip: true },
    { id: '2-3', label: 'Shot 2.3 · two-shot', clip: false },
  ];
  const IMG = 'demo/';
  const SCRIPT = 'CẢNH 1 · NỘI. QUÁN CÀ PHÊ · ĐÊM\n\nLan bước vào quán, áo còn ướt.\nLAN: “Anh vẫn đến đúng giờ.”\nMINH: “Anh chờ em từ lúc trời bắt đầu mưa.”';

  const shotHtml = (s, i) => `
    <div class="dn n-shot" id="d-s${s.id}" style="left:${36 + i * 162}px;top:368px">
      <div class="perf"></div>
      <div class="ph"><img src="${IMG}still-s${s.id}.jpg" alt="">${s.clip ? `<img class="clip" src="${IMG}clip-${s.id}.jpg" alt=""><span class="bd">CLIP</span>` : ''}</div>
      <div class="pg"><b></b></div><h5>${s.label}</h5>
    </div>`;

  root.innerHTML = `
  <div class="demo-stage" id="d-stage">
    <div class="win">
      <div class="tb"><i></i><i></i><i></i><span class="url">storyforge · canvas · Đêm Mưa</span></div>
      <nav class="rl" aria-hidden="true"><b></b><b></b><b class="on"></b><b></b><b></b></nav>
      <div class="cv"><div class="world" id="d-world">
        <svg class="de" id="d-edges" aria-hidden="true"></svg>

        <div class="dn n-script in" id="d-script" style="left:22px;top:22px">
          <div class="tg"><span>Kịch bản</span><span>Đêm Mưa</span></div>
          <div class="tx" id="d-tx"></div>
          <button type="button" id="d-analyze" tabindex="-1">Phân tích ↗</button>
        </div>

        <div class="dz z-char" id="z-char" style="left:280px;top:14px;width:278px;height:254px"><div class="zh">Nhân vật<em>2</em></div></div>
        <div class="dn n-char" id="d-minh" style="left:294px;top:62px"><div class="tg"><span>Nhân vật</span></div><img src="${IMG}minh.jpg" alt=""><h5>Minh</h5><p>Nam · 30 tuổi</p></div>
        <div class="dn n-char" id="d-lan" style="left:426px;top:62px"><div class="tg"><span>Nhân vật</span></div><img src="${IMG}lan.jpg" alt=""><h5>Lan</h5><p>Nữ · 28 tuổi</p></div>

        <div class="dz z-prop" id="z-prop" style="left:578px;top:14px;width:160px;height:254px"><div class="zh">Phụ kiện<em>1</em></div></div>
        <div class="dn n-prop" id="d-prop" style="left:594px;top:100px"><span class="ring"></span><div><h5>Vòng tay bạc</h5><p>của Lan</p></div></div>

        <div class="dz z-loc" id="z-loc" style="left:758px;top:14px;width:238px;height:254px"><div class="zh">Bối cảnh<em>1</em></div></div>
        <div class="dn n-loc" id="d-loc" style="left:772px;top:62px"><div class="tg"><span>Bối cảnh</span></div><img src="${IMG}still-s1-1.jpg" alt=""><h5>Quán Cà Phê</h5><p>đèn vàng ấm, cửa sổ nhìn ra mưa</p></div>

        <div class="dz z-shot" id="z-shot" style="left:22px;top:322px;width:826px;height:190px"><div class="zh">Shot<em>5</em></div></div>
        ${SHOTS.map(shotHtml).join('')}

        <div class="dz z-film" id="z-film" style="left:866px;top:322px;width:172px;height:190px"><div class="zh">Phim</div></div>
        <div class="dn n-film" id="d-film" style="left:883px;top:368px">
          <div style="position:relative"><img src="${IMG}still-s2-3.jpg" alt=""><span class="play"></span></div>
          <button type="button" id="d-assemble" tabindex="-1">Ghép thành phim</button>
        </div>
      </div></div>
    </div>

    <aside class="dpanel" id="d-panel" aria-hidden="true">
      <div class="k"><span>Shot 1.2 · close-up</span><span>16:9</span></div>
      <h4>Minh quay lại nhìn Lan</h4>
      <div class="ph"><img src="${IMG}still-s1-2.jpg" alt=""><img class="clip" src="${IMG}clip-1-2.jpg" alt=""></div>
      <div class="say">MINH: “Anh chờ em từ lúc trời bắt đầu mưa.”</div>
      <div class="ln w1"></div><div class="ln w2"></div>
      <div class="at"><span>Đính kèm</span><img src="${IMG}minh.jpg" alt=""><img src="${IMG}still-s1-1.jpg" alt=""></div>
      <div class="up">Tải clip lên</div>
    </aside>

    <div class="dcursor" id="d-cursor" aria-hidden="true">
      <span class="rg"></span>
      <svg viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.6L9.8 19z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>
    </div>
  </div>`;

  const $ = (id) => document.getElementById(id);
  const stage = $('d-stage'), world = $('d-world'), edges = $('d-edges'), cursor = $('d-cursor'), panel = $('d-panel');
  const nodes = [...root.querySelectorAll('.dn')];
  const scale = () => parseFloat(getComputedStyle(root).getPropertyValue('--s')) || 1;

  // ---- Thu phóng theo bề ngang ----
  const fitStage = () => root.style.setProperty('--s', String(root.clientWidth / 1120));
  fitStage();
  if (window.ResizeObserver) new ResizeObserver(fitStage).observe(root); else window.addEventListener('resize', fitStage);

  // ---- Đường nối ----
  const link = (a, b, horizontal) => ({ a, b, h: !!horizontal });
  const EDGES = [
    link('d-lan', 'd-s1-1'), link('d-minh', 'd-s1-2'), link('d-loc', 'd-s1-2'),
    link('d-lan', 'd-s2-1'), link('d-minh', 'd-s2-1'), link('d-prop', 'd-s2-2'),
    link('d-lan', 'd-s2-3'), link('d-minh', 'd-s2-3'),
    ...SHOTS.map((s) => link('d-s' + s.id, 'd-film', true)),
  ];
  function pathOf(e) {
    const A = $(e.a), B = $(e.b);
    if (e.h) {
      const x1 = A.offsetLeft + A.offsetWidth, y1 = A.offsetTop + A.offsetHeight / 2, x2 = B.offsetLeft, y2 = B.offsetTop + 100, d = Math.max(20, (x2 - x1) / 2);
      return `M${x1},${y1} C${x1 + d},${y1} ${x2 - d},${y2} ${x2},${y2}`;
    }
    const x1 = A.offsetLeft + A.offsetWidth / 2, y1 = A.offsetTop + A.offsetHeight, x2 = B.offsetLeft + B.offsetWidth / 2, y2 = B.offsetTop, d = (y2 - y1) / 2;
    return `M${x1},${y1} C${x1},${y1 + d} ${x2},${y2 - d} ${x2},${y2}`;
  }
  EDGES.forEach((e) => {
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', pathOf(e));
    e.el = p; edges.appendChild(p);
  });

  // ---- Công cụ diễn ----
  let gen = 0;
  const sleep = (ms) => { const g = gen; return new Promise((res, rej) => setTimeout(() => (g === gen ? res() : rej('cancel')), ms)); };
  const on = (id, cls = 'in') => $(id).classList.add(cls);
  const off = (id, cls) => $(id).classList.remove(cls);
  const centerOf = (el) => {
    const r = el.getBoundingClientRect(), s = stage.getBoundingClientRect(), k = scale();
    return { x: (r.left + r.width / 2 - s.left) / k, y: (r.top + r.height / 2 - s.top) / k };
  };
  const moveTo = (x, y) => { cursor.style.transform = `translate(${x}px, ${y}px)`; };
  async function click(el, dx = 0, dy = 0) {
    const c = centerOf(el);
    moveTo(c.x + dx, c.y + dy);
    await sleep(800);
    cursor.classList.remove('press'); void cursor.offsetWidth; cursor.classList.add('press');
    el.classList.add('press');
    await sleep(160);
    el.classList.remove('press');
  }
  const camera = (cx, cy, k) => { world.style.transform = k === 1 ? 'none' : `translate(${380 - k * cx}px, ${300 - k * cy}px) scale(${k})`; };
  async function type(el, text, speed) {
    el.textContent = '';
    for (let i = 0; i < text.length; i++) {
      el.textContent += text[i];
      if (text[i] !== ' ' && text[i] !== '\n') await sleep(speed);
    }
  }
  function focusOn(id) {
    const keep = new Set([id]);
    EDGES.forEach((e) => {
      const hit = e.a === id || e.b === id;
      e.el.classList.toggle('on', hit);
      if (hit) { keep.add(e.a); keep.add(e.b); }
    });
    nodes.forEach((n) => n.classList.toggle('dim', n.id !== 'd-script' && !keep.has(n.id)));
    nodes.forEach((n) => n.classList.toggle('sel', n.id === id));
  }
  function unfocus() {
    EDGES.forEach((e) => e.el.classList.remove('on'));
    nodes.forEach((n) => n.classList.remove('dim', 'sel'));
  }

  function reset() {
    root.querySelectorAll('.dz, .dn:not(.n-script)').forEach((n) => n.classList.remove('in', 'has-clip', 'run', 'done', 'dim', 'sel'));
    $('d-script').classList.remove('sent', 'sel', 'dim');
    $('d-tx').textContent = '';
    EDGES.forEach((e) => e.el.classList.remove('vis', 'on'));
    panel.classList.remove('open', 'clip'); camera(0, 0, 1);
    cursor.style.transition = 'none'; moveTo(560, 600); void cursor.offsetWidth; cursor.style.transition = '';
  }

  function finalState() {
    ['z-char', 'z-prop', 'z-loc', 'z-shot', 'z-film', 'd-minh', 'd-lan', 'd-prop', 'd-loc', 'd-film', ...SHOTS.map((s) => 'd-s' + s.id)].forEach((id) => on(id));
    SHOTS.forEach((s) => { if (s.clip) $('d-s' + s.id).classList.add('has-clip'); });
    $('d-tx').textContent = SCRIPT; $('d-script').classList.add('sent');
    on('d-film', 'done');
    EDGES.forEach((e) => { e.el.classList.add('vis'); if (e.b === 'd-film') e.el.classList.add('on'); });
    cursor.style.display = 'none';
  }

  // ---- Năm nhịp ----
  async function beats() {
    await sleep(700);
    // 1. Dán kịch bản
    await type($('d-tx'), SCRIPT, 22);
    await sleep(350);
    await click($('d-analyze'));
    on('d-script', 'sent');

    // 2. Tách tài sản (nhân vật, phụ kiện, bối cảnh, shot) vào đúng vùng màu
    on('z-char'); await sleep(250); on('d-minh'); await sleep(250); on('d-lan'); await sleep(350);
    on('z-prop'); await sleep(200); on('d-prop'); await sleep(350);
    on('z-loc'); await sleep(200); on('d-loc'); await sleep(350);
    on('z-shot');
    for (const s of SHOTS) { await sleep(150); on('d-s' + s.id); }
    await sleep(250); on('z-film'); on('d-film');
    EDGES.forEach((e) => e.el.classList.add('vis'));
    await sleep(800);

    // 3. Chọn một shot: đường nối sáng, máy quay đẩy vào, thẻ chi tiết trượt ra
    const target = $('d-s1-2');
    await click(target, 0, -6);
    focusOn('d-s1-2');
    camera(target.offsetLeft + 75, target.offsetTop + 60, 1.3);
    await sleep(600);
    panel.classList.add('open');
    await sleep(1500);

    // 4. Có clip
    on('d-s1-2', 'run'); await sleep(1200);
    on('d-s1-2', 'has-clip'); panel.classList.add('clip');
    await sleep(1500);

    // 5. Ghép phim: máy quay lùi ra, các shot có clip lần lượt sáng, phim hoàn tất
    panel.classList.remove('open'); unfocus(); camera(0, 0, 1);
    await sleep(700);
    await click($('d-assemble'), 0, 4);
    for (const s of SHOTS.filter((x) => x.clip && x.id !== '1-2')) { on('d-s' + s.id, 'run'); await sleep(200); on('d-s' + s.id, 'has-clip'); }
    await sleep(500);
    on('d-film', 'done');
    EDGES.forEach((e) => e.el.classList.toggle('on', e.b === 'd-film'));
    await sleep(2600);
    unfocus();
    stage.style.opacity = '0';   // mờ dần rồi mới quay về đầu, để vòng lặp không có đường nối giật
    await sleep(650);
  }

  let running = false, visible = false;
  async function play() {
    if (running) return;
    running = true;
    const my = ++gen;
    try {
      while (my === gen) { reset(); stage.style.opacity = '1'; await sleep(300); await beats(); }
    } catch (e) { if (e !== 'cancel') throw e; }
    running = false;
  }
  const stop = () => { gen++; running = false; stage.style.opacity = '1'; };
  const sync = () => (visible && !document.hidden ? play() : stop());

  // ---- Chọn kiểu hiển thị ----
  const looks = document.querySelectorAll('.looks button');
  looks.forEach((b) => b.addEventListener('click', () => {
    root.dataset.look = b.dataset.look;
    looks.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));

  if (reduce) { finalState(); return; }
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((es) => { visible = es[0].isIntersecting; sync(); }, { threshold: 0.2 }).observe(root);
  } else { visible = true; sync(); }
  document.addEventListener('visibilitychange', sync);
})();
