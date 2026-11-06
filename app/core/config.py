from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VICOBA API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    EXPOSE_DEBUG_OTP: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/kikoba_db"

    # Security
    SECRET_KEY: str = "super_secret_kikoba_development_jwt_key_vicoba_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Third Party Integrations
    PAYMENT_GATEWAY_URL: str = "https://api.clickpesa.com"
    PAYMENT_GATEWAY_API_KEY: str = "mock_key"
    PAYMENT_GATEWAY_CLIENT_ID: str = "mock_client_id"

    # SMS Gateway (Elive - message.elive.co.tz)
    SMS_GATEWAY_URL: str = "https://message.elive.co.tz/api/v1/vendor/message/send"
    ELIVE_API_KEY: str = ""
    ELIVE_API_SECRET: str = ""
    SMS_SENDER_ID: str = "VICOBA"
    ELIVE_DELIVERY_REPORT_URL: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
