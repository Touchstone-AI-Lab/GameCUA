"""The env-* commands that build, create, observe and drive containerized environments."""

import argparse
import json
from pathlib import Path

from .manager import Environment, build, docker, inspect_host

ACTIONS = (
    "status",
    "start",
    "connect",
    "stop",
    "clean",
    "observe",
    "exec",
    "trial",
    "resume",
    "interrupt",
    "cancel",
    "steam-prepare",
    "steam-cancel",
)


def add_commands(commands):
    for name in ("env-build", "env-host"):
        commands.add_parser(name)
    create = commands.add_parser("env-create")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--installation", type=Path)
    create.add_argument("--snapshot", type=Path)
    create.add_argument(
        "--renderer", choices=("software", "egl", "nvidia", "wsl-d3d12"), default="software"
    )
    create.add_argument("--gpu", default="0")
    create.add_argument("--mode", choices=("evaluation", "development"), default="evaluation")
    create.add_argument("--cpus", type=float, default=2)
    create.add_argument("--memory", default="2g")
    create.add_argument("--steam", action="store_true")
    create.add_argument("--steam-environment", type=Path)
    for name in ACTIONS:
        command = commands.add_parser("env-" + name)
        command.add_argument("--environment", type=Path, required=True)
        if name == "exec":
            command.add_argument("arguments", nargs=argparse.REMAINDER)
        if name in ("trial", "resume"):
            command.add_argument("--trial-spec", type=Path, required=True)
            command.add_argument("--seconds", type=float, default=90)
            command.add_argument("--name", default="trial")
        if name == "observe":
            command.add_argument("--output", type=Path)
        if name == "steam-prepare":
            command.add_argument("--app-id", type=int, default=646570)
            command.add_argument("--timeout", type=int, default=900)


def screenshot(environment, output):
    """Save the game window (Steam environments) or the whole display to a host file."""
    capture = "from PIL import ImageGrab; ImageGrab.grab(xdisplay=':99').save('/state/agent.png')"
    if environment.meta["steam"]:
        trial = environment.root / "work" / environment.meta["trial"]
        title = json.loads((trial / "game.json").read_text())["window_title"]
        capture = (
            "from gamecua.desktop import X11Desktop; "
            f"d=X11Desktop(title={title!r}); "
            "d.capture(focus=False).save('/state/agent.png'); d.close()"
        )
    docker("exec", environment.meta["container"], "python", "-c", capture)
    output.write_bytes((environment.root / "private/agent.png").read_bytes())


def execute_environment(args):
    action = args.command.removeprefix("env-")
    if action == "build":
        return {"image": build()}
    if action == "host":
        return inspect_host()
    if action == "create":
        return Environment(args.output).create(
            args.installation,
            args.snapshot,
            args.mode,
            renderer=args.renderer,
            cpus=args.cpus,
            memory=args.memory,
            steam=args.steam,
            steam_environment=args.steam_environment,
        )
    environment = Environment(args.environment)
    if action in ("status", "start", "connect", "stop", "clean"):
        return getattr(environment, action)()
    if action == "exec":
        return environment.exec(
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
    if action in ("trial", "resume"):
        environment.trial(args.trial_spec, args.seconds, args.name, resume=action == "resume")
        return {"started": True, "workspace": str(environment.root / "work")}
    if action == "interrupt":
        state = json.loads((environment.root / "private/execution.json").read_text())
        return environment.exec(["kill", "-INT", str(state["pid"])])
    if action == "cancel":
        (environment.root / "work" / environment.meta["trial"] / "STOP").touch()
        return {"cancel_requested": True}
    if action == "observe":
        result = environment.status()
        state = environment.root / "private/execution.json"
        result["execution"] = json.loads(state.read_text()) if state.exists() else None
        if args.output:
            screenshot(environment, args.output)
            result["screenshot"] = str(args.output)
        return result
    if action == "steam-prepare":
        environment.exec(
            [
                *("python", "-m", "gamecua.games.steam.preparation"),
                *("--app-id", str(args.app_id), "--timeout", str(args.timeout)),
            ],
            detach=True,
        )
        return {"preparation_started": True, **environment.connect()}
    (environment.root / "private/CANCEL_STEAM").touch()
    return {"cancel_requested": True}
