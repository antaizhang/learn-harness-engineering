"""Entry point: launch the Knowledge Base web app.

    python app.py            # serve on http://127.0.0.1:5001
    KB_PORT=8080 python app.py

This is the Python/Flask equivalent of ``npm run dev`` for the Electron app.
"""

import os

from src.web.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("KB_PORT", "5001"))
    host = os.environ.get("KB_HOST", "127.0.0.1")
    print(f"[dev] Knowledge Base running at http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
