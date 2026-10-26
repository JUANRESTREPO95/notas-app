# Notas

App web self-hosted de notas Markdown y recordatorios, pensada para correr 24/7
en un servidor doméstico y usarse desde el navegador en PC, tablet y móvil.
Incluye una API con tokens por dispositivo y permisos por carpeta para que
agentes o scripts lean y escriban sin compartir la contraseña.

## Características

- Carpetas y subcarpetas con árbol plegable.
- Notas Markdown con frontmatter, autoguardado y vista previa.
- Barra de formato: títulos, negrita, cursiva, tachado, listas, checklist,
  tablas, citas, código, separadores y enlaces.
- Búsqueda full-text con SQLite FTS5.
- Recordatorios con fecha, detalle Markdown y estado pendiente/completado.
- Historial por nota con restauración de versiones.
- Panel de ajustes para cambiar usuario y contraseña.
- Tokens de API con nombre, permisos por carpeta y revocación.
- Tema claro, oscuro o del sistema.
- Manifiesto PWA e interfaz responsive.
- Accesibilidad WCAG AA (probada con axe en claro/oscuro y varios tamaños).
- Docker y Docker Compose.

## Stack

- **FastAPI** + **SQLite** + **Markdown en disco**.
- **Jinja2** + JavaScript vanilla, sin build de frontend.
- **Docker** para el despliegue.
- Fuente Plus Jakarta Sans incluida; sin dependencias de CDN.

## Inicio rápido con Docker

```bash
git clone https://github.com/JUANRESTREPO95/notas-app.git
cd notas-app
cp .env.example .env
```

Edita `.env` y cambia como mínimo `SECRET_KEY` y `ADMIN_PASSWORD`:

```bash
docker compose up -d --build
```

- App: `http://localhost:3001`
- Documentación de la API: `http://localhost:3001/docs`
- Salud: `http://localhost:3001/api/health`

Los datos quedan en el volumen `notas-data`. Para respaldarlos, copia ese
volumen o la carpeta `data/` si corres la app sin Docker.

## Desarrollo local

