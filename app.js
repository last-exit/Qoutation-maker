/* Smart Quotation Engine — frontend logic. No external dependencies (offline-safe). Company name/branding is data-driven from company.json (see applyCompanyBranding). */

// ---------------------------------------------------------------------------
// Inline icon set (replaces the Lucide CDN so the app has zero network dependency)
// ---------------------------------------------------------------------------
const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.6 1H21a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-4"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  tag: '<path d="M20.6 12.6 12 21.2 2.8 12 2.8 2.8 12 2.8z" /><circle cx="8" cy="8" r="1.3" fill="currentColor" stroke="none"/>',
  pin: '<path d="M12 21s7-6.5 7-11.5A7 7 0 0 0 5 9.5C5 14.5 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.3"/>',
  sheet: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
  word: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8l1.5 8L10.5 9l2 7L14 8"/>',
  trash: '<path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2m2 0-.8 12a2 2 0 0 1-2 1.9H8.8a2 2 0 0 1-2-1.9L6 7"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  check: '<path d="M8 12l3 3 6-7"/><circle cx="12" cy="12" r="10"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v5M12 16h.01"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5-9 9"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7M21 4v6h-6"/>',
  sparkles: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2"/>',
  trending: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
  layers: '<path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l1.4-4.2A8.5 8.5 0 1 1 21 11.5z"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  link: '<path d="M10 14a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  chevronDown: '<path d="M6 9l6 6 6-6"/>',
  chevronRight: '<path d="M9 18l6-6-6-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.5 2.1L8 9.7a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
};
function svgWrap(name) {
  return `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>`;
}
function icon(name, cls) { return `<span class="icon ${cls || ''}">${svgWrap(name)}</span>`; }

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let draftItems = [];
let activeMarkup = 0.04;
let discountType = null;
let discountValue = 0;
let currentImagePickerItemId = null;
let lastCompileResult = null;
let historyCache = [];
let lastMatches = [];
let lastLibraryMatches = [];

