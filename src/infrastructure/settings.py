from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nginx Log Anomaly Detection"
    environment: str = "dev"
    database_url: str = "sqlite:///./data/logdetector.db"
    artifact_dir: str = "./artifacts"
    model_type: str = "isolation_forest"
    anomaly_threshold: float = 0.5
    baseline_threshold: float = 0.85
    log_level: str = "INFO"
    ingest_batch_size: int = 500
    auto_train_on_startup: bool = False
    bootstrap_log_path: str = "./data/logs/normal.jsonl"
    bootstrap_log_format: str = "jsonl"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
