#!/usr/bin/env python3
"""Envía un resumen limpio de recordatorios de Notas por WhatsApp.

Horario: 08:00, 13:00 y 18:00 en America/Bogota. Si no hay pendientes, no envía.

Prueba sin enviar:
    notificar_recordatorios.py --dry-run

Enviar ahora (solo para pruebas manuales):
    notificar_recordatorios.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")
SCHEDULES = {"08:00", "13:00", "18:00"}
STATE = Path.home() / ".hermes" / "state" / "notas_notifier.json"
HERMES_ENV = Path.home() / ".hermes" / ".env"
HERMES_BIN = os.environ.get(
    "HERMES_BIN", str(Path.home() / ".hermes" / "hermes-agent" / ".hermes" / "bin" / "hermes")
)
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def load_config() -> tuple[str, str]:
    env = os.environ.copy()
    if HERMES_ENV.exists():
        for line in HERMES_ENV.read_text(encoding="utf-8").splitlines():
            clean = line.strip()
            if clean.startswith("export "):
                clean = clean[7:]
            if clean.startswith("NOTAS_API_"):
                key, _, value = clean.partition("=")
                env[key] = value.strip().strip('"').strip("'")
    base = env.get("NOTAS_API_URL", "http://127.0.0.1:3001").rstrip("/")
    token = env.get("NOTAS_API_TOKEN", "")
    if not token:
        raise SystemExit("Falta NOTAS_API_TOKEN en ~/.hermes/.env")
    return base, token


def fetch_reminders(base: str, token: str) -> list[dict]:
    request = urllib.request.Request(
        base + "/api/reminders?done=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8")).get("reminders", [])
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"No se pudo conectar a {base}: {error.reason}") from error


def parse_due(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(TZ)


def build_message(reminders: list[dict]) -> str:
    now = datetime.now(TZ)
    today = now.date()
    groups: dict[str, list[str]] = {
        "overdue": [],
        "today": [],
        "upcoming": [],
        "undated": [],
    }

    for reminder in reminders:
        if reminder.get("done"):
            continue
        title = " ".join(str(reminder.get("title", "")).split())[:200]
        if not title:
            continue
        due = parse_due(reminder.get("due_at"))
        if due is None:
            groups["undated"].append(f"□ {title}")
            continue
        label = f"□ {due.day} {MONTHS[due.month - 1]} {due:%H:%M} — {title}"
        if due < now:
            groups["overdue"].append(label)
        elif due.date() == today:
            groups["today"].append(label)
        else:
            groups["upcoming"].append(label)

    total = sum(len(items) for items in groups.values())
    if total == 0:
        return ""

    lines = ["📋 *PENDIENTES*"]
    for key, heading in (
        ("overdue", "⚠️ *Vencidos*"),
        ("today", "📅 *Hoy*"),
        ("upcoming", "📆 *Próximos*"),
        ("undated", "□ *Sin fecha*"),
    ):
        items = groups[key]
        if items:
            lines.append("")
            lines.append(heading)
            lines.extend(items)

    if total > 30:
        lines.append("")
        lines.append(f"… y {total - 30} más")
    return "\n".join(lines)


def send(message: str, target: str) -> None:
    result = subprocess.run(
        [HERMES_BIN, "send", "--to", target, message],
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"hermes send salió con {result.returncode}")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, STATE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Notificador de recordatorios de Notas")
    parser.add_argument("--dry-run", action="store_true", help="Imprimir sin enviar")
    parser.add_argument("--force", action="store_true", help="Enviar ahora, sin esperar horario")
    parser.add_argument("--to", default="whatsapp", help="Destino de hermes send")
    args = parser.parse_args()

    base, token = load_config()

    if args.dry_run or args.force:
        message = build_message(fetch_reminders(base, token))
        if not message:
            print("(sin pendientes)")
            return 0
        print(message)
        if args.force and not args.dry_run:
            send(message, args.to)
            print("enviado")
        return 0

    print("notificador de recordatorios iniciado", flush=True)
    while True:
        now = datetime.now(TZ)
        slot = now.strftime("%Y-%m-%dT%H:%M")
        if now.strftime("%H:%M") in SCHEDULES:
            state = load_state()
            if state.get("last_slot") != slot:
                try:
                    message = build_message(fetch_reminders(base, token))
                    if message:
                        send(message, args.to)
                        print(f"[{slot}] enviado", flush=True)
                    else:
                        print(f"[{slot}] sin pendientes", flush=True)
                    state["last_slot"] = slot
                    state["last_run"] = slot
                    save_state(state)
                except Exception as error:
                    print(f"[{slot}] error: {error}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