function api() { return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null; }
function uid() { return Date.now() + '_' + Math.random().toString(36).slice(2); }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function money(n) { return (Number(n) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
// A photo borrowed from a similar item in another quote (not this exact line's own photo).
function isBorrowedPhoto(src) { return typeof src === 'string' && (src.startsWith('matched') || src.startsWith('suggested')); }

function skeletonCards(n) {
  let html = '';
  for (let i = 0; i < n; i++) {
    html += `
      <div class="skeleton-card">
        <div class="skeleton" style="width:64px;height:64px;flex-shrink:0;"></div>
        <div style="flex:1;">
          <div class="skeleton skeleton-line" style="width:40%;"></div>
          <div class="skeleton skeleton-line" style="width:85%;"></div>
          <div class="skeleton skeleton-line" style="width:60%;"></div>
        </div>
      </div>`;
  }
  return html;
}

// ---------------------------------------------------------------------------
// Toast notifications (replaces blocking browser alert() everywhere in the app)
// ---------------------------------------------------------------------------
const TOAST_ICONS = { success: 'check', error: 'alert', warning: 'alert', info: 'sparkles' };

function showToast(message, type, duration) {
  type = type || 'info';
  duration = duration || (type === 'error' ? 6000 : 4000);
  const container = document.getElementById('toast-container');
  if (!container) { console.log(`[${type}]`, message); return; }

  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `${icon(TOAST_ICONS[type] || 'sparkles', 'icon toast-icon')}<div class="toast-msg">${esc(message)}</div><span class="toast-close">${icon('close', 'icon-sm')}</span>`;
  container.appendChild(el);

  const dismiss = () => {
    if (!el.parentNode) return;
    el.classList.add('closing');
    setTimeout(() => el.remove(), 260);
  };
  el.querySelector('.toast-close').addEventListener('click', dismiss);
  const timer = setTimeout(dismiss, duration);
  el.addEventListener('mouseenter', () => clearTimeout(timer));
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts
// ---------------------------------------------------------------------------
document.addEventListener('keydown', function (e) {
  const active = document.activeElement;
  const typing = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT');

  if (e.key === 'Escape') {
    if (document.getElementById('image-picker-overlay').classList.contains('open')) closeImagePicker();
    else if (document.getElementById('success-modal-overlay').classList.contains('open')) closeSuccessModal();
    else if (document.getElementById('settings-modal-overlay').classList.contains('open')) closeSettingsModal();
    return;
  }

  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    goToNewQuotation();
    return;
  }

  if (e.key === '/' && !typing) {
    const searchInput = document.getElementById('search-input');
    if (searchInput && !document.getElementById('view-compiler').classList.contains('hidden')) {
      e.preventDefault();
      searchInput.focus();
    }
    return;
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    const compileBtn = document.getElementById('compile-btn');
    if (compileBtn && !compileBtn.disabled && !document.getElementById('view-compiler').classList.contains('hidden')) {
      e.preventDefault();
      compileQuote();
    }
  }
});

// ---------------------------------------------------------------------------
// Boot / theme / tabs
// ---------------------------------------------------------------------------
// Script tag is at the end of <body>, so the DOM is already parsed by the time this runs.
initTheme();
hydrateIcons();
renderDraft();
positionActiveTabPill();
initWorkspaceSplitter();
initCompilerVSplit();

window.addEventListener('pywebviewready', bootBackend);
setTimeout(function () { if (api()) bootBackend(); }, 800);

function bootBackend() {
  checkDbStatus();
  updateAnalyticsDashboard();
  applyCompanyBranding();
  loadHomeDashboard();
}

function applyCompanyBranding() {
  if (!api()) return;
  api().get_company_info().then(function (res) {
    if (!res.success || !res.company) return;
    const name = res.company.name || 'Company';
    document.title = `${name} Smart Quotation Engine`;
    const titleEl = document.getElementById('brand-title-text');
    if (titleEl) titleEl.innerText = name;

    const greetingEl = document.getElementById('home-greeting-title');
    if (greetingEl) {
      const hour = new Date().getHours();
      const timeGreeting = hour < 12 ? 'Good morning' : (hour < 18 ? 'Good afternoon' : 'Good evening');
      greetingEl.innerText = res.company.pm_name ? `${timeGreeting}, ${res.company.pm_name}` : `${timeGreeting} — ${name}`;
    }
    const subtitleEl = document.getElementById('home-greeting-subtitle');
    if (subtitleEl && res.company.pm_name) {
      subtitleEl.innerText = `${name} · search historical rates, compile a quote, and get it out the door in minutes.`;
    }
  }).catch(function () { /* non-critical, keep static defaults */ });
}

// ---------------------------------------------------------------------------
// Home dashboard
// ---------------------------------------------------------------------------
function loadHomeDashboard() {
  updateAnalyticsDashboard();
  loadHomeRecent();
}

function loadHomeRecent() {
  const container = document.getElementById('home-recent-list');
  if (!container) return;
  if (!api()) { container.innerHTML = `<div class="empty-state">${icon('history', 'icon-lg')}<p>Connect the backend to see recent quotations.</p></div>`; return; }

  container.innerHTML = skeletonCards(2);
  api().get_history(5).then(function (res) {
    if (!res.success || !res.items || res.items.length === 0) {
      container.innerHTML = `<div class="empty-state">${icon('history', 'icon-lg')}<p>No quotations generated yet.</p><p style="margin-top:4px;">Compile your first one from the Compiler Workspace.</p></div>`;
      return;
    }
    container.innerHTML = res.items.map(function (q, idx) {
      const pillClass = q.status === 'Won' ? 'status-pill-won' : (q.status === 'Lost' ? 'status-pill-lost' : 'status-pill-sent');
      return `
        <div class="home-recent-item anim-in" style="animation-delay:${idx * 40}ms;" onclick="cloneHistoryItem(${q.id})">
          <div style="min-width:0;">
            <div class="home-recent-client">${esc(q.client_name)}</div>
            <div class="home-recent-meta">${icon('pin', 'icon-sm')} ${esc(q.venue || '-')} &middot; ${esc(q.quote_date)}</div>
          </div>
          <div style="text-align:right;flex-shrink:0;">
            <div class="home-recent-total">${money(q.grand_total)} AED</div>
            <span class="status-pill ${pillClass}" style="margin-top:3px;">${esc(q.status || 'Sent')}</span>
          </div>
        </div>`;
    }).join('');
  }).catch(function () {
    container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>Could not load recent quotations.</span></div>`;
  });
}

function hydrateIcons() {
  document.querySelectorAll('[data-icon]').forEach(el => {
    const name = el.getAttribute('data-icon');
    if (ICONS[name]) el.innerHTML = svgWrap(name);
  });
}

function initTheme() {
  const saved = localStorage.getItem('rc-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', cur);
  localStorage.setItem('rc-theme', cur);
  updateThemeIcon(cur);
}
function updateThemeIcon(theme) {
  const btn = document.getElementById('theme-toggle-icon');
  if (btn) btn.innerHTML = svgWrap(theme === 'light' ? 'moon' : 'sun');
}

// ---------------------------------------------------------------------------
// Resizable workspace (Smart Matcher | Quotation Compiler)
// ---------------------------------------------------------------------------
function initWorkspaceSplitter() {
  // Kept function-local: this runs from the top-level boot block above, so file-scope
  // `const`s down here would still be in their temporal dead zone and throw.
  // Even split. The compiler holds the draft rows (description + unit/qty/rate + thumbnail),
  // which cramp far more readily than a list of match cards, so it no longer gets the
  // smaller half by default. Drag or double-click to re-balance.
  const SPLIT_DEFAULT = 0.5;
  const SPLIT_MIN_PX = 340;           // below this a panel's form grids start wrapping badly
  const SPLITTER_PX = 18;

  const splitter = document.getElementById('workspace-splitter');
  const workspace = splitter && splitter.closest('.workspace');
  if (!workspace) return;

  let frac = parseFloat(localStorage.getItem('rc-workspace-split'));
  if (!(frac > 0 && frac < 1)) frac = SPLIT_DEFAULT;
  applySplit(frac);

  function applySplit(f) {
    const avail = workspace.getBoundingClientRect().width - SPLITTER_PX;
    // Clamp in pixels, not fractions, so the floor holds at any window size.
    if (avail > SPLIT_MIN_PX * 2) {
      const minF = SPLIT_MIN_PX / avail;
      f = Math.min(1 - minF, Math.max(minF, f));
    } else {
      f = Math.min(0.8, Math.max(0.2, f));
    }
    frac = f;
    workspace.style.setProperty('--ws-left', f.toFixed(4) + 'fr');
    workspace.style.setProperty('--ws-right', (1 - f).toFixed(4) + 'fr');
    splitter.setAttribute('aria-valuenow', Math.round(f * 100));
  }

  function pointToFrac(clientX) {
    const rect = workspace.getBoundingClientRect();
    return (clientX - rect.left - SPLITTER_PX / 2) / (rect.width - SPLITTER_PX);
  }

  function stopDrag() {
    if (!workspace.classList.contains('ws-dragging')) return;
    workspace.classList.remove('ws-dragging');
    document.body.classList.remove('ws-dragging');
    localStorage.setItem('rc-workspace-split', String(frac));
  }

  splitter.addEventListener('mousedown', function (e) {
    e.preventDefault();  // stop the drag from selecting text across both panels
    splitter.focus();    // preventDefault also suppresses focus, so hand it over explicitly
    workspace.classList.add('ws-dragging');
    document.body.classList.add('ws-dragging');
  });
  document.addEventListener('mousemove', function (e) {
    if (!workspace.classList.contains('ws-dragging')) return;
    applySplit(pointToFrac(e.clientX));
  });
  document.addEventListener('mouseup', stopDrag);
  // Pointer can leave the window mid-drag; without this the splitter stays "stuck" to it.
  window.addEventListener('blur', stopDrag);

  splitter.addEventListener('dblclick', function () {
    applySplit(SPLIT_DEFAULT);
    localStorage.setItem('rc-workspace-split', String(frac));
  });

  splitter.addEventListener('keydown', function (e) {
    const step = e.shiftKey ? 0.05 : 0.02;
    if (e.key === 'ArrowLeft') applySplit(frac - step);
    else if (e.key === 'ArrowRight') applySplit(frac + step);
    else if (e.key === 'Home') applySplit(SPLIT_DEFAULT);
    else return;
    e.preventDefault();
    localStorage.setItem('rc-workspace-split', String(frac));
  });

  // Re-clamp on window resize so a shrunken window can't push a panel under its minimum.
  window.addEventListener('resize', function () { applySplit(frac); });
}

// ---------------------------------------------------------------------------
// Compiler vertical splitter (item list | pricing block)
// ---------------------------------------------------------------------------
function initCompilerVSplit() {
  const splitter = document.getElementById('compiler-vsplit');
  const footer = document.getElementById('compiler-footer');
  const panel = splitter && splitter.closest('.panel-right');
  const list = document.getElementById('draft-items-container');
  if (!splitter || !footer || !panel || !list) return;

  const MIN_FOOTER = 150;  // summary + format row + Generate button must stay reachable
  const MIN_LIST = 90;
  let footerH = parseFloat(localStorage.getItem('rc-compiler-footer-h'));

  function naturalFooterHeight() {
    // Measure once with the height constraint lifted, so "reset" returns to content size.
    const prev = footer.style.height;
    footer.style.height = 'auto';
    const h = footer.getBoundingClientRect().height;
    footer.style.height = prev;
    return h;
  }

  function applyFooter(h) {
    const panelRect = panel.getBoundingClientRect();
    // The compiler view starts hidden, so every rect here is 0 until it is first shown.
    // Sizing off those zeros pins the footer to MIN_FOOTER and cuts the Generate button off.
    if (panelRect.height <= 0) return;
    const listTop = list.getBoundingClientRect().top - panelRect.top;
    const maxFooter = Math.max(MIN_FOOTER, panelRect.height - listTop - MIN_LIST - splitter.offsetHeight);
    footerH = Math.min(maxFooter, Math.max(MIN_FOOTER, h));
    footer.style.height = footerH + 'px';
    splitter.setAttribute('aria-valuenow', Math.round(footerH));
  }

  // Until the PM interacts, the footer is content-sized and footerH is unset. Any relative
  // adjustment (arrow keys) needs a real starting number or it resolves to NaN and no-ops.
  function ensureSeeded() {
    if (!(footerH > 0)) footerH = footer.getBoundingClientRect().height;
  }

  function stopDrag() {
    if (!panel.classList.contains('vsplit-dragging')) return;
    panel.classList.remove('vsplit-dragging');
    document.body.classList.remove('vsplit-dragging');
    localStorage.setItem('rc-compiler-footer-h', String(footerH));
  }

  splitter.addEventListener('mousedown', function (e) {
    e.preventDefault();
    splitter.focus();
    ensureSeeded();
    panel.classList.add('vsplit-dragging');
    document.body.classList.add('vsplit-dragging');
  });
  document.addEventListener('mousemove', function (e) {
    if (!panel.classList.contains('vsplit-dragging')) return;
    // Footer grows as the pointer moves up, so measure from the panel's bottom edge.
    applyFooter(panel.getBoundingClientRect().bottom - e.clientY);
  });
  document.addEventListener('mouseup', stopDrag);
  window.addEventListener('blur', stopDrag);

  splitter.addEventListener('dblclick', function () {
    applyFooter(naturalFooterHeight());
    localStorage.setItem('rc-compiler-footer-h', String(footerH));
  });

  splitter.addEventListener('keydown', function (e) {
    const step = e.shiftKey ? 40 : 14;
    ensureSeeded();
    if (e.key === 'ArrowUp') applyFooter(footerH + step);
    else if (e.key === 'ArrowDown') applyFooter(footerH - step);
    else if (e.key === 'Home') applyFooter(naturalFooterHeight());
    else return;
    e.preventDefault();
    localStorage.setItem('rc-compiler-footer-h', String(footerH));
  });

  window.addEventListener('resize', function () { if (footerH > 0) applyFooter(footerH); });

  // Left content-sized unless the PM has actually chosen a height. A default of "whatever the
  // pricing block needs" is the one value guaranteed to keep the Generate button on screen.
  if (footerH > 0) {
    // Restore lazily: the panel has no measurable size until the compiler tab is first shown.
    const ro = new ResizeObserver(function () {
      if (panel.getBoundingClientRect().height > 0) {
        applyFooter(footerH);
        ro.disconnect();
      }
    });
    ro.observe(panel);
    applyFooter(footerH);
  }
}

const TAB_TITLES = { home: 'Home', compiler: 'Compiler Workspace', review: 'Needs Review', history: 'Quotation History', estimator: 'Automated Design Estimator' };
// Home has its own hero; Review/History/Estimator already carry a panel title. Only
// Compiler gets the shared page-head, since it's the one view that never had a headline.
const TAB_EYEBROWS = { compiler: 'Quotation Builder' };

function switchTab(tab) {
  document.getElementById('view-home').classList.toggle('hidden', tab !== 'home');
  document.getElementById('view-compiler').classList.toggle('hidden', tab !== 'compiler');
  document.getElementById('view-history').classList.toggle('hidden', tab !== 'history');
  document.getElementById('view-review').classList.toggle('hidden', tab !== 'review');
  document.getElementById('view-estimator').classList.toggle('hidden', tab !== 'estimator');

  document.querySelectorAll('.seg').forEach(function (s) {
    s.classList.toggle('active', s.getAttribute('data-tab') === tab);
  });
  positionActiveTabPill();

  const pageHead = document.getElementById('page-head');
  if (tab === 'compiler') {
    pageHead.classList.remove('hidden');
    document.getElementById('page-eyebrow').innerText = TAB_EYEBROWS[tab] || '';
    document.getElementById('page-title').innerText = TAB_TITLES[tab];
  } else {
    pageHead.classList.add('hidden');
  }

  if (tab === 'home') loadHomeDashboard();
  if (tab === 'history') loadHistory();
  if (tab === 'review') loadReviewQueue();
  if (tab === 'estimator') loadEstimatorOptions();
}

// Slides the dark (or cherry, on Asphalt mode) pill under whichever tab is active —
// the sidebar's stacked nav had no equivalent motion, this is the top-nav's signature move.
function positionActiveTabPill() {
  const wrap = document.getElementById('segwrap');
  const pill = document.getElementById('segpill');
  const active = wrap && wrap.querySelector('.seg.active');
  if (!wrap || !pill || !active) return;
  pill.style.width = active.offsetWidth + 'px';
  pill.style.transform = 'translateX(' + active.offsetLeft + 'px)';
}
window.addEventListener('resize', positionActiveTabPill);

function goToNewQuotation() {
  switchTab('compiler');
  setTimeout(() => { const el = document.getElementById('search-input'); if (el) el.focus(); }, 50);
}

function goToSync() {
  openSettingsModal();
  setTimeout(() => { const el = document.getElementById('folder-path-input'); if (el) el.focus(); }, 50);
}

function openSettingsModal() { document.getElementById('settings-modal-overlay').classList.add('open'); }
function closeSettingsModal() { document.getElementById('settings-modal-overlay').classList.remove('open'); }

// ---------------------------------------------------------------------------
// Status / analytics
// ---------------------------------------------------------------------------
function checkDbStatus() {
  if (!api()) return;
  api().get_db_status().then(function (res) {
    const dot = document.getElementById('db-indicator');
    const txt = document.getElementById('db-status-text');
    if (res.status === 'ready') {
      dot.className = 'status-dot ok';
      txt.innerText = `DB Connected (${res.count} items)`;
    } else {
      dot.className = 'status-dot err';
      txt.innerText = res.message || 'DB Offline';
    }
  });
}

function updateAnalyticsDashboard() {
  if (!api()) return;
  api().get_analytics().then(function (d) {
    document.getElementById('stat-total-items').innerText = d.total_items;
    document.getElementById('stat-avg-price').innerText = d.avg_price + ' AED';
    document.getElementById('stat-max-price').innerText = d.max_price + ' AED';
    document.getElementById('stat-year-range').innerText = `${d.year_min} - ${d.year_max}`;
    document.getElementById('stat-venues').innerText = d.venues;
    document.getElementById('stat-needs-review').innerText = d.needs_review || 0;

    const badge = document.getElementById('review-tab-count');
    if (d.needs_review > 0) {
      badge.innerText = d.needs_review;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }

    const reviewDesc = document.getElementById('home-review-desc');
    if (reviewDesc) {
      reviewDesc.innerText = d.needs_review > 0
        ? `${d.needs_review} item${d.needs_review === 1 ? '' : 's'} flagged for your attention.`
        : 'All clear — nothing flagged right now.';
    }
  });
}

// ---------------------------------------------------------------------------
// Sync / index
// ---------------------------------------------------------------------------
function syncFolder() {
  const pathInput = document.getElementById('folder-path-input');
  const syncBtn = document.getElementById('sync-btn');
  const spinner = document.getElementById('sync-spinner');
  const feedback = document.getElementById('index-feedback');

  const folderPath = pathInput.value.trim();
  if (!folderPath) return;
  if (!api()) { showToast('Backend connection missing.', 'error'); return; }

  syncBtn.disabled = true;
  spinner.classList.add('spin');
  feedback.classList.add('hidden');

  api().index_files(folderPath).then(function (res) {
    syncBtn.disabled = false;
    spinner.classList.remove('spin');
    if (res.success) {
      feedback.classList.remove('hidden');
      feedback.className = 'banner banner-success';
      feedback.innerHTML = icon('check', 'icon') + `<span>${esc(res.message)}</span>`;
      checkDbStatus();
      updateAnalyticsDashboard();
    } else {
      feedback.classList.remove('hidden');
      feedback.className = 'banner banner-error';
      feedback.innerHTML = icon('alert', 'icon') + `<span>${esc(res.error)}</span>`;
    }
  }).catch(function (err) {
    syncBtn.disabled = false;
    spinner.classList.remove('spin');
    showToast('Error invoking indexing engine: ' + err, 'error');
  });
}

// ---------------------------------------------------------------------------
// Search / matches
// ---------------------------------------------------------------------------
function changeMarkup(val) {
  document.getElementById('markup-label').innerText = val + '%';
  activeMarkup = parseFloat(val) / 100.0;
  const query = document.getElementById('search-input').value.trim();
  if (query) searchMatcher();
}

function searchMatcher(event) {
  if (event) event.preventDefault();
  const input = document.getElementById('search-input');
  const container = document.getElementById('matches-list');
  const query = input.value.trim();
  if (!query) return;

  if (event) {
    container.innerHTML = skeletonCards(3);
  }
  if (!api()) { container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>API connection missing.</span></div>`; return; }

  api().search_items(query, activeMarkup).then(function (res) {
    if (!res.success) { container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(res.error)}</span></div>`; return; }
    renderMatches(res.matches || []);
  }).catch(function (err) {
    container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>Search error: ${esc(err)}</span></div>`;
  });
}

// The markup compounds over a quote's real age, so age is what explains the adjusted rate.
// "0.014y" is noise; "5 days old" is the reason the number barely moved.
function formatAge(years) {
  const y = Number(years) || 0;
  const days = Math.round(y * 365.25);
  if (days < 1) return 'today';
  if (days < 31) return `${days} day${days === 1 ? '' : 's'}`;
  const months = Math.round(days / 30.44);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'}`;
  const wholeYears = Math.floor(y);
  const remMonths = Math.round((y - wholeYears) * 12);
  if (remMonths === 0 || remMonths === 12) return `${wholeYears + (remMonths === 12 ? 1 : 0)}y`;
  return `${wholeYears}y ${remMonths}mo`;
}

// Show the uplift that was actually applied, not the annual rate that was requested — a
// week-old quote earns ~0% and the label must say so rather than claiming the slider value.
function upliftHtml(m) {
  const original = Number(m.original_rate) || 0;
  const adjusted = Number(m.adjusted_rate) || 0;
  const pct = original > 0 ? ((adjusted - original) / original) * 100 : 0;
  if (pct < 0.05) {
    return `<div><div class="rate-label">Adjusted</div>
      <div style="color:var(--text-muted);" title="Too recent for the ${Math.round(activeMarkup * 100)}% annual markup to have accrued yet.">No uplift yet</div></div>`;
  }
  return `<div><div class="rate-label" style="color:var(--accent-strong)">Adjusted (+${pct.toFixed(1)}%)</div>
    <div style="color:var(--accent-strong);font-weight:700;" title="${Math.round(activeMarkup * 100)}% annual markup compounded over ${formatAge(m.elapsed_years)}.">${money(adjusted)} AED</div></div>`;
}

function renderMatches(matches) {
  const container = document.getElementById('matches-list');
  if (matches.length === 0) {
    container.innerHTML = `<div class="empty-state">${icon('search', 'icon-lg')}<p>No historical matches found. Try syncing a folder first.</p></div>`;
    return;
  }
  lastMatches = matches;
  let html = '';
  matches.forEach(function (m, idx) {
    const borrowed = isBorrowedPhoto(m.image_source);
    const imageHtml = m.image_base64
      ? `<img src="${m.image_base64}"/>${borrowed ? `<span class="borrowed-badge" title="${esc(m.image_source)}">ref</span>` : ''}`
      : icon('image', 'icon-lg');
    html += `
      <div class="match-card anim-in" style="animation-delay:${idx * 45}ms;" onclick='addMatchedItemToDraft(${JSON.stringify(m).replace(/'/g, '&apos;')})'>
        <div class="match-thumb" id="match-thumb-${m.id}">${imageHtml}</div>
        <div style="flex:1;min-width:0;">
          <div class="match-meta-row">
            <span class="chip chip-accent">${m.similarity}% Match</span>
            <span class="chip chip-muted">${icon('pin', 'icon-sm')} ${esc(m.venue)}</span>
            <span class="chip chip-muted">${icon('calendar', 'icon-sm')} ${esc(m.quote_date)} · ${formatAge(m.elapsed_years)} old</span>
            ${m.file_name ? `<button class="chip chip-link" title="Open ${esc(m.file_name)} to check this item against the original"
                 onclick="event.stopPropagation(); openSourceFile('${esc(m.file_name).replace(/'/g, "\\'")}')">${icon('sheet', 'icon-sm')} Open file</button>` : ''}
          </div>
          <div class="match-desc">${esc(m.description)}</div>
          <div class="match-rates">
            <div style="display:flex;gap:18px;">
              <div><div class="rate-label">Original</div><div>${money(m.original_rate)} AED</div></div>
              ${upliftHtml(m)}
            </div>
            <div style="font-size:9.5px;font-weight:700;color:var(--accent);display:flex;align-items:center;gap:4px;">Add to draft ${icon('arrowRight', 'icon-sm')}</div>
          </div>
        </div>
      </div>`;
  });
  container.innerHTML = html;
}

function addMatchedItemToDraft(item) {
  draftItems.push({
    id: uid(), description: item.description, unit: item.unit || 'Pcs', qty: 1,
    rate: item.adjusted_rate || item.original_rate, image_base64: item.image_base64 || '',
    image_source: item.image_source || '',
  });
  renderDraft();
}

function addCustomDraftRow() {
  draftItems.push({ id: uid(), description: 'Custom Event Production Item', unit: 'Pcs', qty: 1, rate: 0, image_base64: '', image_source: '' });
  renderDraft();
}

// ---------------------------------------------------------------------------
// Draft compiler
// ---------------------------------------------------------------------------
const UNIT_OPTIONS = ['Pcs', 'Set', 'Lump Sum', 'Sqm', 'Days', 'Hrs', 'Nos'];

function renderDraft() {
  const container = document.getElementById('draft-items-container');
  const compileBtn = document.getElementById('compile-btn');

  if (draftItems.length === 0) {
    container.innerHTML = `<div class="empty-state">${icon('sheet', 'icon-lg')}<p>No items in draft quote.</p><p style="margin-top:4px;">Select items from matches or add a custom row.</p></div>`;
    compileBtn.disabled = true;
    updateSummary();
    return;
  }

  compileBtn.disabled = false;
  let html = '';
  draftItems.forEach(function (item, idx) {
    const thumb = item.image_base64
      ? `<img src="${item.image_base64}"/>${isBorrowedPhoto(item.image_source) ? `<span class="borrowed-badge" title="${esc(item.image_source)}">ref</span>` : ''}`
      : icon('image', 'icon');
    const unitOptionsHtml = UNIT_OPTIONS.map(u => `<option value="${u}" ${item.unit === u ? 'selected' : ''}>${u}</option>`).join('');
    html += `
      <div class="draft-item anim-in" style="animation-delay:${idx * 40}ms;">
        <div class="draft-item-head">
          <span style="font-size:9.5px;color:var(--text-muted);font-weight:700;">ITEM #${idx + 1}</span>
          <div style="display:flex;gap:10px;">
            ${item.image_base64 ? `<span class="icon-btn" style="width:26px;height:26px;cursor:pointer;color:var(--accent-strong);" onclick="saveDraftImageToLibrary('${item.id}')" title="Save this photo to the reusable library">${icon('sparkles', 'icon-sm')}</span>` : ''}
            <span class="icon-btn" style="width:26px;height:26px;cursor:pointer;" onclick="openImagePicker('${item.id}')" title="Set image">${icon('image', 'icon-sm')}</span>
            <span class="icon-btn" style="width:26px;height:26px;cursor:pointer;color:var(--danger);" onclick="deleteDraftItem('${item.id}')" title="Remove">${icon('trash', 'icon-sm')}</span>
          </div>
        </div>
        <div style="display:flex;gap:8px;">
          <div class="draft-thumb" id="draft-thumb-${item.id}" onclick="openImagePicker('${item.id}')">${thumb}</div>
          <textarea rows="2" class="input" style="flex:1;" oninput="updateDraftValue('${item.id}','description',this.value)">${esc(item.description)}</textarea>
        </div>
        <div class="draft-grid">
          <div>
            <label class="field-label">Unit</label>
            <select class="input" onchange="updateDraftValue('${item.id}','unit',this.value)">${unitOptionsHtml}</select>
          </div>
          <div>
            <label class="field-label">Qty</label>
            <input type="number" min="0" step="1" class="input" value="${item.qty}" oninput="updateDraftValue('${item.id}','qty',parseFloat(this.value)||0)"/>
          </div>
          <div>
            <label class="field-label">Rate (AED)</label>
            <input type="number" min="0" step="0.01" class="input num" id="rate-input-${item.id}" value="${item.rate}" style="text-align:right;" oninput="updateDraftValue('${item.id}','rate',parseFloat(this.value)||0)"/>
          </div>
        </div>
        <div class="pct-row">
          <button class="pct-btn" onclick="adjustRate('${item.id}',0.05)">+5%</button>
          <button class="pct-btn" onclick="adjustRate('${item.id}',0.10)">+10%</button>
          <button class="pct-btn" onclick="adjustRate('${item.id}',-0.05)">-5%</button>
          <button class="pct-btn" onclick="adjustRate('${item.id}',-0.10)">-10%</button>
        </div>
        <div class="num" style="text-align:right;margin-top:6px;font-size:11px;color:var(--text-secondary);">
          Subtotal: <b class="num-strong" style="color:var(--text-primary);">${money(item.qty * item.rate)} AED</b>
        </div>
      </div>`;
  });
  container.innerHTML = html;
  updateSummary();
}

function updateDraftValue(id, key, val) {
  const item = draftItems.find(i => i.id === id);
  if (!item) return;
  // A negative qty and a negative rate multiply back to a positive line total, so a typo'd
  // minus sign used to inflate the subtotal silently. Neither value is ever legitimately
  // below zero on a quotation; clamp at the source rather than trying to catch it later.
  if ((key === 'qty' || key === 'rate') && (!isFinite(val) || val < 0)) val = 0;
  item[key] = val;
  if (key === 'qty' || key === 'rate') updateSummary();
}

function adjustRate(id, pct) {
  const item = draftItems.find(i => i.id === id);
  if (!item) return;
  item.rate = Math.round(item.rate * (1 + pct) * 100) / 100;
  renderDraft();
}

function deleteDraftItem(id) {
  draftItems = draftItems.filter(i => i.id !== id);
  renderDraft();
}

function setDiscountType(type) {
  discountType = document.getElementById('discount-type').value || null;
  updateSummary();
}
function onDiscountValueChange(val) {
  discountValue = parseFloat(val) || 0;
  updateSummary();
}

function updateSummary() {
  let subtotal = 0;
  draftItems.forEach(i => { subtotal += (Number(i.qty) || 0) * (Number(i.rate) || 0); });

  let discountAmount = 0;
  if (discountType === 'percent') discountAmount = subtotal * (discountValue / 100);
  else if (discountType === 'flat') discountAmount = discountValue;
  discountAmount = Math.max(0, Math.min(discountAmount, subtotal));

  const discountedSubtotal = subtotal - discountAmount;
  const vat = discountedSubtotal * 0.05;
  const total = discountedSubtotal + vat;

  document.getElementById('summary-subtotal').innerText = money(subtotal) + ' AED';
  const discountRow = document.getElementById('summary-discount-row');
  if (discountAmount > 0) {
    discountRow.classList.remove('hidden');
    document.getElementById('summary-discount').innerText = '-' + money(discountAmount) + ' AED';
  } else {
    discountRow.classList.add('hidden');
  }
  document.getElementById('summary-vat').innerText = money(vat) + ' AED';
  document.getElementById('summary-total').innerText = money(total) + ' AED';
}

// ---------------------------------------------------------------------------
// Image picker modal
// ---------------------------------------------------------------------------
function openImagePicker(itemId) {
  currentImagePickerItemId = itemId;
  const item = draftItems.find(i => i.id === itemId);
  document.getElementById('image-picker-overlay').classList.add('open');
  document.getElementById('image-url-input').value = '';
  document.getElementById('image-search-results').innerHTML = '';
  document.getElementById('image-search-query').value = (item ? item.description.split('\n')[0] : '').slice(0, 60);
  switchImagePickerTab('library');
}
function closeImagePicker() {
  document.getElementById('image-picker-overlay').classList.remove('open');
  currentImagePickerItemId = null;
}
function switchImagePickerTab(tab) {
  ['library', 'search', 'url', 'upload'].forEach(t => {
    document.getElementById('img-tab-' + t).classList.toggle('active', t === tab);
    document.getElementById('img-panel-' + t).classList.toggle('hidden', t !== tab);
  });
  if (tab === 'library') runLibrarySearch();
}


function runLibrarySearch() {
  const results = document.getElementById('library-search-results');
  if (!results) return;
  const item = draftItems.find(i => i.id === currentImagePickerItemId);
  const query = item ? item.description : '';
  if (!api() || !query.trim()) {
    results.innerHTML = `<div class="empty-state" style="padding:16px;">${icon('sparkles', 'icon-lg')}<p>No description to match against yet.</p></div>`;
    return;
  }
  results.innerHTML = `<div class="empty-state" style="padding:16px;">${icon('refresh', 'icon spin')}<p style="margin-top:6px;">Checking your photo library...</p></div>`;
  api().search_photo_library(query, 6).then(function (res) {
    if (!res.success) { results.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(res.error)}</span></div>`; return; }
    if (!res.matches || res.matches.length === 0) {
      results.innerHTML = `<div class="empty-state" style="padding:16px;">${icon('sparkles', 'icon-lg')}<p>Nothing saved yet for something like this.</p><p style="margin-top:4px;">Set a real photo below, then save it here for next time.</p></div>`;
      return;
    }
    // Hold the matches and reference them by index: inlining each data URI into an onclick
    // attribute duplicated every thumbnail's full base64 payload into the HTML string.
    lastLibraryMatches = res.matches;
    results.innerHTML = `<div class="image-grid">${res.matches.map((m, i) => `
      <div style="position:relative;">
        <img src="${esc(m.image_base64)}" onclick="applyLibraryMatch(${i})" title="${esc(m.description)}"/>
        <span class="chip chip-accent" style="position:absolute;bottom:4px;left:4px;font-size:8.5px;padding:1px 6px;">${m.similarity}%</span>
      </div>`).join('')}</div>`;
  }).catch(function (err) {
    results.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(err)}</span></div>`;
  });
}

function applyLibraryMatch(idx) {
  const m = lastLibraryMatches[idx];
  if (m) applyImageToItem(m.image_base64);
}

function saveDraftImageToLibrary(itemId) {
  if (!api()) return;
  const item = draftItems.find(i => i.id === itemId);
  if (!item || !item.image_base64) return;
  api().save_photo_to_library(item.description, item.image_base64).then(function (res) {
    if (res.success) showToast('Saved to your photo library for next time.', 'success');
    else showToast('Could not save to library: ' + res.error, 'error');
  }).catch(function (err) {
    showToast('Error saving to library: ' + err, 'error');
  });
}

function runImageSearch() {
  const q = document.getElementById('image-search-query').value.trim();
  const results = document.getElementById('image-search-results');
  if (!q || !api()) return;
  results.innerHTML = `<div class="empty-state" style="padding:16px;">${icon('refresh', 'icon spin')}<p style="margin-top:6px;">Searching online (best-effort)...</p></div>`;
  api().fetch_image_suggestions(q).then(function (res) {
    if (!res.success) {
      results.innerHTML = `<div class="banner banner-warning">${icon('alert', 'icon')}<span>${esc(res.error || 'No internet connection — try Paste URL or Upload instead.')}</span></div>`;
      return;
    }
    // These URLs come from a third-party search endpoint, so they are untrusted input.
    // Escape them into the attributes and hand the URL over via dataset rather than
    // interpolating it into an inline handler — a quote in the URL used to break out of
    // src="..." and inject a live event handler.
    results.innerHTML = `<div class="image-grid">${res.results.map(r =>
      `<img src="${esc(r.thumbnail_url)}" data-source-url="${esc(r.source_url)}"
            onclick="selectSuggestedImage(this.dataset.sourceUrl)"/>`).join('')}</div>`;
  }).catch(function (err) {
    results.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(err)}</span></div>`;
  });
}
function selectSuggestedImage(sourceUrl) {
  if (!api()) return;
  const targetId = currentImagePickerItemId;
  api().fetch_image_from_url(sourceUrl).then(function (res) {
    if (res.success) applyImageToItem(res.image_base64, '', targetId);
    else showToast('Could not fetch that image: ' + res.error, 'error');
  });
}
function pasteImageUrl() {
  const url = document.getElementById('image-url-input').value.trim();
  if (!url || !api()) return;
  const targetId = currentImagePickerItemId;
  api().fetch_image_from_url(url).then(function (res) {
    if (res.success) applyImageToItem(res.image_base64, '', targetId);
    else showToast('Could not fetch that image: ' + res.error, 'error');
  });
}
function uploadImageForItem() {
  if (!api()) return;
  const targetId = currentImagePickerItemId;
  api().upload_image_dialog().then(function (res) {
    if (res.success) applyImageToItem(res.image_base64, '', targetId);
    else if (res.error !== 'No file selected.') showToast('Upload failed: ' + res.error, 'error');
  });
}
// targetId pins the image to the row the picker was opened for. Fetches are async, so
// without it a slow download lands on whichever row is selected when it finally resolves —
// or is dropped entirely if the picker was closed in the meantime.
function applyImageToItem(base64, source, targetId) {
  const id = targetId || currentImagePickerItemId;
  const item = draftItems.find(i => i.id === id);
  if (item) {
    item.image_base64 = base64;
    item.image_source = source || '';
    renderDraft();
  }
  closeImagePicker();
}

