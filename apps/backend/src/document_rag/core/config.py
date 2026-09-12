"""Load and validate application settings with Dynaconf."""

from os import environ
from pathlib import Path

from dynaconf import Dynaconf, Validator
from dynaconf.base import LazySettings
from dynaconf.vendor.dotenv import dotenv_values


def load_settings(
    env_file: str | Path = ".env",
    require_openai: bool = False,
) -> LazySettings:
    """Load configuration and reject invalid runtime values."""

    application_settings = Dynaconf(
        envvar_prefix=False,
        environments=False,
        load_dotenv=False,
        settings_files=[],
    )
    environment_values = dotenv_values(str(Path(env_file).resolve()))
    for name, value in environment_values.items():
        if name not in environ and value is not None:
            application_settings.set(name, value, tomlfy=True)

    validators = [
        Validator(
            "ENVIRONMENT",
            is_in=("development", "test", "production"),
        ),
        Validator("APP_NAME", must_exist=True, len_min=1),
        Validator("API_PREFIX", must_exist=True, startswith="/"),
        Validator("CORS_ORIGINS", must_exist=True, is_type_of=list),
        Validator("DATABASE_URL", must_exist=True, len_min=1),
        Validator("UPLOAD_DIRECTORY", must_exist=True, len_min=1),
        Validator("MARKDOWN_DIRECTORY", must_exist=True, len_min=1),
        Validator("CHROMA_DIRECTORY", must_exist=True, len_min=1),
        Validator("CHROMA_COLLECTION", must_exist=True, len_min=1),
        Validator("EMBEDDING_MODEL", must_exist=True, len_min=1),
        Validator("GENERATION_MODEL", must_exist=True, len_min=1),
        Validator("OCR_LANGUAGE", eq="en"),
        Validator("MAX_UPLOAD_BYTES", gte=1),
        Validator("MAX_DOCUMENT_PAGES", gte=1),
        Validator("EXTRACTION_TIMEOUT_SECONDS", gte=1),
        Validator("OPENAI_TIMEOUT_SECONDS", gte=1),
        Validator("SEMANTIC_BREAK_PERCENTILE", gte=1, lte=99),
        Validator("MIN_CHUNK_TOKENS", gte=1),
        Validator("MAX_CHUNK_TOKENS", gte=1),
        Validator("RAG_TOP_K", gte=1),
        Validator("LOG_LEVEL", is_in=("DEBUG", "INFO", "WARNING", "ERROR")),
    ]

    if require_openai:
        validators.append(
            Validator("OPENAI_API_KEY", must_exist=True, len_min=1),
        )

    for validator in validators:
        validator.validate(application_settings)

    if application_settings.MIN_CHUNK_TOKENS >= application_settings.MAX_CHUNK_TOKENS:
        raise ValueError("MIN_CHUNK_TOKENS must be lower than MAX_CHUNK_TOKENS")

    return application_settings
