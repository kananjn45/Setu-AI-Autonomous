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

# Auto-delegate to workspace .venv if executed via an unconfigured python environment
venv_python = os.path.join(workspace_root, ".venv", "Scripts", "python.exe")
is_running_in_project_venv = os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(os.path.abspath(venv_python))

try:
    import uvicorn
    import fastapi
except ImportError:
    if os.path.exists(venv_python) and not is_running_in_project_venv:
        import subprocess
        sys.exit(subprocess.call([venv_python] + sys.argv))
    else:
        print("\n[!] 'uvicorn' or 'fastapi' missing from the current Python environment.")
        print(f"[*] Interpreter: {sys.executable}")
        print("[*] Automatically installing dependencies from requirements.txt...\n")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(workspace_root, "requirements.txt")])
        import uvicorn
        import fastapi

import webbrowser

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

    uvicorn.run("settle_ai.server:app", host=host, port=port, reload=True)
