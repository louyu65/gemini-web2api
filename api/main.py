"""
FastAPI wrapper for Gemini Web API.
Provides OpenAI-compatible endpoints for chat completions and image generation.
"""

import asyncio
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Ensure local gemini_webapi is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "Gemini-API-master" / "src"))

from gemini_webapi import GeminiClient
from gemini_webapi.types import ModelOutput

from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    Choice,
    StreamChoice,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageData,
    ImageDownloadRequest,
    RefreshCookieRequest,
    RefreshCookieResponse,
)
from .gemini_service import GeminiService
from .monitor import CookieMonitor


# ---------------------------------------------------------------------------
# Image storage
# ---------------------------------------------------------------------------

IMAGE_DIR = Path(__file__).resolve().parent.parent / "generated_images"
IMAGE_DIR.mkdir(exist_ok=True)


def _local_image_url(filename: str, request: Request | None = None) -> str:
    """Build the publicly accessible URL for a stored image."""
    if request is not None:
        base = str(request.base_url).rstrip("/")
        return f"{base}/images/{filename}"
    # Fallback for cases where request context is unavailable
    port = os.getenv("PORT", "8000")
    return f"http://127.0.0.1:{port}/images/{filename}"


# ---------------------------------------------------------------------------
# Lifespan: init / shutdown Gemini client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    service = await GeminiService.get_instance("tests/cookie.json")
    app.state.gemini = service

    # Start background cookie health monitor
    interval = int(os.getenv("COOKIE_CHECK_INTERVAL", "300"))
    monitor = CookieMonitor(service, interval=interval)
    monitor.start()
    app.state.monitor = monitor

    yield

    monitor.stop()
    if service.client:
        await service.client.close()


app = FastAPI(
    title="Gemini API Wrapper",
    description="OpenAI-compatible REST API for Google Gemini (web).",
    version="0.1.0",
    lifespan=lifespan,
)

# Serve generated images statically
app.mount("/images", StaticFiles(directory=str(IMAGE_DIR)), name="images")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now_ts() -> int:
    return int(time.time())


