import os

# Set required env vars before any app module is imported.
# These are used only in tests — real values come from .env in dev/prod.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAVELRY_CLIENT_ID", "test-ravelry-client-id")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
os.environ.setdefault("STORAGE_BASE_PATH", "/tmp/test_storage")
