/*
 * Renderer logic -- vanilla-JS port of src/renderer (App.tsx + components).
 *
 * `knowledgeBase` mirrors the Electron preload contextBridge API
 * (src/preload/preload.ts): the same method shape, backed by fetch calls to
 * the Flask `/api/*` routes that stand in for the IPC channels.
 */

const api = {
  async _json(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    return res.json();
  },
};

const knowledgeBase = {
  documents: {
    list: () => api._json('GET', '/api/documents'),
    import: (filePath) => api._json('POST', '/api/documents/import', { filePath }),
    importFile: async (file) => {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/api/documents/import', { method: 'POST', body: fd });
      return res.json();
    },
    get: (id) => api._json('GET', `/api/documents/${id}`),
    delete: (id) => api._json('DELETE', `/api/documents/${id}`),
  },
  indexing: {
    start: (documentId) => api._json('POST', '/api/indexing/start', { documentId }),
    status: () => api._json('GET', '/api/indexing/status'),
    chunks: (documentId) => api._json('GET', `/api/indexing/chunks/${documentId}`),
  },
  qa: {
    ask: (question) => api._json('POST', '/api/qa/ask', { question }),
    history: () => api._json('GET', '/api/qa/history'),
  },
};

// --- Application state (mirrors App.tsx useState hooks) ---
const state = {
  documents: [],
  selectedDoc: null,
  appStatus: { documentsLoaded: 0, indexStatus: 'idle', lastActivity: '' },
  lastResponse: null,
  showChunks: false,
  chunks: [],
};

// --- Helpers ---
const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(message) {
  let el = $('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.style.cssText =
      'position:fixed;bottom:48px;left:50%;transform:translateX(-50%);' +
      'background:#0f3460;color:#e0e0e0;padding:8px 16px;border-radius:6px;' +
      'font-size:12px;border:1px solid #533483;z-index:1000;opacity:0;transition:opacity .2s;';
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.style.opacity = '1';
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.style.opacity = '0'; }, 2600);
}

// --- Rendering ---
function renderDocumentList() {
  const list = $('document-list');
  $('doc-count').textContent = state.documents.length;
  if (state.documents.length === 0) {
    list.innerHTML =
      '<div class="doc-empty">No documents imported yet.<br>' +
      '<span class="hint">Import documents to get started.</span></div>';
    return;
  }
  list.innerHTML = state.documents
    .map((doc) => {
      const selected = state.selectedDoc && state.selectedDoc.id === doc.id ? ' selected' : '';
      const check = doc.status === 'indexed' ? '✓ ' : '';
      const kb = (doc.size / 1024).toFixed(1);
      return (
        `<div class="doc-card${selected}" data-id="${doc.id}">` +
        `<div class="doc-title">${esc(doc.title)}</div>` +
        `<div class="doc-meta">${check}${kb} KB</div></div>`
      );
    })
    .join('');
  list.querySelectorAll('.doc-card').forEach((card) => {
    card.addEventListener('click', () => {
      const doc = state.documents.find((d) => d.id === card.dataset.id);
      selectDocument(doc);
    });
  });
}

