from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import router as pattern_router
from app.routers.abbreviation import router as abbreviation_router
from app.routers.auth import router as auth_router
from app.routers.scaling import router as scaling_router

app = FastAPI(
    title="Knitting App API",
    description="API endpoints for pattern translation app — TFM MIW UPM",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(pattern_router)
app.include_router(abbreviation_router)
app.include_router(scaling_router)

# Serve uploaded files (cover images, original PDFs, parsed JSON)
# cover_image_path is stored as "storage/covers/<uuid>.jpg",
# so mounting STORAGE_BASE_PATH at /storage makes the URL
# http://localhost:8000/storage/covers/<uuid>.jpg resolve correctly.
_storage_dir = Path(settings.STORAGE_BASE_PATH)
_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(_storage_dir)), name="storage")


@app.get("/")
def root():
    return {"message": "Knitting App API running"}
