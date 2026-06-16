explain.md — Project Overview (Current State)This document explains what the project does today, how to run it, how to verify each piece, and what’s still missing compared to the full plan.What the project can do right now•Backend: Django REST API with Postgres◦Accepts PDF uploads per company via POST /docs/upload.◦Persists Company, Document, and placeholder Chunk/chat models.◦Lists documents with GET /docs?company_id=... and returns a document’s details with GET /docs/{id}.◦Chat guardrail endpoint POST /chat/ask that:▪Checks whether the company has any indexed content (chunks on ready documents).▪If no content is indexed, returns 400 with: Please upload a PDF before asking the chatbot any questions.▪Calls a Gemini-based policy classifier (using your GEMINI_API_KEY) and returns a placeholder answer (retrieval/answering not implemented yet).◦Separate quick-check endpoint POST /chat/policy-check to verify the Gemini API key/classifier without requiring indexed content.•Frontend: Vue app (Vite dev server)◦Simple dashboard with an upload form: choose a company_id and a PDF, then upload to the backend.◦Shows the backend endpoint in the UI and displays the upload result (document id + status).•Dev environment: Docker + Makefile◦make dev builds and runs Postgres, the Django backend, and the Vue frontend.◦Backend available at http://localhost:8000, frontend at http://localhost:4200.◦.env includes GEMINI_API_KEY and dev settings; it is injected into the backend.What it does NOT do yet (gaps vs. full plan)•Ingestion pipeline (PDF → text → chunks → embeddings → ready) is not implemented yet.◦No Celery/Redis workers.◦No PDF parsing (pypdf/pdfminer.six), text cleanup, or chunking.◦No embeddings model calls (Gemini Embeddings) and no pgvector column (embedding_vec) or vector index setup.◦Document.status remains uploaded; it is never progressed to processing/ready.◦Chunk rows are not created.•Retrieval for POST /chat/ask is not implemented (no vector + keyword hybrid search, no topK logic).•The Answerer LLM call isn’t implemented; POST /chat/ask returns a placeholder answer.•Observability (structured logging, redaction), rate limiting/quotas, and audit trails are not yet integrated.•Frontend does not include a chat interface yet; only file upload.Result: While uploads work, the chatbot cannot answer questions “based on the uploaded PDFs” yet because no chunks/embeddings exist for retrieval. The guardrail will always return 400 until ingestion/backfill creates chunks and marks documents ready.Can it do everything you stated in your guess?Your guess:•“takes a pdf file from frontend and sends it to the backend and saves it”◦Status: Yes. This works today via the Vue upload form and POST /docs/upload.•“After saving it the frontend should be able to ask question of the backend based on the pdf provided”◦Status: Not yet. The backend has the endpoints and the Gemini policy classifier, but ingestion, embeddings, and retrieval aren’t implemented, so there’s no indexed context. POST /chat/ask will return 400 with the guardrail message until chunks exist.You can, however, test POST /chat/policy-check to confirm the Gemini key works and see a structured policy classification for any question.How to run everythingFrom the project/ directory:make dev•Frontend: http://localhost:4200•Backend: http://localhost:8000•Postgres: exposed on 5432 (with a named volume pg_data)View logs (optional):docker compose -f docker/docker-compose.yml logs -f backendStop:make stopHow to test the current features1)Upload a PDF (from the frontend)•Open http://localhost:4200.•Enter a Company ID (e.g., 1), choose a .pdf, click Upload.•You should see a success message with document_id and status=uploaded.2)Upload a PDF (via curl)curl -F company_id=1 \
-F file=@/path/to/file.pdf \
http://localhost:8000/docs/uploadExpected:{"document_id": 1, "status": "uploaded"}3)List documentscurl "http://localhost:8000/docs?company_id=1"4)Document detailscurl "http://localhost:8000/docs/1"5)Quick AI policy check (verifies Gemini key and classifier)curl -X POST http://localhost:8000/chat/policy-check \
-H 'Content-Type: application/json' \
-d '{"company_id":1, "question":"Who is the president?"}'Expected: 200 OK with a classifier object: related, reason, sanitized_query, policy_tags.6)Chat ask (will guardrail 400 until ingestion exists)curl -X POST http://localhost:8000/chat/ask \
-H 'Content-Type: application/json' \
-d '{"company_id":1, "question":"What are our store holiday hours?"}'Expected: 400 with { "error": "Please upload a PDF before asking the chatbot any questions." } because there are no indexed Chunks yet.Current API surface•POST /docs/upload (multipart form-data)◦Body: company_id (int), file (PDF)◦Returns: { document_id, status }•GET /docs?company_id=...◦Returns: list of documents for that company•GET /docs/{id}◦Returns: document details•POST /chat/ask◦Body: { company_id: int, user_id?: string, question: string, session_id?: string }◦Guardrail: returns 400 if no indexed content; otherwise returns classifier + placeholder answer•POST /chat/policy-check◦Body: { company_id: int, question: string }◦Returns only the classifier (useful for verifying GEMINI_API_KEY)Data model (implemented now)•Company(id, name, created_at)•Document(company, filename, storage_path, page_count, status, error_message, created_at)•Chunk(company, document, page_from, page_to, text, embedding, version, created_at)•ChatSession(company, user_id, created_at)•ChatTurn(session, user_question, sanitized_query, related, policy_tags, reason, answer_json, topk_chunks, created_at)Note: Chunk.embedding is a BinaryField placeholder. The pgvector embedding_vec column and related indexes are not yet added.Configuration and secrets•.env (development only):◦DJANGO_SECRET_KEY, DEBUG, DB_*, GEMINI_API_KEY, VITE_API_BASE◦The backend reads GEMINI_API_KEY for the Gemini calls.Security note: Do not commit real production keys. The provided key should be rotated if it was ever shared publicly.What’s next to meet the full plan•Add Celery + Redis and implement ingest_document(document_id) task:◦Extract text per page from the stored PDF (pypdf or pdfminer.six).◦Normalize text and chunk into ~500–1000 token segments with overlap; record page_from/page_to.◦Get embeddings via Gemini Embeddings API; write vectors into a new core_chunk.embedding_vec vector(768) column.◦Create IVFFLAT index for embedding_vec and GIN trigram index for text.◦Mark Document.status = 'ready' when done.•Implement hybrid retrieval query (topK) and wire it into POST /chat/ask.•Implement Answerer LLM call and structured JSON response (answer, follow_up_question, citations) with grounding rules.•Add observability (structured logs with redaction), rate limiting, per-company quotas, and audit trails.•Build a simple chat UI in the frontend that calls POST /chat/ask and displays classifier/answer/citations.Summary•Yes, the system currently allows PDF upload from the frontend to the backend and saves it.•No, it does not yet answer questions based on the uploaded PDFs. The ingestion pipeline and retrieval must be implemented first. You can, however, verify the AI key and policy classifier via POST /chat/policy-check.If you want, I can outline the exact database migration for pgvector, add the Celery skeleton, and provide the retrieval SQL + embedding client next to move from “uploaded” to a working chat over your PDFs.
# Project Explain — End‑to‑End Overview (Backend + Frontend)

