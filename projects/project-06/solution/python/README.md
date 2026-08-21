# Knowledge Base -- Python (Flask) port

# Knowledge Base -- Python (Flask) port -- Project 06 (capstone)

A functionally-equivalent Python rewrite of this project's Electron + React +
TypeScript app. Same product (document import, indexing, grounded mock Q&A with
citations, local JSON/text persistence), delivered as a Flask web app instead of
an Electron desktop app.

The capstone brings the full feature set together:

* **Structured logging** (`src/services/logger.py`) across every service and the
  web layer. Control verbosity with `LOG_LEVEL` (`DEBUG`/`INFO`/`WARN`/`ERROR`).
* **Conversation History** view -- toggle **History** in the header for a
  chat-style transcript with expandable citations, confidence, and per-answer
  feedback; **Clear History** wipes it.
* **Feedback** -- Thumbs Up / Thumbs Down on answers, stored in `feedback.json`
  (`/api/feedback`).
* **Reset** -- the header **Reset** button clears all documents, chunks, history,
  and feedback (`/api/reset`).
* **10 MB import guard** -- oversized files are rejected on import.

### Harness / ops scripts

```sh
python scripts/check_architecture.py   # layer-boundary checks
python scripts/benchmark.py            # import/index/query/integrity benchmark
python scripts/cleanup_scanner.py      # scan the data dir for stale artifacts
```

## Architecture mapping

| Electron / TypeScript            | Python / Flask                                   |
|----------------------------------|--------------------------------------------------|
| `src/main/main.ts`               | `src/web/app.py` (`create_app` factory)          |
| `src/main/ipc-handlers.ts`       | the `/api/*` routes in `src/web/app.py`          |
| `src/preload/preload.ts`         | the `knowledgeBase` client in `static/app.js`    |
| `src/renderer/*` (React)         | `templates/index.html` + `static/app.js`/`.css`  |
| `src/services/*.ts`              | `src/services/*.py` (direct port)                |
| `src/shared/types.ts`            | `src/shared/types.py` (TypedDicts + IPC_CHANNELS)|

The IPC channel names in `src/shared/types.py` map one-to-one onto the HTTP
routes, so the API surface matches the original preload bridge.

## Run

```sh
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
python app.py                    # http://127.0.0.1:5001  (set KB_PORT to change)
```

Application data is written under `.kb-data/` by default (override with the
`KB_DATA_DIR` environment variable), mirroring the Electron `userData` directory.

## Seeding documents

As in the original Project 01, the in-app **Import** button is a stub -- a real
desktop app would open a file dialog. Drive import via the API (this mirrors
calling `window.knowledgeBase.documents.import(filePath)` from the console):

```sh
curl -X POST http://127.0.0.1:5001/api/documents/import \
     -H 'Content-Type: application/json' \
     -d '{"filePath": "data/sample-documents/design-notes.md"}'
```

Or use the convenience seeder, which imports and indexes the bundled samples:

```sh
python seed.py
```

## Test

```sh
pip install pytest
python -m pytest        # service-layer + API tests
```
