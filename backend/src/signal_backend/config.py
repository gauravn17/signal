from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://signal:signal@localhost:5432/signal"
    redis_url: str = "redis://localhost:6379/0"
    github_token: str = ""
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"


settings = Settings()
