"""Official Steam client: QR login, game installation and cached-session checks inside an environment."""

import fcntl
import io
import json
import os
import re
import signal
import subprocess
import tarfile
import time
from pathlib import Path

import httpx
import qrcode
from PIL import ImageGrab

from ...storage import write_json

BOOTSTRAP = "https://repo.steampowered.com/steam/archive/beta/steam_1.0.0.79.tar.gz"
STATE = Path("/state")
CLIENT = STATE / "home/.steam/debian-installation"
QR = re.compile(r"^https://s\.team/q/[0-9A-Za-z/_%\-]+$")


def clear():
    for path in STATE.glob("steam-qr*.png"):
        path.unlink(missing_ok=True)


def update(status, **values):
    write_json(STATE / "steam.json", {"status": status, "challenge": False, **values})


def install():
    if (CLIENT / "steam.sh").exists():
        return
    response = httpx.get(BOOTSTRAP, follow_redirects=True, timeout=120)
    response.raise_for_status()
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        nested = archive.extractfile("steam-launcher/bootstraplinux_ubuntu12_32.tar.xz").read()
    CLIENT.mkdir(parents=True, mode=0o700)
    with tarfile.open(fileobj=io.BytesIO(nested), mode="r:xz") as archive:
        archive.extractall(CLIENT, filter="data")


def logged_in(started, offset=0):
    logins = CLIENT / "config/loginusers.vdf"
    connection = CLIENT / "logs/connection_log.txt"
    if not connection.exists():
        return False
    text = logins.read_text(errors="replace") if logins.exists() else ""
    with connection.open("rb") as file:
        file.seek(offset if connection.stat().st_size >= offset else 0)
        recent = file.read().decode(errors="replace")
    active = connection.stat().st_mtime >= started and bool(
        re.search(
            r"LogOnResponse[^\n]*(?:OK|EResult 1\b)|\[Logged On,",
            recent[-16384:],
        )
    )
    if not active:
        return False
    if '"AccountName"' in text and re.search(r'"MostRecent"\s+"1"', text):
        return True
    config = CLIENT / "config/config.vdf"
    accounts = re.findall(r"\[Logged On,[^\n]*\[U:1:(\d+)\]", recent)
    if not config.exists() or not accounts:
        return False
    persisted = re.findall(r'"SteamID"\s+"(\d+)"', config.read_text(errors="replace"))
    return str(76561197960265728 + int(accounts[-1])) in persisted


CLIENT_LAYOUTS = (("ubuntu12_32", "ubuntu12_64"), ("steamrt64",))
CONNECTION_STATES = re.compile(
    r"\[(Logged On|Logged Off|Connecting|Connected|Disconnected|Not Connected)(?:,|\])"
)


def owned_clients(proc, directories):
    """List the live official client processes of this user from one client layout."""
    executables = [CLIENT / directory / "steam" for directory in directories]
    clients = []
    for path in proc.iterdir():
        try:
            if not path.name.isdigit() or path.stat().st_uid != os.getuid():
                continue
            if not any(
                target.is_file() and os.path.samefile(path / "exe", target)
                for target in executables
            ):
                continue
            stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if stat[0] != "Z":
                clients.append({"pid": int(path.name), "start_ticks": stat[19]})
        except (OSError, IndexError):
            continue
    return clients


def client_identity(proc=Path("/proc")):
    """Return the newest running official client, preferring the older client layout."""
    for directories in CLIENT_LAYOUTS:
        clients = owned_clients(proc, directories)
        if clients:
            return max(clients, key=lambda client: int(client["start_ticks"]))
    return None


def verify_cached_session():
    """Return the running client if its connection log still ends logged on."""
    current = client_identity()
    connection = CLIENT / "logs/connection_log.txt"
    text = connection.read_text(errors="replace")[-16384:] if connection.exists() else ""
    if not current or CONNECTION_STATES.findall(text)[-1:] != ["Logged On"]:
        raise RuntimeError("The verified Steam session changed or is no longer logged in")
    return current


def installed_app(app_id):
    manifest = CLIENT / f"steamapps/appmanifest_{app_id}.acf"
    if not manifest.exists():
        return None
    text = manifest.read_text(errors="replace")
    values = dict(re.findall(r'"(\w+)"\s+"([^"\n]*)"', text))
    if values.get("StateFlags") != "4" or values.get("appid") != str(app_id):
        return None
    name = values.get("installdir", "")
    directory = (CLIENT / "steamapps/common" / name).resolve()
    if not name or not directory.is_dir():
        return None
    return {"directory": str(directory), "build_id": values.get("buildid"), "app_id": app_id}


