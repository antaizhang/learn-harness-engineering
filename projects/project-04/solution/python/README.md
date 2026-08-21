# Knowledge Base -- Python (Flask) port

A functionally-equivalent Python rewrite of this project's Electron + React +
TypeScript app. Same product (document import, indexing, grounded mock Q&A with
citations, local JSON/text persistence), delivered as a Flask web app instead of
an Electron desktop app.

Project 04 adds runtime observability and structural guardrails:

* **Structured logging** (`src/services/logger.py`) -- JSON log entries with
  level/timestamp/service/message, used across the services and the web layer.
  Control verbosity with `LOG_LEVEL` (`DEBUG`/`INFO`/`WARN`/`ERROR`).
* **Architecture boundary check** (`scripts/check_architecture.py`) -- fails if
  the service layer depends on Flask or the web layer, or if shared types stop
  being a leaf module. Run it with `python scripts/check_architecture.py`.

The chunking pipeline is written so long documents never yield empty chunks
(the seeded defect this project's exercise is about); `test_services.py` guards
that invariant.

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
