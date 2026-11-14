import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, categories, parts

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title="ZHAGARAM Jewellery API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(parts.router)
app.include_router(categories.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "mongo" if settings.use_mongo else "json"}
