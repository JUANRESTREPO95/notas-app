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
AGENT_MARKER = "<!-- iris:configuracion:v2 -->"
AGENT_MARKER_V1 = "<!-- iris:configuracion -->"

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

## Agentes nuevos: qué hacer

1. **Leer esta nota** completa. Es pública y se descarga desde `/agente`, sin
   sesión.
2. **Pedir el token** de la API al usuario (Ajustes → API) y no guardarlo aquí:
   esta nota es pública.
3. **Leer la configuración y al usuario** con ese token:
   - `Iris/configuracion/configuracion.md` — cómo debe responder Iris: tono,
     reglas y límites.
   - `Iris/configuracion/usuario.md` — nombre, edad, qué hace, preferencias y
     cualquier dato que deba recordar.
4. **Instalar Iris** si el equipo no lo tiene:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/JUANRESTREPO95/iris-agent/main/install.sh | sudo bash
   ```

   El instalador pregunta el canal (Telegram o WhatsApp), el modelo y si quieres
   Notas como memoria persistente.

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
        content = post.content or ""
        if AGENT_MARKER not in content:
            block = AGENT_SECTION.strip("\n")
            if AGENT_MARKER_V1 in content:
                # Actualiza la sección de la versión anterior: se reemplaza
                # desde su marca hasta el final (se añadía al final de la nota).
                head = content[: content.index(AGENT_MARKER_V1)].rstrip()
            else:
                head = content.rstrip()
            post.content = f"{head}\n\n{block}\n" if head else f"{block}\n"
            meta = dict(post.metadata or {})
            meta["updated"] = now_iso(settings.timezone)
            post.metadata = meta
            dump_post(agent_path, post)
            created.append("Agente")

    return created
