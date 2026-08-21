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
    getContent: (id) => api._json('GET', `/api/documents/${id}/content`),
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
  showImport: false,
  // DocumentDetail-local state
  showChunks: false,
  chunks: [],
  content: null,
  showContent: false,
  loadingContent: false,
};

// --- Helpers ---
const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

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

function importPanelHtml() {
  return (
    '<div class="import-panel">' +
    '<div class="import-title">Import Documents</div>' +
    '<div class="import-hint">Choose a file to import.<br>Supported: .txt, .md files</div>' +
    '<input id="import-file" type="file" accept=".txt,.md" />' +
    '</div>'
  );
}

function detailHtml(doc) {
  const rows = [
    `<div>Filename: ${esc(doc.filename)}</div>`,
    `<div>Imported: ${new Date(doc.importedAt).toLocaleString()}</div>`,
    `<div>Size: ${(doc.size / 1024).toFixed(1)} KB</div>`,
    `<div>Status: ${esc(doc.status)}</div>`,
  ];
  if (doc.chunks !== undefined) rows.push(`<div>Chunks: ${doc.chunks}</div>`);

  const contentLabel = state.loadingContent
    ? 'Loading...'
    : state.showContent
    ? 'Hide Content'
    : 'View Content';
  let actions =
    `<button class="btn btn-secondary" id="view-content">${contentLabel}</button>` +
    `<button class="btn btn-secondary" id="toggle-chunks">` +
    `${state.showChunks ? 'Hide' : 'Show'} Chunks (${state.chunks.length})</button>`;
  if (doc.status !== 'indexed') {
    actions += `<button class="btn btn-primary" id="index-doc">Index Document</button>`;
  }
  actions += `<button class="btn btn-danger" id="delete-doc">Delete</button>`;

  let contentHtml = '';
  if (state.showContent && state.content) {
    contentHtml = `<div class="content-viewer">${esc(state.content)}</div>`;
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

  return (
    `<div class="detail"><h2>${esc(doc.title)}</h2>` +
    `<div class="detail-meta">${rows.join('')}</div>` +
    `<div class="detail-actions">${actions}</div>${contentHtml}${chunksHtml}</div>`
  );
}

function renderDetail() {
  const area = $('detail-area');
  const parts = [];
  const doc = state.selectedDoc;

  if (state.showImport) {
    parts.push(importPanelHtml());
  } else if (doc) {
    parts.push(detailHtml(doc));
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
  wireDetailEvents();
}

function wireDetailEvents() {
  const fileInput = $('import-file');
  if (fileInput)
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) handleImport(file);
    });

  const viewBtn = $('view-content');
  if (viewBtn) viewBtn.addEventListener('click', loadContent);

  const toggle = $('toggle-chunks');
  if (toggle)
    toggle.addEventListener('click', () => { state.showChunks = !state.showChunks; renderDetail(); });

  const indexBtn = $('index-doc');
  if (indexBtn)
    indexBtn.addEventListener('click', async () => {
      await knowledgeBase.indexing.start(state.selectedDoc.id);
      state.chunks = await knowledgeBase.indexing.chunks(state.selectedDoc.id);
      renderDetail();
    });

  const deleteBtn = $('delete-doc');
  if (deleteBtn) deleteBtn.addEventListener('click', () => handleDeleteDocument(state.selectedDoc.id));
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
  state.showImport = false;
  state.showChunks = false;
  state.content = null;
  state.showContent = false;
  state.chunks = await knowledgeBase.indexing.chunks(doc.id);
  renderDocumentList();
  renderDetail();
}

async function loadContent() {
  if (state.content) {
    state.showContent = !state.showContent;
    renderDetail();
    return;
  }
  state.loadingContent = true;
  renderDetail();
  try {
    state.content = await knowledgeBase.documents.getContent(state.selectedDoc.id);
    state.showContent = true;
  } catch (err) {
    console.error('Failed to load document content:', err);
  } finally {
    state.loadingContent = false;
    renderDetail();
  }
}

async function handleImport(file) {
  try {
    await knowledgeBase.documents.importFile(file);
    await refreshDocuments();
    state.showImport = false;
    renderDetail();
  } catch (err) {
    console.error('Import failed:', err);
  }
}

async function handleDeleteDocument(id) {
  try {
    await knowledgeBase.documents.delete(id);
    if (state.selectedDoc && state.selectedDoc.id === id) state.selectedDoc = null;
    await refreshDocuments();
  } catch (err) {
    console.error('Delete failed:', err);
  }
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
  $('import-btn').addEventListener('click', () => {
    state.showImport = !state.showImport;
    $('import-btn').textContent = state.showImport ? 'Cancel' : '+ Import';
    renderDetail();
  });
  $('question-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('question-input');
    const q = input.value.trim();
    if (!q) return;
    handleAskQuestion(q);
    input.value = '';
  });
  window.knowledgeBase = knowledgeBase;
  refreshDocuments(); // load documents on mount (basic persistence)
}

document.addEventListener('DOMContentLoaded', init);
