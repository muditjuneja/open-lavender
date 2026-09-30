import pytest

from lavender.robot import feetech as ft
from lavender.robot.sts_head import StsHead


def test_ping_packet_matches_feetech_docs():
    # Reference example from the Feetech protocol manual: ping servo 1.
    assert ft.make_packet(1, ft.INST_PING) == bytes.fromhex("ffff010201fb")


def test_write_torque_packet_checksum():
    pkt = ft.make_packet(1, ft.INST_WRITE, bytes([ft.REG_TORQUE_ENABLE, 1]))
    assert pkt[:6] == bytes([0xFF, 0xFF, 1, 4, 3, 40])
    assert pkt[-1] == (~(1 + 4 + 3 + 40 + 1)) & 0xFF


def test_goal_block_is_little_endian():
    assert ft.goal_block(2048, 500, acc=10) == bytes([10, 0x00, 0x08, 0, 0, 0xF4, 0x01])


def test_sync_write_layout():
    pkt = ft.sync_write_packet(ft.REG_ACC, {1: b"\x01\x02", 2: b"\x03\x04"})
    # FF FF FE LEN 83 start data_len [id d d] [id d d] chk; LEN = (L+1)*N + 4
    assert pkt[:5] == bytes([0xFF, 0xFF, 0xFE, (2 + 1) * 2 + 4, 0x83])
    assert pkt[5:-1] == bytes([ft.REG_ACC, 2, 1, 1, 2, 2, 3, 4])
    with pytest.raises(ValueError):
        ft.sync_write_packet(ft.REG_ACC, {1: b"\x01", 2: b"\x01\x02"})


def test_degrees_to_ticks():
    assert ft.degrees_to_ticks(0) == 2048
    assert ft.degrees_to_ticks(90) == 3072
    assert ft.degrees_to_ticks(90, invert=True) == 1024
    assert ft.degrees_to_ticks(9999) == 4095


def test_parse_status_roundtrip_and_bad_checksum():
    body = bytes([1, 4, 0, 0x00, 0x08])  # id, len, err, pos lo/hi
    pkt = b"\xff\xff" + body + bytes([ft.checksum(body)])
    assert ft.parse_status(pkt) == (1, 0, b"\x00\x08")
    with pytest.raises(IOError):
        ft.parse_status(pkt[:-1] + b"\x00")


class FakePort:
    """Answers every non-broadcast instruction with an OK status packet."""

    def __init__(self):
        self.written: list[bytes] = []
        self._reply = b""

    def reset_input_buffer(self):
        self._reply = b""

    def write(self, data):
        self.written.append(data)
        sid = data[2]
        if sid != ft.BROADCAST_ID:
            body = bytes([sid, 2, 0])
            self._reply = b"\xff\xff" + body + bytes([ft.checksum(body)])

    def read(self, size):
        out, self._reply = self._reply[:size], self._reply[size:]
        return out


def test_sts_head_moves_with_sync_write():
    port = FakePort()
    head = StsHead(ft.FeetechBus(port), sleep=lambda s: None)
    port.written.clear()
    head.look(30, -10)
    (pkt,) = port.written
    assert pkt[4] == ft.INST_SYNC_WRITE
    params = pkt[5:-1]
    pan_pos = params[2 + 2] | (params[2 + 3] << 8)  # [start, len, id, acc, posL, posH, ...]
    assert pan_pos == ft.degrees_to_ticks(30)
