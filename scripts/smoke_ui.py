"""Comprueba las páginas y los estáticos contra la app local."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BASE = os.getenv("NOTAS_BASE", "http://127.0.0.1:8010")
USER = os.getenv("NOTAS_USER") or os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("NOTAS_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")


def wait_for_server(client: httpx.Client) -> None:
    for _ in range(40):
        try:
            if client.get("/api/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise SystemExit("la app no respondió")


def main() -> int:
    if not PASSWORD:
        print("Falta NOTAS_PASSWORD o ADMIN_PASSWORD en .env", file=sys.stderr)
        return 2

    with httpx.Client(base_url=BASE, timeout=10, follow_redirects=False) as client:
        wait_for_server(client)

        login_page = client.get("/login")
        print("login page", login_page.status_code, "Entrar" in login_page.text)

        login = client.post(
            "/login", data={"username": USER, "password": PASSWORD}
        )
        print("login post", login.status_code, login.headers.get("location"))

        notes_page = client.get("/notes")
        print(
            "notes page",
            notes_page.status_code,
            "Recordatorios" in notes_page.text,
            "Buscar notas" in notes_page.text,
        )

        reminders_page = client.get("/reminders")
        print("reminders page", reminders_page.status_code, "Nuevo recordatorio" in reminders_page.text)

        for asset in ("/static/app.css", "/static/app.js", "/static/manifest.webmanifest", "/static/icon.svg"):
            response = client.get(asset)
            print(asset, response.status_code, len(response.content))

        preview = client.post(
            "/partials/preview",
            data={"content": "# Hola\n\n**mundo** <script>alert(1)</script>"},
        )
        print(
            "preview",
            preview.status_code,
            "<h1>Hola</h1>" in preview.text,
            "<script>" not in preview.text,
        )

        tree = client.get("/api/tree").json()
        if tree["notes"]:
            note_id = tree["notes"][0]["id"]
            note_page = client.get(f"/notes?note={note_id}")
            print(
                "note page",
                note_page.status_code,
                'aria-label="Vista previa"' in note_page.text,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
