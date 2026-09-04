FROM python:3.12.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

USER app

FROM base AS production

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS development

USER root
RUN pip install --no-cache-dir ".[dev]"
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
RUN chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
