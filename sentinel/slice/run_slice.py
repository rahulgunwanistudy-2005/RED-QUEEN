"""SOF-160 smoke script: `python -m sentinel.slice.run_slice`.

Prints the {bypass: ...} verdict JSON, persists a findings row, emits one OTel
trace, and (best-effort) pushes the score event to a running server so the
frontend dial updates.
"""
from __future__ import annotations

import json
import sys

from sentinel.config import SERVER_URL
from sentinel.db import run_migrations
from sentinel.slice.core import run_thin_slice


def main() -> int:
    run_migrations()  # idempotent — ensures the findings table exists
    verdict, score_event = run_thin_slice()

    print(json.dumps(verdict.model_dump(), indent=2))

    try:
        import httpx

        httpx.post(f"{SERVER_URL}/events", json=score_event, timeout=2.0)
        print(f"\n[stream] score event pushed to {SERVER_URL}/events", file=sys.stderr)
    except Exception as exc:  # server not running is fine for the CLI smoke check
        print(f"\n[stream] server not reachable ({exc}); skipped live push", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
