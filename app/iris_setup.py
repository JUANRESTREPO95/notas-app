"""Estructura de memoria de Iris dentro de Notas.

Crea, de forma idempotente, la carpeta Iris/configuracion con las notas de
configuración y usuario, y añade la sección correspondiente a la nota Agente.
"""

from __future__ import annotations

from uuid import uuid4

import frontmatter

from .agent_note import find_agent_note_path
from .config import Settings
from .storage import (
    NOTE_SUFFIX,
    create_folder,
    dump_post,
    load_post,
    now_iso,
    safe_path,
)

IRIS_FOLDER = "Iris"
IRIS_CONFIG_FOLDER = "Iris/configuracion"
IRIS_CONFIG_SLUG = "configuracion"
IRIS_USER_SLUG = "usuario"
AGENT_MARKER = "<!-- iris:configuracion -->"

CONFIG_CONTENT = """# Configuración de Iris

Aquí vive la configuración de Iris: cómo debe responder y qué reglas sigue.

## Identidad

- Nombre: Iris
- Rol: asistente personal y agente de Claude Code

## Tono

- Cercano, directo y en español.
- Respuestas cortas, sin relleno.

## Reglas

- Leer la nota `Agente` antes de responder.
- Leer `Iris/configuracion/usuario` para conocer a la persona.
- No pedir documentos ni datos que no estén en la memoria.
- Guardar en Notas lo importante para próximas conversaciones.

## Límites

- No ejecutar acciones destructivas sin confirmación.
- No compartir datos personales con terceros.
"""

USER_CONTENT = """# Usuario

Datos de la persona que usa Iris. Se leen antes de atender cualquier mensaje.

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

## Configuración de Iris

La configuración de Iris y los datos de la persona viven en `Iris/configuracion`:

- `Configuración` (`Iris/configuracion/configuracion.md`): cómo debe responder
  Iris, su tono, reglas y límites.
- `Usuario` (`Iris/configuracion/usuario.md`): nombre, edad, qué hace,
  preferencias y cualquier dato que deba recordar.

Cualquier agente que atienda por Iris debe leer esas dos notas antes de responder.
"""


def _ensure_folder(notes_dir, rel: str) -> bool:
    try:
        create_folder(notes_dir, rel)
        return True
    except FileExistsError:
        return False


def _ensure_note(
    notes_dir, folder_rel: str, slug: str, title: str, content: str, timezone: str
) -> bool:
    folder = safe_path(notes_dir, folder_rel)
    path = folder / f"{slug}{NOTE_SUFFIX}"
    if path.exists():
        return False
    stamp = now_iso(timezone)
    post = frontmatter.Post(
        content,
        id=uuid4().hex,
        title=title,
        created=stamp,
        updated=stamp,
    )
    dump_post(path, post)
    return True


def ensure_iris_setup(settings: Settings) -> list[str]:
    """Crea lo que falte. Devuelve las rutas creadas o modificadas."""
    created: list[str] = []
    notes_dir = settings.notes_dir

    for folder in (IRIS_FOLDER, IRIS_CONFIG_FOLDER):
        if _ensure_folder(notes_dir, folder):
            created.append(folder)

    if _ensure_note(
        notes_dir,
        IRIS_CONFIG_FOLDER,
        IRIS_CONFIG_SLUG,
        "Configuración",
        CONFIG_CONTENT,
        settings.timezone,
    ):
        created.append(f"{IRIS_CONFIG_FOLDER}/{IRIS_CONFIG_SLUG}{NOTE_SUFFIX}")

    if _ensure_note(
        notes_dir,
        IRIS_CONFIG_FOLDER,
        IRIS_USER_SLUG,
        "Usuario",
        USER_CONTENT,
        settings.timezone,
    ):
        created.append(f"{IRIS_CONFIG_FOLDER}/{IRIS_USER_SLUG}{NOTE_SUFFIX}")

    agent_path = find_agent_note_path(settings)
    if agent_path is not None:
        post = load_post(agent_path)
        if AGENT_MARKER not in (post.content or ""):
            post.content = f"{post.content.rstrip()}\n{AGENT_SECTION}"
            meta = dict(post.metadata or {})
            meta["updated"] = now_iso(settings.timezone)
            post.metadata = meta
            dump_post(agent_path, post)
            created.append("Agente")

    return created
