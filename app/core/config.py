from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    RAVELRY_CLIENT_ID: str
    RAVELRY_CLIENT_SECRET: str = ""
    RAVELRY_REDIRECT_URI: str = "http://localhost:8000/auth/ravelry/callback"
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    GROQ_API_KEY: str
    STORAGE_BASE_PATH: str = "/app/storage"
    USE_MOCK_LLM: bool = False
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "firebase-service-account.json"
    FIREBASE_WEB_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""


settings = Settings()
