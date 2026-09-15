"""Export the FastAPI contract as deterministic JSON documentation."""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    destination = repository / "docs" / "api" / "openapi.json"
    destination.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
