"""HTML -> PDF via headless Chromium (Playwright).

Graceful: if Playwright or its browser isn't installed, returns None and the caller falls back to
the print-optimised HTML (Cmd/Ctrl-P). Install once with: ``python -m playwright install chromium``.
Rendering from the live URL keeps /static and web fonts resolving for full fidelity.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def url_to_pdf(url: str, out_path: Path) -> Optional[Path]:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            page.pdf(path=str(out_path), prefer_css_page_size=True, print_background=True)
            browser.close()
        return out_path
    except Exception:
        return None


def html_to_pdf(html: str, out_path: Path) -> Optional[Path]:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.pdf(path=str(out_path), prefer_css_page_size=True, print_background=True)
            browser.close()
        return out_path
    except Exception:
        return None
