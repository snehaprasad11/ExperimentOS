"""Backend settings, loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Empty by default so the app imports without a DB (e.g. in CI for the
    # pure endpoints); DB-backed endpoints raise clearly if it is unset.
    database_url: str = ""


settings = Settings()  # reads DATABASE_URL from .env
