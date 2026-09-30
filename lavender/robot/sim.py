"""A simulated robot that prints what the body would do. No hardware needed."""

from __future__ import annotations

import time
from typing import Callable

from .base import Robot


class SimRobot(Robot):
    name = "sim"

    def __init__(
        self,
        has_legs: bool = True,
        realtime: bool = True,
        log: Callable[[str], None] | None = print,
    ) -> None:
        super().__init__(sleep=time.sleep if realtime else (lambda _s: None))
        self.has_legs = has_legs
        self._log = log or (lambda _msg: None)
        self.events: list[tuple] = []

    def _move_head(self, yaw: float, pitch: float, duration_s: float) -> None:
        self.events.append(("head", round(yaw, 1), round(pitch, 1), duration_s))

    def _play_sound(self, name: str) -> None:
        self.events.append(("sound", name))
        self._log("  🦆 QUACK!" if name == "quack" else f"  🔊 ({name})")

    def _walk(self, vx: float, yaw_rate: float, duration_s: float) -> None:
        self.events.append(("walk", vx, yaw_rate, duration_s))
        self._log(f"  🦆 waddles (vx={vx:.2f} m/s, turn={yaw_rate:.2f} rad/s) for {duration_s:.1f}s")
        self._sleep(min(duration_s, 1.0))

    def _set_posture(self, pose: str) -> None:
        self.events.append(("posture", pose))
        self._log(f"  🦆 {'stands up' if pose == 'stand' else 'sits down'}")

    def look(self, yaw: float, pitch: float, duration_s: float = 0.4) -> str:
        result = super().look(yaw, pitch, duration_s)
        self._log(f"  🦆 looks {_describe(self.yaw, self.pitch)}")
        return result

    def emote(self, kind: str) -> str:
        result = super().emote(kind)
        self._log(f"  🦆 *{kind.replace('_', ' ')}*")
        return result


def _describe(yaw: float, pitch: float) -> str:
    parts = []
    if yaw > 10:
        parts.append("left")
    elif yaw < -10:
        parts.append("right")
    if pitch > 10:
        parts.append("up")
    elif pitch < -10:
        parts.append("down")
    return " and ".join(parts) or "straight ahead"