// ---------------------------------------------------------------------------
// Compile / generate
// ---------------------------------------------------------------------------
// Everything worth stopping a PM for, gathered before the files are written. This is the one
// action in the app that produces a document a paying client will read, and it was previously
// a single unguarded click.
function preflightWarnings() {
  const warnings = [];
  const client = document.getElementById('client-name-input').value.trim();
  const venue = document.getElementById('client-venue-input').value.trim();

  if (!client) warnings.push('No client name — the quotation will be addressed to "Client".');
  if (!venue) warnings.push('No venue set.');

  const zeroRate = draftItems.filter(i => !(Number(i.rate) > 0)).length;
  if (zeroRate > 0) warnings.push(`${zeroRate} item(s) priced at 0.00 AED.`);

  const zeroQty = draftItems.filter(i => !(Number(i.qty) > 0)).length;
  if (zeroQty > 0) warnings.push(`${zeroQty} item(s) with a quantity of 0.`);

  const placeholder = draftItems.filter(i => /^\s*custom event production item\s*$/i.test(i.description || '')).length;
  if (placeholder > 0) warnings.push(`${placeholder} item(s) still using the default description.`);

  const noDesc = draftItems.filter(i => !(i.description || '').trim()).length;
  if (noDesc > 0) warnings.push(`${noDesc} item(s) with no description.`);

  return warnings;
}

