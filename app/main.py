from fastapi import FastAPI

from app.routers import router as pattern_router

app = FastAPI(
    title="Knitting App API",
    description="API endpoints for pattern translation app — TFM MIW UPM",
    version="0.1.0",
)

app.include_router(pattern_router)


@app.get("/")
def root():
    return {"message": "Knitting App API running"}
