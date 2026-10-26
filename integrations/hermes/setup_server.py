#!/usr/bin/env python3
"""Prepara carpetas, token y entorno de Hermes para la app Notas.

Se ejecuta en el servidor, después de levantar el contenedor:

    python3 integrations/hermes/setup_server.py \
        --base http://127.0.0.1:3001 \
        --app-env ~/notas-app/.env \
        --hermes-env ~/.hermes/.env

Crea:
    hermes-libre      escritura total para Hermes
    hermes-lectura    solo lectura para Hermes
    hermes-privado    sin acceso para Hermes
    recordatorios     escritura para Hermes

Escribe NOTAS_API_URL y NOTAS_API_TOKEN en el .env de Hermes y verifica los
permisos. No imprime el token.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

FOLDERS = [
    "hermes-libre",
    "hermes-lectura",
    "hermes-privado",
    "recordatorios",
    "hermes-libre/Conversaciones",
]
RULES = [
    {"path": "hermes-libre", "level": "write"},
    {"path": "hermes-lectura", "level": "read"},
    {"path": "recordatorios", "level": "write"},
]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.session = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        token: str | None = None,
    ) -> tuple[int, dict | str]:
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        headers = {"Content-Type": "application/json"}
        opener = self.session
        if token:
            headers["Authorization"] = f"Bearer {token}"
            opener = urllib.request.build_opener()
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=headers
        )
        try:
            with opener.open(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                return response.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body
            return error.code, parsed
        except urllib.error.URLError as error:
            raise SystemExit(f"No se pudo conectar a {self.base}: {error.reason}")

    def login(self, user: str, password: str) -> None:
        status, data = self.request(
            "POST", "/api/login", {"username": user, "password": password}
        )
        if status != 200:
            raise SystemExit(f"Login falló ({status}): {data}")


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(str(path) + f".bak.notas-{stamp}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(backup, 0o600)
    return backup


def update_hermes_env(path: Path, base: str, token: str) -> Path | None:
    backup = backup_file(path)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.match(r"^(export\s+)?NOTAS_API_(URL|TOKEN)=", line.strip()):
                continue
            lines.append(line)
    lines.extend([f"NOTAS_API_URL={base}", f"NOTAS_API_TOKEN={token}"])
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Configura Hermes para Notas")
    parser.add_argument("--base", default="http://127.0.0.1:3001")
    parser.add_argument("--app-env", default="~/notas-app/.env")
    parser.add_argument("--hermes-env", default="~/.hermes/.env")
    parser.add_argument("--token-name", default="hermes")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    app_env = Path(args.app_env).expanduser()
    hermes_env = Path(args.hermes_env).expanduser()
    config = read_env(app_env)
    user = config.get("ADMIN_USER")
    password = config.get("ADMIN_PASSWORD")
    if not user or not password:
        print(f"Faltan ADMIN_USER/ADMIN_PASSWORD en {app_env}", file=sys.stderr)
        return 2

    admin = Api(base)
    admin.login(user, password)

    print("== carpetas ==")
    for folder in FOLDERS:
        status, _ = admin.request("POST", "/api/folders", {"path": folder})
        label = {201: "creada", 409: "ya existía"}.get(status, str(status))
        print(f"{folder}: {label}")

    print("== tokens ==")
    status, data = admin.request("GET", "/api/tokens")
    if status != 200:
        print(f"No se pudieron listar tokens ({status}): {data}", file=sys.stderr)
        return 1
    for item in data.get("tokens", []):
        if item.get("name") == args.token_name:
            admin.request("DELETE", f"/api/tokens/{item['id']}")
            print(f"token anterior {item['id']} eliminado")

    status, created = admin.request(
        "POST", "/api/tokens", {"name": args.token_name, "rules": RULES}
    )
    if status != 201 or "token" not in created:
        print(f"No se pudo crear el token ({status}): {created}", file=sys.stderr)
        return 1
    token = created["token"]
    print(f"token {created['id']} creado con {len(RULES)} reglas")

    if not args.skip_verify:
        print("== verificación ==")
        agent = Api(base)

        status, tree = agent.request("GET", "/api/tree", token=token)
        visible = sorted(tree.get("folders", [])) if isinstance(tree, dict) else []
        print("árbol visible:", visible)
        if "hermes-privado" in visible:
            print("FALLO: Hermes ve hermes-privado", file=sys.stderr)
            return 1
        for expected in ("hermes-libre", "hermes-lectura", "recordatorios"):
            if expected not in visible:
                print(f"FALLO: falta {expected} en el árbol", file=sys.stderr)
                return 1

        status, _ = agent.request(
            "POST",
            "/api/notes",
            {"folder": "hermes-privado", "title": "No", "content": "No"},
            token=token,
        )
        print("escribir en hermes-privado:", status, "(esperado 403)")
        if status != 403:
            return 1

        status, _ = agent.request(
            "POST",
            "/api/notes",
            {"folder": "hermes-lectura", "title": "No", "content": "No"},
            token=token,
        )
        print("escribir en hermes-lectura:", status, "(esperado 403)")
        if status != 403:
            return 1

        status, note = agent.request(
            "POST",
            "/api/notes",
            {"folder": "hermes-libre", "title": "Prueba de permisos", "content": "ok"},
            token=token,
        )
        print("escribir en hermes-libre:", status, "(esperado 201)")
        if status != 201:
            return 1
        agent.request("DELETE", f"/api/notes/{note['id']}", token=token)

        status, note = agent.request(
            "POST",
            "/api/reminders",
            {"title": "Prueba de Hermes", "body": "temporal"},
            token=token,
        )
        print("crear recordatorio:", status, "(esperado 201)")
        if status != 201:
            return 1
        agent.request("DELETE", f"/api/reminders/{note['id']}", token=token)

        status, read_note = admin.request(
            "POST",
            "/api/notes",
            {"folder": "hermes-lectura", "title": "Solo lectura", "content": "visible"},
        )
        if status == 201:
            status_read, _ = agent.request(
                "GET", f"/api/notes/{read_note['id']}", token=token
            )
            print("leer hermes-lectura:", status_read, "(esperado 200)")
            admin.request("DELETE", f"/api/notes/{read_note['id']}")

        status, private_note = admin.request(
            "POST",
            "/api/notes",
            {"folder": "hermes-privado", "title": "Privada", "content": "secreta"},
        )
        if status == 201:
            status_private, _ = agent.request(
                "GET", f"/api/notes/{private_note['id']}", token=token
            )
            print("leer hermes-privado:", status_private, "(esperado 403)")
            admin.request("DELETE", f"/api/notes/{private_note['id']}")

    backup = update_hermes_env(hermes_env, base, token)
    print(f"== entorno de Hermes ==")
    print(f"escrito {hermes_env}")
    if backup:
        print(f"respaldo {backup}")
    print("token y URL configurados; no se imprimió el token")
    return 0


if __name__ == "__main__":
    sys.exit(main())
