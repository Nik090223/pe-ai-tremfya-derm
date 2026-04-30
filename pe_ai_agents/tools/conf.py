"""Conf adapter -- read/diff/draft-PR over ``conf/{brand}/...``.

In production this drives PRs against the PE.AI repo's ``conf/`` tree.
In the harness all writes are routed to a sandbox dir under
``runs/<run_id>/conf_drafts/`` so no live config is touched.

Drafting a PR against ``conf/base/*`` is HIGH risk -- the approval gate
catches that via the policy table.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConfDraft:
    """Sandbox-only draft of a config edit."""

    file_path: str
    original: str
    proposed: str

    def unified_diff(self) -> str:
        return "\n".join(
            difflib.unified_diff(
                self.original.splitlines(),
                self.proposed.splitlines(),
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
                lineterm="",
            )
        )


class FakeConf:
    """In-memory conf tree. Tests pre-populate ``files`` to simulate the repo."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self._files: dict[str, str] = dict(files or {})
        self._drafts: list[ConfDraft] = []

    def read(self, path: str) -> str:
        return self._files.get(path, "")

    def diff(self, path: str, proposed: str) -> str:
        return ConfDraft(
            file_path=path,
            original=self._files.get(path, ""),
            proposed=proposed,
        ).unified_diff()

    def draft_pr(self, *, path: str, proposed: str) -> ConfDraft:
        draft = ConfDraft(
            file_path=path,
            original=self._files.get(path, ""),
            proposed=proposed,
        )
        self._drafts.append(draft)
        return draft

    @property
    def drafts(self) -> list[ConfDraft]:
        return list(self._drafts)
