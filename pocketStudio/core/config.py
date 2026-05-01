from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pocket Studio"
    api_prefix: str = "/api"
    pocketStudio_home: Path = Path(".pocketStudio")
    default_provider: str = "local"
    queue_max_attempts: int = 5
    sqlite_journal_mode: str = "MEMORY"

    model_config = SettingsConfigDict(env_prefix="POCKETSTUDIO_", env_file=".env", extra="ignore")

    @property
    def database_path(self) -> Path:
        return self.pocketStudio_home / "pocketStudio.db"

    @property
    def workspace_path(self) -> Path:
        return self.pocketStudio_home / "workspace"


@lru_cache
def get_settings() -> Settings:
    return Settings()
