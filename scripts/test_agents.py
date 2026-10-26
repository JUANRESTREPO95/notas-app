"""Prueba de integración de tokens de agentes (Claude/Hermes)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BASE = os.getenv("NOTAS_BASE", "http://127.0.0.1:8010")
USER = os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("Falta ADMIN_PASSWORD en .env", file=sys.stderr)
        return 2

    tokens: list[str] = []
    with httpx.Client(base_url=BASE, timeout=10) as admin:
        login = admin.post("/api/login", json={"username": USER, "password": PASSWORD})
        login.raise_for_status()

        read = admin.post(
            "/api/tokens",
            json={"name": "test-read", "rules": [{"path": "Notas", "level": "read"}]},
        )
        read.raise_for_status()
        read_data = read.json()
        tokens.append(read_data["id"])

        with httpx.Client(
            base_url=BASE, timeout=10, headers={"Authorization": f"Bearer {read_data['token']}"}
        ) as agent:
            tree = agent.get("/api/tree")
            print("lectura tree", tree.status_code, tree.json()["folders"])
            denied = agent.post(
                "/api/notes",
                json={"folder": "Notas", "title": "No permitida", "content": "x"},
            )
            print("escritura denegada", denied.status_code)
            assert denied.status_code == 403

        write = admin.post(
            "/api/tokens",
            json={"name": "test-write", "rules": [{"path": "Notas", "level": "write"}]},
        )
        write.raise_for_status()
        write_data = write.json()
        tokens.append(write_data["id"])

        with httpx.Client(
            base_url=BASE, timeout=10, headers={"Authorization": f"Bearer {write_data['token']}"}
        ) as agent:
            created = agent.post(
                "/api/notes",
                json={"folder": "Notas", "title": "Token test", "content": "desde agente"},
            )
            print("escritura permitida", created.status_code)
            assert created.status_code == 201
            note_id = created.json()["id"]
            deleted = agent.delete(f"/api/notes/{note_id}")
            print("borrado del agente", deleted.status_code)
            assert deleted.status_code == 200

        for token_id in tokens:
            admin.delete(f"/api/tokens/{token_id}")

    print("tokens de prueba eliminados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
