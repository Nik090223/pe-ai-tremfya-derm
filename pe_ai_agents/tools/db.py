"""DB adapter -- wraps ``pipelines/wrapper_utils/database_utility.py``.

In production: Redshift / Snowflake / RDS via the existing utility.
In the harness: ``FakeDB`` returns canned rows for known query patterns
so the Quick Analyst agent has something to render.
"""

from __future__ import annotations

from typing import Any


class FakeDB:
    """Canned-row DB substitute. Tests register expected queries up-front."""

    def __init__(self) -> None:
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def register(self, query_signature: str, rows: list[dict[str, Any]]) -> None:
        self._fixtures[query_signature] = list(rows)

    def query(self, *, sql: str) -> list[dict[str, Any]]:
        # Match by exact string for the harness; production uses parameterised
        # queries via the database_utility.
        key = " ".join(sql.split())
        return list(self._fixtures.get(key, []))
