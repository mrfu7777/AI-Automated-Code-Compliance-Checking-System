# Contributing

## Branches

- Keep main deployable.
- Use short-lived feature branches named feature/short-description.
- Use fix/short-description for defect fixes.
- Rebase or merge the current main branch before final review.

## Commits

Use concise English Conventional Commit messages:

- feat: add a user-visible capability
- fix: correct a defect
- docs: change documentation only
- test: add or correct tests
- refactor: change structure without changing behavior
- chore: update tooling or maintenance files

## Definition of Done

A change is complete when:

- the API and data contracts are explicit;
- authorization and audit implications are considered;
- asynchronous work reports progress and failure;
- tests cover the intended behavior and important failure paths;
- previous milestone tests still pass;
- migrations upgrade from the previous released schema;
- public documentation is updated in English;
- private project files and credentials remain outside Git.

## Pull request checks

Run before opening a pull request:

~~~shell
make check
docker compose -f infra/docker-compose.yml config --quiet
~~~

Changes to architecture or stable contracts require an Architecture Decision Record.
