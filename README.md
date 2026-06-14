# croco-sign-backend

Backend that translates **Polish Sign Language (PJM)** video into spoken-language text.
A client picks an AI model, uploads a video, and retrieves the translation. Translation
runs asynchronously: the request returns immediately with a job id, and the client either
polls or subscribes for the result.

## Tech stack

- Python 3.10, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management
- `pydantic` / `pydantic-settings` for DTOs and configuration

## Architecture

Hexagonal / ports-and-adapters. Dependencies point inward — `api → services → domain` —
and `infrastructure` implements the domain **ports**. The domain has no framework imports.

```
src/croco_sign/
  main.py                 # app factory (create_app) + composition root, CORS, exception handlers
  core/                   # config (pydantic-settings), logging
  domain/                 # models, ports (PJMTranslator, JobStore), exceptions — pure Python
  services/               # TranslationService — the use case
  infrastructure/
    translators/          # registry (name -> translator) + MockPJMTranslator
    storage/              # in-memory JobStore (with pub/sub) + temp video storage
  api/                    # schemas (DTOs), dependencies (DI), errors (domain->HTTP), routers/
tests/                    # flow, error-path, and SSE/CORS tests
```

Key patterns: **Registry + Strategy** for runtime model selection (the registry owns the
model name; translators only implement `translate(...)`), centralized domain-exception →
HTTP mapping, DI via FastAPI `Depends` + `app.state` singletons, and the app-factory
pattern for testability.

## Running

```bash
uv sync
uv run uvicorn croco_sign.main:app --reload   # or: python main.py
```

Interactive API docs: <http://localhost:8000/docs>

## Configuration

Settings load from the environment with the `CROCO_` prefix (or a `.env` file). See
`src/croco_sign/core/config.py`.

| Setting | Env var | Default |
| --- | --- | --- |
| Default target language | `CROCO_DEFAULT_TARGET_LANGUAGE` | `pl` |
| Max upload size (bytes) | `CROCO_MAX_UPLOAD_BYTES` | `104857600` (100 MiB) |
| Allowed video MIME types | `CROCO_ALLOWED_MIME_TYPES` | mp4, quicktime, webm, matroska |
| CORS allowed origins | `CROCO_CORS_ALLOW_ORIGINS` | `["*"]` (lock down in production) |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/models` | List available translation models |
| `POST` | `/models/{model_name}/translate` | Submit a video (multipart `video` + optional `target_language`); returns **202** with `job_id` and `status_url` |
| `GET` | `/jobs/{job_id}` | Poll job status / result |
| `GET` | `/jobs/{job_id}/events` | **SSE** stream of status changes until terminal |
| `GET` | `/health` | Liveness check |

Supported target languages: `pl`, `en`. Job lifecycle: `pending → running →
succeeded | failed`.

### Subscribing from a frontend (SSE)

```js
const es = new EventSource(`/jobs/${id}/events`);
es.onmessage = (e) => {
  const job = JSON.parse(e.data);   // { status, result, error, ... }
  if (["succeeded", "failed"].includes(job.status)) es.close();
};
```

The stream emits the current snapshot immediately, then one event per status change, and
closes on a terminal status. Polling `GET /jobs/{job_id}` is an equivalent fallback.

## Testing

```bash
uv run pytest
```

Covers the end-to-end async flow, error paths (404 / 413 / 415 / 422), and SSE + CORS.
