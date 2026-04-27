from fastapi import FastAPI

app = FastAPI(
    title="Knitting App API",
    description="API endpoints for pattern translation app — TFM MIW UPM",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"message": "Knitting App API running"}