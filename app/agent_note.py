"""Nota del sistema «Agente».

Es la puerta de entrada para agentes nuevos: se crea sola, no se puede borrar,
se puede editar y se publica sin sesión en /agente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter

from .config import Settings
from .storage import dump_post, load_post, now_iso, NOTE_SUFFIX

AGENT_NOTE_ID = "agente"
AGENT_NOTE_TITLE = "Agente"
AGENT_NOTE_FILENAME = f"{AGENT_NOTE_TITLE}{NOTE_SUFFIX}"
AGENT_ROUTE = "/agente"

DEFAULT_CONTENT = """# Agente

Nota del sistema. Se crea sola, no se puede borrar y sí se puede editar.

Se publica sin sesión en `/agente` de este mismo dominio, para que cualquier
agente nuevo lea estas instrucciones antes de conectarse.

> Esta nota es pública: no pongas aquí tokens, contraseñas ni secretos.

## Cómo conectarse

1. Pide al usuario el token de la API (Ajustes → API). No lo guardes aquí.
2. Usa este mismo dominio como `NOTAS_API_URL`.
3. Comprueba el acceso:

   ```bash
   curl -H "Authorization: Bearer <token>" <dominio>/api/tree
   ```

## Instrucciones permanentes

Escribe debajo todo lo que el agente debe leer y cumplir antes de trabajar.
"""


def find_agent_note_path(settings: Settings) -> Path | None:
    """Devuelve la ruta de la nota Agente, esté donde esté."""
    notes_dir = settings.notes_dir
    candidate = notes_dir / AGENT_NOTE_FILENAME
    if candidate.is_file():
        return candidate
    if not notes_dir.exists():
        return None
    for path in sorted(notes_dir.rglob(f"*{NOTE_SUFFIX}")):
        parts = path.relative_to(notes_dir).parts
        if any(part.startswith(".") for part in parts):
            continue
        try:
            post = frontmatter.load(path)
        except Exception:
            continue
        if str((post.metadata or {}).get("id") or "") == AGENT_NOTE_ID:
            return path
    return None


def ensure_agent_note(settings: Settings) -> bool:
    """Crea la nota Agente si no existe. Devuelve True si la creó."""
    notes_dir = settings.notes_dir
    notes_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_iso(settings.timezone)

    path = find_agent_note_path(settings)
    if path is None:
        post = frontmatter.Post(
            DEFAULT_CONTENT,
            id=AGENT_NOTE_ID,
            title=AGENT_NOTE_TITLE,
            protected=True,
            created=stamp,
            updated=stamp,
        )
        dump_post(notes_dir / AGENT_NOTE_FILENAME, post)
        return True

    post = load_post(path)
    meta = dict(post.metadata or {})
    changed = False
    if str(meta.get("id") or "") != AGENT_NOTE_ID:
        meta["id"] = AGENT_NOTE_ID
        changed = True
    if not str(meta.get("title") or "").strip():
        meta["title"] = AGENT_NOTE_TITLE
        changed = True
    if meta.get("protected") is not True:
        meta["protected"] = True
        changed = True
    if not str(meta.get("created") or ""):
        meta["created"] = stamp
        changed = True
    if not str(meta.get("updated") or ""):
        meta["updated"] = meta.get("created") or stamp
        changed = True
    if changed:
        post.metadata = meta
        dump_post(path, post)
    return False


def is_agent_note(note: dict[str, Any] | None) -> bool:
    """True si la nota es la del sistema (por id o por marca protected)."""
    if not note:
        return False
    if str(note.get("id") or "") == AGENT_NOTE_ID:
        return True
    metadata = note.get("metadata") or {}
    return metadata.get("protected") is True


def agent_note_content(settings: Settings) -> str | None:
    """Contenido en Markdown de la nota Agente, o None si no existe."""
    path = find_agent_note_path(settings)
    if path is None:
        return None
    try:
        return frontmatter.load(path).content
    except Exception:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
