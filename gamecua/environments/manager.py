"""Docker environment lifecycle: one container per environment directory with its own display, state and workspace."""

import json
import os
import platform
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from ..storage import write_json

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "gamecua-environment:0.7.14"
WSL_LIBRARIES = Path("/usr/lib/wsl")


def docker(*args, timeout=120, stdin=None):
    result = subprocess.run(
        ["docker", *map(str, args)], input=stdin, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Docker operation failed")
    return result.stdout.strip()


def build():
    with tempfile.TemporaryDirectory(prefix="gamecua-image-") as folder:
        context = Path(folder)
        for name in ("pyproject.toml", "requirements.lock.txt"):
            shutil.copyfile(ROOT / name, context / name)
        for name in ("gamecua", "benchmarks"):
            shutil.copytree(
                ROOT / name, context / name, ignore=shutil.ignore_patterns("__pycache__")
            )
        shutil.copyfile(Path(__file__).parent / "assets/Dockerfile", context / "Dockerfile")
        cache = os.getenv("GAMECUA_BUILD_CACHE")
        if cache:
            shutil.copytree(cache, context / "build-cache")
        else:
            (context / "build-cache").mkdir()
        mirror = os.getenv("GAMECUA_REGISTRY_MIRROR")
        subprocess.run(
            [
                "docker",
                "build",
                *("--build-arg", f"HOST_UID={os.getuid()}"),
                *("--build-arg", f"HOST_GID={os.getgid()}"),
                *(["--build-arg", f"BASE_REGISTRY={mirror.rstrip('/')}"] if mirror else []),
                *("-t", IMAGE, folder),
            ],
            check=True,
        )
    return docker("image", "inspect", IMAGE, "--format", "{{.Id}}")


def inspect_host():
    def probe(args):
        result = subprocess.run(args, capture_output=True, text=True)
        return {"exit": result.returncode, "output": result.stdout.strip()}

    version = Path("/sys/module/vmwgfx/version")
    return {
        "system": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "docker": probe(["docker", "version"]),
        "memory": probe(["free", "-b"]),
        "disk": probe(["df", "-B1", str(ROOT)]),
        "graphics": probe(["lspci", "-nn"]),
        "driver": probe(["readlink", "-f", "/sys/class/drm/card0/device/driver"]),
        "vmwgfx_version": version.read_text().strip() if version.exists() else None,
        "devices": [str(p) for p in Path("/dev/dri").glob("*") if p.is_char_device()],
    }


def apparmor_profile(path=Path("/proc/self/attr/current")):
    return path.read_text().replace("\0", "").split(" (")[0].strip()


def renderer_arguments(renderer, gpu):
    """Return the docker run arguments, render device and GPU access mode for a renderer."""
    if renderer == "egl":
        device = Path("/dev/dri/renderD128")
        args = ["--device", str(device), "--group-add", str(device.stat().st_gid)]
        return args + ["-e", f"GAMECUA_RENDER_DEVICE={device}"], str(device), None
    if renderer == "nvidia":
        if nvidia_runtime():
            args, access = ["--runtime", "nvidia", "-e", "NVIDIA_VISIBLE_DEVICES=" + gpu], "runtime"
            args += ["-e", "NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compat32"]
        else:
            args, access = ["--device", "nvidia.com/gpu=" + gpu], "cdi"
        return args + ["-e", f"GAMECUA_RENDER_DEVICE=nvidia{gpu}"], f"nvidia{gpu}", access
    if renderer == "wsl-d3d12":
        args = [
            *("--device", "/dev/dxg"),
            *("--mount", f"type=bind,src={WSL_LIBRARIES},dst=/usr/lib/wsl,readonly"),
            *("-e", "LD_LIBRARY_PATH=/usr/lib/wsl/lib"),
            *("-e", "MESA_D3D12_DEFAULT_ADAPTER_NAME=" + gpu),
            *("-e", "GAMECUA_RENDER_DEVICE=" + gpu),
        ]
        return args, gpu, "wsl"
    return [], None, None


class Environment:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.path = self.root / "environment.local.json"
        self.meta = json.loads(self.path.read_text()) if self.path.exists() else None

    def create(
        self,
        installation,
        snapshot,
        mode="evaluation",
        renderer="software",
        cpus=2,
        memory="2g",
        image=IMAGE,
        steam=False,
        steam_environment=None,
        mounts=(),
        gpu="0",
    ):
        steam_home = None
        if steam_environment:
            source = Environment(steam_environment)
            steam_home = Path(source.meta.get("steam_home") or source.root / "private/home")
            steam_home, steam = steam_home.resolve(), True
        self.root.mkdir(parents=True, mode=0o700)
        state, work = self.root / "private", self.root / "work"
        state.mkdir(mode=0o700)
        work.mkdir(mode=0o700)
        (state / "machine-id").write_text(uuid.uuid4().hex + "\n")
        (state / "access-token").write_text(secrets.token_urlsafe(32))
        (state / "access-token").chmod(0o600)
        image_id = docker("image", "inspect", image, "--format", "{{.Id}}")
        name = "gamecua-" + uuid.uuid4().hex[:12]
        args = [
            *("run", "-d", "--init", "--user", f"{os.getuid()}:{os.getgid()}"),
            *("--name", name, "--label", "gamecua.managed=true"),
            *("--cpus", str(cpus), "--memory", memory, "--shm-size", "512m"),
            *("--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-p", "127.0.0.1::8080"),
            *("-e", "LIBGL_ALWAYS_SOFTWARE=" + ("1" if renderer == "software" else "0")),
            *("--mount", f"type=bind,src={state / 'machine-id'},dst=/etc/machine-id,readonly"),
            *("--mount", f"type=bind,src={state},dst=/state"),
            *("--mount", f"type=bind,src={work},dst=/work"),
        ]
        for source, target in ((installation, "/installation"), (snapshot, "/snapshot")):
            if source:
                args += ["--mount", f"type=bind,src={Path(source).resolve()},dst={target},readonly"]
        for source, target in mounts:
            args += ["--mount", f"type=bind,src={Path(source).resolve()},dst={target}"]
        args += ["-e", "GAMECUA_GRAPHICS_PRESET=" + renderer]
        extra, render_device, gpu_access = renderer_arguments(renderer, gpu)
        args += extra
        if steam_home:
            args += ["--mount", f"type=bind,src={steam_home},dst=/state/home"]
        if steam:
            profile = os.getenv("GAMECUA_STEAM_APPARMOR_PROFILE") or apparmor_profile()
            args += [
                "--security-opt",
                "apparmor=" + profile,
                "--security-opt",
                "seccomp=unconfined",
            ]
        try:
            container = docker(*args, image_id)
            self.meta = {
                "container": container,
                "name": name,
                "image": image_id,
                "mode": mode,
                "renderer": renderer,
                "render_device": render_device,
                "egl_device": "egl0" if renderer in ("egl", "nvidia") else None,
                "cpus": cpus,
                "memory": memory,
                "steam": steam,
                "steam_home": str(steam_home) if steam_home else None,
                "created_at": time.time(),
                "host": inspect_host(),
                "installation": str(Path(installation).resolve()) if installation else None,
                "snapshot": str(Path(snapshot).resolve()) if snapshot else None,
            }
            write_json(self.path, self.meta)
            return self.wait_ready("Environment readiness timed out")
        except BaseException:
            if self.meta:
                logs = subprocess.run(
                    ["docker", "logs", self.meta["container"]], capture_output=True, text=True
                )
                (state / "startup.log").write_text(logs.stdout + logs.stderr)
                docker("rm", "-f", self.meta["container"])
            raise

    def wait_ready(self, message):
        for _ in range(150):
            if (self.root / "private/ready.json").exists():
                return self.status()
            if not self.status()["running"]:
                raise RuntimeError("Graphical session exited; inspect environment logs")
            time.sleep(0.2)
        raise TimeoutError(message)

    def status(self):
        info = json.loads(docker("inspect", self.meta["container"]))[0]
        ports = info["NetworkSettings"]["Ports"].get("8080/tcp") or []
        healthy = False
        if info["State"]["Running"]:
            healthy = not subprocess.run(
                ["docker", "exec", self.meta["container"], "xdpyinfo"],
                capture_output=True,
                timeout=10,
            ).returncode
        ready = self.root / "private/ready.json"
        return {
            "healthy": healthy,
            "name": self.meta["name"],
            "running": info["State"]["Running"],
            "mode": self.meta["mode"],
            "image": info["Image"],
            "url": f"http://127.0.0.1:{ports[0]['HostPort']}/" if ports else None,
            "ready": json.loads(ready.read_text()) if ready.exists() else None,
            "workspace": str(self.root / "work"),
        }

    def connect(self):
        return {
            "url": self.status()["url"] + "#" + (self.root / "private/access-token").read_text(),
            "read_only": True,
            "ssh": "Forward the reported localhost port with SSH -L; treat the URL as private",
        }

    def exec(self, args, detach=False, env=None):
        """Run a command in the container, passing its environment through a private file."""
        request = self.root / "private" / ("request-" + uuid.uuid4().hex + ".local.json")
        write_json(request, {"args": args, "env": env or {}})
        request.chmod(0o600)
        invocation = [
            "exec",
            *(["-d"] if detach else []),
            self.meta["container"],
            "python",
            "-c",
            "import json,os,sys; from pathlib import Path; f=Path(sys.argv[1]); p=json.loads(f.read_text()); f.unlink(); os.environ.update(p['env']); os.execvp(p['args'][0],p['args'])",
            "/state/" + request.name,
        ]
        try:
            return docker(*invocation, timeout=600)
        except BaseException:
            request.unlink(missing_ok=True)
            raise

    def trial(self, spec, seconds, name="trial", resume=False, catalog=None, start_gate=None):
        """Start the Trial worker detached in the container."""
        from ..cli import load_env

        spec_path = Path(spec).resolve()
        catalog_root = Path(catalog).resolve() if catalog else ROOT / "benchmarks"
        args = ["python", "-m", "gamecua.cli"]
        container_catalog = "/opt/gamecua/benchmarks"
        if catalog:
            target = self.root / "work/configuration"
            if not target.exists():
                shutil.copytree(catalog_root, target)
            container_catalog = "/work/configuration"
            args += ["--catalog", container_catalog]
        if resume:
            args += ["resume-trial", "--run-dir", "/work/" + name]
        else:
            args += [
                *("trial", "--trial-spec"),
                f"{container_catalog}/{spec_path.relative_to(catalog_root)}",
                *("--installation", "/installation", "--snapshot", "/snapshot"),
                *("--seconds", str(seconds), "--output", "/work/" + name),
            ]
        if start_gate:
            args += ["--start-gate", str(start_gate)]
        load_env()
        model_id = json.loads(spec_path.read_text())["model_id"]
        key = next(
            model["api_key_env"]
            for model in map(
                json.loads, map(Path.read_text, (catalog_root / "models").glob("*.json"))
            )
            if model["id"] == model_id
        )
        self.meta["trial"] = name
        write_json(self.path, self.meta)
        provenance = {
            k: v
            for k, v in self.meta.items()
            if k not in ("container", "name", "installation", "snapshot", "steam_home")
        }
        harbor_case = self.root / "work/harbor-case.json"
        if harbor_case.exists():
            provenance["harbor"] = json.loads(harbor_case.read_text())
        provenance["display"] = json.loads((self.root / "private/ready.json").read_text())
        dependencies = self.root / "private/dependencies.json"
        if dependencies.exists():
            provenance["dependencies"] = json.loads(dependencies.read_text())
        write_json(self.root / "work/environment.json", provenance)
        return self.exec(
            ["python", "-m", "gamecua.environments.worker", *args],
            detach=True,
            env={key: os.environ[key]},
        )

    def start(self):
        (self.root / "private/ready.json").unlink(missing_ok=True)
        docker("start", self.meta["container"])
        return self.wait_ready("Environment restart timed out")

    def stop(self):
        return docker("stop", "--time", "15", self.meta["container"])

    def clean(self):
        result = docker("rm", "-f", self.meta["container"])
        for pattern in ("access-token", "steam-qr*.png", "request-*.local.json"):
            for path in (self.root / "private").glob(pattern):
                path.unlink(missing_ok=True)
        return result
