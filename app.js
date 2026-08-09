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
let catalogCache = [];
let editingCatalogItemId = null;

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
  el.setAttribute('role', 'status');
  el.innerHTML = `${icon(TOAST_ICONS[type] || 'sparkles', 'icon toast-icon')}<div class="toast-msg">${esc(message)}</div><button type="button" class="toast-close" aria-label="Dismiss">${icon('close', 'icon-sm')}</button>`;
  container.appendChild(el);

  const dismiss = () => {
    if (!el.parentNode) return;
    el.classList.add('closing');
    setTimeout(() => el.remove(), 260);
  };
  el.querySelector('.toast-close').addEventListener('click', dismiss);
  // Hovering to read a longer message used to only ever pause the clock — moving the
  // mouse away left it paused forever, so the toast would sit there until manually closed.
  let timer = setTimeout(dismiss, duration);
  el.addEventListener('mouseenter', () => clearTimeout(timer));
  el.addEventListener('mouseleave', () => { timer = setTimeout(dismiss, duration); });
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
    else if (document.getElementById('catalog-item-modal-overlay').classList.contains('open')) closeCatalogItemModal();
    else if (document.getElementById('client-ledger-modal-overlay').classList.contains('open')) closeClientLedgerModal();
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
initTabsKeyboardNav();
initWorkspaceSplitter();
initCompilerVSplit();

window.addEventListener('pywebviewready', bootBackend);
setTimeout(function () { if (api()) bootBackend(); }, 800);

function bootBackend() {
  checkDbStatus();
  updateAnalyticsDashboard();
  applyCompanyBranding();
  loadHomeDashboard();
  refreshCatalogCache();
}

// Warms catalogCache in the background so the Compiler's "Est. Margin" line has cost data
// to look up without making the PM wait — margin is a nice-to-know, not blocking.
function refreshCatalogCache() {
  if (!api()) return;
  api().get_catalog_items().then(function (res) {
    if (res.success) catalogCache = res.items;
  }).catch(function () { /* non-critical */ });
}