function renderDetail() {
  const area = $('detail-area');
  const parts = [];
  const doc = state.selectedDoc;
  if (doc) {
    const rows = [
      `<div>Filename: ${esc(doc.filename)}</div>`,
      `<div>Imported: ${new Date(doc.importedAt).toLocaleString()}</div>`,
      `<div>Size: ${(doc.size / 1024).toFixed(1)} KB</div>`,
      `<div>Status: ${esc(doc.status)}</div>`,
    ];
    if (doc.chunks !== undefined) rows.push(`<div>Chunks: ${doc.chunks}</div>`);

    let actions =
      `<button class="btn btn-secondary" id="toggle-chunks">` +
      `${state.showChunks ? 'Hide' : 'Show'} Chunks (${state.chunks.length})</button>`;
    if (doc.status !== 'indexed') {
      actions += `<button class="btn btn-primary" id="index-doc">Index Document</button>`;
    }

    let chunksHtml = '';
    if (state.showChunks) {
      chunksHtml = state.chunks
        .map(
          (chunk) =>
            `<div class="chunk"><div class="chunk-head">Chunk ${chunk.index} ` +
            `(${chunk.metadata.charCount} chars)</div>${esc(chunk.content)}</div>`
        )
        .join('');
    }

    parts.push(
      `<div class="detail"><h2>${esc(doc.title)}</h2>` +
      `<div class="detail-meta">${rows.join('')}</div>` +
      `<div class="detail-actions">${actions}</div>${chunksHtml}</div>`
    );
  } else {
    parts.push('<div class="placeholder">Select a document or ask a question to get started</div>');
  }

  if (state.lastResponse) {
    const r = state.lastResponse;
    let citations = '';
    if (r.citations.length > 0) {
      citations =
        '<div class="citations"><strong>Citations:</strong>' +
        r.citations
          .map(
            (c) =>
              `<div class="citation">${esc(c.documentTitle)} (chunk ${c.chunkIndex}): ` +
              `${esc(c.excerpt.substring(0, 100))}...</div>`
          )
          .join('') +
        '</div>';
    }
    parts.push(
      `<div class="answer-block"><div class="answer-text">${esc(r.answer)}</div>${citations}</div>`
    );
  }

  area.innerHTML = parts.join('');

  const toggle = $('toggle-chunks');
  if (toggle) toggle.addEventListener('click', () => { state.showChunks = !state.showChunks; renderDetail(); });
  const indexBtn = $('index-doc');
  if (indexBtn)
    indexBtn.addEventListener('click', async () => {
      await knowledgeBase.indexing.start(doc.id);
      state.chunks = await knowledgeBase.indexing.chunks(doc.id);
      renderDetail();
    });
}

function renderStatusBar() {
  const s = state.appStatus;
  const colors = { idle: '#888', indexing: '#f0ad4e', ready: '#5cb85c', error: '#d9534f' };
  $('status-dot').style.background = colors[s.indexStatus] || '#888';
  $('status-index').textContent = s.indexStatus == null ? '' : s.indexStatus;
  $('status-docs').textContent = s.documentsLoaded == null ? '' : s.documentsLoaded;
  $('status-activity').textContent = s.lastActivity
    ? `Last activity: ${new Date(s.lastActivity).toLocaleTimeString()}`
    : '';
}

// --- Actions (mirror App.tsx callbacks) ---
async function refreshDocuments() {
  try {
    state.documents = await knowledgeBase.documents.list();
    state.appStatus = await knowledgeBase.indexing.status();
    if (state.selectedDoc) {
      state.selectedDoc = state.documents.find((d) => d.id === state.selectedDoc.id) || null;
    }
    renderDocumentList();
    renderDetail();
    renderStatusBar();
  } catch (err) {
    console.error('Failed to refresh documents:', err);
  }
}

async function selectDocument(doc) {
  state.selectedDoc = doc;
  state.showChunks = false;
  state.chunks = await knowledgeBase.indexing.chunks(doc.id);
  renderDocumentList();
  renderDetail();
}

// In P1 the renderer import is a stub -- a real app would open a file dialog.
function handleImport() {
  console.log('Import triggered - use window.knowledgeBase.documents.import(filePath)');
  toast('Import triggered - drive it via the API: POST /api/documents/import');
}

async function handleAskQuestion(question) {
  try {
    state.lastResponse = await knowledgeBase.qa.ask(question);
    renderDetail();
  } catch (err) {
    console.error('Q&A failed:', err);
  }
}

// --- Wire up ---
function init() {
  $('refresh-btn').addEventListener('click', refreshDocuments);
  $('import-btn').addEventListener('click', handleImport);
  $('question-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('question-input');
    const q = input.value.trim();
    if (!q) return;
    handleAskQuestion(q);
    input.value = '';
  });
  // Expose the bridge for console-driven use, mirroring window.knowledgeBase.
  window.knowledgeBase = knowledgeBase;
  refreshDocuments();
}

document.addEventListener('DOMContentLoaded', init);
