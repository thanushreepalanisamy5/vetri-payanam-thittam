"""ComicCraft - AI Comic Story Creator.

Run from the project root:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log = logging.getLogger("comiccraft")
    log.info("Image backend: %s | Flash model: %s | Pro model: %s",
             config.IMAGE_BACKEND, config.GEMINI_FLASH_MODEL, config.GEMINI_PRO_MODEL)
    if not config.GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY is not set - add it to .env before generating comics.")
    yield


app = FastAPI(
    title="ComicCraft",
    description="Generate comic stories with Gemini and Stable Diffusion, then export them as PDF.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.include_router(router)