Requisitos: Python 3.12+ y, preferiblemente, [`uv`](https://github.com/astral-sh/uv).

```bash
cp .env.example .env
./dev.sh
```

- App: `http://localhost:8010`
- API y documentación: `http://localhost:8010/docs`

También puedes hacerlo a mano:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8010
```

### Pruebas

```bash
pytest -q
```

Utilidades opcionales:

```bash
python scripts/smoke.py        # API
python scripts/smoke_ui.py     # páginas y estáticos
python scripts/test_agents.py  # tokens y permisos de agentes
```

Los scripts leen `ADMIN_USER`, `ADMIN_PASSWORD` y `NOTAS_BASE` desde `.env` o
desde el entorno. No hay credenciales escritas en el código.

## Variables de entorno

| Variable | Uso |
|---|---|
| `DATA_DIR` | Carpeta de datos (por defecto `./data`) |
| `SECRET_KEY` | Firma de las cookies de sesión |
| `ADMIN_USER` | Usuario inicial |
| `ADMIN_PASSWORD` | Contraseña inicial |
| `TIMEZONE` | Zona horaria (por defecto `America/Bogota`) |
| `COOKIE_SECURE` | `true` cuando la app se sirva por HTTPS |
| `APP_NAME` | Nombre visible |

`SECRET_KEY` y `ADMIN_PASSWORD` deben ser largos y aleatorios. Si la app está
detrás de un proxy con HTTPS, pon `COOKIE_SECURE=true`.

## Cómo guarda los datos

Cada nota es un archivo `.md` con frontmatter:

```markdown
---
id: 6f1c...
title: Mi nota
created: 2026-10-25T21:00:00-05:00
updated: 2026-10-25T21:00:00-05:00
---
Contenido en Markdown.
```

Las carpetas son directorios dentro de `data/notes/`. SQLite guarda el índice
de búsqueda, los recordatorios, los usuarios, los tokens y el historial de
versiones.

```text
data/
  app.db
  notes/
    Carpeta/
      nota.md
```

Si un archivo se crea por fuera de la API, el indexador le añade el frontmatter
que falte y lo incorpora. Se reindexa cada 30 segundos.

## API y agentes

La interfaz usa una cookie de sesión. Los agentes y scripts usan **tokens
Bearer** con reglas por ruta:

```json
[
  {"path": "notas", "level": "write"},
  {"path": "lectura", "level": "read"}
]
```

- La regla del prefijo más largo gana.
- Una ruta sin regla queda denegada.
- Los permisos de escritura incluyen lectura.
- La sesión del administrador tiene acceso total.
- Los tokens se muestran una sola vez; se guarda su hash, no el token.

Ejemplo:

```bash
curl -H "Authorization: Bearer nsk_..." \
  http://localhost:3001/api/tree
```

Crear un token desde la terminal:

```bash
python scripts/create_token.py --name mi-agente \
  --rule notas:write --rule lectura:read
```

### Endpoints principales

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/health` | Estado de la app |
| `POST` | `/api/login` | Login de la interfaz |
| `GET` | `/api/me` | Usuario actual |
| `GET` | `/api/tree` | Árbol de carpetas y notas |
| `POST` | `/api/folders` | Crear carpeta |
| `PATCH` | `/api/folders` | Renombrar o mover carpeta |
| `DELETE` | `/api/folders` | Eliminar carpeta vacía |
| `POST` | `/api/notes` | Crear nota |
| `GET` | `/api/notes/{id}` | Leer nota |
| `PUT` | `/api/notes/{id}` | Editar nota |
| `DELETE` | `/api/notes/{id}` | Eliminar nota |
| `POST` | `/api/notes/{id}/move` | Mover nota |
| `GET` | `/api/notes/{id}/versions` | Listar versiones |
| `GET` | `/api/notes/{id}/versions/{version_id}` | Leer versión |
| `POST` | `/api/notes/{id}/versions/{version_id}/restore` | Restaurar versión |
| `GET` | `/api/search?q=` | Buscar |
| `POST` | `/api/reindex` | Reindexar |
| `GET` | `/api/reminders` | Listar recordatorios |
| `POST` | `/api/reminders` | Crear recordatorio |
| `PATCH` | `/api/reminders/{id}` | Editar o completar |
| `DELETE` | `/api/reminders/{id}` | Eliminar recordatorio |
| `GET` | `/api/tokens` | Listar tokens |
| `POST` | `/api/tokens` | Crear token |
| `PATCH` | `/api/tokens/{id}` | Editar permisos |
| `DELETE` | `/api/tokens/{id}` | Revocar token |

## Estructura del proyecto

```text
app/
  main.py        arranque, sesiones y reindexado
  config.py      variables de entorno
  db.py          esquema y conexión SQLite
  storage.py     archivos Markdown y carpetas
  indexer.py     índice y búsqueda FTS5
  history.py     versionado de notas
  security.py    contraseñas, sesiones, tokens y permisos
  pages.py       páginas HTML y vista previa Markdown
  routers/       auth, folders, notes, reminders, tokens
templates/       base, login, notas, recordatorios, ajustes
static/          CSS, JS, fuente local, manifiesto e icono
scripts/         utilidades de desarrollo y tokens
tests/           pruebas con pytest
integrations/    integración opcional con Hermes
design-system/   documento del sistema de diseño
```

## Seguridad

- Cambia `SECRET_KEY` y `ADMIN_PASSWORD` antes de exponer la app.
- No publiques `.env`, `data/`, tokens ni copias de la base.
- Usa HTTPS y `COOKIE_SECURE=true` si sale de la red local.
- Crea un token por dispositivo o agente y revócalo si se pierde.
- Haz backups periódicos del volumen `notas-data`.
- No des a un agente más permisos de los que necesita.

## Integración con Hermes (opcional)

`integrations/hermes/` incluye un CLI, una skill y un notificador de
recordatorios por WhatsApp para un agente que corre en el mismo servidor.
Consulta `integrations/hermes/README.md`.

## Estado

- [x] Backend, interfaz responsive, búsqueda, recordatorios y tokens.
- [x] Historial de versiones por nota.
- [x] Docker y despliegue en servidor.
- [x] Accesibilidad WCAG AA.
- [ ] Service worker y uso offline completo.
- [ ] Backups automáticos.
- [ ] Invalidar las demás sesiones al cambiar la contraseña.
- [ ] Rate limiting y 2FA opcional.
- [ ] Adjuntos.
