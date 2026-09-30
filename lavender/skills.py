"""The skills layer: the only interface between a brain and the body.

Skills are defined once in neutral JSON Schema and converted to each provider's
tool format. The brain never sends joint angles for the legs; it asks for
high-level actions and the body decides how to do them safely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .camera import NullCamera
from .memory import Memory
from .robot.animations import EMOTES
from .robot.base import Robot


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


SKILLS: list[Skill] = [
    Skill(
        "look",
        "Turn your head. yaw_deg: +left / -right (-90..90). pitch_deg: +up / -down (-30..40). "
        "0,0 is straight ahead. Use this to look at people or things you are talking about.",
        _obj({"yaw_deg": {"type": "number"}, "pitch_deg": {"type": "number"}}, ["yaw_deg", "pitch_deg"]),
    ),
    Skill(
        "emote",
        "Play an expressive head animation (quack plays your quack sound). Use these often and "
        "naturally, the way a person uses facial expressions.",
        _obj({"kind": {"type": "string", "enum": list(EMOTES)}}, ["kind"]),
    ),
    Skill(
        "walk",
        "Waddle. vx: forward speed in m/s (-0.15..0.25). yaw_rate: turning speed in rad/s, +left "
        "(-1..1). duration_s: 0..10. Fails politely if this body has no legs.",
        _obj(
            {"vx": {"type": "number"}, "yaw_rate": {"type": "number"}, "duration_s": {"type": "number"}},
            ["vx", "yaw_rate", "duration_s"],
        ),
    ),
    Skill(
        "set_posture",
        "Stand up or sit down.",
        _obj({"pose": {"type": "string", "enum": ["stand", "sit"]}}, ["pose"]),
    ),
    Skill(
        "take_photo",
        "Take a photo with the camera in your face and look at it. Use it whenever you need to "
        "see: who is there, what someone is showing you, what is around you.",
        _obj({}, []),
    ),
    Skill(
        "remember",
        "Save a fact to long-term memory, e.g. names, preferences, plans or important events. "
        "Write it as a short standalone sentence.",
        _obj({"fact": {"type": "string"}}, ["fact"]),
    ),
    Skill("get_status", "Read your body state: head pose, posture, whether you have legs.", _obj({}, [])),
]


@dataclass
class SkillResult:
    text: str
    image_jpeg: bytes | None = None
    is_error: bool = False


class SkillRunner:
    def __init__(self, robot: Robot, camera=None, memory: Memory | None = None) -> None:
        self.robot = robot
        self.camera = camera or NullCamera()
        self.memory = memory or Memory(None)
        self.skills = {s.name: s for s in SKILLS}

    def run(self, name: str, args: dict | str | None) -> SkillResult:
        try:
            if isinstance(args, str):
                args = json.loads(args or "{}")
            args = args or {}
            return self._dispatch(name, args)
        except Exception as exc:  # report every failure back to the model as a tool error
            return SkillResult(f"Error in {name}: {exc}", is_error=True)

    def _dispatch(self, name: str, a: dict) -> SkillResult:
        r = self.robot
        if name == "look":
            return SkillResult(r.look(a["yaw_deg"], a["pitch_deg"]))
        if name == "emote":
            return SkillResult(r.emote(a["kind"]))
        if name == "walk":
            return SkillResult(r.walk(a["vx"], a["yaw_rate"], a["duration_s"]))
        if name == "set_posture":
            return SkillResult(r.set_posture(a["pose"]))
        if name == "take_photo":
            jpeg = self.camera.snapshot()
            if jpeg is None:
                return SkillResult("No camera is connected, so you can't see anything right now.")
            return SkillResult("Here is what your camera sees.", image_jpeg=jpeg)
        if name == "remember":
            return SkillResult(self.memory.remember(a["fact"]))
        if name == "get_status":
            return SkillResult(json.dumps(r.status()))
        raise ValueError(f"unknown skill {name!r}")


def anthropic_tools() -> list[dict]:
    return [
        {"name": s.name, "description": s.description, "input_schema": s.parameters, "strict": True}
        for s in SKILLS
    ]


def openai_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": s.name, "description": s.description, "parameters": s.parameters}}
        for s in SKILLS
    ]
