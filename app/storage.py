from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import frontmatter

NOTE_SUFFIX = ".md"


def now_iso(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).replace(microsecond=0).isoformat()


def mtime_iso(path: Path, timezone: str) -> str:
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=ZoneInfo(timezone))
    return stamp.replace(microsecond=0).isoformat()


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text or "nota"


def normalize_rel(rel: str) -> str:
    raw = (rel or "").strip().replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("ruta inválida")
    rel = raw.strip("/")
    if rel in ("", "."):
        return ""
    path = PurePosixPath(rel)
    if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
        raise ValueError("ruta inválida")
    if any(part.startswith(".") for part in path.parts):
        raise ValueError("ruta inválida")
    return path.as_posix()


def safe_path(root: Path, rel: str) -> Path:
    clean = normalize_rel(rel)
    target = (root / clean).resolve() if clean else root.resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("ruta fuera del almacén")
    return target


def relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def load_post(path: Path) -> frontmatter.Post:
    try:
        return frontmatter.load(path)
    except Exception:
        return frontmatter.Post(path.read_text(encoding="utf-8", errors="replace"))


def dump_post(path: Path, post: frontmatter.Post) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def ensure_metadata(path: Path, timezone: str, seen_ids: set[str] | None = None) -> dict[str, Any]:
    """Garantiza id, título y fechas en el frontmatter y devuelve la nota."""
    post = load_post(path)
    meta = dict(post.metadata or {})
    changed = False

    note_id = str(meta.get("id") or "")
    if not note_id or (seen_ids is not None and note_id in seen_ids):
        note_id = uuid4().hex
        meta["id"] = note_id
        changed = True

    title = str(meta.get("title") or "").strip() or path.stem
    if meta.get("title") != title:
        meta["title"] = title
        changed = True

    created = meta.get("created") or mtime_iso(path, timezone)
    if meta.get("created") != created:
        meta["created"] = created
        changed = True

    updated = meta.get("updated") or created
    if meta.get("updated") != updated:
        meta["updated"] = updated
        changed = True

    if changed:
        post.metadata = meta
        dump_post(path, post)

    return {
        "id": note_id,
        "path": path,
        "title": title,
        "created": str(meta["created"]),
        "updated": str(meta["updated"]),
        "content": post.content,
        "metadata": meta,
    }


def scan_notes(notes_dir: Path, timezone: str) -> list[dict[str, Any]]:
    """Recorre todos los .md y les garantiza frontmatter e id único."""
    notes: list[dict[str, Any]] = []
    if not notes_dir.exists():
        return notes

    seen: set[str] = set()
    for path in sorted(notes_dir.rglob(f"*{NOTE_SUFFIX}")):
        rel_parts = path.relative_to(notes_dir).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        note = ensure_metadata(path, timezone, seen)
        note["rel_path"] = relative_path(notes_dir, path)
        seen.add(note["id"])
        notes.append(note)
    return notes


def list_folders(notes_dir: Path) -> list[str]:
    folders: list[str] = []
    if not notes_dir.exists():
        return folders
    for path in sorted(notes_dir.rglob("*")):
        if not path.is_dir():
            continue
        rel_parts = path.relative_to(notes_dir).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        folders.append(path.relative_to(notes_dir).as_posix())
    return folders


def unique_note_path(folder: Path, title: str) -> Path:
    base = slugify(title)
    candidate = folder / f"{base}{NOTE_SUFFIX}"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{base}-{counter}{NOTE_SUFFIX}"
        counter += 1
    return candidate


def create_folder(notes_dir: Path, rel: str) -> str:
    clean = normalize_rel(rel)
    if not clean:
        raise ValueError("nombre de carpeta vacío")
    target = safe_path(notes_dir, clean)
    if target.exists():
        raise FileExistsError("la carpeta ya existe")
    target.mkdir(parents=True)
    return clean


def rename_folder(notes_dir: Path, old_rel: str, new_rel: str) -> str:
    old_clean = normalize_rel(old_rel)
    new_clean = normalize_rel(new_rel)
    if not old_clean or not new_clean:
        raise ValueError("ruta de carpeta vacía")
    old = safe_path(notes_dir, old_clean)
    new = safe_path(notes_dir, new_clean)
    if not old.is_dir():
        raise FileNotFoundError("la carpeta no existe")
    if new.exists():
        raise FileExistsError("el destino ya existe")
    if new.is_relative_to(old):
        raise ValueError("no se puede mover una carpeta dentro de sí misma")
    new.parent.mkdir(parents=True, exist_ok=True)
    old.rename(new)
    return new_clean


def delete_folder(notes_dir: Path, rel: str, recursive: bool = False) -> None:
    clean = normalize_rel(rel)
    if not clean:
        raise ValueError("no se puede borrar la raíz")
    target = safe_path(notes_dir, clean)
    if not target.is_dir():
        raise FileNotFoundError("la carpeta no existe")
    if recursive:
        shutil.rmtree(target)
    else:
        target.rmdir()


def create_note(notes_dir: Path, folder_rel: str, title: str, content: str, timezone: str) -> dict[str, Any]:
    folder = safe_path(notes_dir, folder_rel)
    if not folder.is_dir():
        raise FileNotFoundError("la carpeta no existe")
    path = unique_note_path(folder, title)
    stamp = now_iso(timezone)
    post = frontmatter.Post(content, id=uuid4().hex, title=title, created=stamp, updated=stamp)
    dump_post(path, post)
    note = ensure_metadata(path, timezone)
    note["rel_path"] = relative_path(notes_dir, path)
    return note


def update_note(notes_dir: Path, rel: str, timezone: str, title: str | None, content: str | None) -> dict[str, Any]:
    path = safe_path(notes_dir, rel)
    if not path.is_file():
        raise FileNotFoundError("la nota no existe")
    note = ensure_metadata(path, timezone)
    post = load_post(path)
    meta = dict(post.metadata or {})
    if title is not None:
        meta["title"] = title
    if content is not None:
        post.content = content
    meta["updated"] = now_iso(timezone)
    post.metadata = meta
    dump_post(path, post)
    note = ensure_metadata(path, timezone)
    note["rel_path"] = relative_path(notes_dir, path)
    return note


def delete_note(notes_dir: Path, rel: str) -> None:
    path = safe_path(notes_dir, rel)
    if not path.is_file():
        raise FileNotFoundError("la nota no existe")
    path.unlink()


def move_note(notes_dir: Path, rel: str, new_folder_rel: str) -> str:
    source = safe_path(notes_dir, rel)
    if not source.is_file():
        raise FileNotFoundError("la nota no existe")
    folder = safe_path(notes_dir, new_folder_rel)
    if not folder.is_dir():
        raise FileNotFoundError("la carpeta destino no existe")
    target = folder / source.name
    if target.exists():
        target = unique_note_path(folder, source.stem)
    source.rename(target)
    return relative_path(notes_dir, target)
