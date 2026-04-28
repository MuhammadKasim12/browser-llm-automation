"""
Export a Google Doc to PDF using a saved browser session.
Usage: uv run python gdoc_to_pdf.py <google_doc_url> [output_path]
Run gdoc_login.py first to create the session file.
"""
import asyncio
import os
import sys
import re
from playwright.async_api import async_playwright

STORAGE_STATE_PATH = os.path.join(os.path.dirname(__file__), "google_session.json")


def extract_doc_id(url: str) -> str:
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        raise ValueError(f"Could not extract document ID from URL: {url}")
    return match.group(1)


async def export_gdoc(doc_url: str, output_path: str):
    if not os.path.exists(STORAGE_STATE_PATH):
        print("ERROR: No session found. Please run: uv run python gdoc_login.py")
        sys.exit(1)

    doc_id = extract_doc_id(doc_url)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=STORAGE_STATE_PATH,
            accept_downloads=True,
        )
        page = await context.new_page()

        # Verify login
        await page.goto("https://docs.google.com", wait_until="domcontentloaded")
        if "accounts.google.com" in page.url or "signin" in page.url:
            await browser.close()
            print("ERROR: Session expired. Please run: uv run python gdoc_login.py")
            sys.exit(1)

        print(f"Logged in. Exporting doc {doc_id}...")

        async with page.expect_download(timeout=30000) as download_info:
            await page.evaluate(f"window.location = '{export_url}'")

        download = await download_info.value
        await download.save_as(output_path)
        await browser.close()
        print(f"Saved to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python gdoc_to_pdf.py <google_doc_url> [output_path]")
        sys.exit(1)

    doc_url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/gdoc_export.pdf"

    asyncio.run(export_gdoc(doc_url, output_path))


if __name__ == "__main__":
    main()
