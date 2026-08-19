"""
DME coordinator demo — Eleanor Martinez's wheelchair case.
Run: python demo.py  (or: make run)
"""

import csv
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def _load_env() -> None:
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_suppliers() -> list[dict]:
    path = Path(__file__).parent / "suppliers.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    _load_env()

    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set. Get a free key at console.groq.com and add it to .env")
        sys.exit(1)

    from src.case import make_eleanor_case
    from src.coordinator import DMECoordinator

    case = make_eleanor_case()
    suppliers = _load_suppliers()
    DMECoordinator(case, suppliers).run()


if __name__ == "__main__":
    main()
