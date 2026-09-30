"""Brain backed by Claude (Anthropic Messages API) with a manual tool-use loop."""

from __future__ import annotations

import base64

from ..skills import SkillResult, SkillRunner, anthropic_tools
from .base import ToolObserver
from .persona import system_prompt

DEFAULT_MODEL = "claude-opus-5-5"
MAX_STEPS = 8


class AnthropicBrain:
    def __init__(
        self,
        skills: SkillRunner,
        name: str = "Lavender",
        model: str = DEFAULT_MODEL,
        effort: str = "low",
        client=None,
        on_tool: ToolObserver | None = None,
    ) -> None:
        if client is None:
            import anthropic  # pip install open-lavender[anthropic]

            client = anthropic.Anthropic()
        self.client = client
        self.skills = skills
        self.model = model
        # Chat is latency-sensitive, so default to low effort; raise it for harder tasks.
        self.effort = effort
        self.on_tool = on_tool
        # The system prompt is fixed for the session (memory is loaded once) so the
        # conversation prefix stays stable and cacheable.
        self.system = system_prompt(name, skills.memory.render())
        self.tools = anthropic_tools()
        self.messages: list[dict] = []

    def respond(self, user_text: str) -> str:
        start = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        spoken: list[str] = []
        try:
            for _ in range(MAX_STEPS):
                response = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=self.system,
                    tools=self.tools,
                    messages=self.messages,
                    output_config={"effort": self.effort},
                    # If a safety classifier declines, the API retries on a fallback model.
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if response.stop_reason == "refusal":
                    del self.messages[start:]
                    return "Hmm, I'd rather not do that one."

                # Append the full content unchanged (thinking blocks included).
                self.messages.append({"role": "assistant", "content": response.content})
                spoken += [b.text for b in response.content if b.type == "text" and b.text.strip()]

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if response.stop_reason != "tool_use" or not tool_uses:
                    return " ".join(spoken).strip()

                results = [self._run_tool(b) for b in tool_uses]
                self.messages.append({"role": "user", "content": results})
            return " ".join(spoken).strip() or "I got a bit carried away there."
        except Exception:
            del self.messages[start:]  # keep history valid for the next turn
            raise

    def _run_tool(self, block) -> dict:
        args = dict(block.input or {})
        result = self.skills.run(block.name, args)
        if self.on_tool:
            self.on_tool(block.name, args, result)
        return tool_result_block(block.id, result)


def tool_result_block(tool_use_id: str, result: SkillResult) -> dict:
    content: list[dict] = [{"type": "text", "text": result.text}]
    if result.image_jpeg:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(result.image_jpeg).decode(),
            },
        })
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if result.is_error:
        block["is_error"] = True
    return block
