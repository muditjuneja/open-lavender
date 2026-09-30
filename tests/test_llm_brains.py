"""Exercise the LLM tool loops against fake clients (no network, no API keys)."""

import json
from types import SimpleNamespace as NS

from lavender.brain.anthropic_brain import AnthropicBrain
from lavender.brain.openai_compat import OpenAICompatBrain
from lavender.robot.sim import SimRobot
from lavender.skills import SkillRunner


class FakeCamera:
    def snapshot(self):
        return b"\xff\xd8jpeg"


def skills():
    robot = SimRobot(realtime=False, log=None)
    return robot, SkillRunner(robot, camera=FakeCamera())


# --- Anthropic -----------------------------------------------------------------------

def a_text(t):
    return NS(type="text", text=t)


def a_tool(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


class FakeAnthropic:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        # Snapshot the message list; the brain keeps appending to it.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def test_anthropic_loop_runs_tools_and_returns_speech():
    robot, sk = skills()
    client = FakeAnthropic([
        NS(stop_reason="tool_use", content=[
            NS(type="thinking", thinking=""),
            a_text("Ooh, let me see!"),
            a_tool("t1", "emote", {"kind": "quack"}),
            a_tool("t2", "take_photo", {}),
        ]),
        NS(stop_reason="end_turn", content=[a_text("I see three people waving.")]),
    ])
    brain = AnthropicBrain(sk, client=client)
    reply = brain.respond("Look at the audience!")
    assert reply == "Ooh, let me see! I see three people waving."
    assert ("sound", "quack") in robot.events

    second = client.requests[1]
    assert second["model"] == "claude-opus-5-5"
    assert second["fallbacks"] == "default"
    # Parallel tool results go back together in one user message, image included.
    results = second["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert results[1]["content"][1]["type"] == "image"
    # Assistant content (thinking block included) is echoed back unchanged.
    assert second["messages"][1]["content"][0].type == "thinking"


def test_anthropic_refusal_rolls_back_history():
    _, sk = skills()
    client = FakeAnthropic([NS(stop_reason="refusal", content=[])])
    brain = AnthropicBrain(sk, client=client)
    brain.respond("something bad")
    assert brain.messages == []


# --- OpenAI-compatible --------------------------------------------------------------------

def o_resp(content=None, calls=None):
    tool_calls = [
        NS(id=i, function=NS(name=n, arguments=json.dumps(a) if not isinstance(a, str) else a))
        for i, n, a in (calls or [])
    ] or None
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class FakeOpenAI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def test_openai_loop_sends_photo_as_user_image():
    robot, sk = skills()
    client = FakeOpenAI([
        o_resp(None, [("c1", "look", {"yaw_deg": 30, "pitch_deg": 0}), ("c2", "take_photo", {})]),
        o_resp("A cat is on the sofa!"),
    ])
    brain = OpenAICompatBrain(sk, model="any-local-model", client=client)
    assert brain.respond("what's over there?") == "A cat is on the sofa!"
    assert robot.yaw == 30
    msgs = client.requests[1]["messages"]
    assert [m["role"] for m in msgs[-4:]] == ["assistant", "tool", "tool", "user"]
    assert msgs[-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_openai_bad_arguments_become_tool_error():
    _, sk = skills()
    client = FakeOpenAI([o_resp(None, [("c1", "look", "{oops")]), o_resp("Sorry!")])
    brain = OpenAICompatBrain(sk, model="m", client=client)
    assert brain.respond("look") == "Sorry!"
    tool_msg = client.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["content"].startswith("ERROR")
