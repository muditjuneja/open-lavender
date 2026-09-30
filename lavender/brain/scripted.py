"""An offline, rule-based brain. Needs no API key or model.

Useful for testing a body and for demos without a network. It uses the same skills
layer as the LLM brains, so anything that works here works for them too.
"""

from __future__ import annotations

import re

from ..skills import SkillRunner
from .base import ToolObserver

# (pattern, [(skill, args), ...], reply). The first matching rule wins.
RULES: list[tuple[str, list[tuple[str, dict]], str]] = [
    (r"\bquack\b", [("emote", {"kind": "quack"})], "There you go!"),
    (r"\b(dance|party)\b", [("emote", {"kind": "dance"})], "I've got moves."),
    (r"\blook (to the |at the )?left\b", [("look", {"yaw_deg": 45, "pitch_deg": 0})], "Looking left."),
    (r"\blook (to the |at the )?right\b", [("look", {"yaw_deg": -45, "pitch_deg": 0})], "Looking right."),
    (r"\blook up\b", [("look", {"yaw_deg": 0, "pitch_deg": 30})], "Ooh, what's up there?"),
    (r"\blook down\b", [("look", {"yaw_deg": 0, "pitch_deg": -25})], "Looking down."),
    (r"\b(look at me|look here|look forward)\b", [("look", {"yaw_deg": 0, "pitch_deg": 5})], "Hi!"),
    (r"\b(what do you see|take a (photo|picture)|look around)\b", [("take_photo", {})], "{take_photo}"),
    (r"\b(walk|come here|go forward)\b", [("walk", {"vx": 0.15, "yaw_rate": 0, "duration_s": 2})], "{walk}"),
    (r"\bsit\b", [("set_posture", {"pose": "sit"})], "{set_posture}"),
    (r"\bstand\b", [("set_posture", {"pose": "stand"})], "{set_posture}"),
    (r"\b(yes|agree|right\?)\b", [("emote", {"kind": "nod"})], "Yes!"),
    (r"\b(no|disagree)\b", [("emote", {"kind": "shake"})], "Nope."),
    (r"\b(tired|sleep|good night)\b", [("emote", {"kind": "sleepy"})], "Sleepy duck mode."),
    (r"\bmy name is (\w+)", [("remember", {"fact": "The user's name is {0}."}), ("emote", {"kind": "happy_wiggle"})],
     "Nice to meet you, {0}!"),
    (r"\b(hi|hello|hey)\b", [("emote", {"kind": "happy_wiggle"})], "Hi! I'm {name}."),
]


class ScriptedBrain:
    def __init__(self, skills: SkillRunner, name: str = "Lavender", on_tool: ToolObserver | None = None) -> None:
        self.skills = skills
        self.name = name
        self.on_tool = on_tool

    def respond(self, user_text: str) -> str:
        text = user_text.lower()
        for pattern, calls, reply in RULES:
            m = re.search(pattern, text)
            if not m:
                continue
            groups = [g.capitalize() for g in m.groups() if g]
            results = {}
            for skill, args in calls:
                args = {k: v.format(*groups) if isinstance(v, str) else v for k, v in args.items()}
                results[skill] = self._call(skill, args)
            return reply.format(*groups, name=self.name, **results)
        self._call("emote", {"kind": "curious"})
        return "Hmm? I'm a simple scripted duck. Try: quack, dance, look left, what do you see, my name is ..."

    def _call(self, skill: str, args: dict) -> str:
        result = self.skills.run(skill, args)
        if self.on_tool:
            self.on_tool(skill, args, result)
        return result.text
