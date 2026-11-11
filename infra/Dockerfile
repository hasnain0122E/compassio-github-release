FROM ghcr.io/astral-sh/uv:0.13.0 AS uv
FROM python:3.12.15-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/compassio_ml/pyproject.toml packages/compassio_ml/pyproject.toml
RUN uv sync --locked --no-dev --no-install-workspace
COPY apps/api/src apps/api/src
COPY packages/compassio_ml/src packages/compassio_ml/src
RUN uv sync --locked --no-dev --no-editable && \
    useradd --uid 10001 --create-home compassio && \
    mkdir -p /app/data/db && chown compassio:compassio /app/data/db
COPY configs configs
COPY docs/research/model_v2/fast_benchmark_aggregates.json docs/research/model_v2/
COPY infra/start_api.py infra/healthcheck.py infra/provision_runtime.py infra/
COPY scripts/runtime_artifacts.py infra/runtime_artifacts.py
USER 10001:10001
ENV COMPASSIO_ENVIRONMENT=production COMPASSIO_SOURCE_DATA_ACCESS=public
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "infra/healthcheck.py"]
CMD ["python", "infra/start_api.py"]