function loadMarginStat() {
  const el = document.getElementById('stat-margin-month');
  if (!el || !api()) return;
  api().get_margin_summary(30).then(function (res) {
    if (res.success) el.innerText = money(res.summary.total_margin) + ' AED';
  }).catch(function () { /* non-critical */ });
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
  loadMarginStat();
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
        <button type="button" class="home-recent-item anim-in" style="animation-delay:${idx * 40}ms;" onclick="cloneHistoryItem(${q.id})">
          <div style="min-width:0;">
            <div class="home-recent-client">${esc(q.client_name)}</div>
            <div class="home-recent-meta">${icon('pin', 'icon-sm')} ${esc(q.venue || '-')} &middot; ${esc(q.quote_date)}</div>
          </div>
          <div style="text-align:right;flex-shrink:0;">
            <div class="home-recent-total">${money(q.grand_total)} AED</div>
            <span class="status-pill ${pillClass}" style="margin-top:3px;">${esc(q.status || 'Sent')}</span>
          </div>
        </button>`;
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
    splitter.setAttribute('aria-valuemax', Math.round(maxFooter));
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

const TAB_TITLES = { home: 'Home', compiler: 'Compiler Workspace', catalog: 'Item Catalog', jobs: 'Jobs', review: 'Needs Review', history: 'Quotation History', estimator: 'Automated Design Estimator' };
// Home has its own hero; Review/History/Estimator already carry a panel title. Only
// Compiler gets the shared page-head, since it's the one view that never had a headline.
const TAB_EYEBROWS = { compiler: 'Quotation Builder' };

function switchTab(tab) {
  document.getElementById('view-home').classList.toggle('hidden', tab !== 'home');
  document.getElementById('view-compiler').classList.toggle('hidden', tab !== 'compiler');
  document.getElementById('view-catalog').classList.toggle('hidden', tab !== 'catalog');
  document.getElementById('view-jobs').classList.toggle('hidden', tab !== 'jobs');
  document.getElementById('view-history').classList.toggle('hidden', tab !== 'history');
  document.getElementById('view-review').classList.toggle('hidden', tab !== 'review');
  document.getElementById('view-estimator').classList.toggle('hidden', tab !== 'estimator');

  document.querySelectorAll('.nav-item').forEach(function (s) {
    const isActive = s.getAttribute('data-tab') === tab;
    s.classList.toggle('active', isActive);
    s.setAttribute('aria-selected', String(isActive));
    s.tabIndex = isActive ? 0 : -1;
  });

  // The topbar stays visible on every tab now (not just Compiler), so its title/eyebrow
  // always describe whichever view is open.
  document.getElementById('page-eyebrow').innerText = TAB_EYEBROWS[tab] || '';
  document.getElementById('page-title').innerText = TAB_TITLES[tab];

  if (tab === 'home') loadHomeDashboard();
  if (tab === 'catalog') loadCatalog();
  if (tab === 'jobs') loadJobs();
  if (tab === 'history') loadHistory();
  if (tab === 'review') loadReviewQueue();
  if (tab === 'estimator') loadEstimatorOptions();
}

// Arrow-key traversal for the tablist, per the standard ARIA tabs pattern: Up/Down move
// focus and activate the neighboring item (Home/End jump to the first/last) — Up/Down
// rather than Left/Right now that navigation is a vertical sidebar list.
function initTabsKeyboardNav() {
  const wrap = document.getElementById('segwrap');
  if (!wrap) return;
  wrap.addEventListener('keydown', function (e) {
    const tabs = Array.from(wrap.querySelectorAll('.nav-item'));
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex === -1) return;
    let nextIndex = null;
    if (e.key === 'ArrowDown') nextIndex = (currentIndex + 1) % tabs.length;
    else if (e.key === 'ArrowUp') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') nextIndex = 0;
    else if (e.key === 'End') nextIndex = tabs.length - 1;
    else return;
    e.preventDefault();
    const next = tabs[nextIndex];
    next.focus();
    switchTab(next.getAttribute('data-tab'));
  });
}

function goToNewQuotation() {
  switchTab('compiler');
  setTimeout(() => { const el = document.getElementById('search-input'); if (el) el.focus(); }, 50);
}

function goToSync() {
  openSettingsModal();
  setTimeout(() => { const el = document.getElementById('folder-path-input'); if (el) el.focus(); }, 50);
}

// ---------------------------------------------------------------------------
// Modal focus management — a closed modal used to leave its inputs keyboard-focusable
// (only opacity/pointer-events changed, not visibility), so Tab could reach a hidden
// "Sync & Build Index" button and Enter would fire it. Now that CSS gates visibility too,
// pair every open with a focus trap and every close with focus restored to whatever
// triggered it.
let _lastFocusedBeforeModal = null;

function trapFocus(overlayEl) {
  const focusable = overlayEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  function handler(e) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  overlayEl._focusTrapHandler = handler;
  overlayEl.addEventListener('keydown', handler);
  first.focus();
}

function releaseFocusTrap(overlayEl) {
  if (overlayEl._focusTrapHandler) {
    overlayEl.removeEventListener('keydown', overlayEl._focusTrapHandler);
    overlayEl._focusTrapHandler = null;
  }
  if (_lastFocusedBeforeModal && document.body.contains(_lastFocusedBeforeModal)) {
    _lastFocusedBeforeModal.focus();
  }
  _lastFocusedBeforeModal = null;
}

function openModal(overlayEl) {
  _lastFocusedBeforeModal = document.activeElement;
  overlayEl.classList.add('open');
  // visibility just flipped from hidden this frame — give the browser a tick before
  // querying/focusing descendants.
  setTimeout(() => trapFocus(overlayEl), 0);
}
function closeModal(overlayEl) {
  overlayEl.classList.remove('open');
  releaseFocusTrap(overlayEl);
}

function openSettingsModal() { openModal(document.getElementById('settings-modal-overlay')); }
function closeSettingsModal() { closeModal(document.getElementById('settings-modal-overlay')); }

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
    const imageHtml = m.image_src
      ? `<img src="${esc(m.image_src)}" loading="lazy"/>${borrowed ? `<span class="borrowed-badge" title="${esc(m.image_source)}">ref</span>` : ''}`
      : icon('image', 'icon-lg');
    html += `
      <div class="match-card anim-in" style="animation-delay:${idx * 45}ms;" role="button" tabindex="0"
           onclick='addMatchedItemToDraft(${JSON.stringify(m).replace(/'/g, '&apos;')})'
           onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}">
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
            <div style="font-size:10px;font-weight:700;color:var(--accent);display:flex;align-items:center;gap:4px;">Add to draft ${icon('arrowRight', 'icon-sm')}</div>
          </div>
        </div>
      </div>`;
  });
  container.innerHTML = html;
}

function addMatchedItemToDraft(item) {
  const rate = item.adjusted_rate || item.original_rate;
  draftItems.push({
    id: uid(), description: item.description, unit: item.unit || 'Pcs', qty: 1,
    rate: rate, baseRate: rate, pctAdjust: 0,
    image_ref: item.image_ref || '', image_src: item.image_src || '',
    image_source: item.image_source || '',
  });
  renderDraft();
}

function addCustomDraftRow() {
  draftItems.push({ id: uid(), description: 'Custom Event Production Item', unit: 'Pcs', qty: 1, rate: 0, baseRate: 0, pctAdjust: 0, image_ref: '', image_src: '', image_source: '' });
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
    const thumb = item.image_src
      ? `<img src="${esc(item.image_src)}" loading="lazy"/>${isBorrowedPhoto(item.image_source) ? `<span class="borrowed-badge" title="${esc(item.image_source)}">ref</span>` : ''}`
      : icon('image', 'icon');
    const unitOptionsHtml = UNIT_OPTIONS.map(u => `<option value="${u}" ${item.unit === u ? 'selected' : ''}>${u}</option>`).join('');
    html += `
      <div class="draft-item anim-in" style="animation-delay:${idx * 40}ms;">
        <div class="draft-item-head">
          <span style="font-size:10px;color:var(--text-muted);font-weight:700;">ITEM #${idx + 1}</span>
          <div style="display:flex;gap:10px;">
            ${item.image_ref ? `<button type="button" class="icon-btn" style="width:26px;height:26px;color:var(--accent-strong);" onclick="saveDraftImageToLibrary('${item.id}')" title="Save this photo to the reusable library">${icon('sparkles', 'icon-sm')}</button>` : ''}
            <button type="button" class="icon-btn" style="width:26px;height:26px;" onclick="openImagePicker('${item.id}')" title="Set image">${icon('image', 'icon-sm')}</button>
            <button type="button" class="icon-btn" style="width:26px;height:26px;color:var(--danger);" onclick="deleteDraftItem('${item.id}')" title="Remove">${icon('trash', 'icon-sm')}</button>
          </div>
        </div>
        <div style="display:flex;gap:8px;">
          <button type="button" class="draft-thumb" id="draft-thumb-${item.id}" onclick="openImagePicker('${item.id}')" aria-label="Set image">${thumb}</button>
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
          <button class="pct-btn" onclick="resetRate('${item.id}')" title="Reset to ${money(item.baseRate != null ? item.baseRate : item.rate)} AED">Reset</button>
        </div>
        <div class="num" style="text-align:right;margin-top:6px;font-size:11px;color:var(--text-secondary);">
          Subtotal: <b class="num-strong draft-subtotal" style="color:var(--text-primary);">${money(item.qty * item.rate)} AED</b>
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
  // A manually typed rate is a new reference point, not a nudge — rebase so the +/-% buttons
  // work off what the PM just typed instead of silently snapping back toward the old value.
  if (key === 'rate') { item.baseRate = val; item.pctAdjust = 0; }
  if (key === 'qty' || key === 'rate') updateSummary();
}

// pct is a percentage OFF THE ORIGINAL RATE, not a repeated multiply-in-place — +10% then
// -10% now returns exactly to baseRate instead of landing 1% short from compounding on an
// already-adjusted number. Patches just this row's DOM instead of calling renderDraft(),
// which used to rebuild the whole list and move focus to <body> on every click.
function adjustRate(id, pct) {
  const item = draftItems.find(i => i.id === id);
  if (!item) return;
  if (typeof item.baseRate !== 'number') item.baseRate = item.rate;
  if (typeof item.pctAdjust !== 'number') item.pctAdjust = 0;
  item.pctAdjust = Math.round((item.pctAdjust + pct) * 10000) / 10000;
  item.rate = Math.round(item.baseRate * (1 + item.pctAdjust) * 100) / 100;
  patchDraftRowRate(item);
}

