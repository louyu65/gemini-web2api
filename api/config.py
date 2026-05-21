"""
Application configuration.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

IMAGE_DIR = BASE_DIR / "generated_images"
IMAGE_DIR.mkdir(exist_ok=True)

DEFAULT_COOKIE_PATH = BASE_DIR / "tests" / "cookie.json"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

VERIFY_SSL = os.getenv("GEMINI_VERIFY_SSL", "true").lower() != "false"
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "").strip()
COOKIE_CHECK_INTERVAL = int(os.getenv("COOKIE_CHECK_INTERVAL", "300"))
PORT = int(os.getenv("PORT", "8000"))
