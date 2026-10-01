"""Configuración global de la aplicación (pydantic-settings, desde .env)."""
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import model_validator
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
    access_token_expire_minutes: int = 60
    environment: str = "development"
    admin_bootstrap_password: str | None = None

    default_raiz_origen: str = "C:/Users/TI/Desktop/EntregaDocs"
    default_raiz_repo: str = "C:/Users/TI/Desktop/EntregaDocs/2026"

    debug: bool = False

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 25
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_tls: bool = True
    smtp_from: str = ""
    app_url: str = "http://127.0.0.1:8001"

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() in {"production", "prod"}

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if not self.is_production:
            return self
        if (
            self.secret_key == "change-me-in-production"
            or len(self.secret_key) < 32
            or len(set(self.secret_key)) < 8
        ):
            raise ValueError("SECRET_KEY debe ser única y tener al menos 32 caracteres en producción.")
        parsed_url = urlsplit(self.app_url)
        if parsed_url.scheme.casefold() != "https" or not parsed_url.netloc:
            raise ValueError("APP_URL debe usar HTTPS en producción.")
        return self

    @property
    def temp_dir(self) -> Path:
        d = BACKEND_DIR / "storage" / "tmp"
        d.mkdir(parents=True, exist_ok=True)
        return d


settings = Settings()
