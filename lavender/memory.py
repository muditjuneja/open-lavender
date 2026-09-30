"""Long-term memory: a small JSON file of facts the robot chose to remember."""

from __future__ import annotations

import json
import time
from pathlib import Path


class Memory:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path).expanduser() if path else None
        self.facts: list[dict] = []
        if self.path and self.path.exists():
            self.facts = json.loads(self.path.read_text())

    def remember(self, fact: str) -> str:
        fact = fact.strip()
        if not fact:
            raise ValueError("fact is empty")
        if any(f["fact"] == fact for f in self.facts):
            return "I already knew that."
        self.facts.append({"fact": fact, "at": time.strftime("%Y-%m-%d")})
        self._save()
        return "Remembered."

    def render(self, limit: int = 50) -> str:
        if not self.facts:
            return "(nothing yet)"
        return "\n".join(f"- {f['fact']} (noted {f['at']})" for f in self.facts[-limit:])

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.facts, indent=2))
