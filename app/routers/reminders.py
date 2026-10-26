from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import connect
from ..schemas import ReminderCreate, ReminderUpdate
from ..security import Principal, get_principal
from ..serializers import reminder_out
from ..storage import now_iso

router = APIRouter(prefix="/api", tags=["reminders"])


def _settings(request: Request):
    return request.app.state.settings


def _to_utc(due: datetime | None, tz_name: str) -> str | None:
    if due is None:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "zona horaria inválida") from exc
    if due.tzinfo is None:
        due = due.replace(tzinfo=tz)
    return due.astimezone(dt_timezone.utc).isoformat()


@router.get("/reminders")
def list_reminders(
    request: Request,
    principal: Principal = Depends(get_principal),
    done: bool | None = None,
    upcoming: bool = False,
) -> dict:
    settings = _settings(request)
    clauses: list[str] = []
    params: list[object] = []
    if done is not None:
        clauses.append("done = ?")
        params.append(1 if done else 0)
    if upcoming:
        clauses.append("done = 0 AND due_at IS NOT NULL AND due_at >= ?")
        params.append(datetime.now(dt_timezone.utc).isoformat())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    order = (
        " ORDER BY due_at ASC, created_at DESC"
        if upcoming
        else " ORDER BY done ASC, due_at IS NULL, due_at ASC, created_at DESC"
    )
    with connect(settings.db_path) as conn:
        rows = conn.execute(f"SELECT * FROM reminders{where}{order}", params).fetchall()
    return {"reminders": [reminder_out(row) for row in rows]}


@router.post("/reminders", status_code=status.HTTP_201_CREATED)
def create(payload: ReminderCreate, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    due = _to_utc(payload.due_at, payload.timezone)
    stamp = now_iso(settings.timezone)
    reminder_id = uuid4().hex
    with connect(settings.db_path) as conn:
        conn.execute(
            """
            INSERT INTO reminders
                (id, title, body, due_at, timezone, done, note_id, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                reminder_id,
                payload.title,
                payload.body,
                due,
                payload.timezone,
                payload.note_id,
                principal.name,
                stamp,
                stamp,
            ),
        )
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return reminder_out(row)


@router.patch("/reminders/{reminder_id}")
def update(
    reminder_id: str,
    payload: ReminderUpdate,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "recordatorio no encontrado")
        fields: dict[str, object] = {}
        supplied = payload.model_fields_set
        if "title" in supplied and payload.title is not None:
            fields["title"] = payload.title
        if "body" in supplied and payload.body is not None:
            fields["body"] = payload.body
        if "due_at" in supplied:
            fields["due_at"] = _to_utc(payload.due_at, row["timezone"])
        if "done" in supplied and payload.done is not None:
            fields["done"] = 1 if payload.done else 0
        if "note_id" in supplied:
            fields["note_id"] = payload.note_id
        if fields:
            fields["updated_at"] = now_iso(settings.timezone)
            assignments = ", ".join(f"{key} = ?" for key in fields)
            conn.execute(
                f"UPDATE reminders SET {assignments} WHERE id = ?",
                [*fields.values(), reminder_id],
            )
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return reminder_out(row)


@router.delete("/reminders/{reminder_id}")
def remove(reminder_id: str, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recordatorio no encontrado")
    return {"ok": True}