function resetRate(id) {
  const item = draftItems.find(i => i.id === id);
  if (!item) return;
  item.pctAdjust = 0;
  item.rate = typeof item.baseRate === 'number' ? item.baseRate : item.rate;
  patchDraftRowRate(item);
}

function patchDraftRowRate(item) {
  const input = document.getElementById('rate-input-' + item.id);
  if (input) input.value = item.rate;
  const row = input && input.closest('.draft-item');
  const subtotalEl = row && row.querySelector('.draft-subtotal');
  if (subtotalEl) subtotalEl.innerText = money(item.qty * item.rate) + ' AED';
  updateSummary();
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

// Exact normalized-text match against the catalog cache, same rule as catalog_db's
// find_catalog_item_by_description on the backend — a description that isn't in the
// catalog just means no margin data for that line, not an error.
function findCatalogCost(description) {
  const key = (description || '').trim().toLowerCase();
  if (!key) return null;
  const match = catalogCache.find(c => (c.description || '').trim().toLowerCase() === key);
  return (match && match.cost_price != null) ? Number(match.cost_price) : null;
}

function updateSummary() {
  let subtotal = 0;
  let costTotal = 0;
  let itemsWithCost = 0;
  draftItems.forEach(i => {
    const qty = Number(i.qty) || 0;
    subtotal += qty * (Number(i.rate) || 0);
    const cost = findCatalogCost(i.description);
    if (cost != null) { costTotal += qty * cost; itemsWithCost++; }
  });

  const marginRow = document.getElementById('summary-margin-row');
  if (itemsWithCost > 0) {
    marginRow.classList.remove('hidden');
    document.getElementById('summary-margin').innerText = money(subtotal - costTotal) + ' AED';
  } else {
    marginRow.classList.add('hidden');
  }

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
  document.getElementById('image-url-input').value = '';
  document.getElementById('image-search-results').innerHTML = '';
  document.getElementById('image-search-query').value = (item ? item.description.split('\n')[0] : '').slice(0, 60);
  switchImagePickerTab('library');
  openModal(document.getElementById('image-picker-overlay'));
}
function closeImagePicker() {
  closeModal(document.getElementById('image-picker-overlay'));
  currentImagePickerItemId = null;
}
function switchImagePickerTab(tab) {
  ['library', 'search', 'url', 'upload'].forEach(t => {
    const isActive = t === tab;
    const tabEl = document.getElementById('img-tab-' + t);
    tabEl.classList.toggle('active', isActive);
    tabEl.setAttribute('aria-selected', String(isActive));
    document.getElementById('img-panel-' + t).classList.toggle('hidden', !isActive);
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
    // Held by index and referenced from the handler rather than serialized into it — the
    // src is now a short URL, but the description still has no business inside an attribute.
    lastLibraryMatches = res.matches;
    results.innerHTML = `<div class="image-grid">${res.matches.map((m, i) => `
      <div style="position:relative;">
        <img src="${esc(m.image_src)}" loading="lazy" onclick="applyLibraryMatch(${i})" title="${esc(m.description)}"/>
        <span class="chip chip-accent" style="position:absolute;bottom:4px;left:4px;font-size:10px;padding:1px 6px;">${m.similarity}%</span>
      </div>`).join('')}</div>`;
  }).catch(function (err) {
    results.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(err)}</span></div>`;
  });
}

function applyLibraryMatch(idx) {
  const m = lastLibraryMatches[idx];
  if (m) applyImageToItem(m.image_ref, m.image_src);
}

function saveDraftImageToLibrary(itemId) {
  if (!api()) return;
  const item = draftItems.find(i => i.id === itemId);
  if (!item || !item.image_ref) return;
  api().save_photo_to_library(item.description, item.image_ref).then(function (res) {
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
    if (res.success) applyImageToItem(res.image_ref, res.image_src, '', targetId);
    else showToast('Could not fetch that image: ' + res.error, 'error');
  });
}
function pasteImageUrl() {
  const url = document.getElementById('image-url-input').value.trim();
  if (!url || !api()) return;
  const targetId = currentImagePickerItemId;
  api().fetch_image_from_url(url).then(function (res) {
    if (res.success) applyImageToItem(res.image_ref, res.image_src, '', targetId);
    else showToast('Could not fetch that image: ' + res.error, 'error');
  });
}
function uploadImageForItem() {
  if (!api()) return;
  const targetId = currentImagePickerItemId;
  api().upload_image_dialog().then(function (res) {
    if (res.success) applyImageToItem(res.image_ref, res.image_src, '', targetId);
    else if (res.error !== 'No file selected.') showToast('Upload failed: ' + res.error, 'error');
  });
}
// targetId pins the image to the row the picker was opened for. Fetches are async, so
// without it a slow download lands on whichever row is selected when it finally resolves —
// or is dropped entirely if the picker was closed in the meantime.
function applyImageToItem(ref, src, source, targetId) {
  const id = targetId || currentImagePickerItemId;
  const item = draftItems.find(i => i.id === id);
  if (item) {
    item.image_ref = ref || '';
    item.image_src = src || '';
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
    items: draftItems.map(i => ({ description: i.description, unit: i.unit, qty: i.qty, rate: i.rate, image_ref: i.image_ref })),
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
      <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">${icon('clock', 'icon-sm')} Valid until ${esc(res.valid_until || '')}</div>
    </div>
    ${filesHtml}
    <div class="share-btn-row">
      <button type="button" class="share-btn" onclick="shareViaWhatsapp()">${icon('chat', 'icon-lg')}<span>WhatsApp</span></button>
      <button type="button" class="share-btn" onclick="shareViaEmail()">${icon('mail', 'icon-lg')}<span>Email</span></button>
      <button type="button" class="share-btn" onclick="reopenPdf()">${icon('link', 'icon-lg')}<span>Open File</span></button>
    </div>
  `;
  openModal(document.getElementById('success-modal-overlay'));
}
function closeSuccessModal() { closeModal(document.getElementById('success-modal-overlay')); }
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
const HISTORY_COLSPAN = 10;

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

// A quote only becomes an invoice once it's Won — payment fields would be meaningless
// (and misleading) to show while it's still just Sent or has been marked Lost.
function paymentCellHtml(q) {
  if ((q.status || 'Sent') !== 'Won') return `<span style="color:var(--text-muted);">-</span>`;
  const paymentStatus = q.payment_status || 'Unpaid';
  const amountPaid = Number(q.amount_paid) || 0;
  const balance = Math.max(0, (Number(q.grand_total) || 0) - amountPaid);
  const options = ['Unpaid', 'Partial', 'Paid'].map(s => `<option value="${s}" ${s === paymentStatus ? 'selected' : ''}>${s}</option>`).join('');
  const pillClass = paymentStatus === 'Paid' ? 'status-pill-won' : (paymentStatus === 'Partial' ? 'status-pill-sent' : 'status-pill-lost');
  return `
    <div style="display:flex;flex-direction:column;gap:3px;min-width:126px;">
      <span class="status-pill ${pillClass}"><select class="status-select" onchange="updatePayment(${q.id}, this.value, null)">${options}</select></span>
      <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-muted);">
        Paid <input type="number" min="0" step="0.01" class="input" style="width:64px;padding:2px 5px;font-size:10px;" value="${amountPaid}" onchange="updatePayment(${q.id}, null, parseFloat(this.value)||0)">
      </div>
      <div class="num" style="font-size:10px;color:${balance > 0 ? 'var(--danger)' : 'var(--success)'};">Bal: ${money(balance)} AED</div>
    </div>`;
}

function updatePayment(id, status, amount) {
  if (!api()) return;
  const item = historyCache.find(h => h.id === id);
  if (!item) return;
  const finalStatus = status != null ? status : (item.payment_status || 'Unpaid');
  const finalAmount = amount != null ? amount : (Number(item.amount_paid) || 0);
  api().update_payment(id, finalStatus, finalAmount).then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not update payment.', 'error'); return; }
    item.payment_status = finalStatus;
    item.amount_paid = finalAmount;
    renderHistoryTable(applyHistoryFilters(historyCache));
    showToast(`Payment updated for #${id}.`, 'success');
  }).catch(function (err) {
    showToast('Error updating payment: ' + err, 'error');
  });
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
        <td><button type="button" class="client-link" onclick="openClientLedgerForQuote(${q.id})" title="View this client's full history">${esc(q.client_name)}</button></td>
        <td><span class="chip chip-muted">${icon('pin', 'icon-sm')} ${esc(q.venue || '-')}</span></td>
        <td>${esc(q.quote_date)}</td>
        <td>${esc(q.valid_until || '-')}</td>
        <td>${q.item_count}</td>
        <td class="num num-strong">${money(q.grand_total)} AED</td>
        <td>${statusPillHtml(q.id, q.status)}</td>
        <td>${paymentCellHtml(q)}</td>
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
  // Loading a past quote overwrites the draft wholesale — ask first, or a PM mid-edit on a
  // real quote loses it the instant they click a Recent Quotation card by mistake.
  if (draftItems.length > 0 && !confirm(`Load this quotation into the Compiler? Your current draft (${draftItems.length} item${draftItems.length === 1 ? '' : 's'}) will be replaced.`)) return;
  api().get_history_item(id).then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    const q = res.item;
    draftItems = (q.items || []).map(it => ({ id: uid(), description: it.description, unit: it.unit || 'Pcs', qty: it.qty || 1, rate: it.rate || 0, baseRate: it.rate || 0, pctAdjust: 0, image_ref: it.image_ref || '', image_src: it.image_src || '' }));
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
// Client ledger — derived from quotations grouped by client, no standalone clients table.
// ---------------------------------------------------------------------------
function openClientLedgerForQuote(quoteId) {
  const q = historyCache.find(h => h.id === quoteId);
  if (!q) return;
  openClientLedger(q.client_name, q.client_phone);
}

function openClientLedger(clientName, clientPhone) {
  if (!api()) { showToast('Backend connection missing.', 'error'); return; }
  document.getElementById('client-ledger-modal-title').innerText = clientName || 'Client Ledger';
  const body = document.getElementById('client-ledger-modal-body');
  body.innerHTML = skeletonCards(2);
  openModal(document.getElementById('client-ledger-modal-overlay'));
  api().get_client_ledger(clientName, clientPhone).then(function (res) {
    if (!res.success) { body.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(res.error)}</span></div>`; return; }
    renderClientLedger(res.ledger);
  }).catch(function (err) {
    body.innerHTML = `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(err)}</span></div>`;
  });
}

function renderClientLedger(ledger) {
  const body = document.getElementById('client-ledger-modal-body');
  const summary = `
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px;">
      <div class="stat-card"><div><div class="stat-label">Total Billed</div><div class="stat-value">${money(ledger.total_billed)} AED</div></div></div>
      <div class="stat-card"><div><div class="stat-label">Total Paid</div><div class="stat-value">${money(ledger.total_paid)} AED</div></div></div>
      <div class="stat-card"><div><div class="stat-label">Outstanding</div><div class="stat-value" style="color:${ledger.total_outstanding > 0 ? 'var(--danger)' : 'var(--success)'};">${money(ledger.total_outstanding)} AED</div></div></div>
    </div>`;
  if (ledger.items.length === 0) {
    body.innerHTML = summary + `<div class="empty-state">${icon('history', 'icon-lg')}<p>No quotations for this client yet.</p></div>`;
    return;
  }
  const rows = ledger.items.map(function (q) {
    const pillClass = q.status === 'Won' ? 'status-pill-won' : (q.status === 'Lost' ? 'status-pill-lost' : 'status-pill-sent');
    return `
      <tr>
        <td>#${q.id}</td>
        <td>${esc(q.quote_date)}</td>
        <td><span class="chip chip-muted">${icon('pin', 'icon-sm')} ${esc(q.venue || '-')}</span></td>
        <td class="num">${money(q.grand_total)} AED</td>
        <td><span class="status-pill ${pillClass}">${esc(q.status || 'Sent')}</span></td>
        <td class="num">${q.status === 'Won' ? money(q.amount_paid || 0) + ' AED' : '-'}</td>
      </tr>`;
  }).join('');
  body.innerHTML = summary + `
    <div class="history-table-wrap" style="max-height:320px;">
      <table class="history-table">
        <thead><tr><th>Ref</th><th>Date</th><th>Venue</th><th>Total</th><th>Status</th><th>Paid</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function closeClientLedgerModal() { closeModal(document.getElementById('client-ledger-modal-overlay')); }

// ---------------------------------------------------------------------------
// Item Catalog — a persistent, PM-editable item list, independent of the historical
// index that gets destructively rebuilt on every sync. This is the only place a cost_price
// lives, which is what makes margin reporting (see compileQuote) possible at all.
// ---------------------------------------------------------------------------
const CATALOG_COLSPAN = 7;

function loadCatalog() {
  const container = document.getElementById('catalog-table-body');
  if (!api()) { container.innerHTML = `<tr><td colspan="${CATALOG_COLSPAN}">Connect the backend to see the catalog.</td></tr>`; return; }
  container.innerHTML = Array(3).fill(
    `<tr><td colspan="${CATALOG_COLSPAN}"><div class="skeleton skeleton-line" style="width:100%;height:16px;"></div></td></tr>`
  ).join('');
  api().get_catalog_items().then(function (res) {
    if (!res.success) { container.innerHTML = `<tr><td colspan="${CATALOG_COLSPAN}">${esc(res.error)}</td></tr>`; return; }
    catalogCache = res.items;
    renderCatalogTable(applyCatalogFilter(catalogCache));
  });
}

function applyCatalogFilter(items) {
  const q = document.getElementById('catalog-search').value.trim().toLowerCase();
  if (!q) return items;
  return items.filter(i =>
    (i.description || '').toLowerCase().includes(q) || (i.category || '').toLowerCase().includes(q));
}

function filterCatalog() {
  renderCatalogTable(applyCatalogFilter(catalogCache));
}

function renderCatalogTable(items) {
  const container = document.getElementById('catalog-table-body');
  if (items.length === 0) {
    container.innerHTML = `<tr><td colspan="${CATALOG_COLSPAN}"><div class="empty-state">${icon('database', 'icon-lg')}<p>No catalog items yet.</p><p style="margin-top:4px;">Add your first item to start tracking cost and margin.</p></div></td></tr>`;
    return;
  }
  container.innerHTML = items.map(function (it, idx) {
    const hasCost = it.cost_price != null && it.cost_price !== '';
    const margin = hasCost ? (Number(it.rate) || 0) - Number(it.cost_price) : null;
    return `
      <tr style="animation-delay:${Math.min(idx * 30, 300)}ms;">
        <td>${esc(it.description)}</td>
        <td>${it.category ? `<span class="chip chip-muted">${esc(it.category)}</span>` : '-'}</td>
        <td>${esc(it.unit)}</td>
        <td class="num">${money(it.rate)} AED</td>
        <td class="num">${hasCost ? money(it.cost_price) + ' AED' : '-'}</td>
        <td class="num" style="color:${margin != null && margin < 0 ? 'var(--danger)' : 'var(--success)'};">${margin != null ? money(margin) + ' AED' : '-'}</td>
        <td>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="openCatalogItemModal(${it.id})">${icon('edit', 'icon-sm')} Edit</button>
            <button class="btn btn-danger-ghost btn-sm" onclick="deleteCatalogItem(${it.id})">${icon('trash', 'icon-sm')}</button>
          </div>
        </td>
      </tr>`;
  }).join('');
}

function openCatalogItemModal(itemId) {
  editingCatalogItemId = itemId || null;
  const item = itemId ? catalogCache.find(i => i.id === itemId) : null;
  document.getElementById('catalog-item-modal-title').innerText = item ? 'Edit Catalog Item' : 'Add Catalog Item';
  document.getElementById('catalog-desc-input').value = item ? item.description : '';
  document.getElementById('catalog-category-input').value = item ? (item.category || '') : '';
  document.getElementById('catalog-unit-input').value = item ? item.unit : 'Pcs';
  document.getElementById('catalog-rate-input').value = item ? item.rate : 0;
  document.getElementById('catalog-cost-input').value = item && item.cost_price != null ? item.cost_price : '';
  openModal(document.getElementById('catalog-item-modal-overlay'));
}
function closeCatalogItemModal() {
  closeModal(document.getElementById('catalog-item-modal-overlay'));
  editingCatalogItemId = null;
}

function saveCatalogItem() {
  if (!api()) { showToast('Backend connection missing.', 'error'); return; }
  const description = document.getElementById('catalog-desc-input').value.trim();
  if (!description) { showToast('Description is required.', 'warning'); return; }

  const payload = {
    id: editingCatalogItemId,
    description: description,
    category: document.getElementById('catalog-category-input').value.trim() || null,
    unit: document.getElementById('catalog-unit-input').value.trim() || 'Pcs',
    rate: parseFloat(document.getElementById('catalog-rate-input').value) || 0,
    cost_price: document.getElementById('catalog-cost-input').value.trim() === ''
      ? null : parseFloat(document.getElementById('catalog-cost-input').value) || 0,
  };

  const saveBtn = document.getElementById('catalog-save-btn');
  saveBtn.disabled = true;
  api().save_catalog_item(payload).then(function (res) {
    saveBtn.disabled = false;
    if (!res.success) { showToast(res.error || 'Could not save item.', 'error'); return; }
    showToast(editingCatalogItemId ? 'Catalog item updated.' : 'Catalog item added.', 'success');
    closeCatalogItemModal();
    loadCatalog();
  }).catch(function (err) {
    saveBtn.disabled = false;
    showToast('Error saving catalog item: ' + err, 'error');
  });
}

function deleteCatalogItem(id) {
  if (!confirm('Delete this catalog item? This does not affect any quotations already generated.')) return;
  if (!api()) return;
  api().delete_catalog_item(id).then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not delete item.', 'error'); return; }
    showToast('Catalog item removed.', 'info');
    loadCatalog();
  });
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
// Jobs — what happens after a quote is won
// ---------------------------------------------------------------------------
// A quotation says what a job should earn. Everything below is about what it
// actually cost, so margin stops being an estimate multiplied by a guess.

let jobsCache = [];
let jobStatusFilter = '';
const JOB_STATUSES = ['Planned', 'In Progress', 'Complete', 'Cancelled'];
const COST_CATEGORIES = ['Material', 'Labour', 'Transport', 'Subcontract', 'Other'];

function setJobFilter(status) {
  jobStatusFilter = status;
  document.querySelectorAll('#jobs-filter-row .status-filter-chip').forEach(function (chip) {
    chip.classList.toggle('active', chip.getAttribute('data-status') === status);
  });
  renderJobs();
}

function loadJobs() {
  if (!api()) return;
  const list = document.getElementById('jobs-list');
  list.innerHTML = skeletonCards(3);

  api().get_jobs().then(function (res) {
    if (!res.success) { list.innerHTML = bannerError(res.error); return; }
    jobsCache = res.jobs || [];
    renderJobs();
    updateJobsTabCount();
  }).catch(function (err) { list.innerHTML = bannerError(err); });

  api().get_job_margin_report(90).then(function (res) {
    if (res.success) renderJobsSummary(res.report);
  });
}

function updateJobsTabCount() {
  const badge = document.getElementById('jobs-tab-count');
  if (!badge) return;
  const active = jobsCache.filter(j => j.status === 'In Progress' || j.status === 'Planned').length;
  badge.innerText = active;
  badge.classList.toggle('hidden', active === 0);
}

function renderJobsSummary(r) {
  const el = document.getElementById('jobs-summary');
  if (!el) return;
  // How much of the period the margin actually covers is stated next to it. A margin
  // computed from two of twenty jobs is not a business figure, and presenting it
  // without that context is how the old catalog-based margin misled.
  const coverage = r.jobs_without_costs
    ? `<div class="stat-note">${r.jobs_costed} of ${r.jobs_total} jobs have costs recorded</div>`
    : `<div class="stat-note">all ${r.jobs_total} jobs costed</div>`;
  el.innerHTML = `
    <div class="stat-card"><div class="stat-label">Quoted (90 days)</div>
      <div class="stat-value">${money(r.quoted_total)}</div></div>
    <div class="stat-card"><div class="stat-label">Actual Cost</div>
      <div class="stat-value">${money(r.actual_cost)}</div></div>
    <div class="stat-card"><div class="stat-label">Margin</div>
      <div class="stat-value ${r.margin < 0 ? 'stat-danger' : ''}">${money(r.margin)}</div>
      <div class="stat-note">${r.margin_pct}%</div></div>
    <div class="stat-card"><div class="stat-label">Coverage</div>
      <div class="stat-value">${r.jobs_costed}/${r.jobs_total}</div>${coverage}</div>`;
}

function renderJobs() {
  const list = document.getElementById('jobs-list');
  const rows = jobStatusFilter ? jobsCache.filter(j => j.status === jobStatusFilter) : jobsCache;

  if (rows.length === 0) {
    list.innerHTML = `<div class="empty-state">${icon('pin', 'icon-lg')}
      <p>No jobs here yet.</p>
      <p style="margin-top:4px;">Mark a quotation Won in Invoices to open a job for it, or add one directly.</p></div>`;
    return;
  }

  list.innerHTML = rows.map(function (j, idx) {
    const pill = j.status === 'Complete' ? 'status-pill-won'
      : (j.status === 'Cancelled' ? 'status-pill-lost' : 'status-pill-sent');
    // Only claim a margin when costs exist. Otherwise say so plainly — a job with
    // nothing booked would read as 100% margin, which is worse than saying nothing.
    const marginCell = j.has_costs
      ? `<div class="job-margin ${j.margin < 0 ? 'stat-danger' : ''}">${money(j.margin)} <span class="job-margin-pct">${j.margin_pct}%</span></div>`
      : `<div class="job-margin job-margin-unknown">no costs recorded</div>`;
    return `
      <div class="job-card anim-in" style="animation-delay:${Math.min(idx * 35, 300)}ms;">
        <div class="job-card-head">
          <div style="min-width:0;">
            <div class="job-title">${esc(j.title || 'Untitled job')}</div>
            <div class="job-meta">
              <span class="chip chip-muted">${j.job_number}</span>
              <span>${esc(j.client_name || '-')}</span>
              ${j.venue ? `<span>${icon('pin', 'icon-sm')} ${esc(j.venue)}</span>` : ''}
              ${j.start_date ? `<span>${esc(j.start_date)}</span>` : ''}
            </div>
          </div>
          <div style="display:flex;gap:10px;align-items:center;flex-shrink:0;">
            <select class="input input-sm ${pill}" onchange="changeJobStatus(${j.id}, this.value)">
              ${JOB_STATUSES.map(st => `<option value="${st}" ${st === j.status ? 'selected' : ''}>${st}</option>`).join('')}
            </select>
            <button class="btn btn-ghost btn-sm" onclick="openJob(${j.id})">${icon('edit', 'icon-sm')} Costs</button>
            <button class="btn btn-danger-ghost btn-sm" onclick="removeJob(${j.id})">${icon('trash', 'icon-sm')}</button>
          </div>
        </div>
        <div class="job-figures">
          <div><span class="job-fig-label">Quoted</span><span class="job-fig">${money(j.quoted_total)}</span></div>
          <div><span class="job-fig-label">Actual</span><span class="job-fig">${money(j.actual_cost)}</span></div>
          <div><span class="job-fig-label">Margin</span>${marginCell}</div>
        </div>
      </div>`;
  }).join('');
}

function changeJobStatus(jobId, status) {
  api().update_job(jobId, { status: status }).then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    loadJobs();
  });
}

