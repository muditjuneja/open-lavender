# open-lavender

An open-source, hackable version of **"Lavender"**, the little duck robot OpenAI brought on stage at DevDay 2026.

> **What Lavender actually is:** OpenAI didn't build the robot. It is a **Microduck**, a $399 robot from
> Hugging Face and Pollen Robotics (announced 27 Aug 2026). "Lavender" was the name given to the unit in the
> demo. OpenAI connected it to its API: realtime voice, vision and image generation, called as tools. In the demo it
> answered voice commands ("Hey Lavender, can you quack if you can hear me?"), looked at the audience and
> drew a picture of them.
>
> The Microduck **software** is open (Apache-2.0: SDK, simulation and the RL training stack). The **mechanical and
> electronic design files are not open**, and Pollen has asked the press not to call it open hardware.
> This project aims for a fully open robot: open hardware, open body software and a swappable "brain" that
> can run on open models.
>
> **Design rule:** we build on the fully open Open Duck Mini and give the robot **its own look**. We don't copy
> the Microduck's or Disney's BDX design, so everything published here is clean to share and build on.

## Quick start (Phase 0: brain first)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
lavender --debug                       # offline scripted brain + simulated duck, no API key needed
```

Swap in a real brain:

```bash
pip install -e ".[anthropic]"  && lavender --brain anthropic                   # Claude (ANTHROPIC_API_KEY)
pip install -e ".[openai]"     && lavender --brain openai --model <model>      # OpenAI (OPENAI_API_KEY)
lavender --brain openai --base-url http://localhost:11434/v1 --model <model>   # local model via Ollama, vLLM, llama.cpp…
```

For a local model, pick one that supports **tool calling** (and ideally vision, so `take_photo` works;
otherwise add `--no-vision`). Other options:

| Flag | What it does |
|---|---|
| `--robot sim` / `sim-head` / `sts-head` | simulated duck with legs / simulated head only / real 2-servo STS3215 pan-tilt head |
| `--port /dev/ttyUSB0 --pan-id 1 --tilt-id 2` | servo bus settings for `sts-head` |
| `--camera 0` | webcam for `take_photo` (`pip install -e ".[camera]"`) |
| `--memory PATH` | long-term memory file (default `~/.lavender/memory.json`, `''` disables it) |

The Claude brain defaults to `claude-opus-5-5` at `--effort low` to keep replies fast. It also turns on the API's
server-side refusal fallback: if a safety check declines a request, the API retries it on a fallback model.

```
lavender/
  skills.py            the only interface between brain and body (tool schemas + dispatcher)
  brain/               scripted (offline) · anthropic_brain (Claude) · openai_compat (OpenAI + local servers) · persona
  robot/               base behaviour (look/emote/walk) · sim · feetech STS bus driver · sts_head · animations
  memory.py camera.py cli.py
tests/                 pytest; LLM loops are tested against fake clients, no network needed
```

Status: runs end-to-end with the scripted brain and simulated body. The Claude and OpenAI-compatible loops
pass tests against fake clients but **haven't been run against the live APIs yet**. The Feetech driver's
packet encoding is tested but **hasn't been run on real servos yet**.

---

## 1. What the original has (reference target)

Taken from press coverage of the Microduck launch. Check these against `pollen-robotics/microduck` before relying on them.

| Area | Microduck |
|---|---|
| Size / weight | ~25 cm tall, 14 cm wide, < 800 g |
| Compute | Rockchip **RK3566** with an NPU, 1 GB RAM, 32 GB storage |
| Actuators | **15 motors** across the legs, neck and head, plus an articulated **beak** (it can pick things up) |
| Vision | Front camera with an indicator light |
| Depth | 8×8 time-of-flight "LiDAR" matrix |
| Balance | **2 IMUs** (body and head) |
| Audio | Microphones and a speaker. Each unit generates its own voice on first boot and keeps it |
| Other | Wi-Fi, Bluetooth, 2 NFC antennas |
| Power | Removable **NP-F550** battery (2S Li-ion, 2600 mAh), about 1 h of runtime |
| Low-level software | **Rust** runtime running a 50 Hz control loop and the motor bus |
| Locomotion | RL policies (**PPO** in **mjlab / MuJoCo Warp**) exported to **ONNX**. About 1–2 h on one GPU for a usable gait |
| Skills out of the box | walk, sit, stand, kick, grab, roller-skate, get back up |

It is a descendant of Antoine Pirrone's **[Open Duck Mini](https://github.com/apirrone/Open_Duck_Mini)**, a
fully open, 3D-printed mini version of Disney's BDX droid. That project is our hardware starting point.

## 2. Architecture: three loops at three speeds

The "alive" feeling comes from a layered system. The LLM never drives joints directly.

```
 ┌──────────────────────────── BRAIN (laptop / home server / cloud) ─ ~1 Hz ────────────────────────────┐
 │  wake word → speech-to-speech or ASR→LLM→TTS · vision-language model · memory · persona            │
 │  outputs: speech audio + TOOL CALLS  (walk_to, look_at, emote("quack"), grab, take_photo, draw…)   │
 └───────────────────────────────▲──────────────────────────────┬─────────────────────────────────────┘
          audio/video/state (WebRTC/WebSocket)                  │ tool calls (JSON)
 ┌───────────────────────────────┴──────────────────────────────▼─────────────────────────────────────┐
 │  SKILLS / BEHAVIOUR (on robot) ─ 10–30 Hz                                                          │
 │  skill server · animation player (quack, wiggle, dance) · face/gaze tracking on NPU · idle life    │
 │  (breathing, blinking indicator, glances) · safety (fall detect, battery, stall)                  │
 └───────────────────────────────▲──────────────────────────────┬─────────────────────────────────────┘
                                 │ commands: twist, head pose, body pose, mode
 ┌───────────────────────────────┴──────────────────────────────▼─────────────────────────────────────┐
 │  BODY (on robot) ─ 50 Hz                                                                           │
 │  ONNX RL policy (walk / stand / recover) · motor bus · IMU fusion                                  │
 └────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Why three loops:
