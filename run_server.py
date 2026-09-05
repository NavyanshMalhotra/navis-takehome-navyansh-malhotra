#!/usr/bin/env python3
"""
Server runner for Nevis Agentic Platform.
Starts the FastAPI backend and serves the interactive web dashboard.
Auto-delegates to local .venv if current Python environment lacks dependencies.

Usage:
    python3 run_server.py
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Auto-delegate to .venv if current interpreter lacks uvicorn
venv_python = BASE_DIR / ".venv" / "bin" / "python3"
if sys.executable != str(venv_python) and venv_python.exists():
    try:
        import uvicorn
        import fastapi
    except ImportError:
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

try:
    import uvicorn
    from config import config
except ImportError:
    print("\n[ERROR] Missing required server packages ('uvicorn', 'fastapi').")
    print("Please install them or run with the project virtual environment:")
    print("    source .venv/bin/activate && python3 run_server.py")
    print("Or:")
    print("    .venv/bin/python3 run_server.py\n")
    sys.exit(1)

if __name__ == "__main__":
    print("=" * 80)
    print("NEVIS AGENTIC WEALTH ONBOARDING PLATFORM")
    print(f"Starting server on http://{config.server_host}:{config.server_port}")
    print("=" * 80)
    uvicorn.run(
        "server.api:app",
        host=config.server_host,
        port=config.server_port,
        reload=False,
        log_level="info"
    )
