from fastapi import FastAPI

from src.api.routes import launches, satellites

app = FastAPI(
    title="Space Data Intelligence API",
    description="Launch manifests, satellite registries, and orbital data.",
    version="0.1.0",
)

app.include_router(launches.router, prefix="/launches", tags=["Launches"])
app.include_router(satellites.router, prefix="/satellites", tags=["Satellites"])
