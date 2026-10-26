"""Crea un token de agente y lo imprime una sola vez.

Ejemplos:
    python scripts/create_token.py --name claude \
        --rule 01-claude:write --rule 02-lectura:read
    python scripts/create_token.py --name hermes --rule notas:write
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un token de agente")
    parser.add_argument("--name", required=True, help="Nombre del token")
    parser.add_argument(
        "--rule",
        action="append",
        default=[],
        help="Permiso con formato ruta:read|write (repetible)",
    )
    parser.add_argument("--base", default=os.getenv("NOTAS_BASE", "http://127.0.0.1:8010"))
    parser.add_argument("--user", default=os.getenv("ADMIN_USER", "admin"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", ""))
    args = parser.parse_args()

    if not args.password:
        print("Falta ADMIN_PASSWORD (en .env o con --password).", file=sys.stderr)
        return 2

    rules = []
    for raw in args.rule:
        path, _, level = raw.partition(":")
        level = level or "read"
        if level not in {"read", "write"}:
            print(f"Nivel inválido en {raw!r}: usa read o write.", file=sys.stderr)
            return 2
        rules.append({"path": path, "level": level})

    with httpx.Client(base_url=args.base, timeout=10) as client:
        login = client.post(
            "/api/login", json={"username": args.user, "password": args.password}
        )
        if login.status_code != 200:
            print("No se pudo iniciar sesión.", file=sys.stderr)
            return 1

        response = client.post(
            "/api/tokens", json={"name": args.name, "rules": rules}
        )
        if response.status_code != 201:
            print(f"Error {response.status_code}: {response.text}", file=sys.stderr)
            return 1

        data = response.json()
        print(data["token"])
        print(f"id={data['id']} reglas={data['rules']}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
