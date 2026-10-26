from __future__ import annotations

import re
import sqlite3
from typing import Any

from .config import Settings
from .db import connect
from .storage import ensure_metadata, relative_path, safe_path, scan_notes


def reindex(settings: Settings) -> int:
    """Reconstruye el índice. Es barato para miles de notas."""
    notes = scan_notes(settings.notes_dir, settings.timezone)
    with connect(settings.db_path) as conn:
        conn.execute("DELETE FROM notes_index")
        conn.execute("DELETE FROM notes_fts")
        conn.executemany(
            "INSERT INTO notes_index (id, path, title, updated_at) VALUES (?, ?, ?, ?)",
            [(n["id"], n["rel_path"], n["title"], n["updated"]) for n in notes],
        )
        conn.executemany(
            "INSERT INTO notes_fts (id, path, title, content) VALUES (?, ?, ?, ?)",
            [(n["id"], n["rel_path"], n["title"], n["content"]) for n in notes],
        )
    return len(notes)


def search_notes(settings: Settings, query: str, limit: int = 50) -> list[dict[str, Any]]:
    terms = re.findall(r"\w+", query, flags=re.UNICODE)
    if not terms:
        return []
    match = " AND ".join(f'"{term}"' for term in terms)
    sql = """
        SELECT n.id, n.path, n.title,
               snippet(notes_fts, 3, '<mark>', '</mark>', '…', 20) AS snippet
        FROM notes_fts
        JOIN notes_index n ON n.id = notes_fts.id
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    with connect(settings.db_path) as conn:
        try:
            rows = conn.execute(sql, (match, limit)).fetchall()
        except sqlite3.OperationalError:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT id, path, title, '' AS snippet
                FROM notes_index
                WHERE title LIKE ? OR path LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
    return [dict(row) for row in rows]


def get_note_path(settings: Settings, note_id: str) -> str | None:
    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT path FROM notes_index WHERE id = ?", (note_id,)).fetchone()
    return row["path"] if row else None


def get_note(settings: Settings, note_id: str) -> dict[str, Any] | None:
    rel = get_note_path(settings, note_id)
    if rel is None:
        reindex(settings)
        rel = get_note_path(settings, note_id)
        if rel is None:
            return None
    path = safe_path(settings.notes_dir, rel)
    if not path.is_file():
        return None
    note = ensure_metadata(path, settings.timezone)
    note["rel_path"] = relative_path(settings.notes_dir, path)
    return note
