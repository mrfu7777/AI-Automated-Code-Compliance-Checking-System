# AI Automated Code Compliance Checking System

An AI-assisted platform for preliminary building code compliance review, initially focused on fire safety requirements for existing-building renovation projects.

The system is designed to help architects review drawings and project documents against one or more building codes. It converts uploaded regulations into a versioned, traceable knowledge base, extracts verifiable facts from project files, executes deterministic compliance rules, and links every finding to both the relevant code clause and the supporting project evidence.

> This project is a professional decision-support tool. It does not replace licensed architects, statutory drawing review, fire inspection, or approval by the relevant authorities.

## The Problem

Fire safety review is difficult to automate because:

- regulations contain scope conditions, thresholds, exceptions, and cross-references;
- multiple national, local, client, and project-specific standards may apply at the same time;
- existing-building records are often incomplete and may include scanned PDFs, CAD exports, spreadsheets, reports, photographs, and BIM models;
- a plausible AI answer is not sufficient for a safety-related decision;
- every conclusion must remain reproducible and traceable after drawings or regulations change.

## Product Goal

The platform will allow an architect to:

1. Upload building codes and technical standards.
2. Convert searchable or scanned documents into structured clauses.
3. Review and publish versioned compliance rule packages.
4. Upload project drawings, reports, schedules, images, and IFC models.
5. Extract project facts with page-level or object-level evidence.
6. Run one or more rule packages against a frozen project snapshot.
7. Receive one of five explicit results for each rule:
   - Compliant
   - Non-compliant
   - Insufficient information
   - Manual review required
   - Not applicable
8. Navigate from a finding to the original regulation and the exact project evidence.
9. Correct extracted facts, assign findings, upload revisions, and perform incremental rechecks.
10. Export a traceable review report and issue list.

## Initial Scope

The first supported regulation is:

- GB 55037-2022, *General Code for Fire Protection of Buildings*

The MVP will focus on approximately 20 to 30 high-value checks, including:

- building use, height, floor count, and fire-resistance classification;
- fire separation distance;
- fire compartments and fire barriers;
- number and width of exits;
- evacuation doors, corridors, and stairs;
- evacuation travel distance;
- fire-service access and fire-fighting operation areas;
- fire elevators and refuge requirements;
- insulation and interior finish fire performance;
- basic triggering conditions for fire protection systems.

The MVP prioritizes reliable, evidence-backed conclusions over full code coverage.

## Core Design Principles

### Evidence before conclusions

Every result must identify:

- the regulation, edition, clause number, and original clause text;
- why the clause applies to the project;
- the project facts used by the rule;
- the source file, page, drawing region, BIM object, or manual input behind each fact;
- the rule package version and review timestamp.

### AI proposes; controlled logic decides

AI models may assist with OCR correction, document understanding, drawing recognition, semantic retrieval, structured-data extraction, and plain-language explanations.

Published compliance decisions are produced by a deterministic rule engine using reviewed rules and verified project facts. AI-generated clauses, facts, and rules remain candidates until they pass schema validation and the required human review.

### Missing information is a valid result

The system must never convert uncertainty into a compliant result. If a required fact is unavailable, contradictory, or unreliable, the result must be marked as insufficient information or manual review required.

### Regulations are versioned data

New and revised regulations follow a controlled lifecycle:

1. File upload and integrity check
2. Text extraction or OCR
3. Layout analysis and clause segmentation
4. Candidate structure and rule generation
5. Human verification
6. Automated rule testing
7. Immutable rule package publication
8. Inclusion in a project review package

Historical projects retain the exact regulation and rule versions used for their original review.

## Planned Architecture

~~~text
React Web Application
          |
       FastAPI
          |
  +-------+--------------------+
  |       |                    |
PostgreSQL + pgvector      MinIO / S3
  |
Redis + Celery
  |
  +-- PDF and OCR workers
  +-- Regulation parsing workers
  +-- Drawing and IFC parsing workers
  +-- Compliance rule engine
  +-- Report generation workers
          |
      Model Gateway
          |