def await_game(app_id, deadline):
    if not installed_app(app_id):
        subprocess.Popen(
            [str(CLIENT / "steam.sh"), f"steam://install/{app_id}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    while time.monotonic() < deadline:
        if (STATE / "CANCEL_STEAM").exists():
            update("cancelled")
            return
        installation = installed_app(app_id)
        if installation:
            write_json(STATE / "steam-prepared.local.json", installation)
            update(
                "ready",
                app_id=app_id,
                build_id=installation["build_id"],
                launch_verification="skipped",
            )
            return
        update(
            "awaiting_installation",
            app_id=app_id,
            message="Official client install confirmation may require explicit developer input",
        )
        time.sleep(2)
    update(
        "expired", app_id=app_id, reason="Installation did not finish within preparation timeout"
    )


def prepare(app_id=646570, timeout=900):
    lock = (STATE / "steam-preparation.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    clear()
    (STATE / "CANCEL_STEAM").unlink(missing_ok=True)
    update("starting")
    process = None
    started = time.time()
    logins = CLIENT / "config/loginusers.vdf"
    if logins.exists():
        logins.write_text(re.sub(r'("WantsOfflineMode"\s+)"1"', r'\1"0"', logins.read_text()))
    connection = CLIENT / "logs/connection_log.txt"
    offset = connection.stat().st_size if connection.exists() else 0
    try:
        install()
        with (STATE / "steam-client.private.log").open("a") as log:
            process = subprocess.Popen(
                [
                    "dbus-run-session",
                    "--",
                    str(CLIENT / "steam.sh"),
                    "-cef-disable-gpu",
                    "-cef-force-opaque-backgrounds",
                ],
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        write_json(STATE / "steam-process.local.json", {"pid": process.pid})
        deadline = time.monotonic() + timeout
        last_qr = ""
        refreshed_at = None
        while time.monotonic() < deadline:
            if (STATE / "CANCEL_STEAM").exists():
                update("cancelled")
                return
            if logged_in(started, offset):
                clear()
                update("authenticated", app_id=app_id)
                await_game(app_id, deadline)
                return
            private_log = STATE / "steam-client.private.log"
            recent = private_log.read_text(errors="replace")[-65536:]
            if "fatal error: failed to load steamui.so" in recent.lower():
                update("failed", reason="Official client cannot load its runtime dependencies")
                return
            subprocess.run(
                ["xdotool", "search", "--name", "^Steam$", "windowmap"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            image = ImageGrab.grab(xdisplay=":99")
            output = io.BytesIO()
            image.save(output, format="PNG")
            decoded = (
                subprocess.run(
                    ["zbarimg", "-q", "--raw", "-"], input=output.getvalue(), capture_output=True
                )
                .stdout.decode(errors="replace")
                .strip()
            )
            if QR.fullmatch(decoded):
                if decoded != last_qr:
                    refreshed_at = time.time()
                    last_qr = decoded
                temp = STATE / "steam-qr.next.png"
                qrcode.make(decoded).save(temp)
                temp.replace(STATE / "steam-qr.png")
                update(
                    "waiting_for_scan",
                    challenge=True,
                    app_id=app_id,
                    purpose="Authorize the official Steam client; no separate download helper",
                    refreshed_at=refreshed_at,
                )
            else:
                clear()
                update("waiting_for_client", app_id=app_id)
            if process.poll() is not None:
                restart_deadline = min(deadline, time.monotonic() + 30)
                while time.monotonic() < restart_deadline and not client_identity():
                    time.sleep(1)
                if not client_identity():
                    update("failed", reason="Official client exited; inspect private local logs")
                    return
            time.sleep(2)
        update("expired", app_id=app_id)
    except Exception as exc:
        update("failed", reason="Steam preparation failed", error_type=type(exc).__name__)
        raise RuntimeError("Steam preparation failed; private details are not exported") from None
    finally:
        clear()
        status = json.loads((STATE / "steam.json").read_text())["status"]
        if status not in ("authenticated", "ready") and process:
            try:
                subprocess.run(
                    [str(CLIENT / "steam.sh"), "-shutdown"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


def start_cached_client(timeout=120):
    started = time.time()
    logins = CLIENT / "config/loginusers.vdf"
    if logins.exists():
        logins.write_text(re.sub(r'("WantsOfflineMode"\s+)"1"', r'\1"0"', logins.read_text()))
    connection = CLIENT / "logs/connection_log.txt"
    offset = connection.stat().st_size if connection.exists() else 0
    with (STATE / "steam-client.private.log").open("a") as log:
        subprocess.Popen(
            [
                str(CLIENT / "steam.sh"),
                "-silent",
                "-cef-disable-gpu",
                "-cef-force-opaque-backgrounds",
            ],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    for _ in range(timeout):
        if logged_in(started, offset):
            update("authenticated", challenge=False)
            return
        time.sleep(1)
    raise RuntimeError("Official Steam client requires renewed authorization or could not start")


def stop_client(timeout=60):
    subprocess.run(
        [str(CLIENT / "steam.sh"), "-shutdown"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if subprocess.run(
            ["pgrep", "-u", str(os.getuid()), "-x", "steam"], capture_output=True
        ).returncode:
            return
        time.sleep(0.5)
    raise RuntimeError("Official client did not stop before restart")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", type=int, default=646570)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    prepare(args.app_id, args.timeout)


if __name__ == "__main__":
    main()
