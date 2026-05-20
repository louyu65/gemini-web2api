"""
Entry point to start the Gemini API wrapper server.
Usage:
    python run.py
    uvicorn run:app --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

# Ensure api package and gemini_webapi source are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests" / "Gemini-API-master" / "src"))

from api.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True)
