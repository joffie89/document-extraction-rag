# Document Extraction + RAG

A single-user MVP for uploading documents, extracting editable Markdown with
Docling, preparing the content with semantic or hierarchical chunking, and
testing grounded answers with OpenAI embeddings and ChromaDB.

The React production build and FastAPI backend are served from one local Docker
container. SQLite, uploads, Markdown, Docling models, and Chroma data persist in
a named Docker volume.

## Workflow

1. Upload a format registered by the installed Docling release.
2. Docling extracts Markdown in the background with English-only OCR.
3. Review and edit the Markdown in the browser.
4. Choose semantic or hierarchical chunking.
5. Index the chunks in ChromaDB with `text-embedding-3-small`.
6. Ask questions answered by `gpt-4.1-mini` with retrieved source references.

Semantic chunking embeds Markdown blocks and detects topic changes from cosine
distance. Hierarchical chunking builds document, section, subsection, and
paragraph nodes; retrieval expands paragraph hits to their nearest parent
context.

## Run with Docker

Requirements:

- Docker Desktop or Docker Engine with Compose v2
- An OpenAI API key in the root `.env` file

If `.env` does not exist, create it from `.env.example` and set:

```dotenv
OPENAI_API_KEY=your-server-owned-key
```

Build and start the lean image:

```bash
docker compose up --build
```

Open <http://localhost:8000>. The port is bound to localhost only.

Stop the application without deleting its data:

```bash
docker compose down
```

The first extraction can be slower while Docling downloads its required models
into the persistent volume.

### Optional full-format image

The default image keeps only the runtime required for common modern documents,
PDFs, images, spreadsheets, HTML, Markdown, and English RapidOCR. The optional
target adds Docling ASR/XBRL dependencies plus FFmpeg and LibreOffice for media
and legacy Office conversions.

PowerShell:

```powershell
$env:DOCKER_TARGET = "full-runtime"
docker compose up --build
```

Bash:

```bash
DOCKER_TARGET=full-runtime docker compose up --build
```

Some registered formats still require format-specific inputs, such as an EBCDIC
record layout, and invalid or encrypted source files are reported as extraction
failures.

## Local backend development with UV

Python 3.12 and UV are required.

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn document_rag.main:app --reload
```

The API is available at <http://localhost:8000/api/v1> and OpenAPI documentation
at <http://localhost:8000/docs>.

Run the quality checks:

```bash
uv run ruff check --no-cache .
uv run ruff format --check --no-cache .
uv run pytest -p no:cacheprovider -q
```

No automated test makes a live OpenAI request. OpenAI results are replaced with
fakes, while SQLite and ChromaDB use disposable local test directories.

## Local frontend development

Node.js 24 is required when running the UI outside Docker.

```bash
cd apps/web
npm install
npm run dev
```

Vite proxies `/api` requests to the FastAPI server on port 8000.

## API summary

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Process health |
| `GET` | `/api/v1/formats` | Installed Docling capabilities |
| `POST` | `/api/v1/documents` | Upload and schedule extraction |
| `GET` | `/api/v1/documents` | List document states |
| `GET` | `/api/v1/documents/{id}` | Read one document state |
| `GET` | `/api/v1/documents/{id}/markdown` | Read extracted Markdown |
| `PUT` | `/api/v1/documents/{id}/markdown` | Save edited Markdown |
| `POST` | `/api/v1/documents/{id}/rag` | Build the selected index |
| `POST` | `/api/v1/documents/{id}/ask` | Run a grounded question |

## Project structure

```text
.
├── .github/workflows/ci.yml
├── apps/
│   ├── backend/
│   │   ├── src/document_rag/
│   │   │   ├── core/{config.py,models.py}
│   │   │   ├── application/{document_operations.py,rag_operations.py}
│   │   │   ├── infrastructure/
│   │   │   │   ├── docling/{configuration.py,formats.py,parser.py}
│   │   │   │   ├── chunking/{semantic.py,hierarchical.py}
│   │   │   │   ├── database.py
│   │   │   │   ├── storage.py
│   │   │   │   ├── chroma_store.py
│   │   │   │   └── openai_client.py
│   │   │   ├── api/{routes.py,schemas.py}
│   │   │   └── main.py
│   │   ├── migrations/{env.py,versions/0001_initial.py}
│   │   └── tests/
│   └── web/
│       ├── src/components/
│       ├── src/{api.js,App.jsx,main.jsx,styles.css}
│       ├── index.html
│       ├── package.json
│       └── vite.config.js
├── alembic.ini
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

Empty Python package markers are omitted from the diagram.

## Configuration and security

All application runtime values live in the ignored `.env` file; there are no
configuration defaults embedded in Python. The committed `.env.example`
intentionally mirrors the required names as a secret-free setup template.
Dynaconf loads and validates those values before the application starts.

The OpenAI key is used only by FastAPI and is excluded from Git and the Docker
build context. It is never returned to React or written to application logs.

The container runs as a non-root user with dropped Linux capabilities, a
read-only root filesystem, and a writable temporary filesystem. Application
data is isolated in the `rag_data` volume.

This is intentionally a single-host, single-user MVP. FastAPI background tasks
are not a durable job queue, there is no authentication layer, and the Compose
deployment is not highly available. Those are deliberate limits rather than
hidden production guarantees.
