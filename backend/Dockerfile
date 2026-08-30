# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Prevent .pyc files and force stdout/stderr to be unbuffered (better container logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build psycopg2 / bcrypt wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY app ./app

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# /health is used by the HEALTHCHECK and by Kubernetes' liveness probe
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
