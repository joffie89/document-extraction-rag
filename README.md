# Document Extraction + RAG

A single-user MVP for uploading documents, extracting editable Markdown with
Docling, preparing the content with semantic or hierarchical chunking, and
testing grounded answers with OpenAI embeddings and ChromaDB.

The React production build and FastAPI backend are served from one local Docker
container. SQLite, uploads, Markdown, Docling models, and Chroma data persist in
a named Docker volume.

## Evaluation

The evaluation corpus contains four GOV.UK documents released under the Open
Government Licence v3.0 except where otherwise stated; third-party material
retains its own terms. The development set contains 40 questions and the
held-out set contains 20 questions. Answers are assessed by an LLM judge;
before that judge runs, a deterministic rule marks a refusal as incorrect when
the question is answerable from the corpus.

The development results below are from
[`evaluation/report_v2.md`](evaluation/report_v2.md). All configurations use
hierarchical chunking and the v1.2 judge.

| Metric | Embedding k=5 (baseline) | Hybrid k=5 | Hybrid k=10 | Hybrid k=10 + document hint + grounded prompt |
| --- | ---: | ---: | ---: | ---: |
| Questions | 40 | 40 | 40 | 40 |
| Correct / partial / incorrect | 29/3/8 | 29/2/9 | 30/2/8 | 31/2/7 |
| Correct rate | 72.5% | 72.5% | 75.0% | 77.5% |
| Retrieval hit rate | 67.6% | 67.6% | 70.6% | 70.6% |
| Mean first-hit rank | 2.04 | 1.91 | 2.21 | 2.04 |
| Answerable refusals | 7 | 7 | 6 | 7 |
| Answerable refusal rate | 20.6% | 20.6% | 17.6% | 20.6% |
| Not-in-documents correct | 6 | 6 | 5 | 6 |
| Not-in-documents correct rate | 100.0% | 100.0% | 83.3% | 100.0% |
| Citations: all correct | 44.1% | 52.9% | 44.1% | 50.0% |
| Citations: at least one correct | 64.7% | 70.6% | 64.7% | 67.6% |
| Mean latency / question (s) | 2.81 | 2.88 | 3.22 | 2.88 |
| Total question latency (s) | 112.50 | 115.39 | 128.79 | 115.13 |
| Question input tokens | 100460 | 103658 | 173469 | 169245 |
| Question output tokens | 6284 | 6398 | 7085 | 5575 |
| Question cost (USD) | $0.049970 | $0.051431 | $0.080455 | $0.076349 |
| Not-in-documents C/P/I | 6/0/0 | 6/0/0 | 5/0/1 | 6/0/0 |

The held-out results below are from
[`evaluation/report_heldout.md`](evaluation/report_heldout.md). Both
configurations use hierarchical chunking and the v1.2 judge.

| Metric | Embedding k=5 (baseline) | Hybrid k=10 + document hint + grounded prompt |
| --- | ---: | ---: |
| Questions | 20 | 20 |
| Correct / partial / incorrect | 13/1/6 | 12/2/6 |
| Correct rate | 65.0% | 60.0% |
| Retrieval hit rate | 50.0% | 50.0% |
| Mean first-hit rank | 1.62 | 1.25 |
| Answerable refusals | 5 | 5 |
| Answerable refusal rate | 31.2% | 31.2% |
| Not-in-documents correct | 4 | 4 |
| Not-in-documents correct rate | 100.0% | 100.0% |
| Citations: all correct | 43.8% | 50.0% |
| Citations: at least one correct | 50.0% | 50.0% |
| Mean latency / question (s) | 3.02 | 3.03 |
| Total question latency (s) | 60.45 | 60.67 |
| Question input tokens | 50792 | 83954 |
| Question output tokens | 2455 | 2086 |
| Question cost (USD) | $0.024059 | $0.036734 |
| Not-in-documents C/P/I | 4/0/0 | 4/0/0 |

The retrieval changes raised development-set correctness from 72.5% to 77.5%,
but they did not improve the held-out result: correctness was 65.0% for the
embedding baseline and 60.0% for the hybrid, document-hint, grounded-prompt
configuration. Differences of one or two questions are within run-to-run noise.
The main observed failure modes were retrieval misses leading to safe refusals;
a table split across pages leading to a derived figure instead of a directly
supported answer for q003; and confusion between documents.

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
Tests also force the local token-count fallback and reject external network
connections. Normal runtime continues to prefer tiktoken's `cl100k_base`, then
falls back locally if its encoding data is unavailable. Set
`DOCUMENT_RAG_OFFLINE=1` to skip the initial encoding download attempt entirely.

## Batch corpus ingestion

`ingest_corpus.py` is domain-neutral: it recursively discovers PDFs, uploads
each changed file once, and prepares both semantic and hierarchical indexes.
The API server must already be running because extraction and embedding use the
normal application pipeline.

```bash
uv run python ingest_corpus.py
```

The default input is `data/corpus/`. Use `--corpus-dir <path>` for any other
PDF collection. The script writes `ingestion_manifest.json` inside the selected
corpus directory, recording each document ID and both stored strategies. Pass a
strategy when querying either index:

```json
{"question": "What does the document say?", "strategy": "semantic"}
```

If `strategy` is omitted, the most recently prepared strategy remains the
default, matching the interactive application behaviour. Successful entries are
resumed by relative path and SHA-256 fingerprint; use `--force` to re-upload
them. A failed file is recorded without stopping later PDFs. The supplied UK
fraud and AML corpus is documented in `data/corpus/SOURCES.md`; its development
and held-out evaluation questions are in `evaluation/questions_v1.json` and
`evaluation/questions_heldout_v1.json`.

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
| `POST` | `/api/v1/documents/{id}/ask` | Query a selected or active RAG strategy |

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