function removeJob(jobId) {
  const job = jobsCache.find(j => j.id === jobId);
  confirmAction(
    'Delete this job?',
    `${job ? job.job_number + ' — ' : ''}its recorded costs go with it. The quotation is not affected.`,
    function () {
      api().delete_job(jobId).then(function () { loadJobs(); });
    });
}

function bannerError(message) {
  return `<div class="banner banner-error">${icon('alert', 'icon')}<span>${esc(message)}</span></div>`;
}

// --- Job editor -------------------------------------------------------------

let editingJobId = null;

function openNewJob() {
  editingJobId = null;
  fillJobForm({});
  document.getElementById('job-modal-title').innerText = 'New Job';
  openModal(document.getElementById('job-modal-overlay'));
}

function editJob(jobId) {
  editingJobId = jobId;
  fillJobForm(jobsCache.find(j => j.id === jobId) || {});
  document.getElementById('job-modal-title').innerText = 'Edit Job';
  openModal(document.getElementById('job-modal-overlay'));
}

function fillJobForm(job) {
  document.getElementById('job-title-input').value = job.title || '';
  document.getElementById('job-client-input').value = job.client_name || '';
  document.getElementById('job-venue-input').value = job.venue || '';
  document.getElementById('job-quoted-input').value = job.quoted_total || 0;
  document.getElementById('job-start-input').value = job.start_date || '';
  document.getElementById('job-end-input').value = job.end_date || '';
  document.getElementById('job-contact-input').value = job.site_contact || '';
  document.getElementById('job-notes-input').value = job.notes || '';
}

