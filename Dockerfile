FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations before serving traffic, then start the API. Idempotent —
# `alembic upgrade head` is a no-op against an already-current schema. See
# docs/DEPLOYMENT_ARCHITECTURE.md and Procfile's `release:` line, which does
# the same thing on platforms that support a separate release phase.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