This document explains what the project does now, how it’s architected, how to run it, and how to verify it end‑to‑end. It consolidates the latest implementation details (ingestion, retrieval, classifier + answerer, Celery/Redis, pgvector) and the UI.

If you see any older/unstyled content above in this file, this section is the authoritative, up‑to‑date version.


## What’s implemented now

- PDF upload per company (tenant) via the Vue frontend or `POST /docs/upload`.
- Asynchronous ingestion pipeline (Celery + Redis):
  - Parse PDF pages (pypdf), normalize text, chunk with overlap.
  - Generate embeddings with Gemini Embeddings API.
  - Store chunks in Postgres and write vectors to `embedding_vec` (pgvector).
  - Create indexes (IVFFLAT for vector, trigram for text) and mark documents `ready`.
- Hybrid retrieval for questions (vector + trigram keyword fallback).
- Policy classification (Gemini 2.5 Flash): `related`, `reason`, `sanitized_query`, `policy_tags`.
- Answerer (Gemini 2.5 Flash): grounded answer JSON with optional follow‑up question and citations.
- Guardrail: If a company has no indexed content, `/chat/ask` returns 400 with the required message.
- Observability basics: structured console logging and DRF throttling.
- Minimal chat UI in the frontend to ask questions after upload.


## Architecture & Services

