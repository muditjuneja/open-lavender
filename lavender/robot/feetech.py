"""Minimal driver for Feetech STS serial-bus servos (STS3215 and friends).

Protocol: half-duplex UART, default 1 Mbaud.
    packet = 0xFF 0xFF ID LEN INSTR PARAMS... CHECKSUM
    LEN = len(PARAMS) + 2
    CHECKSUM = ~(ID + LEN + INSTR + sum(PARAMS)) & 0xFF
STS-series registers are little-endian.

NOTE: packet encoding is unit-tested, but this driver has not yet been run against
real servos. Try it on a bench with the servos unloaded first.
"""

from __future__ import annotations

from typing import Iterable, Protocol

BROADCAST_ID = 0xFE

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03
INST_SYNC_WRITE = 0x83

REG_TORQUE_ENABLE = 40
REG_ACC = 41
REG_GOAL_POSITION = 42  # followed by GOAL_TIME (44) and GOAL_SPEED (46), 2 bytes each
REG_PRESENT_POSITION = 56

TICKS_PER_REV = 4096
CENTER_TICK = 2048


class SerialPort(Protocol):
    def write(self, data: bytes) -> int | None: ...
    def read(self, size: int) -> bytes: ...
    def reset_input_buffer(self) -> None: ...


def checksum(body: Iterable[int]) -> int:
    return (~sum(body)) & 0xFF


def make_packet(servo_id: int, instruction: int, params: bytes = b"") -> bytes:
    body = bytes([servo_id, len(params) + 2, instruction]) + params
    return b"\xff\xff" + body + bytes([checksum(body)])


def u16(value: int) -> bytes:
    value = int(value)
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"{value} does not fit in 16 bits")
    return bytes([value & 0xFF, value >> 8])


def goal_block(position: int, speed: int, acc: int = 0) -> bytes:
    """7-byte block written from REG_ACC: acc, position, time (unused, 0), speed."""
    return bytes([acc & 0xFF]) + u16(position) + u16(0) + u16(speed)


def sync_write_packet(start_reg: int, data: dict[int, bytes]) -> bytes:
    lengths = {len(d) for d in data.values()}
    if len(lengths) != 1:
        raise ValueError("sync write needs the same data length for every servo")
    (data_len,) = lengths
    params = bytes([start_reg, data_len])
    for servo_id, payload in data.items():
        params += bytes([servo_id]) + payload
    return make_packet(BROADCAST_ID, INST_SYNC_WRITE, params)


def degrees_to_ticks(deg: float, offset_ticks: int = 0, invert: bool = False) -> int:
    ticks = CENTER_TICK + offset_ticks + (-1 if invert else 1) * deg * TICKS_PER_REV / 360.0
    return int(round(max(0, min(TICKS_PER_REV - 1, ticks))))


def parse_status(packet: bytes) -> tuple[int, int, bytes]:
    """Parse a status packet -> (servo_id, error_byte, params). Raises on bad framing."""
    if len(packet) < 6 or packet[:2] != b"\xff\xff":
        raise IOError(f"bad status packet: {packet.hex()}")
    servo_id, length, error = packet[2], packet[3], packet[4]
    params = packet[5 : 5 + length - 2]
    if len(packet) < 4 + length or checksum(packet[2 : 4 + length - 1]) != packet[3 + length]:
        raise IOError(f"status checksum mismatch: {packet.hex()}")
    return servo_id, error, params


class FeetechBus:
    def __init__(self, port: SerialPort) -> None:
        self.port = port

    @classmethod
    def open(cls, device: str, baudrate: int = 1_000_000) -> "FeetechBus":
        import serial  # pyserial; install with `pip install open-lavender[hardware]`

        return cls(serial.Serial(device, baudrate=baudrate, timeout=0.05))

    def _transact(self, packet: bytes, reply_params: int | None) -> bytes:
        self.port.reset_input_buffer()
        self.port.write(packet)
        if reply_params is None:
            return b""
        reply = self.port.read(6 + reply_params)
        _, error, params = parse_status(reply)
        if error:
            raise IOError(f"servo reported error 0x{error:02x}")
        return params

    def ping(self, servo_id: int) -> bool:
        try:
            self._transact(make_packet(servo_id, INST_PING), reply_params=0)
            return True
        except IOError:
            return False

    def set_torque(self, servo_id: int, enabled: bool) -> None:
        self._transact(make_packet(servo_id, INST_WRITE, bytes([REG_TORQUE_ENABLE, int(enabled)])), 0)

    def read_position(self, servo_id: int) -> int:
        params = self._transact(make_packet(servo_id, INST_READ, bytes([REG_PRESENT_POSITION, 2])), 2)
        return params[0] | (params[1] << 8)

    def move_many(self, goals: dict[int, tuple[int, int]], acc: int = 0) -> None:
        """goals: servo_id -> (position_ticks, speed_ticks_per_s). Broadcast, so no reply."""
        data = {sid: goal_block(pos, speed, acc) for sid, (pos, speed) in goals.items()}
        self._transact(sync_write_packet(REG_ACC, data), reply_params=None)
