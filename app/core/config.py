from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CT_", env_file=".env", extra="ignore", validate_assignment=True
    )
    database_url: str = "sqlite:///./generated/ct200.db"
    generation_dir: Path = Path("generated/generations")
    provider: str = "mock"
    model: str = "mock-v1"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr = SecretStr("")
    max_upload_bytes: int = 25 * 1024 * 1024
