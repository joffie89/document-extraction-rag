"""Compose the FastAPI application and its runtime dependencies."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from document_rag.api.routes import router
from document_rag.core.config import load_settings
from document_rag.infrastructure.chroma_store import prepare_collection
from document_rag.infrastructure.database import build_database
from document_rag.infrastructure.docling.configuration import (
    build_document_converter,
)


def create_application() -> FastAPI:
    """Build the API and initialize shared resources during its lifespan."""

    application_settings = load_settings()

    @asynccontextmanager
    async def application_lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Create runtime integrations and close the database on shutdown."""

        runtime_settings = load_settings(require_openai=True)
        logging.basicConfig(
            level=runtime_settings.LOG_LEVEL,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        application.state.settings = runtime_settings
        application.state.engine = build_database(runtime_settings.DATABASE_URL)
        application.state.converter = build_document_converter(
            runtime_settings.EXTRACTION_TIMEOUT_SECONDS,
            runtime_settings.OCR_LANGUAGE,
        )
        application.state.collection = prepare_collection(
            runtime_settings.CHROMA_DIRECTORY,
            runtime_settings.CHROMA_COLLECTION,
        )
        application.state.openai_client = OpenAI(
            api_key=runtime_settings.OPENAI_API_KEY,
            timeout=runtime_settings.OPENAI_TIMEOUT_SECONDS,
            max_retries=2,
        )

        yield

        application.state.engine.dispose()

    application = FastAPI(
        title=application_settings.APP_NAME,
        version="0.1.0",
        lifespan=application_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(application_settings.CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )
    application.include_router(
        router,
        prefix=application_settings.API_PREFIX,
    )

    web_directory = Path("apps/web/dist").resolve()
    if web_directory.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=web_directory, html=True),
            name="web",
        )

    return application


app = create_application()
