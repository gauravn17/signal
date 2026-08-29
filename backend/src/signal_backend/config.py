from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://signal:signal@localhost:5432/signal"
    redis_url: str = "redis://localhost:6379/0"
    github_token: str = ""
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    # Fernet key (32 url-safe base64 bytes) used to encrypt each organization's
    # BYOK github_token/llm_api_key at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # Clerk (auth). clerk_issuer is the JWT "iss" claim to verify against;
    # clerk_jwks_url serves the public keys used to verify token signatures.
    clerk_issuer: str = ""
    clerk_jwks_url: str = ""


settings = Settings()
