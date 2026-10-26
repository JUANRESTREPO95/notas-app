from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str = "dev-secret-change-me"
    admin_user: str = "admin"
    admin_password: str = "changeme"
    timezone: str = "America/Bogota"
    cookie_secure: bool = False
    app_name: str = "Notas"

    @property
    def notes_dir(self) -> Path:
        return self.data_dir / "notes"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @classmethod
    def from_env(cls) -> "Settings":
        raw_dir = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
        data_dir = Path(raw_dir).expanduser()
        if not data_dir.is_absolute():
            data_dir = (BASE_DIR / data_dir).resolve()
        else:
            data_dir = data_dir.resolve()
        return cls(
            data_dir=data_dir,
            secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
            admin_user=os.getenv("ADMIN_USER", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", "changeme"),
            timezone=os.getenv("TIMEZONE", "America/Bogota"),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").strip().lower()
            in {"1", "true", "yes", "on"},
            app_name=os.getenv("APP_NAME", "Notas"),
        )
