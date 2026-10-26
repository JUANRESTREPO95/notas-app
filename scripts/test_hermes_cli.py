"""Prueba el CLI de Hermes y los permisos por carpeta contra una app local."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BASE = os.getenv("NOTAS_BASE", "http://127.0.0.1:8010")
USER = os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "")
CLI = BASE_DIR / "integrations" / "hermes" / "notas_agent.py"

FOLDERS = ["hermes-libre", "hermes-lectura", "hermes-privado", "recordatorios"]
RULES = [
    {"path": "hermes-libre", "level": "write"},
    {"path": "hermes-lectura", "level": "read"},
    {"path": "recordatorios", "level": "write"},
]


def run_cli(env: dict[str, str], *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return json.loads(result.stdout)


def expect_failure(env: dict[str, str], *args: str) -> bool:
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode != 0


def main() -> int:
    if not PASSWORD:
        print("Falta ADMIN_PASSWORD en .env", file=sys.stderr)
        return 2

    with httpx.Client(base_url=BASE, timeout=10) as admin:
        admin.post("/api/login", json={"username": USER, "password": PASSWORD}).raise_for_status()

        for folder in FOLDERS:
            admin.post("/api/folders", json={"path": folder})

        read_note = admin.post(
            "/api/notes",
            json={"folder": "hermes-lectura", "title": "Solo lectura", "content": "visible"},
        ).json()
        private_note = admin.post(
            "/api/notes",
            json={"folder": "hermes-privado", "title": "Privada", "content": "secreta"},
        ).json()

        token_response = admin.post(
            "/api/tokens", json={"name": "hermes-cli-test", "rules": RULES}
        )
        token_response.raise_for_status()
        token = token_response.json()

        env = {
            **os.environ,
            "NOTAS_API_URL": BASE,
            "NOTAS_API_TOKEN": token["token"],
        }

        tree = run_cli(env, "tree")
        print("árbol", sorted(tree["folders"]))
        assert "hermes-privado" not in tree["folders"]

        note = run_cli(
            env, "note-add", "hermes-libre", "Prueba CLI", "--content", "hola"
        )
        print("crear nota libre", note["path"])
        assert run_cli(env, "note-get", note["id"])["content"] == "hola"
        assert run_cli(env, "note-update", note["id"], "--content", "editado")["content"] == "editado"

        reminder_note = run_cli(
            env, "note-add", "recordatorios", "Nota de recordatorio", "--content", "ok"
        )
        print("crear nota recordatorios", reminder_note["path"])

        print("leer solo lectura", run_cli(env, "note-get", read_note["id"])["title"])
        assert expect_failure(env, "note-add", "hermes-lectura", "No", "--content", "x")
        assert expect_failure(env, "note-add", "hermes-privado", "No", "--content", "x")
        assert expect_failure(env, "note-get", private_note["id"])
        search = run_cli(env, "search", "secreta")
        assert search["results"] == []
        print("permisos de carpetas correctos")

        created = run_cli(
            env,
            "add",
            "Prueba CLI Hermes",
            "--due",
            "2026-10-26T09:00",
            "--body",
            "**desde** el CLI",
        )
        print("crear recordatorio", created["id"])
        assert run_cli(env, "list", "--upcoming")["reminders"]
        assert run_cli(env, "done", created["id"])["done"] is True
        run_cli(env, "delete", created["id"])

        run_cli(env, "note-delete", note["id"])
        run_cli(env, "note-delete", reminder_note["id"])
        admin.delete(f"/api/notes/{read_note['id']}")
        admin.delete(f"/api/notes/{private_note['id']}")
        admin.delete(f"/api/tokens/{token['id']}").raise_for_status()

    print("permisos, notas y recordatorios correctos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
