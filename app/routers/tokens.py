from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import connect
from ..schemas import TokenCreate, TokenUpdate
from ..security import Principal, generate_token, get_admin, hash_token
from ..storage import normalize_rel, now_iso

router = APIRouter(prefix="/api", tags=["tokens"])


def _settings(request: Request):
    return request.app.state.settings


def _normalize_rules(rules) -> list[dict]:
    normalized = []
    for rule in rules:
        try:
            path = normalize_rel(rule.path)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        normalized.append({"path": path, "level": rule.level})
    return normalized


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create(payload: TokenCreate, request: Request, principal: Principal = Depends(get_admin)) -> dict:
    settings = _settings(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "el nombre no puede estar vacío")

    rules = _normalize_rules(payload.rules)

    raw = generate_token()
    token_id = uuid4().hex
    with connect(settings.db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM api_tokens WHERE name = ?", (name,)
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "ya existe un token con ese nombre",
            )
        conn.execute(
            """
            INSERT INTO api_tokens (id, user_id, name, token_hash, rules, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                principal.user_id,
                name,
                hash_token(raw),
                json.dumps(rules, ensure_ascii=False),
                now_iso(settings.timezone),
            ),
        )
    return {"id": token_id, "name": name, "rules": rules, "token": raw}


@router.patch("/tokens/{token_id}")
def update(
    token_id: str,
    payload: TokenUpdate,
    request: Request,
    principal: Principal = Depends(get_admin),
) -> dict:
    settings = _settings(request)
    rules = _normalize_rules(payload.rules)
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id FROM api_tokens WHERE id = ?", (token_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "token no encontrado")
        conn.execute(
            "UPDATE api_tokens SET rules = ? WHERE id = ?",
            (json.dumps(rules, ensure_ascii=False), token_id),
        )
    return {"id": token_id, "rules": rules}


@router.get("/tokens")
def list_tokens(request: Request, principal: Principal = Depends(get_admin)) -> dict:
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, rules, created_at, last_used_at FROM api_tokens ORDER BY created_at DESC"
        ).fetchall()
    return {
        "tokens": [
            {
                "id": row["id"],
                "name": row["name"],
                "rules": json.loads(row["rules"]),
                "created_at": row["created_at"],
                "last_used_at": row["last_used_at"],
            }
            for row in rows
        ]
    }


@router.delete("/tokens/{token_id}")
def remove(token_id: str, request: Request, principal: Principal = Depends(get_admin)) -> dict:
    settings = _settings(request)
    with connect(settings.db_path) as conn:
        cursor = conn.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "token no encontrado")
    return {"ok": True}
