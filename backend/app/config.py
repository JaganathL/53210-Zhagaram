import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    admin_username: str = "admin_zha"
    admin_password: str = "zhagaram"
    # Random per process unless configured: tokens are invalidated on restart.
    jwt_secret: str = secrets.token_urlsafe(48)
    jwt_expire_minutes: int = 120
    cors_origins: list[str] = ["http://localhost:4200"]

    # "auto" uses MongoDB when MONGO_URI is set, otherwise the local JSON store.
    storage: Literal["auto", "mongo", "json"] = "auto"
    mongo_uri: str = ""
    mongo_db: str = "zhagaram"
    data_dir: Path = BASE_DIR / "data"
    # Pre-database layout, migrated automatically on first start.
    legacy_data_file: Path = BASE_DIR / "data" / "parts.json"
    legacy_upload_dir: Path = BASE_DIR / "uploads"

    max_upload_bytes: int = 2 * 1024 * 1024

    @property
    def use_mongo(self) -> bool:
        return self.storage == "mongo" or (self.storage == "auto" and bool(self.mongo_uri))


@lru_cache
def get_settings() -> Settings:
    return Settings()
