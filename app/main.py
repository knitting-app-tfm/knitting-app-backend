from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import router as pattern_router
from app.routers.auth import router as auth_router

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


@app.get("/")
def root():
    return {"message": "Knitting App API running"}
