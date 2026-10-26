from __future__ import annotations

from typing import Any


def note_out(note: dict[str, Any], include_content: bool = False) -> dict[str, Any]:
    data = {
        "id": note["id"],
        "path": note["rel_path"],
        "title": note["title"],
        "created": note["created"],
        "updated": note["updated"],
    }
    if include_content:
        data["content"] = note["content"]
    return data


def reminder_out(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "due_at": row["due_at"],
        "timezone": row["timezone"],
        "done": bool(row["done"]),
        "note_id": row["note_id"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
