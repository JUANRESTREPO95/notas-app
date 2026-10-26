"""Prueba rápida contra una instancia local de la app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BASE = os.getenv("NOTAS_BASE", "http://127.0.0.1:8010")
USER = os.getenv("NOTAS_USER") or os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("NOTAS_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("Falta NOTAS_PASSWORD o ADMIN_PASSWORD en .env", file=sys.stderr)
        return 2

    with httpx.Client(base_url=BASE, timeout=10) as client:
        health = client.get("/api/health")
        print("health", health.status_code, health.json())

        login = client.post("/api/login", json={"username": USER, "password": PASSWORD})
        print("login", login.status_code, login.json())
        if login.status_code != 200:
            return 1

        folder = client.post("/api/folders", json={"path": "Notas"})
        print("folder", folder.status_code, folder.json())

        note = client.post(
            "/api/notes",
            json={"folder": "Notas", "title": "Bienvenida", "content": "Primera nota de prueba"},
        )
        print("note", note.status_code, note.json())

        tree = client.get("/api/tree")
        print("tree", tree.status_code, tree.json())

        search = client.get("/api/search", params={"q": "prueba"})
        print("search", search.status_code, search.json())

        reminder = client.post(
            "/api/reminders",
            json={"title": "Probar la app", "due_at": "2026-10-26T09:00:00-05:00"},
        )
        print("reminder", reminder.status_code, reminder.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
