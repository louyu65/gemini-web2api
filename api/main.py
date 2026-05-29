"""
FastAPI wrapper for Gemini Web API.
Provides OpenAI-compatible endpoints for chat completions and image generation.
"""

import asyncio
import base64
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Ensure local gemini_webapi is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "Gemini-API-master" / "src"))

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
from .config import IMAGE_DIR, COOKIE_CHECK_INTERVAL, COOKIE_REFRESH_TOKEN
from .utils import (
    gen_id,
    now_ts,
    extract_prompt_and_files,
    resolve_files,
    guess_mime_from_response,
    save_image,
    local_image_url,
)


# ---------------------------------------------------------------------------
# Lifespan: init / shutdown Gemini client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    service = await GeminiService.get_instance("tests/cookie.json")
    app.state.gemini = service

    # Start background cookie health monitor
    monitor = CookieMonitor(service, interval=COOKIE_CHECK_INTERVAL)
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
# Combined CORS + auth middleware
# ---------------------------------------------------------------------------

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Credentials": "true",
}


@app.middleware("http")
async def cors_auth_middleware(request: Request, call_next):
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)

    # Global auth check (skip /health and static files)
    if COOKIE_REFRESH_TOKEN:
        path = request.url.path
        if path != "/health" and not path.startswith("/images/"):
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"error": "Missing Authorization header"}, headers=CORS_HEADERS)
            token = auth[len("Bearer "):].strip()
            if token != COOKIE_REFRESH_TOKEN:
                return JSONResponse(status_code=401, content={"error": "Invalid token"}, headers=CORS_HEADERS)

    response = await call_next(request)

    # Attach CORS headers to every response
    for key, value in CORS_HEADERS.items():
        response.headers[key] = value
    return response


# ---------------------------------------------------------------------------
# Chat Completions
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    service: GeminiService = app.state.gemini
    prompt, files = extract_prompt_and_files(
        [m.model_dump() for m in req.messages]
    )
    files = await resolve_files(files)

    if req.stream:
        async def event_stream() -> AsyncGenerator[str, None]:
            cid = gen_id()
            created = now_ts()

            # Role chunk
            yield f"data: {json.dumps({
                'id': cid,
                'object': 'chat.completion.chunk',
                'created': created,
                'model': req.model,
                'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]
            }, ensure_ascii=False)}\n\n"

            try:
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
        id=gen_id(),
        created=now_ts(),
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
                    mime = guess_mime_from_response(http_resp)
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
        save_image(image_bytes, f".{mime.split('/')[-1]}")

        if req.response_format == "url":
            # Serve via local static URL (requires StaticFiles mount)
            filename = save_image(image_bytes, f".{mime.split('/')[-1]}")
            url_out = local_image_url(filename, str(request.base_url))
            data_list.append(ImageData(url=url_out, revised_prompt=req.prompt))
        else:
            # Default: return base64 so clients get the image inline without extra auth
            b64_str = base64.b64encode(image_bytes).decode("utf-8")
            data_list.append(ImageData(b64_json=b64_str, revised_prompt=req.prompt))

    if not data_list:
        # If no images were returned, surface any text response from Gemini
        fallback_text = getattr(output, "text", "") or ""
        data_list.append(
            ImageData(revised_prompt=fallback_text or req.prompt)
        )

    return ImageGenerationResponse(created=now_ts(), data=data_list)


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
    Accepts either a JSON dict or a raw JSON string.
    The new cookies will be persisted to the local cookie file.
    """
    service: GeminiService = app.state.gemini

    # Parse cookies: dict or JSON string
    raw = req.cookies
    if isinstance(raw, str):
        try:
            cookies = json.loads(raw)
        except json.JSONDecodeError as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"Invalid JSON string in cookies: {exc}",
                        "type": "invalid_request",
                        "code": "bad_request",
                    }
                },
            )
        if not isinstance(cookies, dict):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "Parsed cookies must be a JSON object.",
                        "type": "invalid_request",
                        "code": "bad_request",
                    }
                },
            )
    else:
        cookies = raw

    try:
        result = await service.refresh_cookie(cookies)
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


# ---------------------------------------------------------------------------
# Extension: cookie refresh with token auth
# ---------------------------------------------------------------------------

@app.post("/v1/extension/refresh-cookie")
async def extension_refresh_cookie(req: Request):
    """
    Receive cookies from the Chrome extension and refresh at runtime.
    Requires Authorization: Bearer <token> matching COOKIE_REFRESH_TOKEN.
    """
    # Parse body
    try:
        body = await req.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON body: {exc}"},
        )

    cookies = body.get("cookies")
    if not isinstance(cookies, dict) or "__Secure-1PSID" not in cookies:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing __Secure-1PSID in cookies"},
        )

    # Refresh
    service: GeminiService = app.state.gemini
    try:
        # Log cookie summary for debugging
        cookie_names = sorted(cookies.keys())
        psid = cookies.get('__Secure-1PSID', '')
        psid_preview = psid[:10] + '...' + psid[-4:] if len(psid) > 14 else psid
        print(f"[Extension] Received {len(cookie_names)} cookies: {cookie_names}, __Secure-1PSID: {psid_preview}")

        result = await service.refresh_cookie(cookies)
        account_status = result.get("account_status", "unknown")
        print(f"[Extension] Cookie refreshed. Account status: {account_status}")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "account_status": account_status,
                "description": result.get("description", ""),
                "message": "Cookie refreshed successfully from extension.",
            },
        )
    except Exception as exc:
        print(f"[Extension] Refresh failed: {exc}")
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
