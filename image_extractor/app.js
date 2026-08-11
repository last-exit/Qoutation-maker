/* UI for the document image extractor.
 *
 * The Python side owns every decision; this file moves paths in and renders records out.
 * Thumbnails are plain <img src="store/ab/....jpg"> requests served by pywebview's HTTP
 * server, which is why no image bytes ever cross the JS bridge.
 */

function api() { return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null; }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
function $(id) { return document.getElementById(id); }

let lastResult = null;
let outputDir = null;
let busy = false;

let toastTimer = null;
function showToast(message, kind) {
  const el = $('toast');
  el.textContent = message;
  el.className = 'toast show' + (kind === 'error' ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 4200);
}

const ACCEPTED = ['.xlsx', '.xlsm', '.docx', '.pdf'];

/* Called from Python when documents were chosen through the native dialog, which does give
   real filesystem paths. */
function ingestPaths(paths) {
  if (!paths || !paths.length) return;
  runExtraction(paths);
}

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    // readAsDataURL gives "data:<type>;base64,xxxx"; Python takes the part after the comma.
    reader.onload = () => resolve({ name: file.name, data: String(reader.result) });
    reader.onerror = () => reject(new Error('Could not read ' + file.name));
    reader.readAsDataURL(file);
  });
}

/* Dropped files. A webview never hands the page a filesystem path, so the bytes are read
   here and sent over — which is why the drop works at all. */
async function ingestDroppedFiles(fileList) {
  const bridge = api();
  if (!bridge || busy) return;

  const files = [...fileList].filter(f => ACCEPTED.some(ext => f.name.toLowerCase().endsWith(ext)));
  const rejected = [...fileList].length - files.length;
  if (!files.length) {
    showToast('Drop an .xlsx, .xlsm, .docx or .pdf file.', 'error');
    return;
  }

  busy = true;
  $('dropzone').classList.add('working');
  $('empty').textContent = 'Reading ' + files.length + ' document' + (files.length === 1 ? '' : 's') + '…';
  $('empty').classList.remove('hidden');

  try {
    const uploads = await Promise.all(files.map(readAsBase64));
    const result = await bridge.extract_uploads(uploads);
    if (!result || !result.success) {
      showToast((result && result.error) || 'Could not read those documents.', 'error');
      return;
    }
    lastResult = result;
    render(result);
    if (rejected) showToast(`${rejected} file${rejected === 1 ? '' : 's'} skipped — not a document this tool reads.`);
  } catch (e) {
    showToast(String(e), 'error');
  } finally {
    busy = false;
    $('dropzone').classList.remove('working');
  }
}

async function runExtraction(paths) {
  const bridge = api();
  if (!bridge || busy) return;

  busy = true;
  $('dropzone').classList.add('working');
  $('empty').textContent = 'Reading ' + paths.length + ' document' + (paths.length === 1 ? '' : 's') + '…';
  $('empty').classList.remove('hidden');

  try {
    const result = await bridge.extract(paths);
    if (!result || !result.success) {
      showToast((result && result.error) || 'Could not read those documents.', 'error');
      return;
    }
    lastResult = result;
    render(result);
  } catch (e) {
    showToast(String(e), 'error');
  } finally {
    busy = false;
    $('dropzone').classList.remove('working');
  }
}

function locationLabel(img) {
  if (img.kind === 'pdf') {
    const box = img.bbox ? ` · ${Math.round(img.bbox[2] - img.bbox[0])}×${Math.round(img.bbox[3] - img.bbox[1])}pt` : '';
    return `Page ${img.page}${box}`;
  }
  return img.location || '';
}

