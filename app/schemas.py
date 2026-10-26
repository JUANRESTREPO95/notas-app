from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class AccountUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    new_password: str | None = Field(default=None, min_length=8, max_length=200)


class FolderCreate(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class FolderRename(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    new_path: str = Field(min_length=1, max_length=500)


class NoteCreate(BaseModel):
    folder: str = ""
    title: str = Field(min_length=1, max_length=200)
    content: str = ""


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None


class NoteMove(BaseModel):
    folder: str = ""


class TokenRule(BaseModel):
    path: str = ""
    level: Literal["read", "write"] = "read"


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rules: list[TokenRule] = Field(default_factory=list)


class TokenUpdate(BaseModel):
    rules: list[TokenRule] = Field(default_factory=list)


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    due_at: datetime | None = None
    timezone: str = "America/Bogota"
    note_id: str | None = None


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = None
    due_at: datetime | None = None
    done: bool | None = None
    note_id: str | None = None
