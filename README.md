# croco-sign-backend

HTTP API for the CrocoSign app. A client uploads a Polish Sign Language (PJM) video and picks a model; the API queues a job, the worker sends the video to the inference service ([pjm-models](https://github.com/crocosign/pjm-models)) to get English text, translates it into the requested language with DeepL (Polish or English) and returns the result. It also serves the corpus clip catalogue and the model results tables shown in the frontend.

This is a research prototype, not a replacement for an interpreter.

## Where this fits

All repositories are under [github.com/crocosign](https://github.com/crocosign), project site https://crocosign.github.io:

CrocoSign (data preparation) -> SpaMo-PJM / Uni-Sign-PJM (training) -> pjm-models (inference) -> **croco-sign-backend** / [croco-sign-frontend](https://github.com/crocosign/croco-sign-frontend) (app).

The frontend calls this API, by default on the same host as the frontend, port 8000. This API calls the pjm-models server at `CROCO_INFERENCE_ENDPOINT`. Corpus clips are streamed from the Hugging Face dataset [croco-corp/pjm-segments](https://huggingface.co/datasets/croco-corp/pjm-segments) (the unfiltered segments, about 40k, as WebDataset shards). The filtered set of 29,932 pairs, with features, splits, translations and videos, is in [croco-corp/pjm-data](https://huggingface.co/datasets/croco-corp/pjm-data).

## Requirements

- Python 3.10, [uv](https://docs.astral.sh/uv/)
- Redis 7 (job state, pub/sub, task queue, clip cache)
- ffmpeg (remuxes dataset clips to MP4 for browser playback; the Docker image installs it)
- A running pjm-models server (`serving/app.py` in that repository) reachable over HTTP
- A DeepL API key

## Configuration

Settings are read from environment variables with the prefix `CROCO_`, or from a `.env` file in the working directory (not committed; see `src/croco_sign/core/config.py`).

Required, no default (the app does not start without them):

- `CROCO_DEEPL_KEY`: DeepL API key
- `CROCO_INFERENCE_ENDPOINT`: full URL of the pjm-models `/translate` endpoint, for example `http://localhost:8000/translate`. Point it at a local container, a remote GPU host or a Tailscale address; restart the API and the worker after changing it.

Optional (defaults in brackets):

- `CROCO_REDIS_URL` [`redis://localhost:6379/0`]
- `CROCO_DEFAULT_TARGET_LANGUAGE` [`pl`]
- `CROCO_MAX_UPLOAD_BYTES` [100 MiB]
- `CROCO_ALLOWED_MIME_TYPES` [mp4, quicktime, webm, matroska]
- `CROCO_CORS_ALLOW_ORIGINS` [`["*"]`, JSON list; restrict it in production]
- `CROCO_SQLITE_DB_PATH` [`data/pjm.db`]
- `CROCO_RESOURCES_BASE_DIR` [`.`, base for architecture diagrams in `resources/`]
- `CROCO_HF_SEGMENTS_REPO_ID` [`croco-corp/pjm-segments`], `CROCO_HF_SEGMENTS_SPLIT` [`train`]
- `CROCO_JOB_TTL_SECONDS`, `CROCO_VIDEO_TTL_SECONDS`, `CROCO_SEGMENT_VIDEO_TTL_SECONDS`

## Run locally

With Docker (API, worker and Redis; put the two required variables in a `.env` next to `docker-compose.yml`). Warning: the Redis service in `docker-compose.yml` is published on host port 6379 and has no authentication, so do not run it on a machine reachable from untrusted networks without closing that port or adding a password:

```bash
docker compose up --build
```

Without Docker, in three terminals (the API and the worker are separate processes that share only Redis):

```bash
redis-server
uv sync
uv run uvicorn croco_sign.main:app --reload
uv run arq croco_sign.worker.WorkerSettings
```

Interactive API docs: http://localhost:8000/docs. For a quick check without a GPU, use the registered model `mock` (it needs no inference service). The worker always runs the DeepL stage, and we did not test the mock model without a DeepL key.

### Catalogue database

`/segments*`, `/metrics` and `/experiments*` read a read-only SQLite file (`data/pjm.db`, git-ignored) that you build once:

```bash
uv run python scripts/csv_to_sqlite.py <corpus metadata csv> data/pjm.db
uv run python scripts/hf_segments_to_sqlite.py data/pjm.db
uv run python scripts/metrics_to_sqlite.py <metrics markdown table> data/pjm.db
```

The corpus metadata CSV (signer and video metadata) is `dialogs_data.csv` in the [croco-corp/pjm-data](https://huggingface.co/datasets/croco-corp/pjm-data) dataset. The metrics markdown table that `metrics_to_sqlite.py` reads is not published, so `/metrics` cannot be rebuilt from public sources; we did not find a public copy. Neither input is in this repository. Model architecture figures are in `resources/`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness |
| GET | `/models` | registered models: `mock` and the 16 pjm-models checkpoints |
| POST | `/models/{model_name}/translate` | multipart `video`, optional `target_language` (`pl` or `en`); returns 202 with `job_id` |
| GET | `/jobs/{job_id}` | job status and result |
| GET | `/jobs/{job_id}/events` | server-sent events until the job finishes |
| GET | `/segments`, `/segments/filters`, `/segments/{id}`, `/segments/{id}/video` | corpus clips with signer metadata |
| GET | `/metrics`, `/experiments/{id}`, `/experiments/{id}/architecture` | results tables and architecture diagrams |

Job lifecycle: `pending -> running -> succeeded | failed`. Error responses: 404, 413, 415, 422 for unknown model or job, too large, wrong type, bad input.

## Tests

```bash
CROCO_DEEPL_KEY=placeholder CROCO_INFERENCE_ENDPOINT=http://localhost:9/translate uv run pytest
```

40 tests pass without Redis, GPU or network: they run in single-process mode with a mock translator. The two variables must still be set (any value) because the app module reads its settings on import.

## Notes

- The inference service is called synchronously from the worker with a 600 s timeout.
- Hexagonal layout: `domain` (ports and models) <- `services` <- `api`; adapters in `infrastructure`.
- Translation is two stages: sign video to English by the model, then English to the target language by DeepL. English output also goes through the DeepL stage.

## License

Our code is under the MIT licence (see `LICENSE`). The corpus clips served by this app come from the Open Repository of the PJM Corpus (University of Warsaw), which is non-commercial only.

## Authors

Wojciech Sieńko and Rostyslav Kovalenko, PJATK engineering thesis, supervised by dr Albert Śledzianowski, MBA.
