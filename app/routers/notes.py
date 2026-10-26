from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..history import get_version, list_versions, record_version
from ..indexer import get_note, get_note_path, reindex, search_notes
from ..schemas import NoteCreate, NoteMove, NoteUpdate
from ..security import Principal, get_admin, get_principal
from ..serializers import note_out
from ..storage import (
    create_note,
    delete_note,
    move_note,
    normalize_rel,
    update_note,
)

router = APIRouter(prefix="/api", tags=["notes"])


def _settings(request: Request):
    return request.app.state.settings


def _require_note(settings, note_id: str) -> tuple[str, dict]:
    rel = get_note_path(settings, note_id)
    if rel is None:
        reindex(settings)
        rel = get_note_path(settings, note_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nota no encontrada")
    note = get_note(settings, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nota no encontrada")
    return rel, note


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def create(payload: NoteCreate, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    try:
        folder = normalize_rel(payload.folder)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not principal.can(folder, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura en esa carpeta")
    try:
        note = create_note(settings.notes_dir, folder, payload.title, payload.content, settings.timezone)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    reindex(settings)
    record_version(
        settings,
        note["id"],
        note["title"],
        note["content"],
        note["updated"],
        source="create",
    )
    return note_out(note, include_content=True)


@router.get("/notes/{note_id}")
def read(note_id: str, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    rel, note = _require_note(settings, note_id)
    if not principal.can(rel, "read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de lectura")
    return note_out(note, include_content=True)


@router.put("/notes/{note_id}")
def update(
    note_id: str,
    payload: NoteUpdate,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    rel, _ = _require_note(settings, note_id)
    if not principal.can(rel, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura")
    try:
        note = update_note(settings.notes_dir, rel, settings.timezone, payload.title, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    reindex(settings)
    record_version(
        settings,
        note_id,
        note["title"],
        note["content"],
        note["updated"],
        source="update",
    )
    return note_out(note, include_content=True)


@router.get("/notes/{note_id}/versions")
def versions(
    note_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    rel, _ = _require_note(settings, note_id)
    if not principal.can(rel, "read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de lectura")
    return {"versions": list_versions(settings, note_id)}


@router.get("/notes/{note_id}/versions/{version_id}")
def version_detail(
    note_id: str,
    version_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    rel, _ = _require_note(settings, note_id)
    if not principal.can(rel, "read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de lectura")
    version = get_version(settings, note_id, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "versión no encontrada")
    return version


@router.post("/notes/{note_id}/versions/{version_id}/restore")
def restore_version(
    note_id: str,
    version_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    rel, current = _require_note(settings, note_id)
    if not principal.can(rel, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura")
    version = get_version(settings, note_id, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "versión no encontrada")
    # Guarda el estado actual para poder deshacer la restauración.
    record_version(
        settings,
        note_id,
        current["title"],
        current["content"],
        current["updated"],
        source="before-restore",
    )
    try:
        note = update_note(
            settings.notes_dir,
            rel,
            settings.timezone,
            version["title"],
            version["content"],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    reindex(settings)
    record_version(
        settings,
        note_id,
        note["title"],
        note["content"],
        note["updated"],
        source=f"restore:{version_id}",
    )
    return note_out(note, include_content=True)


@router.delete("/notes/{note_id}")
def remove(note_id: str, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    rel, _ = _require_note(settings, note_id)
    if not principal.can(rel, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura")
    delete_note(settings.notes_dir, rel)
    reindex(settings)
    return {"ok": True}


@router.post("/notes/{note_id}/move")
def move(
    note_id: str,
    payload: NoteMove,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    rel, _ = _require_note(settings, note_id)
    try:
        folder = normalize_rel(payload.folder)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not principal.can(rel, "write") or not principal.can(folder, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura")
    try:
        new_rel = move_note(settings.notes_dir, rel, folder)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    reindex(settings)
    note = get_note(settings, note_id)
    if note is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "la nota se movió pero no se pudo leer")
    return note_out(note, include_content=True)


@router.get("/search")
def search(q: str, request: Request, principal: Principal = Depends(get_principal), limit: int = 50) -> dict:
    settings = _settings(request)
    results = search_notes(settings, q, limit=min(max(limit, 1), 200))
    if not principal.is_admin:
        results = [item for item in results if principal.can(item["path"], "read")]
    return {"query": q, "results": results}


@router.post("/reindex")
def rebuild(request: Request, principal: Principal = Depends(get_admin)) -> dict:
    return {"indexed": reindex(_settings(request))}