- Backend: Django 5 + DRF
- Database: Postgres 16 with pgvector extension (Docker image `ankane/pgvector:pg16`)
- Worker: Celery + Redis for ingestion
- LLM: Google Gemini 2.5 Flash for classification & answers; `text-embedding-004` for embeddings
- Frontend: Vue 3 (Vite dev server on port 4200)

Docker Compose services (see `project/docker/docker-compose.yml`):
- db: Postgres + pgvector (port 5432)
- redis: Redis 7 (port 6379)
- backend: Django API (port 8000)
- celery-worker: Ingestion worker
- frontend: Vue dev server (port 4200)

Media storage: Uploaded PDFs are stored under `backend/media/docs/<company_id>/` (shared volume for backend and worker).


## Run locally

From the `project/` directory:

- Start everything (db, redis, backend, worker, frontend):
  - `make dev` (detached)
  - or `make debug` (foreground logs)
- Open the apps
  - Frontend: http://localhost:4200
  - Backend: http://localhost:8000
- Stop: `make stop`
- (Optional) Recreate volumes and prune: `make teardown` (destructive in dev)


## Configuration (.env)

`project/.env` (sample values already provided for dev):
- DJANGO_SECRET_KEY=insecure-dev-secret
- DEBUG=1
- DB_NAME=django_db, DB_USER=django_user, DB_PASSWORD=django_password, DB_HOST=db, DB_PORT=5432
- REDIS_URL=redis://redis:6379/0
- GEMINI_API_KEY=... (your key)
- EMBEDDING_DIM=768
- TOPK=6
- VITE_API_BASE=http://localhost:8000
- Optional limit: COMPANY_DAILY_QUOTA=0 (disable) or a positive integer per‑company per‑day


## Data model (core)

- Company(id, name, created_at)
- Document(company, filename, storage_path, page_count, status: uploaded|processing|ready|error, error_message, created_at)
- Chunk(company, document, page_from, page_to, text, embedding (bytes placeholder), version, created_at)
  - Plus a pgvector column `embedding_vec vector(768)` initialized at runtime (see `core/dbinit.py`).
- ChatSession(company, user_id, created_at)
- ChatTurn(session, user_question, sanitized_query, related, policy_tags, reason, answer_json, topk_chunks, created_at)


## Ingestion pipeline (PDF → chunks → embeddings → ready)

Triggered automatically on successful upload.

1) Document saved with status `uploaded`.
2) Celery task (`core.tasks.ingest_document`) runs:
   - Reads PDF from `storage_path` (under `MEDIA_ROOT`).
   - Extracts text per page (pypdf) and normalizes whitespace.
   - Chunks text (target ~500–1000 tokens with overlap) while preserving page ranges.
   - Creates `Chunk` rows with text and metadata.
   - Batches texts to Gemini Embeddings → writes vectors into `core_chunk.embedding_vec`.
   - Creates/ensures indexes (IVFFLAT for vectors; trigram for text).
   - Sets `Document.status = 'ready'` once all chunks are embedded.

If Celery/Redis are not available in dev, the code attempts a synchronous fallback for ingestion.


## Retrieval & LLM calls (Ask → Classify → Answer)

Endpoint: `POST /chat/ask`

- Guardrail: if the company has no indexed `Chunk`s on `ready` docs, returns 400:
  - `{ "error": "Please upload a PDF before asking the chatbot any questions." }`
- Hybrid retrieval:
  - Vector candidates: top 20 by `embedding_vec <-> q_vec` (pgvector)
  - Keyword candidates: top by trigram similarity
  - Weighted/rank fusion → final top‑K (default 6). If vectors missing, keyword‑only fallback.
- Classifier (Gemini 2.5 Flash): returns `{ related, reason, sanitized_query, policy_tags }`.
- If `related=false`: returns classifier + no answer.
- If `related=true`: Answerer (Gemini 2.5 Flash) returns structured JSON:
  - `{ answer, follow_up_question, citations: [{title, snippet, locator}] }`
