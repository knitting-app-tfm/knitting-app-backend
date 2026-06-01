from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    RAVELRY_CLIENT_ID: str
    GROQ_API_KEY: str
    STORAGE_BASE_PATH: str = "/app/storage"
    USE_MOCK_LLM: bool = False
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "firebase-service-account.json"
    FIREBASE_WEB_API_KEY: str = ""


settings = Settings()
