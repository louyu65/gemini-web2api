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
        cookie_count = len(cookies)
        psid_preview = psid[:10] + "..." + psid[-4:] if len(psid) > 14 else psid

        print(f"[GeminiService] _build_client start: psid={psid_preview}, cookies={cookie_count}, has_psidts={bool(psidts)}")

        if not psid:
            raise RuntimeError("Missing __Secure-1PSID in cookie data")

        # Pass all extra cookies to help with session validation
        extra = {
            k: v
            for k, v in cookies.items()
            if k not in {"__Secure-1PSID", "__Secure-1PSIDTS"}
        }
        print(f"[GeminiService] Extra cookies: {len(extra)} ({sorted(extra.keys())})")

        import os
        import tempfile
        verify = os.getenv("GEMINI_VERIFY_SSL", "true").lower() != "false"

        # Close old client first
        if self.client:
            print("[GeminiService] Closing old client...")
            try:
                await self.client.close()
                print("[GeminiService] Old client closed")
            except Exception as e:
                print(f"[GeminiService] Old client close warning: {e}")
            self.client = None

        # Clear cache files — match _get_cookie_cache_dir() from rotate_1psidts.py
        _gemini_cache = os.getenv("GEMINI_COOKIE_PATH")
        cache_dir = Path(_gemini_cache) if _gemini_cache else Path(tempfile.gettempdir()) / "gemini_webapi"
        if cache_dir.exists():
            cleared = 0
            for stale in cache_dir.glob(".cached_cookies_*.json"):
                try:
                    stale.unlink()
                    cleared += 1
                except Exception:
                    pass
            if cleared:
                print(f"[GeminiService] Cleared {cleared} cache file(s)")

        # Create new client
        print(f"[GeminiService] Creating new GeminiClient (psid={psid_preview})...")
        self.client = GeminiClient(
            secure_1psid=psid,
            secure_1psidts=psidts,
            cookies=extra or None,
            verify=verify,
        )

        print("[GeminiService] Calling client.init()...")
        await self.client.init(auto_refresh=True, verbose=False)
        print("[GeminiService] client.init() completed")

        # Log account status for diagnostics
        status = getattr(self.client, "account_status", None)
        if status:
            print(f"[GeminiService] Account status: {status.name} ({status.value}) - {status.description}")
        else:
            print("[GeminiService] Account status: unknown")

        # Verify the client can actually make requests
        try:
            await self.client._fetch_user_status()
            refreshed_status = getattr(self.client, "account_status", None)
            if refreshed_status:
                print(f"[GeminiService] Post-init fetch_user_status: {refreshed_status.name} ({refreshed_status.value})")
        except Exception as e:
            print(f"[GeminiService] Post-init fetch_user_status failed: {e}")

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
