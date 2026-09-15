# Release Process

1. Confirm the worktree is clean and update the version, release notes, OpenAPI snapshot, known
   limitations, and migration head.
2. Run backend Ruff, Mypy, the complete coverage suite, Alembic head validation, frontend lint/tests,
   production build, Compose validation, and shell syntax checks.
3. Push the commit to `main` and wait for backend, frontend, and full-stack Compose jobs.
4. Confirm the guided demo produced its exact expected statuses and report on a fresh stack.
5. Confirm the PostgreSQL archive restored into the isolated CI database.
6. Create an annotated semantic-version tag pointing to the green commit and push it.
7. Wait for the tag workflow to publish immutable API and web images to GitHub Container Registry.
8. Record commit SHA, tag, migration head, image digest, rule-pack version, and rollback backup in the
   deployment change record.

The `latest` image is convenient for evaluation but must not be used as a production rollback point.
Deploy an immutable tag or digest. A database/schema rollback requires the matching database and
MinIO backup; never downgrade only the application when migrations are incompatible.
