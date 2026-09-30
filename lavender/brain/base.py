from __future__ import annotations

from typing import Callable, Protocol

from ..skills import SkillResult

# Called for each tool call the brain makes: (name, arguments, result).
ToolObserver = Callable[[str, dict, SkillResult], None]


class Brain(Protocol):
    def respond(self, user_text: str) -> str:
        """Handle one user utterance: run any skills it needs and return what to say."""
        ...