function saveJob() {
  const payload = {
    title: document.getElementById('job-title-input').value.trim(),
    client_name: document.getElementById('job-client-input').value.trim(),
    venue: document.getElementById('job-venue-input').value.trim(),
    quoted_total: parseFloat(document.getElementById('job-quoted-input').value) || 0,
    start_date: document.getElementById('job-start-input').value,
    end_date: document.getElementById('job-end-input').value,
    site_contact: document.getElementById('job-contact-input').value.trim(),
    notes: document.getElementById('job-notes-input').value.trim(),
  };
  if (!payload.title) { showToast('Give the job a name.', 'error'); return; }

  const done = function (res) {
    if (res && res.success === false) { showToast(res.error, 'error'); return; }
    closeModal(document.getElementById('job-modal-overlay'));
    loadJobs();
  };
  if (editingJobId) api().update_job(editingJobId, payload).then(done);
  else api().create_job(payload).then(done);
}

function removeJob(jobId) {
  const job = jobsCache.find(j => j.id === jobId);
  if (!confirm(`Delete ${job ? job.job_number : 'this job'}?\n\nIts recorded costs go with it. The quotation is not affected.`)) return;
  api().delete_job(jobId).then(function (res) {
    if (res.success === false) { showToast(res.error, 'error'); return; }
    loadJobs();
  });
}

