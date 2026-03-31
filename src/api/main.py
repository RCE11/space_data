from fastapi import FastAPI

from src.api.logging_middleware import RequestLoggingMiddleware
from src.api.routes import launches, satellites

app = FastAPI(
    title="Space Data Intelligence API",
    description=(
        "Clean, queryable access to launch manifests, satellite registries, "
        "and orbital data. Consistent operator names, constellation grouping, "
        "mission classifications, and upcoming launch tracking — no cross-referencing required."
    ),
    version="0.1.0",
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(launches.router, prefix="/launches", tags=["Launches"])
app.include_router(satellites.router, prefix="/satellites", tags=["Satellites"])


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "Space Data Intelligence API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": [
            "/launches/upcoming",
            "/launches/history",
            "/satellites/by-operator",
            "/satellites/by-orbit",
            "/satellites/by-constellation",
        ],
    }
