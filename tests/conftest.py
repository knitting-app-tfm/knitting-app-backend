import os

# Set required env vars before any app module is imported.
# These are used only in tests — real values come from .env in dev/prod.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAVELRY_CLIENT_ID", "test-ravelry-client-id")
os.environ.setdefault("RAVELRY_CLIENT_SECRET", "test-ravelry-client-secret")
os.environ.setdefault(
    "RAVELRY_REDIRECT_URI", "http://localhost:8000/auth/ravelry/callback"
)
os.environ.setdefault("FRONTEND_BASE_URL", "http://localhost:5173")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
os.environ.setdefault("STORAGE_BASE_PATH", "/tmp/test_storage")
