"""Harbor environment and agent adapters; the evaluated model never receives environment tools."""

import asyncio
import json
import shlex
import time
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import (
    EnvironmentCapabilities,
    EnvironmentResourceCapabilities,
)

from ..environments.manager import Environment, docker
from ..storage import write_json
from . import VERSION


def recovery_shift(record):
    try:
        ledger = json.loads(record.read_text()).get("provider_recovery") or {}
    except (OSError, ValueError, AttributeError):
        return 0
    return ledger.get("timeout_credit_seconds", 0) + ledger.get("operator_pause_seconds", 0)


class GameEnvironment(BaseEnvironment):
    def __init__(self, *args, bindings, **kwargs):
        self.binding_path = Path(bindings)
        self.managed = None
        self.model_active = False
        super().__init__(*args, **kwargs)

    @staticmethod
    def type():
        return "gamecua"

    @property
    def capabilities(self):
        return EnvironmentCapabilities(mounted=True)

    @classmethod
    def resource_capabilities(cls):
        return EnvironmentResourceCapabilities(cpu_limit=True, memory_limit=True)

    def _validate_definition(self):
        self.binding = json.loads(self.binding_path.read_text())
        self.case = json.loads((self.environment_dir / "case.json").read_text())

    async def start(self, force_build):
        root = self.trial_paths.trial_dir.parent / ".private" / self.trial_paths.trial_dir.name
        self.managed = Environment(root)
        mounts = []
        for mount in self._mounts:
            source = Path(mount["source"])
            source.mkdir(parents=True, exist_ok=True)
            mounts.append((source, mount["target"]))
        await asyncio.to_thread(
            self.managed.create,
            self.binding["installation"],
            self.binding["snapshot"],
            image=self.case["image"],
            cpus=2,
            memory="2048m",
            steam_environment=self.binding.get("steam_environment"),
            mounts=mounts,
        )
        await asyncio.to_thread(
            docker,
            "exec",
            "-u",
            "root",
            self.managed.meta["container"],
            "sh",
            "-c",
            "mkdir -p /tests /logs/agent /logs/verifier /logs/artifacts && chmod 777 /tests",
        )
        configuration = self.environment_dir / "configuration"
        await self.upload_dir(configuration, "/work/configuration")
        write_json(self.managed.root / "work/harbor-case.json", self.case)
        if self.case["game_id"] == "slay-the-spire":
            await asyncio.to_thread(
                self.managed.exec,
                [
                    "python",
                    "-c",
                    "from gamecua.games.steam.preparation import start_cached_client; start_cached_client()",
                ],
            )
        await asyncio.to_thread(
            self.managed.exec,
            [
                "python",
                "-m",
                "gamecua.harbor.readiness",
                "--game",
                "/work/configuration/games/game.json",
                "--output",
                "/state/readiness",
            ],
        )
        if self.case["game_id"] == "slay-the-spire":
            await asyncio.to_thread(
                self.managed.exec,
                [
                    "python",
                    "-c",
                    "from gamecua.games.steam.preparation import stop_client; stop_client()",
                ],
            )
        self.logger.info("Private game readiness passed; observer available through env-connect")

    async def cancel(self):
        if not self.managed or not self.managed.meta:
            return
        execution = self.managed.root / "private/execution.json"
        for _ in range(20):
            if execution.exists():
                break
            if not self.managed.meta.get("trial"):
                return
            await asyncio.sleep(0.25)
        if not execution.exists() or not json.loads(execution.read_text()).get("running"):
            return
        trial = self.managed.root / "work/trial"
        if trial.exists():
            (trial / "STOP").touch(exist_ok=True)
        else:
            await asyncio.to_thread(
                self.managed.exec, ["kill", "-TERM", str(json.loads(execution.read_text())["pid"])]
            )
        for _ in range(150):
            if not json.loads(execution.read_text()).get("running"):
                return
            await asyncio.sleep(0.5)
        await asyncio.to_thread(
            self.managed.exec, ["kill", "-TERM", str(json.loads(execution.read_text())["pid"])]
        )
        for _ in range(20):
            if not json.loads(execution.read_text()).get("running"):
                return
            await asyncio.sleep(0.5)
        raise RuntimeError("Cancellation did not settle; cleanup will stop the environment")

    async def stop(self, delete):
        if not self.managed or not self.managed.meta:
            return
        try:
            await self.cancel()
            root = self.managed.root / "work/trial"
            if (root / "trial.json").exists():
                await asyncio.to_thread(
                    self.managed.exec, ["python", "-m", "gamecua.harbor.verification"]
                )
        except RuntimeError:
            pass
        finally:
            await asyncio.to_thread(self.managed.clean if delete else self.managed.stop)

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        if self.model_active:
            raise PermissionError("Shell execution is outside the evaluated model interface")
        args = ["docker", "exec"]
        if user or self.default_user:
            args += ["-u", str(user or self.default_user)]
        if cwd:
            args += ["-w", cwd]
        args += [self.managed.meta["container"], "sh", "-c", command]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_sec or 120)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        return ExecResult(
            stdout=stdout.decode(), stderr=stderr.decode(), return_code=process.returncode
        )

    async def upload_file(self, source_path, target_path):
        await asyncio.to_thread(
            docker, "cp", str(source_path), f"{self.managed.meta['container']}:{target_path}"
        )

    async def upload_dir(self, source_dir, target_dir):
        await self.exec("mkdir -p " + shlex.quote(target_dir), user="root")
        await asyncio.to_thread(
            docker,
            "cp",
            str(Path(source_dir)) + "/.",
            f"{self.managed.meta['container']}:{target_dir}",
        )

    async def download_file(self, source_path, target_path):
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            docker, "cp", f"{self.managed.meta['container']}:{source_path}", str(target_path)
        )

    async def download_dir(self, source_dir, target_dir):
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            docker, "cp", f"{self.managed.meta['container']}:{source_dir}/.", str(target_dir)
        )


