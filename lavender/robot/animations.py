"""Head keyframe animations.

Each animation is a list of keyframes. A keyframe moves the head to (yaw, pitch)
*relative to the current gaze* over `duration_s`, and optionally plays a sound
when the keyframe starts. Angles are in degrees: +yaw looks left, +pitch looks up.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Keyframe:
    yaw: float
    pitch: float
    duration_s: float
    sound: str | None = None


def _kf(yaw: float, pitch: float, duration_s: float, sound: str | None = None) -> Keyframe:
    return Keyframe(yaw, pitch, duration_s, sound)


ANIMATIONS: dict[str, list[Keyframe]] = {
    "quack": [_kf(0, 12, 0.08, sound="quack"), _kf(0, -4, 0.10), _kf(0, 8, 0.08), _kf(0, 0, 0.12)],
    "nod": [_kf(0, -15, 0.2), _kf(0, 5, 0.2), _kf(0, -10, 0.2), _kf(0, 0, 0.2)],
    "shake": [_kf(20, 0, 0.18), _kf(-20, 0, 0.25), _kf(15, 0, 0.22), _kf(0, 0, 0.18)],
    "happy_wiggle": [_kf(10, 8, 0.12), _kf(-10, 8, 0.15), _kf(10, 8, 0.15), _kf(-10, 8, 0.15), _kf(0, 0, 0.15)],
    "curious": [_kf(12, 6, 0.35), _kf(12, 6, 0.6), _kf(0, 0, 0.35)],
    "sleepy": [_kf(0, -25, 1.2), _kf(0, -25, 0.8), _kf(0, 0, 0.6)],
    "dance": [
        _kf(25, 10, 0.25, sound="music"), _kf(-25, -5, 0.25), _kf(25, -5, 0.25), _kf(-25, 10, 0.25),
        _kf(0, 15, 0.2), _kf(0, -10, 0.2), _kf(0, 0, 0.2),
    ],
}

EMOTES = tuple(ANIMATIONS)