// --- Costs ------------------------------------------------------------------

let openJobId = null;

function openJob(jobId) {
  openJobId = jobId;
  api().get_job(jobId).then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    renderJobCosts(res.job);
    openModal(document.getElementById('job-costs-modal-overlay'));
  });
}

function renderJobCosts(job) {
  document.getElementById('job-costs-title').innerText = `${job.job_number} — ${job.title || ''}`;

  const breakdown = (job.cost_by_category || []).map(function (c) {
    return `<span class="chip chip-muted">${esc(c.category)} ${money(c.total)}</span>`;
  }).join('');
  document.getElementById('job-costs-summary').innerHTML = `
    <div class="job-figures">
      <div><span class="job-fig-label">Quoted</span><span class="job-fig">${money(job.quoted_total)}</span></div>
      <div><span class="job-fig-label">Actual</span><span class="job-fig">${money(job.actual_cost)}</span></div>
      <div><span class="job-fig-label">Margin</span>
        <span class="job-fig ${job.margin < 0 ? 'stat-danger' : ''}">${money(job.margin)} (${job.margin_pct}%)</span></div>
    </div>
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;">${breakdown}</div>`;

  const body = document.getElementById('job-costs-body');
  if (!job.costs.length) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty-state" style="padding:16px;">
      ${icon('sheet', 'icon-lg')}<p>Nothing booked against this job yet.</p>
      <p style="margin-top:4px;">Until something is, its margin is the quoted one — not a measured one.</p>
      </div></td></tr>`;
    return;
  }
  body.innerHTML = job.costs.map(function (c) {
    return `<tr>
      <td>${esc(c.cost_date || '')}</td>
      <td><span class="chip chip-muted">${esc(c.category)}</span></td>
      <td>${esc(c.description)}</td>
      <td>${esc(c.supplier_name || '-')}</td>
      <td class="num">${c.quantity || ''}</td>
      <td class="num num-strong">${money(c.amount)}</td>
      <td><button class="btn btn-danger-ghost btn-sm" onclick="removeJobCost(${c.id})">${icon('trash', 'icon-sm')}</button></td>
    </tr>`;
  }).join('');
}

function addJobCost() {
  const description = document.getElementById('cost-desc-input').value.trim();
  if (!description) { showToast('What was the cost for?', 'error'); return; }
  const amountRaw = document.getElementById('cost-amount-input').value;
  api().add_job_cost(
    openJobId, description,
    document.getElementById('cost-category-input').value,
    document.getElementById('cost-supplier-input').value.trim() || null,
    parseFloat(document.getElementById('cost-qty-input').value) || 1,
    parseFloat(document.getElementById('cost-unit-input').value) || 0,
    amountRaw === '' ? null : parseFloat(amountRaw),
    document.getElementById('cost-date-input').value || null,
    document.getElementById('cost-ref-input').value.trim()
  ).then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    ['cost-desc-input', 'cost-supplier-input', 'cost-amount-input', 'cost-ref-input'].forEach(function (id) {
      document.getElementById(id).value = '';
    });
    openJob(openJobId);
    loadJobs();
  });
}

function removeJobCost(costId) {
  api().delete_job_cost(costId).then(function () {
    openJob(openJobId);
    loadJobs();
  });
}

// --- Suppliers --------------------------------------------------------------

function openSuppliers() {
  api().get_suppliers().then(function (res) {
    if (!res.success) { showToast(res.error, 'error'); return; }
    const body = document.getElementById('suppliers-body');
    if (!res.suppliers.length) {
      body.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:16px;">
        ${icon('database', 'icon-lg')}<p>No suppliers yet.</p>
        <p style="margin-top:4px;">They are created automatically when you name one on a job cost.</p>
        </div></td></tr>`;
    } else {
      body.innerHTML = res.suppliers.map(function (sup) {
        return `<tr>
          <td>${esc(sup.name)}</td>
          <td>${esc(sup.phone || '-')}</td>
          <td>${esc(sup.email || '-')}</td>
          <td class="num">${sup.cost_entries}</td>
          <td class="num num-strong">${money(sup.total_spend)}</td>
        </tr>`;
      }).join('');
    }
    openModal(document.getElementById('suppliers-modal-overlay'));
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
          rate_overrides: {}, labor_rate_overrides: {},
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

      // Failed specs are dropped from res.items rather than left as placeholders, so the
      // array no longer lines up 1:1 with estimatorSpecs — match on the index the backend
      // stamped onto each item instead of relying on array position.
      res.items.forEach(function (item) {
        const target = document.getElementById(`est-cost-${item.spec_index}`);
        if (target) target.innerHTML = renderItemCost(item, item.spec_index);
      });

      (res.errors || []).forEach(function (e) {
        const target = document.getElementById(`est-cost-${e.index}`);
        if (target) {
          target.innerHTML = e.code
            ? estMissingMaterialForm(e.index, e.code, e.message)
            : `<div class="est-notice est-notice-error">${icon('alert', 'icon-sm')}<span>${esc(e.message)}</span></div>`;
        }
        showToast(`${e.label}: ${e.message}`, 'warning');
      });

      renderEstimatorSummary();
    }).catch(function (err) {
      showToast('Costing failed: ' + err, 'error');
    });
}

