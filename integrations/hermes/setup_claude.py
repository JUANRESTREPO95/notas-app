#!/usr/bin/env python3
"""Crea la carpeta claude-code y un token de Claude.

Escribe un archivo .env local con NOTAS_API_URL y NOTAS_API_TOKEN, sin imprimir
el token. Se ejecuta en el servidor después de levantar Notas.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

FOLDER = "claude-code"
RULES = [{"path": FOLDER, "level": "write"}]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
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

    def request(self, method: str, path: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict | str]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        opener = self.session
        if token:
            headers["Authorization"] = f"Bearer {token}"
            opener = urllib.request.build_opener()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
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

    def login(self, user: str, password: str) -> None:
        status, data = self.request("POST", "/api/login", {"username": user, "password": password})
        if status != 200:
            raise SystemExit(f"Login falló ({status}): {data}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configura Claude en Notas")
    parser.add_argument("--base", default="http://127.0.0.1:3001")
    parser.add_argument("--app-env", default="~/notas-app/.env")
    parser.add_argument("--out", default="~/notas-app/claude-notas.env")
    args = parser.parse_args()

    config = read_env(Path(args.app_env).expanduser())
    user = config.get("ADMIN_USER")
    password = config.get("ADMIN_PASSWORD")
    if not user or not password:
        print("Faltan ADMIN_USER/ADMIN_PASSWORD", file=sys.stderr)
        return 2

    admin = Api(args.base)
    admin.login(user, password)

    status, _ = admin.request("POST", "/api/folders", {"path": FOLDER})
    print("carpeta claude-code:", {201: "creada", 409: "ya existía"}.get(status, status))

    status, data = admin.request("GET", "/api/tokens")
    if status != 200:
        print(f"No se pudieron listar tokens: {status} {data}", file=sys.stderr)
        return 1
    for item in data.get("tokens", []):
        if item.get("name") == "claude-code":
            admin.request("DELETE", f"/api/tokens/{item['id']}")
            print("token anterior de Claude eliminado")

    status, created = admin.request("POST", "/api/tokens", {"name": "claude-code", "rules": RULES})
    if status != 201 or "token" not in created:
        print(f"No se pudo crear el token: {status} {created}", file=sys.stderr)
        return 1
    token = created["token"]
    print("token claude-code:", created["id"])

    # Verificación mínima: crear y borrar una nota.
    test = Api(args.base)
    status, note = test.request(
        "POST",
        "/api/notes",
        {"folder": FOLDER, "title": "Prueba de Claude", "content": "temporal"},
        token=token,
    )
    print("escribir en claude-code:", status, "(esperado 201)")
    if status == 201:
        test.request("DELETE", f"/api/notes/{note['id']}", token=token)

    out = Path(args.out).expanduser()
    out.write_text(
        f"NOTAS_API_URL={args.base.rstrip('/')}\nNOTAS_API_TOKEN={token}\n",
        encoding="utf-8",
    )
    os.chmod(out, 0o600)
    print(f"escrito {out} (sin imprimir el token)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
