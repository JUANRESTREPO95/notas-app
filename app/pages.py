from __future__ import annotations

import posixpath
from datetime import datetime, timezone as dt_timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import bleach
import markdown as markdown_lib
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, Settings
from .db import connect
from .indexer import get_note, search_notes
from .security import session_user, verify_password
from .serializers import reminder_out
from .storage import list_folders, normalize_rel, scan_notes

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

ALLOWED_TAGS = [
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "img", "input", "li", "ol", "p", "pre", "strong", "table", "tbody", "td",
    "th", "thead", "tr", "ul",
]
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "code": ["class"],
    "img": ["src", "alt", "title"],
    "input": ["type", "checked", "disabled"],
    "li": ["class"],
    "th": ["align"],
    "td": ["align"],
    "ul": ["class"],
}


def render_markdown(content: str) -> str:
    html = markdown_lib.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "pymdownx.tasklist"],
    )
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def configure_templates(settings: Settings) -> None:
    tz = ZoneInfo(settings.timezone)

    def to_tz(value):
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)

    def fecha(value):
        if not value:
            return ""
        try:
            parsed = to_tz(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{parsed.day} {MESES[parsed.month - 1]} {parsed:%H:%M}"

    def fecha_hora(value):
        if not value:
            return ""
        try:
            parsed = to_tz(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{parsed.day} {MESES[parsed.month - 1]} {parsed.year}, {parsed:%H:%M}"

    templates.env.filters["fecha"] = fecha
    templates.env.filters["fecha_hora"] = fecha_hora


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _current_user(request: Request):
    user_id = session_user(request)
    if not user_id:
        return None
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        return conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def _login_redirect(request: Request) -> RedirectResponse:
    target = request.url.path
    if request.url.query:
        target += "?" + request.url.query
    return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)


def build_tree(folders: list[str]) -> list[dict]:
    nodes: dict[str, dict] = {}
    roots: list[dict] = []
    for folder in sorted(folders):
        parts = folder.split("/")
        parent = "/".join(parts[:-1])
        node = {"name": parts[-1], "path": folder, "children": []}
        nodes[folder] = node
        if parent and parent in nodes:
            nodes[parent]["children"].append(node)
        else:
            roots.append(node)
    return roots


def folder_options(folders: list[str]) -> list[dict]:
    options = []
    for folder in sorted(folders):
        depth = folder.count("/")
        name = folder.split("/")[-1]
        options.append(
            {"path": folder, "name": name, "depth": depth, "label": "— " * depth + name}
        )
    return options


def breadcrumbs(folder: str) -> list[dict]:
    if not folder:
        return []
    parts = folder.split("/")
    return [
        {"name": part, "path": "/".join(parts[: index + 1])}
        for index, part in enumerate(parts)
    ]


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _current_user(request) is not None:
        return RedirectResponse("/notes", status_code=303)
    settings = _settings(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "app_name": settings.app_name,
            "error": None,
            "username": "",
            "next_url": request.query_params.get("next", ""),
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
):
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None or not verify_password(row["password_hash"], password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "app_name": settings.app_name,
                "error": "Usuario o contraseña incorrectos.",
                "username": username,
                "next_url": next,
            },
            status_code=401,
        )

    request.session.clear()
    request.session["user_id"] = row["id"]
    target = next if next.startswith("/") and not next.startswith("//") else "/notes"
    return RedirectResponse(target, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/")
def home():
    return RedirectResponse("/notes", status_code=303)


@router.get("/notes", response_class=HTMLResponse)
def notes_page(request: Request):
    user = _current_user(request)
    if user is None:
        return _login_redirect(request)

    settings = _settings(request)
    folders = list_folders(settings.notes_dir)
    all_notes = scan_notes(settings.notes_dir, settings.timezone)

    folder_param = request.query_params.get("folder")
    if folder_param is None:
        folder = folders[0] if folders else ""
    else:
        try:
            folder = normalize_rel(folder_param)
        except ValueError:
            folder = ""
    if folder and folder not in folders:
        folder = folders[0] if folders else ""

    note_id = request.query_params.get("note")
    note = get_note(settings, note_id) if note_id else None
    if note is not None:
        folder = posixpath.dirname(note["rel_path"])

    query = (request.query_params.get("q") or "").strip()
    results: list[dict] = []
    if query:
        results = search_notes(settings, query)
        for item in results:
            item["folder"] = posixpath.dirname(item["path"])
    else:
        results = []

    folder_notes = [
        item for item in all_notes if posixpath.dirname(item["rel_path"]) == folder
    ]
    folder_notes.sort(key=lambda item: item["title"].lower())

    return templates.TemplateResponse(
        request=request,
        name="notes.html",
        context={
            "app_name": settings.app_name,
            "active_page": "notes",
            "user": user,
            "tree": build_tree(folders),
            "folder": folder,
            "folder_options": folder_options(folders),
            "notes": folder_notes,
            "results": results,
            "q": query,
            "selected_note": note,
            "selected_note_id": note["id"] if note else None,
            "breadcrumbs": breadcrumbs(folder),
            "focus_search": request.query_params.get("focus") == "search",
            "timezone": settings.timezone,
        },
    )


@router.get("/reminders", response_class=HTMLResponse)
def reminders_page(request: Request):
    user = _current_user(request)
    if user is None:
        return _login_redirect(request)

    settings = _settings(request)
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            ORDER BY done ASC, due_at IS NULL, due_at ASC, created_at DESC
            """
        ).fetchall()

    now = datetime.now(dt_timezone.utc)
    reminders = []
    for row in rows:
        item = reminder_out(row)
        item["body_html"] = render_markdown(item["body"]) if item["body"] else ""
        overdue = False
        if item["due_at"] and not item["done"]:
            try:
                overdue = datetime.fromisoformat(item["due_at"]) < now
            except ValueError:
                overdue = False
        item["overdue"] = overdue
        reminders.append(item)

    return templates.TemplateResponse(
        request=request,
        name="reminders.html",
        context={
            "app_name": settings.app_name,
            "active_page": "reminders",
            "user": user,
            "pending": [item for item in reminders if not item["done"]],
            "done": [item for item in reminders if item["done"]],
            "timezone": settings.timezone,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = _current_user(request)
    if user is None:
        return _login_redirect(request)
    settings = _settings(request)
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "app_name": settings.app_name,
            "active_page": "settings",
            "user": user,
            "timezone": settings.timezone,
        },
    )


@router.post("/partials/preview", response_class=HTMLResponse)
def preview(content: str = Form("")) -> HTMLResponse:
    return HTMLResponse(render_markdown(content))