function compileQuote() {
  if (draftItems.length === 0) return;
  if (!api()) { showToast('Backend connection missing.', 'error'); return; }

  const warnings = preflightWarnings();
  if (warnings.length > 0) {
    const total = document.getElementById('summary-total').innerText;
    const proceed = confirm(
      `This quotation is about to be generated for ${total}.\n\n` +
      `Before it goes out:\n` +
      warnings.map(w => '  • ' + w).join('\n') +
      `\n\nGenerate anyway?`
    );
    if (!proceed) return;
  }

  const formats = [];
  if (document.getElementById('format-xlsx').checked) formats.push('xlsx');
  if (document.getElementById('format-docx').checked) formats.push('docx');
  if (formats.length === 0) formats.push('xlsx');

  const payload = {
    items: draftItems.map(i => ({ description: i.description, unit: i.unit, qty: i.qty, rate: i.rate, image_base64: i.image_base64 })),
    client_name: document.getElementById('client-name-input').value.trim() || 'Client',
    client_phone: document.getElementById('client-phone-input').value.trim(),
    venue: document.getElementById('client-venue-input').value.trim(),
    discount_type: discountType,
    discount_value: discountValue,
    formats: formats,
    validity_days: parseInt(document.getElementById('validity-days-input').value, 10) || 14,
  };

  const compileBtn = document.getElementById('compile-btn');
  const feedback = document.getElementById('compile-feedback');
  compileBtn.disabled = true;
  compileBtn.innerHTML = `${icon('refresh', 'icon spin')} <span>Compiling...</span>`;
  feedback.classList.add('hidden');

  api().compile_quotation(payload).then(function (res) {
    compileBtn.disabled = false;
    compileBtn.innerHTML = `${icon('sheet', 'icon')} <span>Generate Quotation</span>`;

    if (res.success) {
      lastCompileResult = res;
      showSuccessModal(res, payload);
      updateAnalyticsDashboard();
      showToast('Quotation generated successfully.', 'success');
      // A photo that failed to embed leaves a gap in a document the PM is about to send,
      // so it needs saying out loud rather than only in the console.
      if (res.image_failures > 0) {
        showToast(`${res.image_failures} photo(s) could not be embedded — check those rows before sending.`, 'warning', 8000);
      }
    } else {
      feedback.classList.remove('hidden');
      feedback.className = 'banner banner-error';
      feedback.innerHTML = icon('alert', 'icon') + `<span>${esc(res.error)}</span>`;
      showToast(res.error || 'Could not generate quotation.', 'error');
    }
  }).catch(function (err) {
    compileBtn.disabled = false;
    compileBtn.innerHTML = `${icon('sheet', 'icon')} <span>Generate Quotation</span>`;
    showToast('Compilation error: ' + err, 'error');
  });
}

