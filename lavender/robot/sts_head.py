"""Phase 0 hardware: a pan/tilt head made from two Feetech STS3215 servos."""

from __future__ import annotations

import time

from .base import Robot
from .feetech import TICKS_PER_REV, FeetechBus, degrees_to_ticks


class StsHead(Robot):
    name = "sts-head"
    has_legs = False

    def __init__(
        self,
        bus: FeetechBus,
        pan_id: int = 1,
        tilt_id: int = 2,
        pan_offset: int = 0,
        tilt_offset: int = 0,
        invert_pan: bool = False,
        invert_tilt: bool = False,
        sleep=time.sleep,
    ) -> None:
        super().__init__(sleep=sleep)
        self.bus = bus
        self.pan_id, self.tilt_id = pan_id, tilt_id
        self.pan_offset, self.tilt_offset = pan_offset, tilt_offset
        self.invert_pan, self.invert_tilt = invert_pan, invert_tilt
        for sid in (pan_id, tilt_id):
            if not bus.ping(sid):
                raise IOError(f"servo {sid} did not answer a ping; check wiring, power and IDs")
            bus.set_torque(sid, True)
        self._move_head(0, 0, 0.8)

    def _move_head(self, yaw: float, pitch: float, duration_s: float) -> None:
        pan = degrees_to_ticks(yaw, self.pan_offset, self.invert_pan)
        tilt = degrees_to_ticks(pitch, self.tilt_offset, self.invert_tilt)
        d_pan = abs(yaw - self.yaw) * TICKS_PER_REV / 360
        d_tilt = abs(pitch - self.pitch) * TICKS_PER_REV / 360
        t = max(duration_s, 0.05)
        # speed in ticks/s so both joints arrive at about the same time; 0 would mean "max speed"
        self.bus.move_many({
            self.pan_id: (pan, max(50, int(d_pan / t))),
            self.tilt_id: (tilt, max(50, int(d_tilt / t))),
        })

    def close(self) -> None:
        for sid in (self.pan_id, self.tilt_id):
            try:
                self.bus.set_torque(sid, False)
            except IOError:
                pass
