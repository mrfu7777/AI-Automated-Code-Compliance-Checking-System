# Guided V1 Demonstration

The guided demo is the fastest way to show the complete evidence-backed review workflow without
using customer files or redistributing a licensed regulation. It creates synthetic PDFs, positioned
page images, a project, a published demonstration standard, four published rules, three verified
facts, and evidence records in the normal M1–M7 tables. The normal worker, rule engine, workbench,
missing-information endpoint, and report generator handle everything after setup.

The demo content is deliberately labelled synthetic. Its thresholds are training examples, not a
quotation or interpretation of GB 55037-2022 or any other enforceable regulation.

## Start

~~~shell
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
~~~

On Windows PowerShell, use `Copy-Item .env.example .env` for the first command. Docker Desktop must
be running. Wait until PostgreSQL, Redis, MinIO, API, worker, and web are healthy, then open
http://localhost:5173.

## Browser demonstration

1. Click **Load guided V1 demo**. Repeated clicks return the same scenario instead of duplicating it.
2. Confirm that `[DEMO] Existing Office Renovation` and `Synthetic V1 Fire Review Rules` are selected.
3. Click **Run compliance check** and wait for the persisted worker job to succeed.
4. Inspect the four findings in the three-column workbench.
5. Open the synthetic drawing and regulation page evidence.
6. Confirm the missing-information action requests `fire_compartment.area_m2`.
7. Download the PDF and Excel preliminary reports.

Expected deterministic results:

| Rule | Expected result | Reason |
| --- | --- | --- |
| `DEMO-EXIT-COUNT` | Non-compliant | One verified exit; demo threshold is two |
| `DEMO-EXIT-WIDTH` | Compliant | 1.20 m verified; demo threshold is 1.10 m |
| `DEMO-BUILDING-HEIGHT` | Compliant | 21 m verified; demo limit is 24 m |
| `DEMO-COMPARTMENT-AREA` | Insufficient information | No verified area fact exists |

## Command-line smoke check

With the stack running and `jq` available:

~~~shell
scripts/demo-smoke.sh
~~~

This calls the same API used by React, waits for the real Celery job, checks the exact four statuses,
and verifies that the PDF report is downloadable. CI runs this script against a fresh PostgreSQL,
Redis, MinIO, API, worker, and web stack on every main-branch change.

## Safety switch

The endpoint exists only when `APP_ENV=development` and `DEMO_MODE_ENABLED=true`. Production startup
fails if demo mode is enabled. The generated project is visibly prefixed `[DEMO]`, and every PDF/page
states that it is synthetic and not for construction.