function showSuccessModal(res, payload) {
  const body = document.getElementById('success-modal-body');
  let filesHtml = '';
  if (res.xlsx_path) filesHtml += `<div class="banner banner-success" style="margin-top:8px;">${icon('sheet', 'icon')}<span style="word-break:break-all;">${esc(res.xlsx_path)}</span></div>`;
  if (res.docx_path) filesHtml += `<div class="banner banner-success" style="margin-top:8px;">${icon('word', 'icon')}<span style="word-break:break-all;">${esc(res.docx_path)}</span></div>`;
  if (res.pdf_available) {
    filesHtml += `<div class="banner banner-success" style="margin-top:8px;">${icon('check', 'icon')}<span>PDF generated and opened: ${esc(res.pdf_path)}</span></div>`;
  } else {
    filesHtml += `<div class="banner banner-warning" style="margin-top:8px;">${icon('alert', 'icon')}<span>PDF conversion unavailable (${esc(res.pdf_error || 'MS Office not detected')}) — opened the source file instead.</span></div>`;
  }

  body.innerHTML = `
    <div style="text-align:center;margin-bottom:14px;">
      <div class="check-pop" style="width:40px;height:40px;border-radius:50%;background:var(--success-soft);color:var(--success);display:flex;align-items:center;justify-content:center;margin:0 auto 10px;">${icon('check', 'icon-lg')}</div>
      <div style="font-size:22px;font-weight:800;color:var(--accent-strong);">${money(res.totals.grand_total)} AED</div>
      <div style="font-size:11px;color:var(--text-muted);">Grand Total &middot; Quotation Ref Q-${res.history_id}</div>
      <div style="font-size:10.5px;color:var(--text-muted);margin-top:2px;">${icon('clock', 'icon-sm')} Valid until ${esc(res.valid_until || '')}</div>
    </div>
    ${filesHtml}
    <div class="share-btn-row">
      <div class="share-btn" onclick="shareViaWhatsapp()">${icon('chat', 'icon-lg')}<span>WhatsApp</span></div>
      <div class="share-btn" onclick="shareViaEmail()">${icon('mail', 'icon-lg')}<span>Email</span></div>
      <div class="share-btn" onclick="reopenPdf()">${icon('link', 'icon-lg')}<span>Open File</span></div>
    </div>
  `;
  document.getElementById('success-modal-overlay').classList.add('open');
}
function closeSuccessModal() { document.getElementById('success-modal-overlay').classList.remove('open'); }
function shareViaWhatsapp() { if (lastCompileResult && api()) api().open_external_link(lastCompileResult.whatsapp_link); }
function shareViaEmail() { if (lastCompileResult && api()) api().open_external_link(lastCompileResult.mailto_link); }
function reopenPdf() {
  if (!lastCompileResult || !api()) return;
  const path = lastCompileResult.pdf_path || lastCompileResult.xlsx_path || lastCompileResult.docx_path;
  if (path) api().open_path(path);
}

// ---------------------------------------------------------------------------
// History tab
// ---------------------------------------------------------------------------
let historyStatusFilter = '';
const HISTORY_COLSPAN = 9;

function loadHistory() {
  const container = document.getElementById('history-table-body');
  if (!api()) return;
  container.innerHTML = Array(4).fill(
    `<tr><td colspan="${HISTORY_COLSPAN}"><div class="skeleton skeleton-line" style="width:100%;height:16px;"></div></td></tr>`
  ).join('');
  api().get_history(300).then(function (res) {
    if (!res.success) { container.innerHTML = `<tr><td colspan="${HISTORY_COLSPAN}">${esc(res.error)}</td></tr>`; return; }
    historyCache = res.items;
    renderHistoryTable(applyHistoryFilters(historyCache));
  });
}

function applyHistoryFilters(items) {
  const q = document.getElementById('history-search').value.trim().toLowerCase();
  return items.filter(h => {
    const matchesText = !q || (h.client_name || '').toLowerCase().includes(q) || (h.venue || '').toLowerCase().includes(q);
    const matchesStatus = !historyStatusFilter || (h.status || 'Sent') === historyStatusFilter;
    return matchesText && matchesStatus;
  });
}

function setHistoryStatusFilter(status) {
  historyStatusFilter = status;
  document.querySelectorAll('#status-filter-row .status-filter-chip').forEach(chip => {
    chip.classList.toggle('active', chip.getAttribute('data-status') === status);
  });
  renderHistoryTable(applyHistoryFilters(historyCache));
}

function statusPillHtml(id, status) {
  status = status || 'Sent';
  const options = ['Sent', 'Won', 'Lost'].map(s => `<option value="${s}" ${s === status ? 'selected' : ''}>${s}</option>`).join('');
  const pillClass = status === 'Won' ? 'status-pill-won' : (status === 'Lost' ? 'status-pill-lost' : 'status-pill-sent');
  return `<span class="status-pill ${pillClass}"><select class="status-select" onchange="updateQuoteStatus(${id}, this.value)">${options}</select></span>`;
}

function renderHistoryTable(items) {
  const container = document.getElementById('history-table-body');
  if (items.length === 0) {
    container.innerHTML = `<tr><td colspan="${HISTORY_COLSPAN}"><div class="empty-state">${icon('history', 'icon-lg')}<p>No quotations match here.</p></div></td></tr>`;
    return;
  }
  container.innerHTML = items.map(function (q, idx) {
    return `
      <tr style="animation-delay:${Math.min(idx * 30, 300)}ms;">
        <td>#${q.id}</td>
        <td>${esc(q.client_name)}</td>
        <td><span class="chip chip-muted">${icon('pin', 'icon-sm')} ${esc(q.venue || '-')}</span></td>
        <td>${esc(q.quote_date)}</td>
        <td>${esc(q.valid_until || '-')}</td>
        <td>${q.items.length}</td>
        <td class="num num-strong">${money(q.grand_total)} AED</td>
        <td>${statusPillHtml(q.id, q.status)}</td>
        <td>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="cloneHistoryItem(${q.id})">${icon('edit', 'icon-sm')} Clone / Edit</button>
            <button class="btn btn-danger-ghost btn-sm" onclick="deleteHistoryItem(${q.id})">${icon('trash', 'icon-sm')}</button>
          </div>
        </td>
      </tr>`;
  }).join('');
}

function updateQuoteStatus(id, status) {
  if (!api()) return;
  api().update_quotation_status(id, status).then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not update status.', 'error'); return; }
    const item = historyCache.find(h => h.id === id);
    if (item) item.status = status;
    showToast(`Quote #${id} marked as ${status}.`, status === 'Won' ? 'success' : (status === 'Lost' ? 'warning' : 'info'));
  }).catch(function (err) {
    showToast('Error updating status: ' + err, 'error');
  });
}

function cloneHistoryItem(id) {
  if (!api()) return;
  api().get_history_item(id).then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    const q = res.item;
    draftItems = (q.items || []).map(it => ({ id: uid(), description: it.description, unit: it.unit || 'Pcs', qty: it.qty || 1, rate: it.rate || 0, image_base64: it.image_base64 || '' }));
    document.getElementById('client-name-input').value = q.client_name || '';
    document.getElementById('client-phone-input').value = q.client_phone || '';
    document.getElementById('client-venue-input').value = q.venue || '';
    discountType = q.discount_type || null;
    discountValue = q.discount_value || 0;
    document.getElementById('discount-type').value = discountType || '';
    document.getElementById('discount-value-input').value = discountValue || '';
    switchTab('compiler');
    renderDraft();
  });
}

function deleteHistoryItem(id) {
  if (!confirm('Delete this quotation history record? (Generated files on disk are not affected.)')) return;
  if (!api()) return;
  api().delete_history_item(id).then(function () {
    showToast(`Quote #${id} removed from history.`, 'info');
    loadHistory();
  });
}

function filterHistory() {
  renderHistoryTable(applyHistoryFilters(historyCache));
}

