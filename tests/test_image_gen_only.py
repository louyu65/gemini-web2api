"""
Minimal test: only test image generation, without downloading.
Run this to verify if your cookie supports image generation.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "Gemini-API-master" / "src"))

from gemini_webapi import GeminiClient

async def test():
    with open("tests/cookie.json", "r", encoding="utf-8") as f:
        cookies = json.load(f)

    psid = cookies.get("__Secure-1PSID", "")
    psidts = cookies.get("__Secure-1PSIDTS", "")

    if not psid:
        print("ERROR: Missing __Secure-1PSID")
        return

    print(f"__Secure-1PSID: {psid[:20]}...")
    print(f"__Secure-1PSIDTS: {psidts[:20] if psidts else 'EMPTY'}...")

    extra = {k: v for k, v in cookies.items() if k not in {"__Secure-1PSID", "__Secure-1PSIDTS"}}

    client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
    client.cookies = extra

    try:
        await client.init(auto_refresh=False, verbose=True)
        print(f"\nAccount status: {client.account_status.name} ({client.account_status.value})")
        print(f"Description: {client.account_status.description}")

        print("\n--- Generating image: 'draw a cat' ---")
        output = await client.generate_content("draw a cat")

        text = getattr(output, "text", "") or ""
        images = getattr(output, "images", []) or []

        print(f"Text response: {text[:200] if text else '(empty)'}")
        print(f"Images count: {len(images)}")

        if images:
            for i, img in enumerate(images):
                url = getattr(img, "url", None)
                b64 = getattr(img, "b64", None)
                print(f"  Image {i}: url={url[:50] + '...' if url else None}, b64={bool(b64)}")
            print("\nSUCCESS: Image generation works!")
        else:
            print("\nFAILED: No images returned.")
            if "sign" in text.lower() or "out" in text.lower():
                print("Hint: Gemini says you are signed out. Cookie may be expired.")

    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
