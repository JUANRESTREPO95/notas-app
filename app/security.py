from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status

from .db import connect
from .storage import now_iso

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def generate_token() -> str:
    return "nsk_" + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_path(value: str) -> str:
    return (value or "").strip().replace("\\", "/").strip("/")


@dataclass
class Principal:
    user_id: str
    name: str
    is_admin: bool = False
    rules: list[dict[str, Any]] = field(default_factory=list)

    def can(self, rel_path: str, action: str = "read") -> bool:
        if self.is_admin:
            return True
        rel = _clean_path(rel_path)
        best: dict[str, Any] | None = None
        best_len = -1
        for rule in self.rules:
            prefix = _clean_path(str(rule.get("path", "")))
            if prefix and rel != prefix and not rel.startswith(prefix + "/"):
                continue
            if len(prefix) > best_len:
                best = rule
                best_len = len(prefix)
        if best is None:
            return False
        level = str(best.get("level", "read"))
        if action == "read":
            return level in {"read", "write"}
        return level == "write"


def get_principal(request: Request) -> Principal:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
        if not raw:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token vacío")
        settings = request.app.state.settings
        with connect(settings.db_path) as conn:
            row = conn.execute(
                "SELECT id, user_id, name, rules FROM api_tokens WHERE token_hash = ?",
                (hash_token(raw),),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "token inválido",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            conn.execute(
                "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
                (now_iso(settings.timezone), row["id"]),
            )
        return Principal(
            user_id=row["user_id"],
            name=row["name"],
            is_admin=False,
            rules=json.loads(row["rules"]),
        )

    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "no autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = request.app.state.settings
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión inválida")
    return Principal(user_id=row["id"], name=row["username"], is_admin=True)


def get_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requiere sesión de administrador")
    return principal


def session_user(request: Request) -> str | None:
    return request.session.get("user_id")
