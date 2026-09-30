"""Talk to Lavender from the terminal.

    lavender                                   # offline scripted brain + simulated body
    lavender --brain anthropic                 # Claude (needs ANTHROPIC_API_KEY or `ant auth login`)
    lavender --brain openai --model <model>    # OpenAI (needs OPENAI_API_KEY)
    lavender --brain openai --base-url http://localhost:11434/v1 --model <model>   # Ollama etc.
    lavender --robot sts-head --port /dev/ttyUSB0 --camera 0                       # real head + webcam
"""

from __future__ import annotations

import argparse
import json
import sys

from .memory import Memory
from .skills import SkillResult, SkillRunner


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lavender", description="Open-source companion duck robot.")
    p.add_argument("--name", default="Lavender", help="the robot's name")
    p.add_argument("--brain", choices=["scripted", "anthropic", "openai"], default="scripted")
    p.add_argument("--model", help="model id (required for --brain openai)")
    p.add_argument("--base-url", help="OpenAI-compatible server URL, e.g. http://localhost:11434/v1")
    p.add_argument("--effort", default="low", help="Claude effort level (low|medium|high|xhigh|max)")
    p.add_argument("--no-vision", action="store_true", help="the model can't take images")
    p.add_argument("--robot", choices=["sim", "sim-head", "sts-head"], default="sim",
                   help="sim: simulated duck with legs; sim-head: head only; sts-head: 2 real STS servos")
    p.add_argument("--port", default="/dev/ttyUSB0", help="servo bus serial port (sts-head)")
    p.add_argument("--pan-id", type=int, default=1)
    p.add_argument("--tilt-id", type=int, default=2)
    p.add_argument("--camera", type=int, help="webcam index for take_photo (needs opencv)")
    p.add_argument("--memory", default="~/.lavender/memory.json", help="memory file ('' to disable)")
    p.add_argument("--debug", action="store_true", help="print every tool call")
    return p


def make_robot(args):
    if args.robot == "sts-head":
        from .robot.feetech import FeetechBus
        from .robot.sts_head import StsHead

        return StsHead(FeetechBus.open(args.port), pan_id=args.pan_id, tilt_id=args.tilt_id)
    from .robot.sim import SimRobot

    return SimRobot(has_legs=args.robot == "sim")


def make_brain(args, skills: SkillRunner, on_tool):
    if args.brain == "anthropic":
        from .brain.anthropic_brain import DEFAULT_MODEL, AnthropicBrain

        return AnthropicBrain(skills, name=args.name, model=args.model or DEFAULT_MODEL,
                              effort=args.effort, on_tool=on_tool)
    if args.brain == "openai":
        if not args.model:
            sys.exit("--brain openai needs --model (a model your server serves that supports tool calling)")
        from .brain.openai_compat import OpenAICompatBrain

        return OpenAICompatBrain(skills, model=args.model, name=args.name, base_url=args.base_url,
                                 vision=not args.no_vision, on_tool=on_tool)
    from .brain.scripted import ScriptedBrain

    return ScriptedBrain(skills, name=args.name, on_tool=on_tool)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    def on_tool(name: str, tool_args: dict, result: SkillResult) -> None:
        if args.debug:
            flag = " (error)" if result.is_error else ""
            print(f"  · {name}({json.dumps(tool_args)}) -> {result.text[:100]}{flag}")

    camera = None
    if args.camera is not None:
        from .camera import OpenCVCamera

        camera = OpenCVCamera(args.camera)
    robot = make_robot(args)
    skills = SkillRunner(robot, camera=camera, memory=Memory(args.memory or None))
    brain = make_brain(args, skills, on_tool)

    print(f"{args.name} is awake ({args.brain} brain, {args.robot} body). Ctrl-D to quit.")
    try:
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if not text:
                continue
            try:
                reply = brain.respond(text)
            except Exception as exc:  # keep the companion running through API or network errors
                print(f"  ! brain error: {exc}")
                continue
            if reply:
                print(f"{args.name.lower()}> {reply}")
    except KeyboardInterrupt:
        pass
    finally:
        robot.close()
        if camera:
            camera.close()
        print("\nbye!")


if __name__ == "__main__":
    main()