function render(result) {
  const counts = result.counts || {};
  const images = result.images || [];

  // Documents read
  const queueList = $('queue-list');
  queueList.innerHTML = (result.files || []).map(f => `
    <li><span class="qname">${esc(f.file)}</span>
        <span class="qkind">${esc(f.kind)}</span>
        <span class="qcount">${f.images} image${f.images === 1 ? '' : 's'}</span></li>
  `).join('') + (result.skipped || []).map(s => `
    <li class="skipped"><span class="qname">${esc(s.file)}</span>
        <span class="qreason">${esc(s.reason)}</span></li>
  `).join('');
  $('queue').classList.toggle('hidden', !(result.files || []).length && !(result.skipped || []).length);

  // Counts
  const duplicates = counts.images - counts.unique;
  $('summary-counts').textContent =
    `${counts.images} image${counts.images === 1 ? '' : 's'} from ${counts.documents} ` +
    `document${counts.documents === 1 ? '' : 's'} · ${counts.unique} unique` +
    (duplicates > 0 ? ` (${duplicates} duplicate${duplicates === 1 ? '' : 's'} collapsed)` : '');
  $('summary').classList.toggle('hidden', !images.length);
  $('btn-reveal').classList.add('hidden');

  // Notes
  const warnings = result.warnings || [];
  $('warning-list').innerHTML = warnings.map(w => `<li>${esc(w)}</li>`).join('');
  $('warnings').classList.toggle('hidden', !warnings.length);

  // Thumbnails. The whole card is the copy target — clicking a picture to copy it is what
  // people try first — with a visible button so it is discoverable rather than a secret.
  $('results').innerHTML = images.map((img, i) => `
    <figure class="card" data-ref="${esc(img.ref)}" data-index="${i}" title="Click to view · Copy to copy">
      <div class="thumb">
        <img src="${esc(img.image_src)}" alt="${esc(img.location)}" loading="lazy">
        <div class="card-actions">
          <button class="card-btn js-open" type="button">Open</button>
          <button class="card-btn js-copy" type="button">Copy</button>
        </div>
      </div>
      <figcaption>
        <span class="src">${esc(img.source_file)}</span>
        <span class="loc">${esc(locationLabel(img))}</span>
      </figcaption>
    </figure>
  `).join('');

  $('empty').classList.toggle('hidden', images.length > 0);
  if (!images.length) {
    $('empty').textContent = (result.files || []).length
      ? 'No embedded images in those documents.'
      : 'Nothing read yet. Drop a document above, or choose one.';
  }
}

function resetView() {
  lastResult = null;
  $('queue').classList.add('hidden');
  $('summary').classList.add('hidden');
  $('warnings').classList.add('hidden');
  $('results').innerHTML = '';
  $('empty').textContent = 'Nothing read yet. Drop a document above, or choose one.';
  $('empty').classList.remove('hidden');
}

async function copyImage(ref, card) {
  const bridge = api();
  if (!bridge || !ref) return;

  card.classList.add('copying');
  try {
    const result = await bridge.copy_image(ref);
    if (result && result.success) {
      card.classList.add('copied');
      setTimeout(() => card.classList.remove('copied'), 1200);
      showToast('Image copied — paste it anywhere.');
    } else {
      showToast((result && result.error) || 'Could not copy that image.', 'error');
    }
  } catch (e) {
    showToast(String(e), 'error');
  } finally {
    card.classList.remove('copying');
  }
}

/* --- Viewer -------------------------------------------------------------------------- */

let viewerIndex = -1;

function openViewer(index) {
  const images = (lastResult && lastResult.images) || [];
  const img = images[index];
  if (!img) return;

  viewerIndex = index;
  $('viewer-img').src = img.image_src;
  $('viewer-src').textContent = img.source_file;
  $('viewer-loc').textContent = locationLabel(img);
  $('viewer-count').textContent = `${index + 1} of ${images.length}`;
  $('viewer').classList.add('open');
  $('viewer-close').focus();
}

function closeViewer() {
  $('viewer').classList.remove('open');
  $('viewer-img').removeAttribute('src');
  viewerIndex = -1;
}

function stepViewer(delta) {
  const images = (lastResult && lastResult.images) || [];
  if (viewerIndex < 0 || !images.length) return;
  openViewer((viewerIndex + delta + images.length) % images.length);
}