// ---------------------------------------------------------------------------
// Needs Review queue
// ---------------------------------------------------------------------------
function loadReviewQueue() {
  const container = document.getElementById('review-queue-list');
  if (!api()) return;
  container.innerHTML = skeletonCards(3);
  api().get_review_queue(300).then(function (res) {
    if (!res.success) { container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(res.error)}</span></div>`; return; }
    renderReviewQueue(res.items || []);
  }).catch(function (err) {
    container.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(err)}</span></div>`;
  });
}

// Each backend reason maps to the field it blocks and to plain language. The old card showed
// abstract "rate: Low / venue: Low" confidence chips, which contradicted the actual flags
// (an item could read "rate High" while being queued precisely for a missing rate) and never
// said which of the three boxes to touch.
const REVIEW_REASONS = {
  'missing unit rate': { field: 'rate', label: 'No price', fix: 'Type the rate this item was actually sold at.' },
  'missing description': { field: null, label: 'No description', fix: 'The source row had no readable text — dismiss it unless you recognise it.' },
  'unverified venue': { field: 'venue', label: 'Venue unknown', fix: 'Name the venue this job was for.' },
  'reconcile': { field: 'rate', label: "Price doesn't add up", fix: "The rate didn't match the row's own line total — check which is right." },
};

function reviewReasonInfo(reason) {
  const key = Object.keys(REVIEW_REASONS).find(k => String(reason).includes(k));
  return key ? REVIEW_REASONS[key] : { field: null, label: String(reason), fix: '' };
}

function reviewEmptyState() {
  return `<div class="empty-state">${icon('check', 'icon-lg')}<p>Nothing flagged — every indexed item has a confident rate and venue.</p></div>`;
}

function groupByFile(items) {
  const groups = new Map();
  items.forEach(it => {
    const key = it.file_name || 'Unknown file';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(it);
  });
  return groups;
}

function renderReviewQueue(items) {
  const container = document.getElementById('review-queue-list');
  if (items.length === 0) { container.innerHTML = reviewEmptyState(); return; }

  const groups = groupByFile(items);
  let html = '';
  let cardIdx = 0;
  groups.forEach(function (groupItems, fileName) {
    const safeFile = esc(fileName).replace(/'/g, "\\'");
    const groupId = esc(fileName).replace(/[^a-zA-Z0-9]/g, '_');
    // Venue belongs to the file, not the line item, so it gets one control for the whole
    // group — otherwise a 28-item document means typing the same venue 28 times.
    const venueOnly = groupItems.every(it => (it.reasons || []).length === 1 && (it.reasons || [])[0] === 'unverified venue');
    html += `
      <div class="review-file-group" id="review-group-${groupId}">
        <div class="review-file-header">
          <div class="review-file-name" title="${esc(fileName)}">${icon('sheet', 'icon-sm')} ${esc(fileName)} <span class="chip chip-muted">${groupItems.length}</span></div>
          <div style="display:flex;gap:6px;flex-shrink:0;">
            <button class="btn btn-ghost btn-sm" onclick="openSourceFile('${safeFile}')"
                    title="Open the original file to see this row in context">${icon('sheet', 'icon-sm')} Open File</button>
            <button class="btn btn-ghost btn-sm" onclick="dismissReviewGroup('${safeFile}')">${icon('check', 'icon-sm')} Dismiss All in This File</button>
          </div>
        </div>
        <div class="review-bulk-row">
          ${icon('pin', 'icon-sm')}
          <input type="text" class="input" id="bulk-venue-${groupId}" placeholder="Set venue for all ${groupItems.length} item(s) in this file..."
                 value="${esc(groupItems[0].venue === 'Venue Unspecified' ? '' : groupItems[0].venue)}">
          <button class="btn btn-primary btn-sm" onclick="applyBulkVenue('${safeFile}','${groupId}')">${icon('check', 'icon-sm')} Apply to All</button>
        </div>
        ${venueOnly ? `<div class="review-bulk-hint">Only the venue needs confirming for this file — set it above and the whole group clears.</div>` : ''}`;
    groupItems.forEach(function (it) {
      const infos = (it.reasons || []).map(reviewReasonInfo);
      const badExpr = infos.some(i => i.field === 'rate');
      const badVenue = infos.some(i => i.field === 'venue');
      const badges = infos.map(i => `<span class="chip chip-danger">${icon('alert', 'icon-sm')} ${esc(i.label)}</span>`).join('');
      const fixes = infos.filter(i => i.fix).map(i => `<li>${esc(i.fix)}</li>`).join('');
      html += `
        <div class="review-card anim-in" style="animation-delay:${Math.min(cardIdx * 35, 350)}ms;" id="review-card-${it.id}" data-file="${esc(fileName)}">
          <div class="review-card-head">
            <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
              ${badges}
              <span class="chip chip-muted">${icon('calendar', 'icon-sm')} ${esc(it.quote_date)}</span>
            </div>
          </div>
          <div class="review-desc">${esc(it.description) || '<span style="color:var(--text-muted);font-style:italic;">(no description in the source file)</span>'}</div>
          ${fixes ? `<ul class="review-reason">${fixes}</ul>` : ''}
          <div class="review-grid">
            <div>
              <label class="field-label">Rate (AED)${badExpr ? ' <span class="review-needs">needs fixing</span>' : ''}</label>
              <input type="number" min="0" step="0.01" class="input num${badExpr ? ' input-flagged' : ''}" id="rev-rate-${it.id}" value="${it.rate}" style="text-align:right;">
            </div>
            <div>
              <label class="field-label">Unit</label>
              <input type="text" class="input" id="rev-unit-${it.id}" value="${esc(it.unit)}">
            </div>
            <div>
              <label class="field-label">Venue${badVenue ? ' <span class="review-needs">needs fixing</span>' : ''}</label>
              <input type="text" class="input${badVenue ? ' input-flagged' : ''}" id="rev-venue-${it.id}"
                     value="${esc(it.venue === 'Venue Unspecified' ? '' : it.venue)}" placeholder="e.g. Kite Beach">
            </div>
            <button class="btn btn-ghost btn-sm" onclick="dismissReviewItem('${it.id}')"
                    title="Leave this item exactly as it is and stop flagging it. Nothing is deleted.">${icon('close', 'icon-sm')} Leave as-is</button>
            <button class="btn btn-primary btn-sm" onclick="saveReviewCorrection('${it.id}')"
                    title="Save what you typed above into the index. The fix survives future re-syncs.">${icon('check', 'icon-sm')} Save fix</button>
          </div>
        </div>`;
      cardIdx++;
    });
    html += `</div>`;
  });
  container.innerHTML = html;
}

function openSourceFile(fileName) {
  if (!api()) return;
  showToast(`Opening ${fileName}...`, 'info', 2000);
  api().open_source_file(fileName).then(function (res) {
    if (!res.success) showToast(res.error || 'Could not open that file.', 'error', 7000);
  }).catch(function (err) {
    showToast('Could not open that file: ' + err, 'error', 7000);
  });
}

function removeReviewCardFromDom(itemId) {
  const card = document.getElementById(`review-card-${itemId}`);
  if (!card) return;
  const group = card.closest('.review-file-group');
  card.remove();
  if (group && group.querySelectorAll('.review-card').length === 0) group.remove();
  if (document.querySelectorAll('#review-queue-list .review-card').length === 0) {
    document.getElementById('review-queue-list').innerHTML = reviewEmptyState();
  }
}

function saveReviewCorrection(itemId) {
  if (!api()) return;
  const rate = parseFloat(document.getElementById(`rev-rate-${itemId}`).value) || 0;
  const unit = document.getElementById(`rev-unit-${itemId}`).value.trim();
  const venue = document.getElementById(`rev-venue-${itemId}`).value.trim();

  const card = document.getElementById(`review-card-${itemId}`);
  if (card) card.style.opacity = '0.5';

  api().save_correction(itemId, rate, unit, venue).then(function (res) {
    if (!res.success) { showToast('Could not save correction: ' + res.error, 'error'); if (card) card.style.opacity = '1'; return; }
    removeReviewCardFromDom(itemId);
    updateAnalyticsDashboard();
    showToast('Correction saved — this fix will stick on future re-syncs.', 'success');
  }).catch(function (err) {
    showToast('Error saving correction: ' + err, 'error');
    if (card) card.style.opacity = '1';
  });
}

function dismissReviewItem(itemId) {
  if (!api()) return;
  const card = document.getElementById(`review-card-${itemId}`);
  if (card) card.style.opacity = '0.5';

  api().dismiss_review_item(itemId).then(function (res) {
    if (!res.success) { showToast('Could not dismiss: ' + res.error, 'error'); if (card) card.style.opacity = '1'; return; }
    removeReviewCardFromDom(itemId);
    updateAnalyticsDashboard();
  }).catch(function (err) {
    showToast('Error dismissing item: ' + err, 'error');
    if (card) card.style.opacity = '1';
  });
}

function applyBulkVenue(fileName, groupId) {
  if (!api()) return;
  const input = document.getElementById('bulk-venue-' + groupId);
  const venue = input ? input.value.trim() : '';
  if (!venue) { showToast('Enter a venue name first.', 'warning'); return; }

  api().bulk_set_venue_for_file(fileName, venue).then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not apply venue.', 'error'); return; }
    showToast(`Venue "${venue}" applied to ${res.updated} item(s).`, 'success');
    // Reload rather than patching the DOM: items whose only issue was the venue now drop
    // out of the queue entirely, while any with other gaps must stay.
    loadReviewQueue();
    updateAnalyticsDashboard();
  }).catch(function (err) {
    showToast('Bulk venue update failed: ' + err, 'error');
  });
}

function dismissReviewGroup(fileName) {
  if (!api()) return;
  const cards = document.querySelectorAll(`#review-queue-list .review-card[data-file="${CSS.escape(fileName)}"]`);
  if (cards.length === 0) return;
  if (!confirm(`Dismiss all ${cards.length} flagged item(s) from "${fileName}"? They won't be flagged again.`)) return;

  const ids = Array.from(cards).map(c => c.id.replace('review-card-', ''));
  Promise.all(ids.map(id => api().dismiss_review_item(id))).then(function (results) {
    const failed = results.filter(r => !r.success).length;
    ids.forEach(id => removeReviewCardFromDom(id));
    updateAnalyticsDashboard();
    if (failed > 0) showToast(`${failed} item(s) could not be dismissed.`, 'warning');
    else showToast(`Dismissed all flagged items from ${fileName}.`, 'success');
  });
}

