"""FastAPI routes for extraction, editing, indexing, and RAG."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi import status as http_status

from document_rag.api.schemas import (
    DocumentResponse,
    MarkdownPayload,
    QuestionRequest,
    RagAnswerResponse,
    RagPreparationRequest,
    RagPreparationResponse,
)
from document_rag.application.document_operations import (
    create_document,
    load_document_markdown,
    process_document,
    update_document_markdown,
)
from document_rag.application.rag_operations import (
    answer_document_question,
    prepare_document_for_rag,
)
from document_rag.infrastructure.database import find_document, list_documents
from document_rag.infrastructure.docling.formats import (
    matching_formats,
    supported_formats,
)

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Confirm that the API process is accepting requests."""

    return {"status": "healthy"}


@router.get("/formats")
def list_supported_formats() -> dict[str, tuple[str, ...]]:
    """Expose the installed Docling format capability map."""

    return supported_formats()


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    """Store an upload and schedule its Docling extraction."""

    if not file.filename:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="An uploaded file name is required",
        )
    if not matching_formats(file.filename):
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded format is not supported by Docling",
        )

    application_settings = request.app.state.settings

    try:
        document = create_document(
            request.app.state.engine,
            file.filename,
            file.content_type,
            file.file,
            application_settings.UPLOAD_DIRECTORY,
            application_settings.MAX_UPLOAD_BYTES,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    background_tasks.add_task(
        process_document,
        request.app.state.engine,
        request.app.state.converter,
        document.id,
        application_settings.MARKDOWN_DIRECTORY,
        application_settings.MAX_UPLOAD_BYTES,
        application_settings.MAX_DOCUMENT_PAGES,
    )

    return DocumentResponse.model_validate(document)


@router.get("/documents", response_model=list[DocumentResponse])
def get_documents(request: Request) -> list[DocumentResponse]:
    """List all uploaded documents and their current states."""

    documents = list_documents(request.app.state.engine)

    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(request: Request, document_id: str) -> DocumentResponse:
    """Return the current state of one uploaded document."""

    document = find_document(request.app.state.engine, document_id)
    if document is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)


@router.get("/documents/{document_id}/markdown", response_model=MarkdownPayload)
def get_markdown(request: Request, document_id: str) -> MarkdownPayload:
    """Return the current editable Markdown for a document."""

    try:
        markdown = load_document_markdown(request.app.state.engine, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Markdown is not available for this document",
        ) from exc

    return MarkdownPayload(markdown=markdown)


@router.put("/documents/{document_id}/markdown", response_model=DocumentResponse)
def update_markdown(
    request: Request,
    document_id: str,
    payload: MarkdownPayload,
) -> DocumentResponse:
    """Persist a Markdown edit and mark the previous index as stale."""

    try:
        document = update_document_markdown(
            request.app.state.engine,
            document_id,
            payload.markdown,
            request.app.state.settings.MARKDOWN_DIRECTORY,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc

    return DocumentResponse.model_validate(document)


@router.post(
    "/documents/{document_id}/rag",
    response_model=RagPreparationResponse,
)
def prepare_rag(
    request: Request,
    document_id: str,
    payload: RagPreparationRequest,
) -> RagPreparationResponse:
    """Build a semantic or hierarchical Chroma index for a document."""

    try:
        chunks = prepare_document_for_rag(
            request.app.state.engine,
            request.app.state.collection,
            request.app.state.openai_client,
            document_id,
            payload.strategy,
            request.app.state.settings,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Document or Markdown not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RagPreparationResponse(
        document_id=document_id,
        strategy=payload.strategy,
        chunk_count=len(chunks),
        status="indexed",
    )


@router.post(
    "/documents/{document_id}/ask",
    response_model=RagAnswerResponse,
)
def ask_document(
    request: Request,
    document_id: str,
    payload: QuestionRequest,
) -> RagAnswerResponse:
    """Answer a question from the document's active Chroma index."""

    try:
        result = answer_document_question(
            request.app.state.collection,
            request.app.state.openai_client,
            document_id,
            payload.question,
            request.app.state.settings,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Prepare this document for RAG before asking questions",
        ) from exc

    return RagAnswerResponse.model_validate(result)
