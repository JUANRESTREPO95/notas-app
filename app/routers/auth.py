from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import connect
from ..schemas import AccountUpdate, LoginRequest, PasswordChange
from ..security import Principal, get_admin, get_principal, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict:
    settings = request.app.state.settings
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()
    if row is None or not verify_password(row["password_hash"], payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuario o contraseña incorrectos")
    request.session.clear()
    request.session["user_id"] = row["id"]
    return {"ok": True, "user": row["username"]}


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(get_principal)) -> dict:
    return {
        "name": principal.name,
        "user_id": principal.user_id,
        "is_admin": principal.is_admin,
        "rules": principal.rules,
    }


@router.put("/account")
def update_account(
    payload: AccountUpdate,
    request: Request,
    principal: Principal = Depends(get_admin),
) -> dict:
    """Cambia usuario y/o contraseña. La sesión actual sigue abierta."""
    settings = request.app.state.settings
    username = payload.username.strip() if payload.username else None
    if username is None and payload.new_password is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no hay cambios que guardar")

    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE id = ?",
            (principal.user_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuario no encontrado")
        if not verify_password(row["password_hash"], payload.current_password):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "la contraseña actual no es correcta",
            )
        if payload.new_password and verify_password(
            row["password_hash"], payload.new_password
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "la contraseña nueva debe ser distinta",
            )

        if username and username != row["username"]:
            try:
                conn.execute(
                    "UPDATE users SET username = ? WHERE id = ?",
                    (username, principal.user_id),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "ese nombre de usuario ya está en uso",
                ) from exc

        if payload.new_password:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(payload.new_password), principal.user_id),
            )

        final_username = username or row["username"]

    return {"ok": True, "username": final_username}


@router.put("/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    principal: Principal = Depends(get_admin),
) -> dict:
    settings = request.app.state.settings
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (principal.user_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuario no encontrado")
        if not verify_password(row["password_hash"], payload.current_password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "la contraseña actual no es correcta")
        if verify_password(row["password_hash"], payload.new_password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "la contraseña nueva debe ser distinta")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.new_password), principal.user_id),
        )
    return {"ok": True}
