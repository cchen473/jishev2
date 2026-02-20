from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _split_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


@dataclass(frozen=True)
class Settings:
    app_name: str = "NebulaGuard Backend"
    app_version: str = "2.0.0"
    app_mode: str = "earthquake-command"
    base_city: str = os.getenv("BASE_CITY", "成都")
    base_lat: float = float(os.getenv("BASE_LAT", "30.5728"))
    base_lng: float = float(os.getenv("BASE_LNG", "104.0668"))
    host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    port: int = int(os.getenv("BACKEND_PORT", "8000"))
    cors_origins: list[str] = None  # type: ignore[assignment]

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "qwen3-vl-plus")
    openai_vlm_model: str = os.getenv(
        "OPENAI_VLM_MODEL", os.getenv("OPENAI_MODEL", "qwen3-vl-plus")
    )
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")

    auth_secret: str = os.getenv("AUTH_SECRET", "change-me-in-production")
    auth_token_exp_minutes: int = int(os.getenv("AUTH_TOKEN_EXP_MINUTES", "720"))

    upload_dir: Path = Path(
        os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
    ).resolve()
    database_path: Path = Path(
        os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "nebulaguard.db"))
    ).resolve()

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            object.__setattr__(
                self,
                "cors_origins",
                _split_csv(os.getenv("CORS_ORIGINS", "*")) or ["*"],
            )


settings = Settings()
