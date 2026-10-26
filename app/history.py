from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Settings
from .db import connect
from .storage import now_iso, scan_notes

MAX_VERSIONS = 100
UPDATE_WINDOW = timedelta(minutes=5)


def record_version(
    settings: Settings,
    note_id: str,
    title: str,
    content: str,
    note_updated_at: str,
    source: str = "update",
) -> bool:
    """Guarda una versión. Los autoguardados se agrupan cada 5 minutos.

    El contenido actual de la nota siempre queda en el archivo; esta tabla es
    para el historial. Create y restore siempre guardan.
    """
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    with connect(settings.db_path) as conn:
        last = conn.execute(
            """
            SELECT title, content, created_at, source
            FROM note_versions
            WHERE note_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (note_id,),
        ).fetchone()

        if last and last["title"] == title and last["content"] == content:
            return False

        # El primer autoguardado después de crear la nota sí se guarda;
        # los siguientes se agrupan cada 5 minutos.
        if (
            source == "update"
            and last
            and last["title"] == title
            and last["source"] != "create"
        ):
            try:
                last_time = datetime.fromisoformat(last["created_at"])
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=tz)
                if now - last_time < UPDATE_WINDOW:
                    return False
            except ValueError:
                pass

        conn.execute(
            """
            INSERT INTO note_versions
                (note_id, title, content, note_updated_at, created_at, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (note_id, title, content, note_updated_at, now_iso(settings.timezone), source),
        )
        conn.execute(
            """
            DELETE FROM note_versions
            WHERE note_id = ?
              AND id NOT IN (
                  SELECT id FROM note_versions
                  WHERE note_id = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            """,
            (note_id, note_id, MAX_VERSIONS),
        )
    return True


def backfill_versions(settings: Settings) -> int:
    """Crea una versión inicial para notas que todavía no tengan historial."""
    notes = scan_notes(settings.notes_dir, settings.timezone)
    with connect(settings.db_path) as conn:
        existing = {
            row["note_id"]
            for row in conn.execute("SELECT DISTINCT note_id FROM note_versions")
        }
    created = 0
    for note in notes:
        if note["id"] in existing:
            continue
        if record_version(
            settings,
            note["id"],
            note["title"],
            note["content"],
            note["updated"],
            source="snapshot",
        ):
            created += 1
    return created


def list_versions(settings: Settings, note_id: str) -> list[dict]:
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, title, note_updated_at, created_at, source,
                   length(content) AS size
            FROM note_versions
            WHERE note_id = ?
            ORDER BY id DESC
            """,
            (note_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_version(settings: Settings, note_id: str, version_id: int) -> dict | None:
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM note_versions WHERE note_id = ? AND id = ?",
            (note_id, version_id),
        ).fetchone()
    return dict(row) if row else None
