"""Brain for any OpenAI-compatible Chat Completions server.

One class covers OpenAI itself and local/open models served by Ollama, vLLM,
llama.cpp (`llama-server`), LM Studio and similar, as long as the model supports
tool calling. Point `base_url` at the server and pick a model it serves.
"""

from __future__ import annotations

import base64
import json

from ..skills import SkillRunner, openai_tools
from .base import ToolObserver
from .persona import system_prompt

MAX_STEPS = 8


class OpenAICompatBrain:
    def __init__(
        self,
        skills: SkillRunner,
        model: str,
        name: str = "Lavender",
        base_url: str | None = None,
        api_key: str | None = None,
        vision: bool = True,
        client=None,
        on_tool: ToolObserver | None = None,
    ) -> None:
        if client is None:
            import openai  # pip install open-lavender[openai]

            # Local servers ignore the key, but the SDK requires one to be set.
            key = api_key or (None if base_url is None else "not-needed")
            client = openai.OpenAI(base_url=base_url, api_key=key)
        self.client = client
        self.skills = skills
        self.model = model
        self.vision = vision
        self.on_tool = on_tool
        self.tools = openai_tools()
        self.messages: list[dict] = [{"role": "system", "content": system_prompt(name, skills.memory.render())}]

    def respond(self, user_text: str) -> str:
        start = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        spoken: list[str] = []
        try:
            for _ in range(MAX_STEPS):
                response = self.client.chat.completions.create(
                    model=self.model, messages=self.messages, tools=self.tools
                )
                msg = response.choices[0].message
                if msg.content and msg.content.strip():
                    spoken.append(msg.content.strip())
                calls = msg.tool_calls or []
                assistant: dict = {"role": "assistant", "content": msg.content or ""}
                if calls:
                    assistant["tool_calls"] = [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                        for c in calls
                    ]
                self.messages.append(assistant)
                if not calls:
                    return " ".join(spoken).strip()
                self._run_tools(calls)
            return " ".join(spoken).strip() or "I got a bit carried away there."
        except Exception:
            del self.messages[start:]
            raise

    def _run_tools(self, calls) -> None:
        images: list[bytes] = []
        for call in calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
                result_text, is_error = f"Invalid JSON arguments: {call.function.arguments!r}", True
            else:
                result = self.skills.run(call.function.name, args)
                if self.on_tool:
                    self.on_tool(call.function.name, args, result)
                result_text, is_error = result.text, result.is_error
                if result.image_jpeg:
                    if self.vision:
                        images.append(result.image_jpeg)
                    else:
                        result_text += " (The current model can't see images.)"
            self.messages.append({"role": "tool", "tool_call_id": call.id,
                                  "content": ("ERROR: " if is_error else "") + result_text})
        # Chat Completions tool messages are text-only, so photos go in a follow-up user message.
        for jpeg in images:
            url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
            self.messages.append({"role": "user", "content": [
                {"type": "text", "text": "[Photo from your take_photo tool]"},
                {"type": "image_url", "image_url": {"url": url}},
            ]})