Replaceable language and vision models
~~~

The initial implementation will use a modular monolith with asynchronous workers. This keeps the system practical for an individual developer while allowing expensive processing components to be scaled independently later.

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Zustand
- Ant Design
- PDF.js or react-pdf
- Konva.js or SVG overlays
- ECharts

### Backend

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Celery
- Redis
- PostgreSQL
- pgvector
- MinIO or an S3-compatible object store

### Document and Drawing Processing

- PyMuPDF and Poppler
- PaddleOCR
- Pillow and OpenCV
- python-docx
- openpyxl
- IfcOpenShell
- ezdxf
- Shapely
- NetworkX

### Operations

- Docker Compose for local development
- Pytest for automated testing
- OpenTelemetry for tracing
- Prometheus-compatible metrics
- Sentry-compatible error monitoring

## Planned Repository Structure

~~~text
.
├── apps
│   ├── web
│   ├── api
│   └── worker
├── packages
│   ├── rule_engine
│   ├── document_pipeline
│   ├── drawing_pipeline
│   └── schemas
├── standards
│   ├── source
│   ├── parsed
│   └── rule_packs
├── tests
│   ├── golden
│   ├── unit
│   └── integration
├── docs
└── infra
~~~

Private client files, licensed regulation documents, credentials, generated indexes, and model secrets will not be committed to the public repository.

## MVP Delivery Plan

### Phase 1: Foundation

- Project, user, file, and task models
- File upload and preview
- React application shell
- FastAPI service
- PostgreSQL, Redis, Celery, and MinIO integration

### Phase 2: Regulation Ingestion

- Searchable PDF extraction
- Scanned PDF rendering and OCR
- Clause hierarchy and page-coordinate mapping
- Human clause review interface

### Phase 3: Rule Engine

- Typed rule schema
- Restricted expression language
- Applicability, dependency, exception, and missing-data handling
- Versioned rule packages
- Unit and regression tests

### Phase 4: Project Understanding

- Technical report and schedule extraction
- Drawing title, scale, room, door, stair, exit, and dimension candidates
- IFC property and object extraction
- Fact verification and conflict resolution interface

### Phase 5: Review Workflow

- Multi-regulation review packages
- Evidence-linked findings
- Human overrides with audit trails
- Revision comparison and incremental rechecks
- PDF and spreadsheet reports

## Validation Strategy

The project will maintain a manually reviewed Golden Set containing:

- regulation pages and verified OCR text;
- clause hierarchy and source coordinates;
- project facts and their source evidence;
- expected applicability and compliance outcomes;
- compliant, non-compliant, boundary, missing-data, and ambiguous examples.

The most important safety metric is not overall accuracy. It is the number of known serious issues incorrectly classified as compliant.

## Current Status

- Product requirements and system architecture defined
- Initial fire code reviewed
- Public historical-building drawing and IFC samples collected for pipeline development
- MVP rule selection and validation workflow planned
- M0 architecture baseline completed
- React and TypeScript application shell completed
- FastAPI v1 API and Celery worker foundation completed
- PostgreSQL domain schema and initial Alembic migration completed
- Redis, MinIO, and Docker Compose development stack defined
- Backend and frontend quality gates running in GitHub Actions
- M1 project creation and tenant-scoped project access completed
- Streaming PDF upload with a configurable 150 MB limit completed
- Immutable file versions stored in MinIO with SHA-256 metadata in PostgreSQL
- Celery metadata jobs, persistent progress, visible failures, and manual retry completed
- Request-linked audit events and 15-minute presigned downloads completed
- React M1 workspace for projects, versions, and live job status completed
- M2 local text-layer extraction and Chinese OCR fallback completed
- Positioned page records, clause hierarchy, search, and source-page links completed
- Human correction, revision history, split/merge, review, and immutable publishing completed
- Generic job dispatch and lifecycle shared by M1 and M2 processors completed

