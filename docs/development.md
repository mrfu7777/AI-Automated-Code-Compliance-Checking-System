# Development Guide

## Prerequisites

- Docker Desktop with Docker Compose
- Git
- Optional local tools: Python 3.12 and Node.js 22

## Start the stack

1. Copy the example configuration:

   ~~~shell
   cp .env.example .env
   ~~~

2. Replace all placeholder passwords in .env.

3. Start the services:

   ~~~shell
   docker compose -f infra/docker-compose.yml up --build
   ~~~

4. Open:

   - Web application: http://localhost:5173
   - API documentation: http://localhost:8000/docs
   - MinIO console: http://localhost:9001

The M1 upload limit defaults to 150 MB. Change MAX_UPLOAD_SIZE_BYTES only through local or
deployment configuration. MINIO_ENDPOINT is the container-to-container endpoint, while
MINIO_PUBLIC_ENDPOINT is used to generate browser-accessible download links.

The development stack creates a deterministic local organization and architect on first use.
Supplying X-User-ID selects an existing active user and is useful for isolation testing, but it
is not a production authentication mechanism.

## Quality checks

~~~shell
make check
~~~

The equivalent backend commands run from apps/api:

~~~shell
pip install -e ".[dev]"
ruff check .
mypy app
pytest
~~~

The equivalent frontend commands run from apps/web:

~~~shell
npm ci
npm run lint
npm run test
npm run build
~~~

## Database migrations

Create schema revisions only through Alembic:

~~~shell
cd apps/api
alembic upgrade head
alembic revision --autogenerate -m "describe the change"
~~~

Never reset a shared database to handle schema changes. Test every migration from the previously released schema.

The M1 migration is additive: it links jobs to file versions, adds request tracing and retry
limits, and makes a logical file name unique within a project.

## Repository safety

Do not commit:

- customer drawings or reports;
- licensed regulation source files;
- generated OCR data or vector indexes;
- credentials, access tokens, or local environment files;
- database and object-storage volumes.