function estMissingMaterialForm(idx, code, message) {
  return `
    <div class="est-notice est-notice-error">${icon('alert', 'icon-sm')}<span>${esc(message)}</span></div>
    <div class="est-add-material">
      <div class="est-subhead"><span>Add “${esc(code)}” to the rate card</span></div>
      <div class="est-add-material-grid">
        <input type="text" class="input" id="est-mat-desc-${idx}" placeholder="Description">
        <input type="text" class="input" id="est-mat-cat-${idx}" placeholder="Category" value="Uncategorized">
        <input type="text" class="input" id="est-mat-unit-${idx}" placeholder="Unit" value="Unit">
        <input type="number" class="input" id="est-mat-cost-${idx}" placeholder="Avg cost (AED)" min="0" step="0.01">
        <button class="btn btn-primary btn-xs" onclick="estAddMaterial(${idx},'${esc(code)}')">
          ${icon('plus', 'icon-sm')} Add &amp; price
        </button>
      </div>
    </div>`;
}

function estAddMaterial(idx, code) {
  const descEl = document.getElementById(`est-mat-desc-${idx}`);
  const catEl = document.getElementById(`est-mat-cat-${idx}`);
  const unitEl = document.getElementById(`est-mat-unit-${idx}`);
  const costEl = document.getElementById(`est-mat-cost-${idx}`);
  const cost = parseFloat(costEl.value);
  if (!cost || cost <= 0) { showToast('Enter a cost greater than 0 for ' + code + '.', 'warning'); return; }

  api().add_rate_card_item({
    code: code,
    description: (descEl.value || '').trim(),
    category: (catEl.value || '').trim() || 'Uncategorized',
    unit: (unitEl.value || '').trim() || 'Unit',
    avg_cost: cost,
  }).then(function (res) {
    if (!res.success) { showToast(res.error || 'Could not add material.', 'error'); return; }
    estimatorOptions = res.options;
    const badge = document.getElementById('est-ratecard-badge');
    if (badge) badge.innerText = `${estimatorOptions.rate_card.item_count} rates · ${estimatorOptions.rate_card.source}`;
    showToast(`${code} added to the rate card.`, 'success');
    recalcEstimate();
  }).catch(function (err) {
    showToast('Could not add material: ' + err, 'error');
  });
}