- **Balance cannot wait for the network.** The 50 Hz policy and fall recovery run entirely on the robot.
- **Reactions need to be instant.** Gaze tracking, turning toward sound and idle animations run on the robot,
  so the duck feels alive even while the LLM is still thinking.
- **Intelligence can be remote and replaceable.** The brain only sends high-level tool calls, so you can swap
  OpenAI, Claude, Gemini or a fully local model without touching the body.

## 3. Hardware plan (open BOM)

Base: **Open Duck Mini v2** mechanics (Onshape CAD, 3D-printed), scaled and adapted. Add a sensor head and
upgrade the compute. Prices are rough USD estimates.

| Part | Choice | Why | ~Cost |
|---|---|---|---|
| Servos (legs, neck, head) | 14× **Feetech STS3215** (7.4 V, serial bus, position feedback) | Proven in Open Duck Mini, cheap, and the actuator is well modelled for sim-to-real | 210–280 |
| Beak | 1× micro serial servo (e.g. Feetech SCS0009) | Light enough for the head | 8 |
| Servo bus | Waveshare bus-servo adapter / half-duplex UART | | 10 |
| Compute | **Radxa Zero 3W** (RK3566, 2–4 GB) | Same SoC as Microduck, Pi Zero footprint, 0.8 TOPS NPU. Pi Zero 2W is too weak for camera + audio + policy | 35–50 |
| IMU ×2 | BNO085 (or BNO055) body + head | On-chip fusion | 2×25 |
| Camera | Wide-angle MIPI CSI module (e.g. IMX219 160°) | Faces and scene for the VLM | 20 |
| Depth | **VL53L5CX** 8×8 ToF | Same class of sensor as Microduck. Edge and obstacle detection | 18 |
| Audio in | 2× I2S MEMS mics (INMP441) or a 2-mic HAT | Wake word + direction of arrival | 10 |
| Audio out | MAX98357A I2S amp + 28 mm speaker | Quacks and voice | 8 |
| Power | NP-F550 2S Li-ion + dock, buck to 5 V for logic | Removable and cheap. 2S matches the 7.4 V servos | 25 |
| Expression | 1 RGB LED ring around the camera ("eye") | Shows listening / thinking / speaking | 5 |
| Mechanical | PLA/PETG, bearings, M2/M3 hardware, TPU feet | | 40–60 |
| **Total** | | | **≈ $450–550** |

## 4. Software plan

### Body (`body/`)
- **Simulation:** MJCF model of the robot, exported from Onshape (`onshape-to-robot`).
- **Actuator model:** identify the STS3215 dynamics with BAM (Better Actuator Models) so policies transfer to the real robot.
- **Training:** PPO in **mjlab / MuJoCo Warp** or MuJoCo Playground, with domain randomisation (mass, friction,
  latency, backlash, IMU noise). One policy per skill (walk with twist + head-pose commands, stand, get up),
  or one multi-skill policy.
- **Deploy:** ONNX runtime on the RK3566 with a 50 Hz loop in Rust, reusing the Apache-2.0
  Microduck runtime and `rustypot` for the motor bus where possible.

