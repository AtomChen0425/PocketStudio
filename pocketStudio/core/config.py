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
    worker_enabled: bool = True
    worker_poll_interval: float = 0.5
    stale_processing_seconds: int = 600
    heartbeat_enabled: bool = True
    heartbeat_interval_seconds: int = 3600
    build_in_model_model: str = ""
    build_in_model_model_provider: str = "google_genai"
    build_in_model_api_key: str = ""
    build_in_model_temperature: float = 0.2
    build_in_model_max_tokens: int = 256
    build_in_model_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(env_prefix="POCKETSTUDIO_", env_file=".env", extra="ignore")

    @property
    def database_path(self) -> Path:
        return self.pocketStudio_home / "pocketStudio.db"

    @property
    def settings_path(self) -> Path:
        return self.pocketStudio_home / "settings.json"

    @property
    def workspace_path(self) -> Path:
        return self.pocketStudio_home / "workspace"

    @property
    def files_path(self) -> Path:
        return self.pocketStudio_home / "files"

    @property
    def logs_path(self) -> Path:
        return self.pocketStudio_home / "logs"

    @property
    def log_file_path(self) -> Path:
        return self.logs_path / "pocketstudio.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()
