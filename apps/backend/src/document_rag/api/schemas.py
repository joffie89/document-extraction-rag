"""Pydantic request and response contracts for the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Expose the current processing state of an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    media_type: str | None
    size_bytes: int
    status: str
    chunking_strategy: str | None
    created_at: datetime
    updated_at: datetime


class MarkdownPayload(BaseModel):
    """Carry extracted or user-edited Markdown content."""

    markdown: str


class RagPreparationRequest(BaseModel):
    """Select the advanced chunking strategy for a document."""

    strategy: Literal["semantic", "hierarchical"]


class RagPreparationResponse(BaseModel):
    """Report the completed vector-indexing result."""

    document_id: str
    strategy: Literal["semantic", "hierarchical"]
    chunk_count: int
    status: str


class QuestionRequest(BaseModel):
    """Carry a question submitted to the document RAG system."""

    question: str = Field(min_length=1, max_length=2000)


class RagAnswerResponse(BaseModel):
    """Return a grounded answer with its retrieved source metadata."""

    answer: str
    model: str
    sources: list[dict[str, object]]
