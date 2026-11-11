"""Memoria compartida de Iris y Claude Code dentro de Notas.

Crea, de forma idempotente, la nota `configuracion` en la raíz con dos
secciones —Configuración y Usuario— y apunta a ella desde la nota Agente.
La misma nota sirve si se usa Iris o solo Claude Code como memoria.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import frontmatter

from .agent_note import find_agent_note_path
from .config import Settings
from .storage import NOTE_SUFFIX, dump_post, load_post, now_iso, safe_path

MEMORY_SLUG = "configuracion"
MEMORY_TITLE = "Configuración"
MEMORY_FILE = f"{MEMORY_SLUG}{NOTE_SUFFIX}"

# Estructura anterior (Iris/configuracion/{configuracion,usuario}.md).
OLD_FOLDER = "Iris/configuracion"

AGENT_MARKER = "<!-- memoria:compartida:v3 -->"
AGENT_MARKER_OLD = ("<!-- iris:configuracion -->", "<!-- iris:configuracion:v2 -->")

MEMORY_CONTENT = """# Configuración

Memoria compartida por Iris y Claude Code. Ambos leen esta nota antes de
trabajar; edítala aquí y sirve para los dos.

## Configuración

- Nombre del asistente: Iris
- Idioma: español, respuestas cortas y directas.
- Tono: cercano y formal, sin relleno.
- Reglas:
  - Leer la nota `Agente` antes de responder.
  - Leer la sección Usuario para conocer a la persona.
  - No pedir documentos ni datos que no estén en esta nota.
  - Guardar en Notas lo importante para próximas conversaciones.
- Límites:
  - No ejecutar acciones destructivas sin confirmación.
  - No compartir datos personales con terceros.

## Usuario

- Nombre:
- Edad:
- Qué hace:
- Ciudad:
- Zona horaria:
- Preferencias:
- Temas que le gustan:
- Cosas que no le gustan:

## Notas

(Espacio para contexto adicional.)
"""

AGENT_SECTION = f"""
{AGENT_MARKER}

## Memoria compartida

La configuración y los datos de la persona viven en la nota `configuracion`
(`configuracion.md`), con dos secciones:

- **Configuración**: cómo deben responder Iris y Claude Code (tono, reglas,
  límites). Es la misma para ambos.
- **Usuario**: nombre, edad, qué hace, preferencias y cualquier dato que deba
  recordar.

Qué hacer:

1. Lee esta nota (`/agente`) completa, sin sesión.
2. Pide el token de la API (Ajustes → API) y no lo guardes aquí: esta nota es
   pública.
3. Con el token, lee `configuracion.md`.
4. Si el equipo no tiene Iris y quieres instalarlo:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/JUANRESTREPO95/iris-agent/main/install.sh | sudo bash
   ```

   Si solo usas Claude Code, no hace falta instalar nada más: `configuracion.md`
   es la memoria compartida.
"""


def _strip_title(text: str) -> str:
    lines = (text or "").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _migrated_content(notes_dir: Path) -> str | None:
    """Contenido combinado a partir de Iris/configuracion, si existía."""
    old_dir = safe_path(notes_dir, OLD_FOLDER)
    config_path = old_dir / "configuracion.md"
    user_path = old_dir / "usuario.md"
    if not config_path.is_file() and not user_path.is_file():
        return None

    config_body = ""
    user_body = ""
    if config_path.is_file():
        config_body = _strip_title(load_post(config_path).content)
    if user_path.is_file():
        user_body = _strip_title(load_post(user_path).content)

    if not config_body and not user_body:
        return None

    parts = ["# Configuración", ""]
    parts += ["## Configuración", "", config_body or "(Sin contenido.)", ""]
    parts += ["## Usuario", "", user_body or "(Sin contenido.)", ""]
    return "\n".join(parts)


def _ensure_memory_note(settings: Settings) -> bool:
    notes_dir = settings.notes_dir
    path = notes_dir / MEMORY_FILE
    if path.exists():
        return False
    content = _migrated_content(notes_dir) or MEMORY_CONTENT
    stamp = now_iso(settings.timezone)
    post = frontmatter.Post(
        content,
        id=uuid4().hex,
        title=MEMORY_TITLE,
        created=stamp,
        updated=stamp,
    )
    dump_post(path, post)
    return True


def _update_agent_section(settings: Settings) -> bool:
    agent_path = find_agent_note_path(settings)
    if agent_path is None:
        return False
    post = load_post(agent_path)
    content = post.content or ""
    if AGENT_MARKER in content:
        return False

    block = AGENT_SECTION.strip("\n")
    positions = [content.index(m) for m in AGENT_MARKER_OLD if m in content]
    head = content[: min(positions)].rstrip() if positions else content.rstrip()
    post.content = f"{head}\n\n{block}\n" if head else f"{block}\n"
    meta = dict(post.metadata or {})
    meta["updated"] = now_iso(settings.timezone)
    post.metadata = meta
    dump_post(agent_path, post)
    return True


def ensure_memory_setup(settings: Settings) -> list[str]:
    """Crea lo que falte. Devuelve las rutas creadas o modificadas."""
    created: list[str] = []
    if _ensure_memory_note(settings):
        created.append(MEMORY_FILE)
    if _update_agent_section(settings):
        created.append("Agente")
    return created
