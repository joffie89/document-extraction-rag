"""SQLite setup and document persistence functions."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from document_rag.core.models import DatabaseBase, DocumentRecord


def build_database(database_url: str) -> Engine:
    """Create the database engine and ensure its schema is available."""

    url = make_url(database_url)
    connect_args: dict[str, bool] = {}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().resolve().parent.mkdir(
                parents=True,
                exist_ok=True,
            )

    engine = create_engine(database_url, connect_args=connect_args)
    DatabaseBase.metadata.create_all(engine)

    return engine


def save_document(engine: Engine, document: DocumentRecord) -> DocumentRecord:
    """Insert or update a document in one committed transaction."""

    with Session(engine, expire_on_commit=False) as session:
        saved_document = session.merge(document)
        session.commit()
        session.refresh(saved_document)
        session.expunge(saved_document)

    return saved_document


def find_document(engine: Engine, document_id: str) -> DocumentRecord | None:
    """Return a document by identifier when it exists."""

    with Session(engine) as session:
        document = session.get(DocumentRecord, document_id)
        if document is not None:
            session.expunge(document)

    return document


def list_documents(engine: Engine) -> list[DocumentRecord]:
    """Return documents with the newest upload first."""

    statement = select(DocumentRecord).order_by(DocumentRecord.created_at.desc())

    with Session(engine) as session:
        documents = list(session.scalars(statement))
        session.expunge_all()

    return documents
