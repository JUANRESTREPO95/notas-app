"""Capturas de la interfaz en varios tamaños y en modo claro/oscuro."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BASE = os.getenv("NOTAS_BASE", "http://127.0.0.1:8010")
USER = os.getenv("NOTAS_USER") or os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("NOTAS_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")
OUT = BASE_DIR / "screenshots"

VIEWPORTS = [
    (375, 812, "mobile"),
    (768, 1024, "tablet"),
    (1024, 768, "laptop"),
    (1440, 900, "desktop"),
]


def login(page) -> None:
    page.goto(f"{BASE}/login")
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url("**/notes")
    page.wait_for_timeout(600)


def main() -> None:
    if not PASSWORD:
        raise SystemExit("Falta NOTAS_PASSWORD o ADMIN_PASSWORD en .env")

    OUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height, label in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            page.goto(f"{BASE}/login")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / f"login-{label}.png"), full_page=True)

            login(page)
            page.screenshot(path=str(OUT / f"notes-{label}.png"), full_page=True)

            if page.locator(".note-item").count() > 0:
                page.locator(".note-item").first.click()
                page.wait_for_load_state("load")
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT / f"editor-{label}.png"), full_page=False)

            page.goto(f"{BASE}/reminders")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / f"reminders-{label}.png"), full_page=True)

            page.evaluate("localStorage.setItem('notas-theme','dark')")
            page.goto(f"{BASE}/notes")
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"notes-dark-{label}.png"), full_page=True)

            context.close()
        browser.close()
    print(f"capturas en {OUT}")


if __name__ == "__main__":
    main()
