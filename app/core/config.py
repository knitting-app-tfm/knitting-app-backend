from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    RAVELRY_CLIENT_ID: str

    class Config:
        env_file = ".env"


settings = Settings()
