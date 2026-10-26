#!/usr/bin/env python3
"""CLI para que un agente use la API de Notas.

Variables de entorno:
    NOTAS_API_URL    por defecto http://127.0.0.1:3001
    NOTAS_API_TOKEN  token Bearer creado en la app

Recordatorios:
    notas_agent.py add "Comprar leche" --due 2026-10-26T09:00 --body "2 litros"
    notas_agent.py list --upcoming
    notas_agent.py done <id>
    notas_agent.py delete <id>

Notas:
    notas_agent.py tree
    notas_agent.py search "texto"
    notas_agent.py note-add hermes-libre "Título" --content "Contenido"
    notas_agent.py note-add hermes-libre "Título" --file /tmp/nota.md
    notas_agent.py note-get <id>
    notas_agent.py note-update <id> --content "Nuevo contenido"
    notas_agent.py note-move <id> recordatorios
    notas_agent.py note-delete <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("NOTAS_API_URL", "http://127.0.0.1:3001").rstrip("/")
TOKEN = os.environ.get("NOTAS_API_TOKEN", "")

# El .env es la fuente de verdad: el proceso del gateway puede conservar un
# token viejo en su entorno después de cambiarlo.
env_file = Path.home() / ".hermes" / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean.startswith("export "):
            clean = clean[7:]
        if clean.startswith("NOTAS_API_URL="):
            BASE = clean.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
        elif clean.startswith("NOTAS_API_TOKEN="):
            TOKEN = clean.split("=", 1)[1].strip().strip('"').strip("'")


def call(method: str, path: str, payload: dict | None = None) -> dict:
    if not TOKEN:
        sys.exit("Falta NOTAS_API_TOKEN en el entorno.")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        sys.exit(f"HTTP {error.code}: {detail}")
    except urllib.error.URLError as error:
        sys.exit(f"No se pudo conectar a {BASE}: {error.reason}")


def read_content(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    return getattr(args, "content", "") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="API de Notas para agentes")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Crear un recordatorio")
    add.add_argument("title")
    add.add_argument("--body", default="")
    add.add_argument("--due", default=None, help="ISO 8601, ej. 2026-10-26T09:00")
    add.add_argument("--timezone", default="America/Bogota")

    listing = sub.add_parser("list", help="Listar recordatorios")
    listing.add_argument("--upcoming", action="store_true")

    done = sub.add_parser("done", help="Marcar un recordatorio como completado")
    done.add_argument("id")

    delete = sub.add_parser("delete", help="Eliminar un recordatorio")
    delete.add_argument("id")

    sub.add_parser("tree", help="Árbol de carpetas y notas visibles")

    search = sub.add_parser("search", help="Buscar notas")
    search.add_argument("query")

    note_add = sub.add_parser("note-add", help="Crear una nota")
    note_add.add_argument("folder")
    note_add.add_argument("title")
    note_add.add_argument("--content", default="")
    note_add.add_argument("--file", default=None)

    note_get = sub.add_parser("note-get", help="Leer una nota")
    note_get.add_argument("id")

    note_update = sub.add_parser("note-update", help="Editar una nota")
    note_update.add_argument("id")
    note_update.add_argument("--title", default=None)
    note_update.add_argument("--content", default=None)
    note_update.add_argument("--file", default=None)

    note_move = sub.add_parser("note-move", help="Mover una nota de carpeta")
    note_move.add_argument("id")
    note_move.add_argument("folder")

    note_delete = sub.add_parser("note-delete", help="Eliminar una nota")
    note_delete.add_argument("id")

    args = parser.parse_args()

    if args.command == "add":
        result = call(
            "POST",
            "/api/reminders",
            {
                "title": args.title,
                "body": args.body,
                "due_at": args.due,
                "timezone": args.timezone,
            },
        )
    elif args.command == "list":
        result = call("GET", "/api/reminders" + ("?upcoming=true" if args.upcoming else ""))
    elif args.command == "done":
        result = call("PATCH", f"/api/reminders/{urllib.parse.quote(args.id)}", {"done": True})
    elif args.command == "delete":
        result = call("DELETE", f"/api/reminders/{urllib.parse.quote(args.id)}")
    elif args.command == "tree":
        result = call("GET", "/api/tree")
    elif args.command == "search":
        result = call("GET", "/api/search?q=" + urllib.parse.quote_plus(args.query))
    elif args.command == "note-add":
        result = call(
            "POST",
            "/api/notes",
            {
                "folder": args.folder,
                "title": args.title,
                "content": read_content(args),
            },
        )
    elif args.command == "note-get":
        result = call("GET", f"/api/notes/{urllib.parse.quote(args.id)}")
    elif args.command == "note-update":
        payload: dict[str, str] = {}
        if args.title is not None:
            payload["title"] = args.title
        if args.content is not None or args.file is not None:
            payload["content"] = read_content(args)
        if not payload:
            sys.exit("Indica --title, --content o --file.")
        result = call("PUT", f"/api/notes/{urllib.parse.quote(args.id)}", payload)
    elif args.command == "note-move":
        result = call(
            "POST",
            f"/api/notes/{urllib.parse.quote(args.id)}/move",
            {"folder": args.folder},
        )
    else:
        result = call("DELETE", f"/api/notes/{urllib.parse.quote(args.id)}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
