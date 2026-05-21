"""
Cookie health monitor with Feishu (Lark) notifications.

Periodically checks the Gemini account status and sends a Feishu
webhook message when the cookie becomes invalid.
"""

import asyncio
import os

import aiohttp


class FeishuNotifier:
    """Simple Feishu bot webhook notifier."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK", "").strip()

    async def send(self, title: str, content: str) -> None:
        if not self.webhook_url:
            return

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "red",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content},
                    }
                ],
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        print(f"[FeishuNotifier] Failed to send: HTTP {resp.status}")
                    else:
                        print(f"[FeishuNotifier] Alert sent: {title}")
        except Exception as exc:
            print(f"[FeishuNotifier] Exception: {exc}")


class CookieMonitor:
    """
    Background task that periodically checks cookie validity.
    """

    def __init__(
        self,
        gemini_service,
        interval: int = 300,
        notifier: FeishuNotifier | None = None,
    ):
        self.service = gemini_service
        self.interval = interval
        self.notifier = notifier or FeishuNotifier()
        self._task: asyncio.Task | None = None
        self._last_known_ok = True

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            print(f"[CookieMonitor] Started (interval={self.interval}s)")

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
            print("[CookieMonitor] Stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval)
                await self._check_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[CookieMonitor] Error in check loop: {exc}")

    async def _check_once(self) -> None:
        client = getattr(self.service, "client", None)
        if client is None:
            return

        # Re-fetch user status from the server so we detect
        # cookie expiration that happens while the service is running.
        try:
            await client._fetch_user_status()
        except Exception as exc:
            print(f"[CookieMonitor] _fetch_user_status failed: {exc}")
            # Treat failure as invalid
            status_str = "UNKNOWN (fetch failed)"
            is_ok = False
        else:
            try:
                status = getattr(client, "account_status", None)
                if status is None:
                    return
                is_ok = "UNAUTHENTICATED" not in str(status)
                status_str = f"{status.name} ({status.value})" if hasattr(status, "name") else str(status)
            except Exception as exc:
                print(f"[CookieMonitor] Failed to read status: {exc}")
                return

        if is_ok:
            if not self._last_known_ok:
                # Recovered
                print(f"[CookieMonitor] Cookie recovered: {status_str}")
            self._last_known_ok = True
        else:
            print(f"[CookieMonitor] Cookie invalid: {status_str}")
            if self._last_known_ok:
                # State changed from OK -> invalid, send alert
                await self.notifier.send(
                    title="🚨 Gemini Cookie 已失效",
                    content=(
                        f"**账号状态**: {status_str}\n\n"
                        f"**建议操作**:\n"
                        f"1. 重新从浏览器导出最新 Cookie\n"
                        f"2. 调用 `POST /v1/admin/refresh-cookie` 刷新\n"
                        f"3. 或重启服务加载新的 `tests/cookie.json`"
                    ),
                )
            self._last_known_ok = False