// ---------------------------------------------------------------------------
// Automated Design Estimator
//
// Drawings are parsed once into `estimatorSpecs` (the editable truth) and costed on the
// Python side on every change. Nothing here does arithmetic on a price: the browser holds
// dimensions and choices, `calculators.py` holds every formula. That split is the point —
// a number on screen can always be traced to a printed basis string beside it.
// ---------------------------------------------------------------------------
let estimatorSpecs = [];        // editable spec per drawing page
let estimatorPages = [];        // immutable parse output (thumbnail, raw text, warnings)
let estimatorResults = [];      // BOQ per page, from the backend
let estimatorSummary = null;    // cumulative master summary
let estimatorOptions = null;    // dropdown options + rate-card constants
let estimatorMargin = 35;
let estimatorLoaded = false;

const CONFIDENCE_LABELS = {
  high: 'Exact match on drawing',
  medium: 'Read from a dimension pair',
  low: 'Weak — please confirm',
  none: 'Nothing detected — enter manually',
};

function loadEstimatorOptions() {
  if (!api() || estimatorLoaded) return;
  api().get_estimator_options().then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not load estimator options.', 'error'); return; }
    estimatorOptions = res.options;
    estimatorMargin = estimatorOptions.default_margin_pct;
    estimatorLoaded = true;

    const badge = document.getElementById('est-ratecard-badge');
    if (badge) {
      badge.innerText = `${estimatorOptions.rate_card.item_count} rates · ${estimatorOptions.rate_card.source}`;
    }
    // OCR is only needed for raster drawings; vector PDFs are exact either way, so this
    // is stated once as a capability note rather than nagged as an error.
    if (!estimatorOptions.ocr.available) {
      showEstimatorNotice(
        `${estimatorOptions.ocr.hint} PDF drawings are unaffected.`, 'info'
      );
    }
  }).catch(function (err) {
    showToast('Estimator options failed to load: ' + err, 'error');
  });
}

function showEstimatorNotice(message, kind) {
  const el = document.getElementById('est-notice');
  if (!el) return;
  el.className = `est-notice est-notice-${kind || 'info'}`;
  el.innerHTML = `${icon(kind === 'error' ? 'alert' : 'sparkles', 'icon-sm')}<span>${esc(message)}</span>`;
  el.classList.remove('hidden');
}

function pickDesignFiles() {
  if (!api()) { showToast('Backend not ready yet.', 'warning'); return; }

  api().pick_design_files().then(function (res) {
    if (!res.success) {
      if (res.error && res.error !== 'No files selected.') showToast(res.error, 'error');
      return;
    }
    const loading = document.getElementById('est-loading');
    loading.classList.remove('hidden');
    loading.innerHTML = skeletonCards(Math.min(res.paths.length, 3));

    return api().parse_design_files(res.paths).then(function (parsed) {
      loading.classList.add('hidden');
      loading.innerHTML = '';

      if (!parsed.success) { showToast(parsed.error || 'Could not read those files.', 'error'); return; }
      if (!parsed.drawings.length) { showToast('No readable drawing pages found.', 'warning'); return; }

      parsed.drawings.forEach(function (page) {
        estimatorPages.push(page);
        // The detected values seed the editable spec; from here the PM owns them.
        estimatorSpecs.push(Object.assign({}, page.detected, {
          substrate: '', framing: '', finish: 'paint_pu', led_meters: 0,
          cutouts: (page.detected.cutouts || []).map(c => Object.assign({}, c)),
          source: { file: page.file_name, page: page.page_number, thumbnail: page.thumbnail },
        }));
      });

      (parsed.skipped || []).forEach(s => showToast(`${s.file}: ${s.reason}`, 'warning'));
      if ((parsed.warnings || []).length) {
        showEstimatorNotice(parsed.warnings.join('  •  '), 'warning');
      }

      document.getElementById('est-dropzone').classList.add('est-dropzone-compact');
      document.getElementById('est-clear-btn').style.display = '';
      renderEstimatorPages();
      recalcEstimate();
      showToast(`${parsed.drawings.length} drawing page(s) parsed.`, 'success');
    });
  }).catch(function (err) {
    document.getElementById('est-loading').classList.add('hidden');
    showToast('Drawing import failed: ' + err, 'error');
  });
}

function clearEstimator() {
  if (estimatorSpecs.length && !confirm('Clear all uploaded drawings and their estimates?')) return;
  estimatorSpecs = [];
  estimatorPages = [];
  estimatorResults = [];
  estimatorSummary = null;
  document.getElementById('est-pages').innerHTML = '';
  document.getElementById('est-summary').innerHTML = '';
  document.getElementById('est-notice').classList.add('hidden');
  document.getElementById('est-dropzone').classList.remove('est-dropzone-compact');
  document.getElementById('est-clear-btn').style.display = 'none';
}

// --- Rendering -------------------------------------------------------------

