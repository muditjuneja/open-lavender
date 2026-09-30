import json

from lavender.brain.scripted import ScriptedBrain
from lavender.memory import Memory
from lavender.robot.sim import SimRobot
from lavender.skills import SKILLS, SkillRunner, anthropic_tools, openai_tools


class FakeCamera:
    def snapshot(self):
        return b"\xff\xd8fake-jpeg"


def make(tmp_path=None, legs=True, camera=None):
    robot = SimRobot(has_legs=legs, realtime=False, log=None)
    memory = Memory(tmp_path / "mem.json" if tmp_path else None)
    return robot, SkillRunner(robot, camera=camera, memory=memory)


def test_look_is_clamped():
    robot, skills = make()
    res = skills.run("look", {"yaw_deg": 500, "pitch_deg": -500})
    assert not res.is_error
    assert (robot.yaw, robot.pitch) == (90.0, -30.0)


def test_emote_plays_sound_and_returns_to_gaze():
    robot, skills = make()
    skills.run("look", {"yaw_deg": 20, "pitch_deg": 0})
    skills.run("emote", {"kind": "quack"})
    assert ("sound", "quack") in robot.events
    assert (robot.yaw, robot.pitch) == (20.0, 0.0)


def test_errors_become_tool_errors():
    _, skills = make()
    assert skills.run("emote", {"kind": "moonwalk"}).is_error
    assert skills.run("nope", {}).is_error
    assert skills.run("look", "{not json").is_error


def test_head_only_body_refuses_to_walk_politely():
    robot, skills = make(legs=False)
    res = skills.run("walk", {"vx": 0.1, "yaw_rate": 0, "duration_s": 1})
    assert not res.is_error and "no legs" in res.text
    assert not any(e[0] == "walk" for e in robot.events)


def test_take_photo_with_and_without_camera():
    _, skills = make()
    assert skills.run("take_photo", {}).image_jpeg is None
    _, skills = make(camera=FakeCamera())
    assert skills.run("take_photo", {}).image_jpeg.startswith(b"\xff\xd8")


def test_memory_persists(tmp_path):
    _, skills = make(tmp_path)
    skills.run("remember", {"fact": "Sam likes jazz."})
    assert "Sam likes jazz." in Memory(tmp_path / "mem.json").render()


def test_tool_formats_cover_every_skill():
    names = {s.name for s in SKILLS}
    assert {t["name"] for t in anthropic_tools()} == names
    assert {t["function"]["name"] for t in openai_tools()} == names
    json.dumps(anthropic_tools()), json.dumps(openai_tools())


def test_scripted_brain_end_to_end(tmp_path):
    robot, skills = make(tmp_path)
    calls = []
    brain = ScriptedBrain(skills, on_tool=lambda n, a, r: calls.append(n))
    assert brain.respond("Hey Lavender, can you quack?") == "There you go!"
    assert brain.respond("hi, my name is sam") == "Nice to meet you, Sam!"
    assert "The user's name is Sam." in skills.memory.render()
    assert "left" in brain.respond("look left") .lower()
    assert robot.yaw == 45
    assert "no camera" in brain.respond("what do you see?").lower()
    assert calls[:2] == ["emote", "remember"]
