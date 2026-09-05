#!/usr/bin/env python3
"""
Server runner for Nevis Agentic Platform.
Starts the FastAPI backend and serves the interactive web dashboard.

Usage:
    python3 run_server.py
"""

import sys
import uvicorn
from pathlib import Path
from config import config

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