function renderEstimatorPages() {
  const container = document.getElementById('est-pages');
  if (!estimatorSpecs.length) { container.innerHTML = ''; return; }

  let html = '';
  estimatorSpecs.forEach(function (spec, idx) {
    const page = estimatorPages[idx];
    const conf = spec.confidence || 'none';
    const typeOptions = estimatorOptions.item_types
      .map(t => `<option value="${t.key}" ${spec.item_type === t.key ? 'selected' : ''}>${esc(t.label)}</option>`).join('');
    const finishOptions = estimatorOptions.finishes
      .map(f => `<option value="${f.key}" ${spec.finish === f.key ? 'selected' : ''}>${esc(f.label)}</option>`).join('');
    const substrateOptions = ['<option value="">Default (MDF 18mm)</option>'].concat(
      estimatorOptions.substrates.map(s =>
        `<option value="${s.code}" ${spec.substrate === s.code ? 'selected' : ''}>${esc(s.label)} — ${money(s.cost)}</option>`)
    ).join('');
    const framingOptions = ['<option value="">Default (2"x2" studs)</option>'].concat(
      estimatorOptions.framing.map(f =>
        `<option value="${f.code}" ${spec.framing === f.code ? 'selected' : ''}>${esc(f.label)} — ${money(f.cost)}</option>`)
    ).join('');

    html += `
      <div class="est-card anim-in" style="animation-delay:${idx * 50}ms;">
        <div class="est-card-head">
          <div class="est-card-title">
            <span class="est-index">${idx + 1}</span>
            <span>${esc(spec.label)}</span>
          </div>
          <div class="est-card-meta">
            <span class="est-chip">${esc(page.file_name)} · p${page.page_number}/${page.page_count}</span>
            <span class="est-chip est-chip-${page.text_source}">${page.text_source === 'vector' ? 'Vector text' : page.text_source === 'ocr' ? 'OCR' : 'No text'}</span>
            <span class="est-chip est-conf-${conf}" title="${esc(CONFIDENCE_LABELS[conf] || '')}">${conf}</span>
          </div>
        </div>

        <div class="est-split">
          <!-- LEFT: the drawing itself -->
          <div class="est-visual">
            <img src="${page.thumbnail}" alt="${esc(spec.label)}" onclick="openEstimatorPreview(${idx})">
            <div class="est-visual-cap">
              ${page.width_px} × ${page.height_px} px${spec.source_text ? ` · read “${esc(spec.source_text)}”` : ''}
            </div>
            ${(page.warnings || []).map(w => `<div class="est-warn">${icon('alert', 'icon-sm')}<span>${esc(w)}</span></div>`).join('')}
          </div>

          <!-- RIGHT: overrides + live cost -->
          <div class="est-specs">
            <div class="est-field-grid">
              <div class="est-field est-field-wide">
                <label>Item label</label>
                <input type="text" class="input" value="${esc(spec.label)}"
                       onchange="estSet(${idx},'label',this.value)">
              </div>
              <div class="est-field">
                <label>Type</label>
                <select class="input" onchange="estSet(${idx},'item_type',this.value)">${typeOptions}</select>
              </div>
              <div class="est-field">
                <label>Qty</label>
                <input type="number" class="input" min="1" step="1" value="${spec.quantity || 1}"
                       onchange="estSet(${idx},'quantity',this.value)">
              </div>
              <div class="est-field">
                <label>Length (m)</label>
                <input type="number" class="input" min="0" step="0.01" value="${spec.length_m || 0}"
                       onchange="estSet(${idx},'length_m',this.value)">
              </div>
              <div class="est-field">
                <label>Height (m)</label>
                <input type="number" class="input" min="0" step="0.01" value="${spec.height_m || 0}"
                       onchange="estSet(${idx},'height_m',this.value)">
              </div>
              <div class="est-field">
                <label>Depth (m)</label>
                <input type="number" class="input" min="0" step="0.01" value="${spec.depth_m || 0}"
                       onchange="estSet(${idx},'depth_m',this.value)" placeholder="auto">
              </div>
              <div class="est-field">
                <label>Clad faces</label>
                <input type="number" class="input" min="1" max="2" step="1" value="${spec.faces || 1}"
                       onchange="estSet(${idx},'faces',this.value)">
              </div>
              <div class="est-field est-field-wide">
                <label>Finish system</label>
                <select class="input" onchange="estSet(${idx},'finish',this.value)">${finishOptions}</select>
              </div>
              <div class="est-field est-field-wide">
                <label>Substrate board</label>
                <select class="input" onchange="estSet(${idx},'substrate',this.value)">${substrateOptions}</select>
              </div>
              <div class="est-field est-field-wide">
                <label>Framing</label>
                <select class="input" onchange="estSet(${idx},'framing',this.value)">${framingOptions}</select>
              </div>
              <div class="est-field">
                <label>LED strip (m)</label>
                <input type="number" class="input" min="0" step="0.1" value="${spec.led_meters || 0}"
                       onchange="estSet(${idx},'led_meters',this.value)">
              </div>
            </div>

            ${spec.assumed_unit ? `<div class="est-warn">${icon('alert', 'icon-sm')}<span>Units weren't stated on the drawing — read as millimetres. Check the dimensions above.</span></div>` : ''}

            <div class="est-cutouts">
              <div class="est-subhead">
                <span>Cutouts &amp; openings</span>
                <button class="btn btn-ghost btn-xs" onclick="estAddCutout(${idx})">
                  ${icon('plus', 'icon-sm')} Add
                </button>
              </div>
              <div id="est-cutouts-${idx}">${renderCutoutRows(idx)}</div>
            </div>

            <div id="est-cost-${idx}" class="est-cost"></div>
          </div>
        </div>
      </div>`;
  });

  container.innerHTML = html;
}

function renderCutoutRows(idx) {
  const cutouts = estimatorSpecs[idx].cutouts || [];
  if (!cutouts.length) {
    return '<div class="est-empty-inline">None detected — the full face is being clad.</div>';
  }
  return cutouts.map((c, ci) => `
    <div class="est-cutout-row">
      <input type="text" class="input" value="${esc(c.label || '')}" placeholder="Label"
             onchange="estSetCutout(${idx},${ci},'label',this.value)">
      <input type="number" class="input" min="0" step="0.01" value="${c.width_m || 0}" title="Width (m)"
             onchange="estSetCutout(${idx},${ci},'width_m',this.value)">
      <span class="est-x">×</span>
      <input type="number" class="input" min="0" step="0.01" value="${c.height_m || 0}" title="Height (m)"
             onchange="estSetCutout(${idx},${ci},'height_m',this.value)">
      <input type="number" class="input" min="1" step="1" value="${c.count || 1}" title="Count"
             onchange="estSetCutout(${idx},${ci},'count',this.value)">
      <button class="icon-btn" title="Remove" onclick="estRemoveCutout(${idx},${ci})">
        ${icon('close', 'icon-sm')}
      </button>
    </div>`).join('');
}

// --- Edits -----------------------------------------------------------------
// Only the cost panes and the summary re-render on a change, never the inputs — a full
// re-render would steal focus mid-edit and make the overrides unusable.

const NUMERIC_SPEC_FIELDS = ['length_m', 'height_m', 'depth_m', 'faces', 'quantity', 'led_meters'];

function estSet(idx, field, value) {
  if (!estimatorSpecs[idx]) return;
  estimatorSpecs[idx][field] = NUMERIC_SPEC_FIELDS.includes(field) ? (parseFloat(value) || 0) : value;
  recalcEstimate();
}

function estSetCutout(idx, cutIdx, field, value) {
  const cutout = (estimatorSpecs[idx].cutouts || [])[cutIdx];
  if (!cutout) return;
  cutout[field] = field === 'label' ? value : (parseFloat(value) || 0);
  recalcEstimate();
}

function estAddCutout(idx) {
  estimatorSpecs[idx].cutouts = estimatorSpecs[idx].cutouts || [];
  estimatorSpecs[idx].cutouts.push({ label: 'Opening', width_m: 0, height_m: 0, count: 1 });
  document.getElementById(`est-cutouts-${idx}`).innerHTML = renderCutoutRows(idx);
  recalcEstimate();
}

function estRemoveCutout(idx, cutIdx) {
  estimatorSpecs[idx].cutouts.splice(cutIdx, 1);
  document.getElementById(`est-cutouts-${idx}`).innerHTML = renderCutoutRows(idx);
  recalcEstimate();
}

function setEstimatorMargin(value) {
  estimatorMargin = parseFloat(value) || 0;
  recalcEstimate();
}

// --- Costing ---------------------------------------------------------------

function recalcEstimate() {
  if (!api() || !estimatorSpecs.length) return;

  api().compute_design_estimate({ specs: estimatorSpecs, margin_pct: estimatorMargin })
    .then(function (res) {
      if (!res.success) { showToast(res.error || 'Costing failed.', 'error'); return; }
      estimatorResults = res.items;
      estimatorSummary = res.summary;

      res.items.forEach(function (item, idx) {
        const target = document.getElementById(`est-cost-${idx}`);
        if (target) target.innerHTML = renderItemCost(item);
      });
      (res.errors || []).forEach(e => showToast(e, 'warning'));
      renderEstimatorSummary();
    }).catch(function (err) {
      showToast('Costing failed: ' + err, 'error');
    });
}

function renderItemCost(item) {
  const materialRows = item.materials.map(m => `
    <tr>
      <td><span class="est-code">${esc(m.code)}</span> ${esc(m.description)}</td>
      <td class="num">${m.qty}</td>
      <td>${esc(m.unit)}</td>
      <td class="num">${money(m.unit_cost)}</td>
      <td class="num strong">${money(m.line_cost)}</td>
    </tr>
    <tr class="est-basis-row"><td colspan="5">${esc(m.basis)}</td></tr>`).join('');

  const laborRows = item.labor.map(l => `
    <tr>
      <td>Labor — ${esc(l.trade)}</td>
      <td class="num">${l.hours}</td>
      <td>Hrs</td>
      <td class="num">${money(l.rate)}</td>
      <td class="num strong">${money(l.cost)}</td>
    </tr>
    <tr class="est-basis-row"><td colspan="5">${esc(l.basis)}</td></tr>`).join('');

  const surfaceRows = item.surfaces.map(s =>
    `<li><span>${esc(s.name)}</span><code>${esc(s.formula)}</code><b>${s.area_m2.toFixed(2)} m²</b></li>`
  ).join('');

  return `
    <div class="est-area-strip">
      <ul class="est-surfaces">${surfaceRows}</ul>
      <div class="est-area-math">
        <span>Gross <b>${item.gross_area_m2.toFixed(2)} m²</b></span>
        <span>− Cutouts <b>${item.cutout_area_m2.toFixed(2)} m²</b></span>
        <span class="est-net">= Net clad <b>${item.net_area_m2.toFixed(2)} m²</b></span>
      </div>
    </div>

    <table class="est-table">
      <thead><tr><th>Item</th><th class="num">Qty</th><th>Unit</th><th class="num">Rate</th><th class="num">Cost</th></tr></thead>
      <tbody>${materialRows}${laborRows}</tbody>
      <tfoot>
        <tr>
          <td colspan="4">Materials ${item.quantity > 1 ? `× ${item.quantity} units` : ''}</td>
          <td class="num strong">${money(item.material_cost)}</td>
        </tr>
        <tr>
          <td colspan="4">Labor — ${item.labor_hours} hrs</td>
          <td class="num strong">${money(item.labor_cost)}</td>
        </tr>
        <tr class="est-total-row">
          <td colspan="4">Factory cost</td>
          <td class="num strong">${money(item.factory_cost)}</td>
        </tr>
      </tfoot>
    </table>`;
}

function renderEstimatorSummary() {
  const container = document.getElementById('est-summary');
  if (!estimatorSummary) { container.innerHTML = ''; return; }
  const s = estimatorSummary;

  const materialRows = s.consolidated_materials.map(m => `
    <tr>
      <td><span class="est-code">${esc(m.code)}</span> ${esc(m.description)}</td>
      <td>${esc(m.category)}</td>
      <td class="num">${m.qty}</td>
      <td>${esc(m.unit)}</td>
      <td class="num">${money(m.unit_cost)}</td>
      <td class="num strong">${money(m.line_cost)}</td>
    </tr>`).join('');

  const laborRows = s.labor_by_trade.map(l => `
    <tr>
      <td colspan="2">Labor — ${esc(l.trade)}</td>
      <td class="num">${l.hours}</td>
      <td>Hrs</td>
      <td class="num">${money(l.rate)}</td>
      <td class="num strong">${money(l.cost)}</td>
    </tr>`).join('');

  container.innerHTML = `
    <div class="est-master">
      <div class="est-master-head">
        ${icon('trending', 'icon')}
        <div>
          <div class="est-master-title">Master Summary</div>
          <div class="est-master-sub">
            ${s.item_count} item(s) · ${s.total_units} unit(s) · ${s.total_net_area_m2.toFixed(2)} m² clad
          </div>
        </div>
      </div>

      <table class="est-table est-table-master">
        <thead><tr><th>Consolidated take-off</th><th>Category</th><th class="num">Qty</th><th>Unit</th><th class="num">Rate</th><th class="num">Cost</th></tr></thead>
        <tbody>${materialRows}${laborRows}</tbody>
      </table>

      <div class="est-totals">
        <div class="est-total-line"><span>Total materials</span><b>${money(s.total_material_cost)}</b></div>
        <div class="est-total-line"><span>Total labor (${s.total_labor_hours} hrs)</span><b>${money(s.total_labor_cost)}</b></div>
        <div class="est-total-line est-total-factory"><span>Factory cost</span><b>${money(s.factory_cost)}</b></div>
        <div class="est-total-line est-margin-line">
          <span>Margin
            <input type="number" class="input est-margin-input" min="0" step="1" value="${s.margin_pct}"
                   onchange="setEstimatorMargin(this.value)"> %
          </span>
          <b>${money(s.margin_amount)}</b>
        </div>
        <div class="est-total-line est-total-selling">
          <span>Client selling price</span><b>${money(s.selling_price)}</b>
        </div>
      </div>

      <div class="est-actions">
        <label class="est-check">
          <input type="checkbox" id="est-factory-sheet" checked>
          Also write the Factory Production BOQ sheet
        </label>
        <button class="btn btn-primary" onclick="mergeDesignsToProposal()">
          ${icon('arrowRight', 'icon-sm')} Merge All Drawings to Proposal
        </button>
      </div>
      <p class="est-fineprint">
        Client lines are added to the Compiler draft at the marked-up rate. The factory sheet
        is written at raw factory cost and is never part of the client document.
      </p>
    </div>`;
}

// --- Export ----------------------------------------------------------------

function mergeDesignsToProposal() {
  if (!api() || !estimatorSpecs.length) return;

  const includeFactory = document.getElementById('est-factory-sheet').checked;
  const clientName = document.getElementById('client-name-input').value.trim() || 'Client';

  api().merge_designs_to_proposal({
    specs: estimatorSpecs,
    margin_pct: estimatorMargin,
    client_name: clientName,
    include_factory_sheet: includeFactory,
  }).then(function (res) {
    if (!res.success) { showToast(res.error || 'Merge failed.', 'error'); return; }

    res.client_items.forEach(function (row) {
      draftItems.push(Object.assign({ id: uid() }, row));
    });
    renderDraft();

    if (res.factory_sheet) {
      showToast('Factory BOQ written: ' + res.factory_sheet, 'success', 8000);
    }
    showToast(`${res.client_items.length} design item(s) added to the draft quote.`, 'success');
    switchTab('compiler');
  }).catch(function (err) {
    showToast('Merge failed: ' + err, 'error');
  });
}

function openEstimatorPreview(idx) {
  const page = estimatorPages[idx];
  if (!page) return;
  const overlay = document.createElement('div');
  overlay.className = 'est-lightbox';
  overlay.innerHTML = `<img src="${page.thumbnail}" alt="${esc(page.file_name)}">`;
  overlay.addEventListener('click', () => overlay.remove());
  document.body.appendChild(overlay);
}