class GameAgent(BaseAgent):
    @staticmethod
    def name():
        return "gamecua-vision"

    def version(self):
        return VERSION

    async def setup(self, environment):
        managed = environment.managed
        launch = asyncio.create_task(
            asyncio.to_thread(
                managed.trial,
                environment.environment_dir / "configuration/trials/trial.json",
                environment.case["total_seconds"],
                catalog=environment.environment_dir / "configuration",
                start_gate="/state/harbor-start",
            )
        )
        try:
            await asyncio.shield(launch)
            ready = managed.root / "private/harbor-start.ready"
            status = managed.root / "private/execution.json"
            while not ready.exists():
                if status.exists() and not json.loads(status.read_text()).get("running"):
                    raise RuntimeError("Trial preparation failed before gameplay")
                await asyncio.sleep(0.5)
        except BaseException:
            try:
                await asyncio.shield(launch)
            finally:
                await asyncio.shield(environment.cancel())
            raise

    async def run(self, instruction, environment, context):
        managed = environment.managed
        environment.model_active = True
        try:
            (managed.root / "private/harbor-start").touch()
            status = managed.root / "private/execution.json"
            started = time.monotonic()
            record = managed.root / "work/trial/trial.json"
            while True:
                if status.exists():
                    state = json.loads(status.read_text())
                    if not state.get("running"):
                        break
                guard = environment.case["total_seconds"] + 150 + recovery_shift(record)
                if time.monotonic() - started > guard:
                    raise TimeoutError("Trial worker exceeded its lifecycle guard")
                await asyncio.sleep(0.5)
            record = managed.root / "work/trial/trial.json"
            context.metadata = {
                "kind": environment.case["kind"],
                "case_identity": environment.case["identity"],
                "trial_id": json.loads(record.read_text())["id"] if record.exists() else None,
                "gameplay_budget": environment.case["total_seconds"],
                "worker_exit": state.get("exit"),
            }
            write_json(
                self.logs_dir / "execution.json",
                {
                    "exit": state.get("exit"),
                    "gameplay_budget": environment.case["total_seconds"],
                    "kind": environment.case["kind"],
                },
            )
        except BaseException:
            await asyncio.shield(environment.cancel())
            raise
        finally:
            environment.model_active = False
