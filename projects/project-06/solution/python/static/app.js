/*
 * Renderer logic -- vanilla-JS port of src/renderer (App.tsx + components), P06.
 *
 * `knowledgeBase` mirrors the Electron preload contextBridge API
 * (src/preload/preload.ts), backed by fetch calls to the Flask `/api/*` routes.
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
    clearHistory: () => api._json('POST', '/api/qa/clear-history'),
  },
  feedback: {
    submit: (qaTimestamp, question, rating, comment) =>
      api._json('POST', '/api/feedback', { qaTimestamp, question, rating, comment }),
    list: () => api._json('GET', '/api/feedback'),
  },
  app: {
    resetData: () => api._json('POST', '/api/reset'),
  },
};

// --- Application state (mirrors App.tsx useState hooks) ---
const state = {
  documents: [],
  selectedDoc: null,
  appStatus: { documentsLoaded: 0, indexStatus: 'idle', lastActivity: '' },
  lastResponse: null,
  viewMode: 'documents', // 'documents' | 'history'
  // detail-local
  showChunks: false,
  chunks: [],
  // history-local
  conversationHistory: [],
  expandedCitations: new Set(),
};

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(message) {
  let el = $('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), 2200);
}

// --- Document list ---
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
  list.querySelectorAll('.doc-card').forEach((card) =>
    card.addEventListener('click', () => {
      const doc = state.documents.find((d) => d.id === card.dataset.id);
      selectDocument(doc);
    })
  );
}

// --- Detail view ---
function detailHtml(doc) {
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
  actions += `<button class="btn btn-danger" id="delete-doc">Delete</button>`;

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
    `<div class="detail-actions">${actions}</div>${chunksHtml}</div>`
  );
}

function answerBlockHtml(r) {
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
  return (
    '<div class="answer-block">' +
    `<div class="answer-text">${esc(r.answer)}</div>${citations}` +
    '<div class="answer-foot">' +
    `<span class="conf">Confidence: ${(r.confidence * 100).toFixed(0)}%</span>` +
    '<div class="fb-buttons">' +
    '<button class="fb-up" id="fb-up">Thumbs Up</button>' +
    '<button class="fb-down" id="fb-down">Thumbs Down</button>' +
    '</div></div></div>'
  );
}

function renderDetailView() {
  const area = $('detail-area');
  const parts = [];
  if (state.selectedDoc) {
    parts.push(detailHtml(state.selectedDoc));
  } else {
    parts.push('<div class="placeholder">Select a document or ask a question to get started</div>');
  }
  if (state.lastResponse) parts.push(answerBlockHtml(state.lastResponse));
  area.innerHTML = parts.join('');

  const toggle = $('toggle-chunks');
  if (toggle) toggle.addEventListener('click', () => { state.showChunks = !state.showChunks; renderDetailView(); });
  const indexBtn = $('index-doc');
  if (indexBtn) indexBtn.addEventListener('click', () => handleIndexDocument(state.selectedDoc.id));
  const deleteBtn = $('delete-doc');
  if (deleteBtn) deleteBtn.addEventListener('click', () => handleDeleteDocument(state.selectedDoc.id));
  const up = $('fb-up');
  const down = $('fb-down');
  if (up) up.addEventListener('click', async () => {
    await knowledgeBase.feedback.submit(state.lastResponse.timestamp, '', 'positive');
    toast('Thanks for the feedback!');
  });
  if (down) down.addEventListener('click', async () => {
    await knowledgeBase.feedback.submit(state.lastResponse.timestamp, '', 'negative');
    toast('Thanks for the feedback!');
  });
}

// --- Conversation history view (self-fetching, mirrors ConversationHistory.tsx) ---
async function renderHistoryView() {
  const area = $('detail-area');
  state.conversationHistory = await knowledgeBase.qa.history();
  const history = state.conversationHistory;
  if (history.length === 0) {
    area.innerHTML =
      '<div class="placeholder">No conversation history yet. Ask a question to get started.</div>';
    return;
  }

  const head =
    '<div class="conv-head"><h3>Conversation History (' +
    history.length +
    ' exchanges)</h3><button class="btn btn-clear" id="clear-history">Clear History</button></div>';

  const turns = history
    .map((item, index) => {
      const isExpanded = state.expandedCitations.has(index);
      const pct = (item.response.confidence * 100).toFixed(0);
      const confColor =
        item.response.confidence >= 0.7 ? '#5cb85c' : item.response.confidence >= 0.5 ? '#f0ad4e' : '#d9534f';
      const cites = item.response.citations;

      let toggle = '';
      let citeList = '';
      if (cites.length > 0) {
        toggle = `<button class="cite-toggle" data-toggle="${index}">${isExpanded ? 'Hide' : 'Show'} ${cites.length} citation(s)</button>`;
        if (isExpanded) {
          citeList =
            '<div class="cite-list">' +
            cites
              .map(
                (c) =>
                  '<div class="cite"><div class="cite-title">' +
                  `${esc(c.documentTitle)} -- chunk ${c.chunkIndex}</div>` +
                  `<div>${esc(c.excerpt.substring(0, 150))}...</div></div>`
              )
              .join('') +
            '</div>';
        }
      }

      return (
        '<div class="conv-turn">' +
        `<div class="bubble-row right"><div class="bubble user">${esc(item.question)}</div></div>` +
        `<div class="bubble-time right">${new Date(item.response.timestamp).toLocaleTimeString()}</div>` +
        '<div class="bubble-row left"><div class="bubble assistant">' +
        `<div>${esc(item.response.answer)}</div>` +
        `<div class="assistant-foot"><span style="color:${confColor}">Confidence: ${pct}%</span>${toggle}</div>` +
        citeList +
        '<div class="fb-row">' +
        `<button class="fb-up-s" data-fbup="${index}" title="Good answer">+1</button>` +
        `<button class="fb-down-s" data-fbdown="${index}" title="Poor answer">-1</button>` +
        '</div></div></div></div>'
      );
    })
    .join('');

  area.innerHTML = `<div class="conv">${head}<div class="conv-list">${turns}</div></div>`;
  wireHistoryEvents();
}

function wireHistoryEvents() {
  const area = $('detail-area');
  const clear = $('clear-history');
  if (clear)
    clear.addEventListener('click', async () => {
      if (window.confirm('Clear all conversation history? This cannot be undone.')) {
        await knowledgeBase.qa.clearHistory();
        state.expandedCitations.clear();
        renderHistoryView();
      }
    });
  area.querySelectorAll('[data-toggle]').forEach((btn) =>
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.toggle);
      if (state.expandedCitations.has(idx)) state.expandedCitations.delete(idx);
      else state.expandedCitations.add(idx);
      renderHistoryView();
    })
  );
  area.querySelectorAll('[data-fbup]').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const item = state.conversationHistory[Number(btn.dataset.fbup)];
      await knowledgeBase.feedback.submit(item.response.timestamp, item.question, 'positive');
      toast('Thanks for the feedback!');
    })
  );
  area.querySelectorAll('[data-fbdown]').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const item = state.conversationHistory[Number(btn.dataset.fbdown)];
      await knowledgeBase.feedback.submit(item.response.timestamp, item.question, 'negative');
      toast('Thanks for the feedback!');
    })
  );
}

function renderMain() {
  if (state.viewMode === 'history') renderHistoryView();
  else renderDetailView();
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

// --- Actions ---
async function refreshDocuments() {
  try {
    state.documents = await knowledgeBase.documents.list();
    state.appStatus = await knowledgeBase.indexing.status();
    if (state.selectedDoc) {
      state.selectedDoc = state.documents.find((d) => d.id === state.selectedDoc.id) || null;
    }
    renderDocumentList();
    if (state.viewMode === 'documents') renderDetailView();
    renderStatusBar();
  } catch (err) {
    console.error('Failed to refresh documents:', err);
  }
}

async function selectDocument(doc) {
  state.selectedDoc = doc;
  state.viewMode = 'documents';
  state.showChunks = false;
  state.chunks = await knowledgeBase.indexing.chunks(doc.id);
  $('view-btn').textContent = 'History';
  renderDocumentList();
  renderMain();
}

async function handleIndexDocument(documentId) {
  await knowledgeBase.indexing.start(documentId);
  await refreshDocuments();
  const updated = await knowledgeBase.documents.get(documentId);
  if (updated) {
    state.selectedDoc = updated;
    state.chunks = await knowledgeBase.indexing.chunks(documentId);
    renderDocumentList();
    renderDetailView();
  }
}

async function handleDeleteDocument(id) {
  await knowledgeBase.documents.delete(id);
  if (state.selectedDoc && state.selectedDoc.id === id) state.selectedDoc = null;
  await refreshDocuments();
}

function handleImport() {
  console.log('Import triggered - use window.knowledgeBase.documents.import(filePath)');
  toast('Import triggered - drive it via the API: POST /api/documents/import');
}

async function handleAskQuestion(question) {
  try {
    state.lastResponse = await knowledgeBase.qa.ask(question);
    state.appStatus = await knowledgeBase.indexing.status();
    if (state.viewMode === 'history') renderHistoryView();
    else renderDetailView();
    renderStatusBar();
  } catch (err) {
    console.error('Q&A failed:', err);
  }
}

async function handleResetData() {
  if (
    window.confirm(
      'This will delete all imported documents, indexes, Q&A history, and feedback. Continue?'
    )
  ) {
    await knowledgeBase.app.resetData();
    state.documents = [];
    state.selectedDoc = null;
    state.lastResponse = null;
    state.conversationHistory = [];
    state.expandedCitations.clear();
    await refreshDocuments();
    renderMain();
  }
}

function toggleView() {
  state.viewMode = state.viewMode === 'history' ? 'documents' : 'history';
  $('view-btn').textContent = state.viewMode === 'history' ? 'Documents' : 'History';
  renderMain();
}

// --- Wire up ---
function init() {
  $('refresh-btn').addEventListener('click', refreshDocuments);
  $('view-btn').addEventListener('click', toggleView);
  $('reset-btn').addEventListener('click', handleResetData);
  $('import-btn').addEventListener('click', handleImport);
  $('question-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('question-input');
    const q = input.value.trim();
    if (!q) return;
    handleAskQuestion(q);
    input.value = '';
  });
  window.knowledgeBase = knowledgeBase;
  refreshDocuments();
}

document.addEventListener('DOMContentLoaded', init);