document.addEventListener('DOMContentLoaded', () => {
  // Delegated: the grid is rewritten on every run, so per-card listeners would go stale.
  $('results').addEventListener('click', e => {
    const card = e.target.closest('.card');
    if (!card) return;
    if (e.target.closest('.js-copy')) {
      copyImage(card.dataset.ref, card);
      return;
    }
    // Anywhere else on the card — including the Open button — views it.
    openViewer(Number(card.dataset.index));
  });

  $('viewer-close').addEventListener('click', closeViewer);
  $('viewer-prev').addEventListener('click', () => stepViewer(-1));
  $('viewer-next').addEventListener('click', () => stepViewer(1));
  $('viewer-copy').addEventListener('click', () => {
    const img = ((lastResult && lastResult.images) || [])[viewerIndex];
    if (img) copyImage(img.ref, $('viewer'));
  });
  // Clicking the backdrop closes; clicking the picture or the bar does not.
  $('viewer').addEventListener('click', e => { if (e.target === $('viewer')) closeViewer(); });

  document.addEventListener('keydown', e => {
    if (!$('viewer').classList.contains('open')) return;
    if (e.key === 'Escape') closeViewer();
    if (e.key === 'ArrowLeft') stepViewer(-1);
    if (e.key === 'ArrowRight') stepViewer(1);
  });

  // The browser's own drag handling would navigate away from the page; pywebview's native
  // drop handler (bound in app.py) is what actually delivers the paths.
  const dz = $('dropzone');
  ['dragenter', 'dragover'].forEach(evt => dz.addEventListener(evt, e => {
    e.preventDefault();
    dz.classList.add('hover');
  }));
  ['dragleave', 'drop'].forEach(evt => dz.addEventListener(evt, e => {
    e.preventDefault();
    dz.classList.remove('hover');
  }));
  dz.addEventListener('drop', e => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      ingestDroppedFiles(e.dataTransfer.files);
    }
  });
  // Dropping anywhere but the zone would otherwise make the webview navigate to the file,
  // which looks exactly like the app crashing.
  ['dragover', 'drop'].forEach(evt => window.addEventListener(evt, e => e.preventDefault()));
  // The zone is the obvious thing to click, so make it do the obvious thing.
  dz.addEventListener('click', () => $('btn-choose').click());

  $('btn-choose').addEventListener('click', async () => {
    const bridge = api();
    if (!bridge) return;
    const picked = await bridge.pick_files();
    if (!picked.success) {
      if (picked.error !== 'No files selected.') showToast(picked.error, 'error');
      return;
    }
    runExtraction(picked.paths);
  });

  $('btn-clear').addEventListener('click', async () => {
    const bridge = api();
    if (bridge) await bridge.clear();
    resetView();
  });

  $('btn-outdir').addEventListener('click', async () => {
    const bridge = api();
    if (!bridge) return;
    const picked = await bridge.pick_output_folder();
    if (!picked.success) return;
    outputDir = picked.path;
    showToast('Exports will go to ' + outputDir);
  });

  $('btn-export').addEventListener('click', async () => {
    const bridge = api();
    if (!bridge || !lastResult) return;
    const result = await bridge.export(outputDir);
    if (!result || !result.success) {
      showToast((result && result.error) || 'Export failed.', 'error');
      return;
    }
    outputDir = result.out_dir;
    const missing = (result.missing || []).length;
    showToast(`Wrote ${result.written} file${result.written === 1 ? '' : 's'} to ${result.out_dir}` +
              (missing ? ` · ${missing} image${missing === 1 ? '' : 's'} missing from the store` : ''));
    $('btn-reveal').classList.remove('hidden');
  });

  $('btn-copy-all').addEventListener('click', async () => {
    const bridge = api();
    if (!bridge || !lastResult) return;
    const result = await bridge.copy_all_images();
    if (!result || !result.success) {
      showToast((result && result.error) || 'Could not copy those paths.', 'error');
      return;
    }
    showToast(`Copied ${result.count} file path${result.count === 1 ? '' : 's'} — paste into a folder or an attachment box.`);
  });

  $('btn-reveal').addEventListener('click', async () => {
    const bridge = api();
    if (!bridge) return;
    const result = await bridge.reveal(outputDir);
    if (!result.success) showToast(result.error, 'error');
  });
});
