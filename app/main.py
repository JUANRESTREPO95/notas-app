from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import pages
from .config import BASE_DIR, Settings
from .db import connect, init_db
from .history import backfill_versions
from .indexer import reindex
from .routers import auth, folders, notes, reminders, tokens
from .security import hash_password
from .storage import now_iso

logger = logging.getLogger("notas")


def seed_admin(settings: Settings) -> None:
    """Crea el usuario inicial solo si la base está vacía.

    No usa el username del .env para decidir: si se cambia desde Ajustes,
    un reinicio no debe crear un segundo admin con el nombre viejo.
    """
    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (
                    uuid4().hex,
                    settings.admin_user,
                    hash_password(settings.admin_password),
                    now_iso(settings.timezone),
                ),
            )
            logger.warning("Usuario inicial creado: %s", settings.admin_user)


async def _reindex_loop(settings: Settings, interval: float = 30.0) -> None:
    while True:
        try:
            await asyncio.to_thread(reindex, settings)
        except Exception:
            logger.exception("falló la reindexación")
        await asyncio.sleep(interval)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    if settings.secret_key == "dev-secret-change-me":
        logger.warning("SECRET_KEY está por defecto; cámbiala en .env")
    if settings.admin_password == "changeme":
        logger.warning("ADMIN_PASSWORD está por defecto; cámbiala en .env")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.notes_dir.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        seed_admin(settings)
        await asyncio.to_thread(reindex, settings)
        await asyncio.to_thread(backfill_versions, settings)
        task = asyncio.create_task(_reindex_loop(settings))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.cookie_secure,
        same_site="lax",
    )

    pages.configure_templates(settings)

    app.include_router(auth.router)
    app.include_router(folders.router)
    app.include_router(notes.router)
    app.include_router(reminders.router)
    app.include_router(tokens.router)
    app.include_router(pages.router)

    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "app": settings.app_name}

    return app


app = create_app()