function estSetRate(idx, code, value) {
  const spec = estimatorSpecs[idx];
  if (!spec) return;
  spec.rate_overrides = spec.rate_overrides || {};
  const num = parseFloat(value);
  if (isNaN(num) || num < 0) delete spec.rate_overrides[code];
  else spec.rate_overrides[code] = num;
  recalcEstimate();
}

function estSetLaborRate(idx, trade, value) {
  const spec = estimatorSpecs[idx];
  if (!spec) return;
  spec.labor_rate_overrides = spec.labor_rate_overrides || {};
  const num = parseFloat(value);
  if (isNaN(num) || num < 0) delete spec.labor_rate_overrides[trade];
  else spec.labor_rate_overrides[trade] = num;
  recalcEstimate();
}

function renderItemCost(item, idx) {
  if (item.needs_dimensions) {
    return `<div class="est-notice est-notice-warning">${icon('alert', 'icon-sm')}<span>${esc(item.dimension_message)}</span></div>`;
  }

  const materialRows = item.materials.map(m => `
    <tr>
      <td><span class="est-code">${esc(m.code)}</span> ${esc(m.description)}</td>
      <td class="num">${m.qty}</td>
      <td>${esc(m.unit)}</td>
      <td class="num">
        <input type="number" class="input est-rate-input" min="0" step="0.01" value="${m.unit_cost}"
               title="Card rate: ${money(m.default_cost)}${m.unit_cost !== m.default_cost ? ' (overridden)' : ''}"
               onchange="estSetRate(${idx},'${m.code}',this.value)">
      </td>
      <td class="num strong">${money(m.line_cost)}</td>
    </tr>
    <tr class="est-basis-row"><td colspan="5">${esc(m.basis)}</td></tr>`).join('');

  const laborRows = item.labor.map(l => `
    <tr>
      <td>Labor — ${esc(l.trade)}</td>
      <td class="num">${l.hours}</td>
      <td>Hrs</td>
      <td class="num">
        <input type="number" class="input est-rate-input" min="0" step="0.01" value="${l.rate}"
               onchange="estSetLaborRate(${idx},'${l.trade}',this.value)">
      </td>
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
