---
name: notas-reminders
description: "Use when the user asks to create, list or complete reminders, or to create/search notes in Notas."
version: 1.0.0
author: Hermes
---

# Notas — recordatorios y notas

La app **Notas** es la fuente de verdad para recordatorios y notas. Usa el CLI:

```bash
~/.hermes/scripts/notas_agent.py
```

La conexión usa `NOTAS_API_URL` y `NOTAS_API_TOKEN` del `.env` de Hermes.

## Carpetas y permisos

| Carpeta | Permiso de Hermes | Uso |
|---|---|---|
| `hermes-libre` | escribir, editar, borrar | Trabajo general de Hermes |
| `hermes-lectura` | solo leer | Material que comparte el usuario |
| `recordatorios` | escribir | Notas relacionadas con recordatorios |
| `hermes-libre/Conversaciones` | escribir | Resúmenes diarios de conversaciones (hereda el permiso de `hermes-libre`) |
| `hermes-privado` | **sin acceso** | Nunca intentar leerla ni escribirla |

Si una operación devuelve `HTTP 403`, no insistas: significa que no tienes
permiso en esa ruta.

## Recordatorios

```bash
# Crear
~/.hermes/scripts/notas_agent.py add "Comprar leche" \
  --due "2026-10-26T09:00" --body "2 litros"

# Próximos
~/.hermes/scripts/notas_agent.py list --upcoming

# Todos
~/.hermes/scripts/notas_agent.py list

# Completar
~/.hermes/scripts/notas_agent.py done <id>

# Eliminar
~/.hermes/scripts/notas_agent.py delete <id>
```

- La zona horaria es `America/Bogota`. Si `--due` no trae offset, se interpreta
  en esa zona.
- El resumen programado de WhatsApp (8:00, 13:00 y 18:00) lo envía un servicio
  aparte; no lo dupliques en respuestas normales.

## Notas

```bash
# Ver qué carpetas y notas tienes
~/.hermes/scripts/notas_agent.py tree

# Buscar
~/.hermes/scripts/notas_agent.py search "texto"

# Crear
~/.hermes/scripts/notas_agent.py note-add hermes-libre "Título" \
  --content "Contenido en Markdown"

# Resumen diario de conversaciones
~/.hermes/scripts/notas_agent.py note-add hermes-libre/Conversaciones \
  "Resumen Día YYYY-MM-DD" --content "Contenido en Markdown"

# Crear desde un archivo
~/.hermes/scripts/notas_agent.py note-add recordatorios "Título" \
  --file /tmp/nota.md

# Leer
~/.hermes/scripts/notas_agent.py note-get <id>

# Editar
~/.hermes/scripts/notas_agent.py note-update <id> --content "Nuevo contenido"

# Mover
~/.hermes/scripts/notas_agent.py note-move <id> recordatorios

# Borrar
~/.hermes/scripts/notas_agent.py note-delete <id>
```

## Reglas

- No inventes IDs: sácalos de `tree`, `search` o `list`.
- Guarda notas de recordatorios en `recordatorios`.
- Usa `hermes-libre` para trabajo general.
- No intentes acceder a `hermes-privado`.
- No adjuntes bloques de pendientes a respuestas normales; solo cuando el
  usuario los pida o cuando el servicio programado los envíe.