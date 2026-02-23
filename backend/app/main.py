from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from contextlib import asynccontextmanager
from app.services.external_updater import updater
# Se
# tup logging
from app.core.logging import setup_logging
setup_logging()
import logging
logger = logging.getLogger("app")

from app.core.config import settings
from app.api.router import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up JSON Database API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    yield
    logger.info("Shutting down JSON Database API")


app = FastAPI(
    title="JSON Database API",
    version="1.0.0",
    description="High-performance JSON document store",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "JSON Database API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up JSON Database API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Start external updater if URL configured
    if settings.EXTERNAL_UPDATE_URL:
        updater.start()
        logger.info(f"External updater started with interval {settings.UPDATE_INTERVAL_SECONDS}s")
    
    yield
    
    # Shutdown
    logger.info("Shutting down JSON Database API")
    await updater.stop()