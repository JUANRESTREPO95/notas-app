#!/usr/bin/env python3
"""Verifica el CLI de Hermes usando el .env real, sin imprimir el token."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERMES_ENV = Path.home() / ".hermes" / ".env"
CLI = Path.home() / ".hermes" / "scripts" / "notas_agent.py"


def load_env() -> dict[str, str]:
    env = os.environ.copy()
    for line in HERMES_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("NOTAS_API_"):
            key, _, value = line.strip().partition("=")
            env[key] = value.strip().strip('"').strip("'")
    return env


def run(env: dict[str, str], *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print("FALLO", args, result.returncode, result.stderr.strip(), file=sys.stderr)
        raise SystemExit(1)
    return json.loads(result.stdout)


def main() -> int:
    env = load_env()

    tree = run(env, "tree")
    print("tree", sorted(tree["folders"]))
    if "hermes-privado" in tree["folders"]:
        print("FALLO: ve hermes-privado", file=sys.stderr)
        return 1

    note = run(env, "note-add", "hermes-libre", "Verificación de Hermes", "--content", "hola desde Hermes")
    print("nota", note["path"])
    assert run(env, "note-get", note["id"])["content"] == "hola desde Hermes"
    run(env, "note-delete", note["id"])
    print("nota borrada")

    # Limpiar restos de ejecuciones anteriores.
    for item in run(env, "list")["reminders"]:
        if item["title"] == "Verificación de Hermes":
            run(env, "delete", item["id"])

    reminder = run(
        env,
        "add",
        "Verificación de Hermes",
        "--body",
        "temporal",
        "--due",
        "2026-10-27T09:00",
    )
    print("recordatorio", reminder["id"])
    assert run(env, "list", "--upcoming")["reminders"]
    run(env, "done", reminder["id"])
    run(env, "delete", reminder["id"])
    print("recordatorio borrado")

    print("CLI de Hermes OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
