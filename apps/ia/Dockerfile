# Servicio Autónomo de IA PrediCitas CRP · Python 3.12 (Fase 5)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8100 \
    HOST=0.0.0.0 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    COVERAGE_FILE=/tmp/.coverage \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/.pytest_cache"

WORKDIR /app

# Dependencias del sistema: libgomp1 para OpenMP (LightGBM) y curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Usuario sin privilegios: el proceso de la IA no corre como root
RUN useradd --create-home --uid 1000 predicitas
COPY --chown=predicitas:predicitas . .
COPY --from=contracts / /contracts/
USER predicitas

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
