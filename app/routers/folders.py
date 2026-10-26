from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..schemas import FolderCreate, FolderRename
from ..security import Principal, get_principal
from ..serializers import note_out
from ..storage import (
    create_folder,
    delete_folder,
    list_folders,
    normalize_rel,
    rename_folder,
    scan_notes,
)

router = APIRouter(prefix="/api", tags=["folders"])


def _settings(request: Request):
    return request.app.state.settings


@router.get("/tree")
def tree(request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    folders = list_folders(settings.notes_dir)
    notes = scan_notes(settings.notes_dir, settings.timezone)
    if not principal.is_admin:
        folders = [folder for folder in folders if principal.can(folder, "read")]
        notes = [note for note in notes if principal.can(note["rel_path"], "read")]
    return {
        "folders": folders,
        "notes": [note_out(note) for note in notes],
    }


@router.post("/folders", status_code=status.HTTP_201_CREATED)
def create(payload: FolderCreate, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    try:
        clean = normalize_rel(payload.path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not principal.can(clean, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura en esa ruta")
    try:
        created = create_folder(_settings(request).notes_dir, clean)
    except FileExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"path": created}


@router.patch("/folders")
def rename(payload: FolderRename, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    settings = _settings(request)
    try:
        old_clean = normalize_rel(payload.path)
        new_clean = normalize_rel(payload.new_path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not principal.can(old_clean, "write") or not principal.can(new_clean, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura en esa ruta")
    try:
        moved = rename_folder(settings.notes_dir, old_clean, new_clean)
    except FileExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"path": moved}


@router.delete("/folders")
def remove(
    request: Request,
    path: str,
    recursive: bool = False,
    principal: Principal = Depends(get_principal),
) -> dict:
    settings = _settings(request)
    try:
        clean = normalize_rel(path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not principal.can(clean, "write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin permiso de escritura en esa ruta")
    try:
        delete_folder(settings.notes_dir, clean, recursive=recursive)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "la carpeta no está vacía; usa recursive=true para borrarla con todo",
        ) from exc
    return {"ok": True}
