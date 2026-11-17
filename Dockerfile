FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md LICENSE SPEC.md ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "google-auth>=2.35.0" \
    "google-cloud-bigquery>=3.26.0" \
    "google-cloud-bigquery-connection>=1.15.0" \
    "google-cloud-dataplex>=2.6.0" \
    "google-cloud-storage>=2.18.0" \
    "google-genai>=1.0.0" \
    "jsonschema>=4.23.0" \
    "pyyaml>=6.0.2" \
    "uvicorn>=0.32.0"

COPY schemas ./schemas
COPY engine ./engine
COPY packs ./packs
COPY server ./server
COPY web ./web

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
