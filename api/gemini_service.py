"""
Singleton async service wrapping GeminiClient.
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

# Add local gemini_webapi source to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "Gemini-API-master" / "src"))

from gemini_webapi import GeminiClient
from gemini_webapi.types import ModelOutput


class GeminiService:
    _instance: "GeminiService | None" = None
    _lock = asyncio.Lock()

    client: GeminiClient | None = None
    cookie_path: str = ""

    @classmethod
    async def get_instance(cls, cookie_path: str = "tests/cookie.json") -> "GeminiService":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    await instance._init(cookie_path)
                    cls._instance = instance
        return cls._instance

    async def _init(self, cookie_path: str) -> None:
        self.cookie_path = cookie_path
        with open(cookie_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", data) if isinstance(data, dict) else data
        await self._build_client(cookies)

    async def _build_client(self, cookies: dict) -> None:
        """Build or rebuild the GeminiClient from a cookie dict."""
        psid = cookies.get("__Secure-1PSID", "")
        psidts = cookies.get("__Secure-1PSIDTS", "")

        if not psid:
            raise RuntimeError("Missing __Secure-1PSID in cookie data")

        # Pass all extra cookies to help with session validation
        extra = {
            k: v
            for k, v in cookies.items()
            if k not in {"__Secure-1PSID", "__Secure-1PSIDTS"}
        }

        import os
        import tempfile
        verify = os.getenv("GEMINI_VERIFY_SSL", "true").lower() != "false"

        # Close old client first (this may save stale cookies to cache)
        if self.client:
            try:
                await self.client.close()
            except Exception:
                pass
            self.client = None

        # NOW clear cache files — after old client is closed, so its
        # save_cookies() doesn't re-create the cache we just deleted.
        cache_dir = Path(os.getenv("GEMINI_COOKIE_PATH", tempfile.gettempdir())) / "gemini_webapi"
        if cache_dir.exists():
            for stale in cache_dir.glob(".cached_cookies_*.json"):
                try:
                    stale.unlink()
                    print(f"[GeminiService] Cleared stale cache: {stale.name}")
                except Exception:
                    pass

        self.client = GeminiClient(
            secure_1psid=psid,
            secure_1psidts=psidts,
            cookies=extra or None,
            verify=verify,
        )
        await self.client.init(auto_refresh=True, verbose=False)

        # Log account status for diagnostics
        status = getattr(self.client, "account_status", None)
        if status:
            print(f"[GeminiService] Account status: {status.name} ({status.value}) - {status.description}")
        else:
            print("[GeminiService] Account status: unknown")

    async def refresh_cookie(self, cookies: dict) -> dict:
        """
        Refresh cookie at runtime without restarting the service.
        Returns the new account status.
        """
        await self._build_client(cookies)

        # Persist to disk
        if self.cookie_path:
            with open(self.cookie_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)

        status = getattr(self.client, "account_status", None)
        return {
            "account_status": f"{status.name} ({status.value})" if status else "unknown",
            "description": status.description if status else "",
        }

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "gemini",
        stream: bool = False,
    ) -> ModelOutput | AsyncGenerator[ModelOutput, None]:
        if self.client is None:
            raise RuntimeError("Client not initialized")

        # Simple conversion: concatenate messages into a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # For vision, we handle separately
                text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                prompt_parts.append(f"[{role}]: {' '.join(text_parts)}")
            else:
                prompt_parts.append(f"[{role}]: {content}")
        prompt = "\n".join(prompt_parts)

        if stream:
            return self.client.generate_content_stream(prompt)
        return await self.client.generate_content(prompt)

    async def chat_completion_with_files(
        self,
        messages: list[dict],
        model: str = "gemini",
        stream: bool = False,
    ) -> ModelOutput | AsyncGenerator[ModelOutput, None]:
        if self.client is None:
            raise RuntimeError("Client not initialized")

        # Extract text prompt and image paths/urls from messages
        prompt = ""
        files = []

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt += content + "\n"
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        prompt += part.get("text", "") + "\n"
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("file:///"):
                            files.append(url.replace("file:///", ""))
                        elif url.startswith("http"):
                            # Download remote image to temp file
                            files.append(await self._download_image(url))
                        else:
                            files.append(url)

        if stream:
            return self.client.generate_content_stream(prompt.strip(), files=files or None)
        return await self.client.generate_content(prompt.strip(), files=files or None)

    async def generate_image(self, prompt: str) -> list[ModelOutput]:
        """Ask Gemini to generate images and return outputs containing images."""
        if self.client is None:
            raise RuntimeError("Client not initialized")

        # Use a strong model for image generation
        output = await self.client.generate_content(
            f"Generate an image: {prompt}",
        )
        return [output]

    async def _download_image(self, url: str) -> str:
        import aiohttp
        import tempfile
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
                suffix = Path(url).suffix or ".png"
                fd, path = tempfile.mkstemp(suffix=suffix)
                with open(fd, "wb") as f:
                    f.write(data)
                return path


# Global accessor
async def get_gemini_service() -> GeminiService:
    return await GeminiService.get_instance()