- Auditing: stores a `ChatTurn` with classifier fields, answer JSON, and top‑K (ids, scores, pages).
- Throttling & quota: DRF throttles + optional `COMPANY_DAILY_QUOTA` limit.


## API endpoints

- POST `/docs/upload` (multipart)
  - Body: `company_id` (int), `file` (PDF)
  - Returns: `{ document_id, status }` (status starts as `uploaded`)
  - Side effect: enqueues ingestion; final status becomes `ready` when done

- GET `/docs?company_id=...`
  - Returns: list of documents for a company

- GET `/docs/{id}`
  - Returns: document details (including status)

- POST `/chat/ask`
  - Body: `{ company_id: int, question: string, user_id?: string, session_id?: string }`
  - Returns on success (example structure):
    ```json
    {
      "classifier": {
        "related": true,
        "reason": "question is in-scope",
        "sanitized_query": "What are our store holiday hours?",
        "policy_tags": ["hours"]
      },
      "answer": {
        "answer": "Stores are closed on Christmas Day.",
        "follow_up_question": "Do you want hours for New Year’s Day?",
        "citations": [
          {"title":"Store Hours & Holidays","snippet":"Closed: Christmas Day.","locator":"Policies.pdf p.4"}
        ]
      },
      "debug": { "topk": [{"chunk_id": 123, "score": 0.88, "page_from": 4, "page_to": 4}] }
    }
    ```

- POST `/chat/policy-check`
  - Body: `{ company_id: int, question: string }`
  - Returns: `{ classifier: { related, reason, sanitized_query, policy_tags } }`
  - Useful for verifying the Gemini API key and classifier quickly.


## Frontend (Vue)

Open http://localhost:4200 and use the Dashboard:
- Upload form: choose a `company_id` and a PDF → calls `/docs/upload`.
- Chat form: ask a question → calls `/chat/ask` and shows the classifier, answer JSON, and top‑K debug info.

`VITE_API_BASE` is set to `http://localhost:8000` in Compose. CORS is open in Django for local dev.


## How to test (curl)

1) Upload a PDF:

```bash
curl -F company_id=1 \
     -F file=@/path/to/file.pdf \
     http://localhost:8000/docs/upload
```

Expected:
```json
{"document_id": 1, "status": "uploaded"}
```

2) List documents:

```bash
curl "http://localhost:8000/docs?company_id=1"
```

3) Document details:

```bash
curl "http://localhost:8000/docs/1"
```

4) Quick AI policy check (verifies Gemini key and classifier):

```bash
curl -X POST http://localhost:8000/chat/policy-check \
  -H 'Content-Type: application/json' \
  -d '{"company_id":1, "question":"Who is the president?"}'
```

5) Ask the chatbot (after ingestion marks docs ready):

```bash
curl -X POST http://localhost:8000/chat/ask \
  -H 'Content-Type: application/json' \
  -d '{"company_id":1, "question":"What are our store holiday hours?"}'
```

If ingestion isn’t complete or no content exists, you’ll get the guardrail 400 message.


## Troubleshooting

- Gemini errors → 502 from backend: verify `GEMINI_API_KEY` in `.env` and network egress.
- Guardrail 400 on `/chat/ask`:
  - Ensure ingestion finished and `Document.status` is `ready`.
  - Check logs of `celery-worker` for errors.
- DB/vector not ready:
  - Using the `ankane/pgvector:pg16` image; `core/dbinit.py` enables `vector` and `pg_trgm` extensions and creates indexes. Restart if first start failed early.
- Rate limits:
  - DRF throttling applies; adjust in `settings.py` if needed.
  - Optional `COMPANY_DAILY_QUOTA` may block additional asks.


## Security & notes

- `.env` contains development secrets only; do not commit real production keys.
- Consider adding auth (e.g., DRF SimpleJWT), audit logs, and stricter JSON enforcement in production.
- For production, prefer gunicorn/uvicorn and a cloud file store (e.g., S3) for PDFs.


— End of explain.md