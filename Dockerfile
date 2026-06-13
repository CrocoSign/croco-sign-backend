# syntax=docker/dockerfile:1

# Pinned to the project's Python (see .python-version) on a uv-enabled base.
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

# - Don't buffer stdout/stderr so logs show up immediately under compose.
# - Compile bytecode and copy (not link) packages into the image for faster startup.
# - Keep the HF model cache outside the project dir so it can live on a volume.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    HF_HOME=/cache/huggingface

WORKDIR /app

# Install dependencies first, in their own layer, so editing app code doesn't
# bust the (slow) dependency-resolution/download cache.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project and install it.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Put the venv on PATH so `uvicorn`/`python` resolve to the project environment.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Run the production server (no --reload; that's only for local dev via main.py).
CMD ["uvicorn", "croco_sign.main:app", "--host", "0.0.0.0", "--port", "8000"]
