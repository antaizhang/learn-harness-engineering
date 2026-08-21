# Knowledge Base -- Python (Flask) port

A functionally-equivalent Python rewrite of this project's Electron + React +
TypeScript app. Same product (document import, indexing, grounded mock Q&A with
citations, local JSON/text persistence), delivered as a Flask web app instead of
an Electron desktop app.

Project 03 adds: paragraph-aware chunking with per-chunk metadata, document
metadata extraction on import (word/line/paragraph/character counts + file type),
an indexing status bar (indexed count / total chunks / status colours), and
grounded Q&A that cites retrieved chunks with a confidence badge.

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

## Importing documents

Project 02 adds a real **Import** panel: click **+ Import**, choose a `.txt`/`.md`
file, and it is uploaded and stored. You can also view a document's full content
(**View Content**) and delete it (**Delete**) from the detail panel. Documents
persist across restarts under the data directory.

The JSON `filePath` import path and the bundled seeder still work for scripting:

```sh
python seed.py     # import + index the bundled sample documents
```

## Test

```sh
pip install pytest
python -m pytest        # service-layer + API tests
```