### Skills (`lavender/skills.py`) — the API the brain sees
A small set of well-described tools. This interface is what makes the "API-driven robot" demo possible.
Implemented now: `look(yaw_deg, pitch_deg)`, `emote(kind)` (quack, nod, shake, happy_wiggle, curious, sleepy,
dance), `walk(vx, yaw_rate, duration_s)`, `set_posture(stand|sit)`, `take_photo()`, `remember(fact)` and
`get_status()`. Planned: `look_at(person|sound)` (needs face tracking and sound direction) and `grab(target)` (needs the beak).

The robot also runs these without the brain: face tracking (BlazeFace or YOLO-nano on the NPU), sound-source
turning, idle "breathing", and fall recovery.

### Brain (`brain/`) — swappable
Runs on your laptop, a mini PC or in the cloud (the robot's 1 GB of RAM can't host an LLM).

| Function | Hosted option | Open / local option |
|---|---|---|
| Wake word | — | openWakeWord ("hey lavender") |
| Voice activity detection | built into realtime APIs | Silero VAD |
| Speech → text | Realtime API | Whisper / faster-whisper, NVIDIA Parakeet, Moonshine |
| Reasoning + tools | OpenAI Realtime, Claude, Gemini Live | Qwen-VL / Gemma-class VLM via llama.cpp, Ollama or vLLM |
| Full-duplex speech | OpenAI Realtime | Kyutai Moshi / Unmute-style pipeline |
| Text → speech | Realtime API voice | Kokoro, Piper (seed one voice per robot, like Microduck) |
| Drawing ("make a drawing of the audience") | GPT Image | SDXL / FLUX-class local model |
| Memory | — | SQLite + embeddings: people, preferences, past conversations |

Latency budget for feeling natural: **under ~800 ms from end of speech to first sound**. Mask the rest with
instant local reactions (tilt head, LED "thinking" pulse, a small quack).

### Personality
A persona prompt (curious, a bit mischievous, speaks briefly, quacks when excited). It is proactive only when
someone is present (face detected) and there's a reason to be. Memory lets it greet people by name and pick up
old threads. Most of the "companion" quality comes from **idle animation, gaze and timing**, not from the model.

## 5. Roadmap

1. **Phase 0: brain first, no legs.** Laptop mic, webcam and a 2-servo pan/tilt "head" built from 2× STS3215.
   Build the skill API, the brain loop, persona and memory. Get a talking, looking, quacking head working in a weekend.
   - [x] skills layer, simulated body, scripted / Claude / OpenAI-compatible brains, memory, webcam, STS3215 head driver
   - [ ] live-test the brains against real APIs and a local model; bench-test the head on real servos
   - [ ] voice: wake word → speech-to-text → brain → text-to-speech, with a streaming/realtime option
   - [ ] reflexes: face tracking (`look_at person`), idle animations, a listening/thinking/speaking LED
   - [ ] a 3D-printable pan/tilt head with its own look
2. **Phase 1: legs.** Build Open Duck Mini v2, reproduce its walking policy, then move to the RK3566 board.
3. **Phase 2: the Lavender head.** Camera, ToF, mics, speaker, LED eye and beak servo in a new head shell.
   Retrain policies with the new head mass.
4. **Phase 3: integration.** Robot ⇄ brain over WebRTC, on-robot face tracking, a full demo:
   *"Hey Lavender, quack if you can hear me… now look at the audience and draw them."*
5. **Phase 4: more skills.** Grab with the beak, kick, roller-skate, and training new tricks with RL.

**Shortcut:** if you mainly care about the brain, buy a Microduck ($399, ships before Christmas 2026)
and run the `brain/` + `skills/` layers on its open SDK. The body layer here is only needed for fully open hardware.

## References
- Microduck launch: [TechCrunch](https://techcrunch.com/2026/08/27/hugging-face-is-selling-a-cute-399-open-source-duck-robot-microduck/),
  [MarkTechPost technical breakdown](https://www.marktechpost.com/2026/08/28/pollen-robotics-hugging-face-microduck-399-open-source-rl-biped-robot/)
- DevDay 2026 demo: [Simon Willison live blog](https://simonwillison.net/2026/Sep/29/openai-devday-2026-live-blog/),
  [keynote transcript](https://sozai.app/transcript/openai-devday-2026-keynote-full/)
- Open Duck Mini: [hardware + BOM](https://github.com/apirrone/Open_Duck_Mini/blob/v2/README.md),
  [runtime](https://github.com/apirrone/Open_Duck_Mini_Runtime/tree/v2)
- Sibling project: Pollen / Hugging Face **Reachy Mini** (open desktop robot, Python SDK)

## License
Code: [Apache-2.0](LICENSE), the same as Open Duck Mini's and Microduck's software. Hardware files, once they exist,
will use an open hardware license (probably CERN-OHL-P or CERN-OHL-S; still to be decided).
