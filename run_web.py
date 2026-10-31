"""
SETTLE.AI - Web Prototype Launcher
Starts the unified FastAPI + WebSocket server and launches the Ops Command Center in browser.
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure workspace root is in sys.path
workspace_root = os.path.abspath(os.path.dirname(__file__))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Auto-delegate to .venv python if executed via unconfigured global python
venv_python = os.path.join(workspace_root, ".venv", "Scripts", "python.exe")
if sys.prefix == sys.base_prefix and os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    import subprocess
    sys.exit(subprocess.call([venv_python] + sys.argv))

import webbrowser
import uvicorn

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    print("=" * 65)
    print("  🚀 SETU — Autonomous Operations Teammate (Team: 0 and 1)")
    print("  Paytm Build for India Hackathon | Track 3: Autonomous AI Teammates")
    print("  Zero-touch dispute adjudication, Soundbox triage & ledger resolution")
    print("=" * 65)
    print(f"\n  📡 Server URL: {url}")
    print("  Open this link in your browser to view the live prototype!\n")
    print("=" * 65)

    # Automatically open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("settle_ai.server:app", host=host, port=port, reload=False)
