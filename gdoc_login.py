"""
One-time Google login to persist session for gdoc_to_pdf.py
Usage: uv run python gdoc_login.py

A browser window will open. Sign in to Google fully (until you see Google Docs),
then type 'done' and press Enter in this terminal.
"""
import asyncio
from playwright.async_api import async_playwright

STORAGE_STATE_PATH = "google_session.json"


async def login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://docs.google.com")

        print("\nBrowser opened to Google Docs.")
        print("1. Complete the full Google/Intuit SSO sign-in")
        print("2. Wait until you can see your Google Docs homepage")
        print("3. Type 'done' below and press Enter to save the session\n")

        while True:
            val = input("Type 'done' when fully logged in: ").strip().lower()
            if val == "done":
                break

        await context.storage_state(path=STORAGE_STATE_PATH)
        await browser.close()
        print(f"Session saved to {STORAGE_STATE_PATH}")


if __name__ == "__main__":
    asyncio.run(login())
