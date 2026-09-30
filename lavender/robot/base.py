"""Robot interface shared by the simulator and real hardware.

Drivers implement a small set of primitives (`_move_head`, `_play_sound`, and
optionally `_walk` / `_set_posture`). Everything the brain can ask for (looking,
emotes, status) is built on top of those primitives here, so every body gets the
same behaviour for free.
"""

from __future__ import annotations

import time
from typing import Callable

from .animations import ANIMATIONS, EMOTES


class Robot:
    name = "robot"
    has_legs = False
    yaw_limits = (-90.0, 90.0)
    pitch_limits = (-30.0, 40.0)

    def __init__(self, sleep: Callable[[float], None] = time.sleep) -> None:
        self._sleep = sleep
        self.yaw = 0.0
        self.pitch = 0.0
        self.posture = "stand"

    # --- primitives implemented by drivers -------------------------------------------
    def _move_head(self, yaw: float, pitch: float, duration_s: float) -> None:
        raise NotImplementedError

    def _play_sound(self, name: str) -> None:
        """Default: no speaker. Drivers with audio override this."""

    def _walk(self, vx: float, yaw_rate: float, duration_s: float) -> None:
        raise NotImplementedError

    def _set_posture(self, pose: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Release hardware resources."""

    # --- behaviour exposed to the skills layer -----------------------------------------
    def look(self, yaw: float, pitch: float, duration_s: float = 0.4) -> str:
        yaw = _clamp(yaw, *self.yaw_limits)
        pitch = _clamp(pitch, *self.pitch_limits)
        self._move_head(yaw, pitch, duration_s)
        self._sleep(duration_s)
        self.yaw, self.pitch = yaw, pitch
        return f"Looking at yaw={yaw:.0f}°, pitch={pitch:.0f}°."

    def emote(self, kind: str) -> str:
        if kind not in ANIMATIONS:
            raise ValueError(f"Unknown emote {kind!r}. Available: {', '.join(EMOTES)}")
        base_yaw, base_pitch = self.yaw, self.pitch
        for kf in ANIMATIONS[kind]:
            if kf.sound:
                self._play_sound(kf.sound)
            yaw = _clamp(base_yaw + kf.yaw, *self.yaw_limits)
            pitch = _clamp(base_pitch + kf.pitch, *self.pitch_limits)
            self._move_head(yaw, pitch, kf.duration_s)
            self._sleep(kf.duration_s)
        self.yaw, self.pitch = base_yaw, base_pitch
        return f"Did the {kind} emote."

    def walk(self, vx: float, yaw_rate: float, duration_s: float) -> str:
        if not self.has_legs:
            return "This body has no legs yet (head-only build), so it can't walk."
        vx = _clamp(vx, -0.15, 0.25)
        yaw_rate = _clamp(yaw_rate, -1.0, 1.0)
        duration_s = _clamp(duration_s, 0.0, 10.0)
        self._walk(vx, yaw_rate, duration_s)
        return f"Walked at {vx:.2f} m/s, turning {yaw_rate:.2f} rad/s, for {duration_s:.1f}s."

    def set_posture(self, pose: str) -> str:
        if not self.has_legs:
            return "This body has no legs yet (head-only build), so it can't change posture."
        if pose not in ("stand", "sit"):
            raise ValueError("pose must be 'stand' or 'sit'")
        self._set_posture(pose)
        self.posture = pose
        return f"Now {'standing' if pose == 'stand' else 'sitting'}."

    def status(self) -> dict:
        return {
            "body": self.name,
            "has_legs": self.has_legs,
            "head": {"yaw_deg": round(self.yaw, 1), "pitch_deg": round(self.pitch, 1)},
            "posture": self.posture if self.has_legs else None,
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))