## Quick Start

The supported development environment uses Docker.

~~~shell
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
~~~

Replace every placeholder password in .env before using the stack outside an isolated local development machine.

After startup:

- Web application: http://localhost:5173
- API documentation: http://localhost:8000/docs
- API health check: http://localhost:8000/api/v1/health
- MinIO console: http://localhost:9001

Run the complete local quality gate with:

~~~shell
make check
~~~

## M1 Walking Skeleton

The local development environment uses a deterministic architect identity so the vertical
workflow can be exercised before production authentication is introduced. The API still scopes
every project, file, and job query to that actor's organization. Do not treat this development
identity as production authentication.

The first vertical path is:

1. Create a project in the web application.
2. Select the project and upload a PDF of up to 150 MB.
3. The API streams and hashes the file, stores it in MinIO, and records an immutable file version.
4. A persistent job is published to Celery.
5. The worker verifies the stored object and records success or a retryable failure.
6. The browser polls the job API and displays the persisted status.

Uploading another PDF under the same logical document name creates the next version. It never
overwrites the previous object or database record.

M1 endpoints are documented interactively at http://localhost:8000/docs and include:

- POST /api/v1/projects
- GET /api/v1/projects
- GET /api/v1/projects/{project_id}
- GET /api/v1/projects/{project_id}/files
- POST /api/v1/projects/{project_id}/files
- GET /api/v1/projects/{project_id}/jobs
- GET /api/v1/jobs/{job_id}
- POST /api/v1/jobs/{job_id}/retry
- GET /api/v1/file-versions/{file_version_id}/download

## M2 Regulation Digitization

M2 extends the M1 path instead of creating a parallel upload or job system. Upload a PDF with
the `regulation_source` purpose, select its existing immutable `FileVersion`, and create a
`StandardVersion`. The same durable job API then routes a `regulation.parse` job to the M2
processor.

The processor uses PDFium for permissively licensed local PDF rendering and text extraction.
Pages without a reliable text layer fall back to local RapidOCR. It removes repeated page
margins, recognizes chapter, section, and numbered-article headings, and stores each candidate
with its source page, PDF coordinate box, confidence, and evidence record.

Architects can search and correct clauses, change hierarchy, split or merge candidates, and
publish only after all active clauses are reviewed. Every correction stores the previous value,
reviewer, timestamp, and reason. Published versions cannot be edited or reparsed; a new edition
must be created from a new immutable source version.

M2 adds these API groups:

- POST /api/v1/regulations/ingestions
- GET /api/v1/regulations
- GET /api/v1/regulations/versions/{version_id}/pages
- GET /api/v1/regulations/versions/{version_id}/clauses
- PATCH /api/v1/regulations/clauses/{clause_id}
- POST /api/v1/regulations/clauses/{clause_id}/split
- POST /api/v1/regulations/clauses/merge
- POST /api/v1/regulations/versions/{version_id}/publish
- POST /api/v1/regulations/versions/{version_id}/reparse

## Engineering Documentation

- [Development guide](docs/development.md)
- [Architecture baseline](docs/architecture/README.md)
- [Initial domain model](docs/architecture/domain-model.md)
- [OpenAPI baseline](docs/api/openapi.json)
- [M0 release record](docs/releases/m0.md)
- [M1 release record](docs/releases/m1.md)
- [M2 release record](docs/releases/m2.md)

## Data and Copyright Policy

Only data with an appropriate license or explicit project authorization will be used. Public architecture websites will not be scraped without permission. Customer drawings and licensed standards will remain private and will be excluded from the public repository.

## License

No open-source license has been selected yet. Until a license is added, all rights are reserved.

## Disclaimer

This software is intended for preliminary assistance and internal quality control only. Its outputs do not constitute statutory plan review, fire approval, professional certification, or a substitute for qualified expert judgment. Final decisions must be made by appropriately licensed professionals using complete project information and the legally applicable regulations.
