"""
Cookie 诊断脚本：启用详细日志，定位为什么最新 cookie 仍然 UNAUTHENTICATED。

用法：
    python tests/diagnose_cookie.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "Gemini-API-master" / "src"))

from gemini_webapi import GeminiClient


def load_cookies(path: str = "tests/cookie.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cookies" in data:
        return data["cookies"]
    return data


async def diagnose():
    cookies = load_cookies()
    psid = cookies.get("__Secure-1PSID", "")
    psidts = cookies.get("__Secure-1PSIDTS", "")

    print("=" * 60)
    print("Cookie 诊断")
    print("=" * 60)
    print(f"__Secure-1PSID  长度: {len(psid)}  前缀: {psid[:20]}...")
    print(f"__Secure-1PSIDTS 长度: {len(psidts)}  前缀: {psidts[:20]}...")

    # 检查缓存目录
    import tempfile, os
    cache_dir = Path(os.getenv("GEMINI_COOKIE_PATH", tempfile.gettempdir())) / "gemini_webapi"
    print(f"\n缓存目录: {cache_dir}")
    if cache_dir.exists():
        files = list(cache_dir.glob(".cached_cookies_*.json"))
        print(f"缓存文件数: {len(files)}")
        for f in files:
            print(f"  - {f.name} ({f.stat().st_size} bytes)")
    else:
        print("缓存目录不存在")

    # 尝试初始化客户端（启用详细日志）
    print("\n" + "=" * 60)
    print("开始初始化 GeminiClient（verbose=True）")
    print("=" * 60)

    extra = {k: v for k, v in cookies.items() if k not in {"__Secure-1PSID", "__Secure-1PSIDTS"}}

    client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts,
        cookies=extra or None,
    )

    try:
        await client.init(auto_refresh=False, verbose=True)
        status = getattr(client, "account_status", None)
        if status:
            print(f"\n✅ 初始化成功")
            print(f"Account status: {status.name} ({status.value}) - {status.description}")
        else:
            print("\n⚠️ 初始化完成但 account_status 为空")
    except Exception as exc:
        print(f"\n❌ 初始化失败: {exc}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
