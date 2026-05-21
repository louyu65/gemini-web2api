"""
Utility helpers for the Gemini API wrapper.
"""

import asyncio
import base64
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import aiohttp

from .config import IMAGE_DIR


def gen_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now_ts() -> int:
    return int(time.time())


async def download_image(url: str) -> str:
    """Download a remote image to a temp file and return the local path."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            suffix = Path(url.split("?")[0]).suffix or ".png"
            fd, path = tempfile.mkstemp(suffix=suffix)
            with open(fd, "wb") as f:
                f.write(data)
            return path


def extract_prompt_and_files(messages: list[dict]) -> tuple[str, list[str]]:
    """
    Convert OpenAI-style messages into a plain prompt + list of local file paths.
    Supports vision input via image_url (base64, file://, http://).
    """
    prompt_parts = []
    files: list[str] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            prompt_parts.append(f"[{role}]: {content}")
        elif isinstance(content, list):
            text_parts = []
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    text_parts.append(part.get("text", ""))
                elif ptype == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:image"):
                        header, b64 = url.split(",", 1)
                        ext = header.split(";")[0].split("/")[-1] or "png"
                        fd, path = tempfile.mkstemp(suffix=f".{ext}")
                        with open(fd, "wb") as f:
                            f.write(base64.b64decode(b64))
                        files.append(path)
                        text_parts.append("[image attached]")
                    elif url.startswith("file:///"):
                        files.append(url.replace("file:///", ""))
                        text_parts.append("[image attached]")
                    elif url.startswith("http"):
                        files.append(f"__url__:{url}")
                        text_parts.append("[image attached]")
                    else:
                        files.append(url)
                        text_parts.append("[image attached]")
            prompt_parts.append(f"[{role}]: {' '.join(text_parts)}")

    return "\n".join(prompt_parts), files


async def resolve_files(files: list[str]) -> list[str]:
    """Resolve any __url__: prefix entries by downloading them."""
    resolved = []
    for f in files:
        if isinstance(f, str) and f.startswith("__url__:"):
            resolved.append(await download_image(f[8:]))
        else:
            resolved.append(f)
    return resolved


def guess_mime_from_response(resp) -> str:
    """Guess MIME type from response headers."""
    ct = resp.headers.get("content-type", "image/png")
    return ct.split(";")[0].strip().lower()


def save_image(data: bytes, ext: str) -> str:
    """Save image bytes to IMAGE_DIR and return the filename."""
    digest = hashlib.sha256(data).hexdigest()[:16]
    filename = f"{digest}{ext}"
    path = IMAGE_DIR / filename
    if not path.exists():
        with open(path, "wb") as f:
            f.write(data)
    return filename


def local_image_url(filename: str, base_url: str | None = None) -> str:
    """Build the publicly accessible URL for a stored image."""
    if base_url is not None:
        return f"{base_url.rstrip('/')}/images/{filename}"
    port = os.getenv("PORT", "8000")
    return f"http://127.0.0.1:{port}/images/{filename}"