async def _download_image(url: str) -> str:
    """Download a remote image to a temp file and return the local path."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            suffix = Path(url.split("?")[0]).suffix or ".png"
            fd, path = tempfile.mkstemp(suffix=suffix)
            with open(fd, "wb") as f:
                f.write(data)
            return path


def _extract_prompt_and_files(messages: list[dict]) -> tuple[str, list[str]]:
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
                        # Will be downloaded async later
                        files.append(f"__url__:{url}")
                        text_parts.append("[image attached]")
                    else:
                        files.append(url)
                        text_parts.append("[image attached]")
            prompt_parts.append(f"[{role}]: {' '.join(text_parts)}")

    return "\n".join(prompt_parts), files


async def _resolve_files(files: list[str]) -> list[str]:
    """Resolve any __url__: prefix entries by downloading them."""
    resolved = []
    for f in files:
        if isinstance(f, str) and f.startswith("__url__:"):
            resolved.append(await _download_image(f[8:]))
        else:
            resolved.append(f)
    return resolved


# ---------------------------------------------------------------------------
# Chat Completions
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    service: GeminiService = app.state.gemini
    prompt, files = _extract_prompt_and_files(
        [m.model_dump() for m in req.messages]
    )
    files = await _resolve_files(files)

    if req.stream:
        async def event_stream() -> AsyncGenerator[str, None]:
            cid = _gen_id()
            created = _now_ts()

            # Role chunk
            yield f"data: {json.dumps({
                'id': cid,
                'object': 'chat.completion.chunk',
                'created': created,
                'model': req.model,
                'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]
            }, ensure_ascii=False)}\n\n"

            try:
                # Note: generate_content_stream is an async generator function;
                # do NOT await it, just call it and iterate.
                stream_gen = service.client.generate_content_stream(
                    prompt, files=files or None
                )
                async for chunk in stream_gen:
                    delta = getattr(chunk, "text_delta", "") or ""
                    if delta:
                        yield f"data: {json.dumps({
                            'id': cid,
                            'object': 'chat.completion.chunk',
                            'created': created,
                            'model': req.model,
                            'choices': [{'index': 0, 'delta': {'content': delta}, 'finish_reason': None}]
                        }, ensure_ascii=False)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({
                    'id': cid,
                    'object': 'chat.completion.chunk',
                    'created': created,
                    'model': req.model,
                    'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]
                }, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    try:
        output: ModelOutput = await service.client.generate_content(
            prompt, files=files or None
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Gemini upstream error: {exc}",
                    "type": "upstream_error",
                    "code": "bad_gateway",
                }
            },
        )
    text = getattr(output, "text", "") or ""

    return ChatCompletionResponse(
        id=_gen_id(),
        created=_now_ts(),
        model=req.model,
        choices=[
            Choice(
                index=0,
                message={"role": "assistant", "content": text},
                finish_reason="stop",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Image Generations
# ---------------------------------------------------------------------------

@app.post("/v1/images/generations")
async def image_generations(req: ImageGenerationRequest, request: Request):
    service: GeminiService = app.state.gemini

    try:
        output: ModelOutput = await service.client.generate_content(
            f"Generate an image of: {req.prompt}"
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Gemini upstream error: {exc}",
                    "type": "upstream_error",
                    "code": "bad_gateway",
                }
            },
        )

    images = getattr(output, "images", []) or []
    data_list: list[ImageData] = []

    for img in images:
        url = getattr(img, "url", None)
        b64 = getattr(img, "b64", None)
        image_bytes: bytes | None = None
        mime = "image/png"

        # 1. Try to download from Google URL using authenticated session
        if url and service.client and service.client.client:
            try:
                http_resp = await service.client.client.get(url)
                if http_resp.status_code == 200:
                    image_bytes = http_resp.content
                    mime = _guess_mime_from_response(http_resp)
            except Exception:
                pass

        # 2. Fallback to base64 returned by Gemini
        if image_bytes is None and b64:
            try:
                image_bytes = base64.b64decode(b64)
                mime = "image/png"
            except Exception:
                pass

        if image_bytes is None:
            continue

        # Optionally persist to local cache (deduplicated)
        _save_image(image_bytes, f".{mime.split('/')[-1]}")

        if req.response_format == "url":
            # Serve via local static URL (requires StaticFiles mount)
            filename = _save_image(image_bytes, f".{mime.split('/')[-1]}")
            local_url = _local_image_url(filename, request)
            data_list.append(ImageData(url=local_url, revised_prompt=req.prompt))
        else:
            # Default: return base64 so clients get the image inline without extra auth
            b64_str = base64.b64encode(image_bytes).decode("utf-8")
            data_list.append(ImageData(b64_json=b64_str, revised_prompt=req.prompt))

    if not data_list:
        # If no images were returned, surface any text response from Gemini
        # (e.g. refusal message, policy explanation) so the caller knows why.
        fallback_text = getattr(output, "text", "") or ""
        data_list.append(
            ImageData(revised_prompt=fallback_text or req.prompt)
        )

    return ImageGenerationResponse(created=_now_ts(), data=data_list)


def _guess_mime_from_response(resp) -> str:
    """Guess MIME type from response headers."""
    ct = resp.headers.get("content-type", "image/png")
    return ct.split(";")[0].strip().lower()


def _save_image(data: bytes, ext: str) -> str:
    """Save image bytes to IMAGE_DIR and return the filename."""
    digest = hashlib.sha256(data).hexdigest()[:16]
    filename = f"{digest}{ext}"
    path = IMAGE_DIR / filename
    if not path.exists():
        with open(path, "wb") as f:
            f.write(data)
    return filename


# ---------------------------------------------------------------------------
# Image Download (proxy via Gemini cookies)
# ---------------------------------------------------------------------------

@app.post("/v1/images/download")
async def image_download(req: ImageDownloadRequest):
    """
    Download an image from Google (lh3.googleusercontent.com etc.)
    using the authenticated Gemini session cookies.
    Returns the raw image bytes with correct Content-Type.
    """
    service: GeminiService = app.state.gemini
    if not service.client or not service.client.client:
        return JSONResponse(
            status_code=503,
            content={"error": "Gemini client not initialized"},
        )

    try:
        # Use the same AsyncSession that holds the authenticated cookies
        http_resp = await service.client.client.get(req.url)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Failed to download image: {exc}",
                    "type": "upstream_error",
                    "code": "bad_gateway",
                }
            },
        )

    if http_resp.status_code != 200:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Image host returned {http_resp.status_code}",
                    "type": "upstream_error",
                    "code": "bad_gateway",
                }
            },
        )

    content_type = http_resp.headers.get("content-type", "image/png")
    return Response(
        content=http_resp.content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="image.{content_type.split("/")[-1]}"'
        },
    )


# ---------------------------------------------------------------------------
# Models list
# ---------------------------------------------------------------------------

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gemini", "object": "model", "created": 0, "owned_by": "google"},
            {"id": "gemini-vision", "object": "model", "created": 0, "owned_by": "google"},
        ],
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    service: GeminiService = app.state.gemini
    status = "ok"
    account_status = "unknown"
    if service.client:
        try:
            account_status = getattr(service.client, "account_status", "unknown")
            if hasattr(account_status, "name"):
                account_status = f"{account_status.name} ({account_status.value})"
        except Exception:
            pass
        if "UNAUTHENTICATED" in str(account_status):
            status = "degraded"
    return {
        "status": status,
        "account_status": account_status,
        "note": "UNAUTHENTICATED means cookies expired; image generation and advanced features will be unavailable.",
    }


# ---------------------------------------------------------------------------
# Admin: refresh cookie at runtime
# ---------------------------------------------------------------------------

@app.post("/v1/admin/refresh-cookie")
async def refresh_cookie(req: RefreshCookieRequest):
    """
    Refresh cookies at runtime without restarting the service.
    The new cookies will be persisted to the local cookie file.
    """
    service: GeminiService = app.state.gemini
    try:
        result = await service.refresh_cookie(req.cookies)
        return RefreshCookieResponse(
            success=True,
            account_status=result.get("account_status", "unknown"),
            description=result.get("description", ""),
            message="Cookie refreshed and persisted successfully.",
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Failed to refresh cookie: {exc}",
                    "type": "upstream_error",
                    "code": "bad_gateway",
                }
            },
        )
