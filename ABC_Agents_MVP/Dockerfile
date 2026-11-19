# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -r /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi \
    && npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ABC_DB=/app/data/reviews.sqlite3
WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -r /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi \
    && pip install --no-cache-dir -r requirements-web.txt \
    && useradd --uid 10001 --create-home review \
    && mkdir -m 0700 /app/data && chown review:review /app/data
COPY policy.py ./
COPY web/ ./web/
COPY --from=frontend /build/dist ./frontend/dist
USER review
EXPOSE 8000
CMD ["uvicorn", "web.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
