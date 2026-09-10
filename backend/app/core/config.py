"""Configuración global de la aplicación (pydantic-settings, desde .env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://root:@localhost:3306/db_extract_py"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    default_raiz_origen: str = "C:/Users/TI/Desktop/EntregaDocs"
    default_raiz_repo: str = "C:/Users/TI/Desktop/EntregaDocs/2026"

    debug: bool = False

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 25
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_tls: bool = True
    smtp_from: str = ""

    @property
    def temp_dir(self) -> Path:
        d = BACKEND_DIR / "storage" / "tmp"
        d.mkdir(parents=True, exist_ok=True)
        return d


settings = Settings()