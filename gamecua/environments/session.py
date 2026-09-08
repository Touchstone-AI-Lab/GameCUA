"""In-container display, observer web page and readiness probe that the image entrypoint starts."""

import asyncio
import hashlib
import io
import json
import os
import secrets
import signal
import subprocess
import time
from pathlib import Path

from aiohttp import web
from PIL import ImageGrab

STATE = Path("/state")
WORK = Path("/work")
PAGE = r"""<!doctype html><meta charset="utf-8"><title>GameCUA environment</title>
<style>body{font:15px sans-serif;margin:16px}iframe{width:100%;border:0}pre{max-height:320px;overflow:auto;white-space:pre-wrap}#status{white-space:pre-wrap}</style><h1>GameCUA observer</h1><p id="status"></p><img id="qr" hidden width="256">
<iframe id="desktop" width="1300" height="780"></iframe>
<details><summary>Trial actions and events</summary><pre id="events"></pre></details><script>
(async()=>{let t=location.hash.slice(1);history.replaceState(null,'',location.pathname);
if(t)await fetch('/auth',{method:'POST',body:t});
document.getElementById('desktop').src='/desktop/vnc.html?autoconnect=true&resize=scale&path=%2Fwebsocket';
setInterval(async()=>{let s=await fetch('/status');if(!s.ok)return;let j=await s.json();
document.getElementById('status').textContent='Read-only desktop | '+(j.steam?.status || (j.execution?.running?'Trial running':'Ready'))+'\n'+(j.ready?.rendering?.split('\n').find(x=>x.startsWith('OpenGL renderer string:')) || '');
let q=document.getElementById('qr');q.hidden=!j.steam?.challenge;
if(!q.hidden)q.src='/steam-qr?t='+Date.now();
document.getElementById('events').textContent=JSON.stringify(await(await fetch('/events')).json(),null,2);
},2000);})();</script>"""


def state():
    result = {"display": os.environ["DISPLAY"], "read_only": True}
    for name in ("ready", "steam", "execution"):
        path = STATE / f"{name}.json"
        if path.exists():
            result[name] = json.loads(path.read_text())
    return result


def events():
    rows = []
    for root in WORK.glob("*/trial.json"):
        trial = json.loads(root.read_text())
        steps = sorted(root.parent.glob("episodes/*/segments/*/[0-9]*.json"))
        rows.append(
            {
                "trial": root.parent.name,
                "state": trial,
                "latest_observation": str(
                    max(
                        root.parent.glob("episodes/*/segments/*/*_before.png"),
                        key=lambda p: p.stat().st_mtime,
                    ).relative_to(WORK)
                )
                if list(root.parent.glob("episodes/*/segments/*/*_before.png"))
                else None,
                "events": [
                    json.loads(line)
                    for line in (root.parent / "events.jsonl").read_text().splitlines()[-30:]
                ]
                if (root.parent / "events.jsonl").exists()
                else [],
                "steps": [
                    {"path": str(p.relative_to(WORK)), "record": json.loads(p.read_text())}
                    for p in steps[-8:]
                ],
            }
        )
    return rows


async def handle(request):
    token = (STATE / "access-token").read_text().strip()
    cookie_name = "gamecua-" + hashlib.sha256(token.encode()).hexdigest()[:12]
    if request.path == "/auth" and request.method == "POST":
        if not secrets.compare_digest(await request.text(), token):
            raise web.HTTPForbidden()
        response = web.Response(text="Authorized")
        response.set_cookie(cookie_name, token, httponly=True, samesite="Strict")
        return response
    if request.path == "/":
        return web.Response(
            text=PAGE, content_type="text/html", headers={"Cache-Control": "no-store"}
        )
    if not secrets.compare_digest(request.cookies.get(cookie_name, ""), token):
        raise web.HTTPForbidden()
    headers = {"Cache-Control": "no-store"}
    if request.path == "/status":
        return web.json_response(state(), headers=headers)
    if request.path == "/events":
        return web.json_response(events(), headers=headers)
    if request.path == "/screenshot":
        image = ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
        output = io.BytesIO()
        image.save(output, format="PNG")
        return web.Response(body=output.getvalue(), content_type="image/png", headers=headers)
    if request.path == "/steam-qr":
        path = STATE / "steam-qr.png"
        if not path.exists():
            raise web.HTTPNotFound()
        return web.Response(body=path.read_bytes(), content_type="image/png", headers=headers)
    if request.path == "/websocket":
        ws = web.WebSocketResponse(protocols=("binary",))
        await ws.prepare(request)
        reader, writer = await asyncio.open_connection("127.0.0.1", 5900)

        async def incoming():
            async for message in ws:
                if message.type == web.WSMsgType.BINARY:
                    writer.write(message.data)
                    await writer.drain()

        async def outgoing():
            while data := await reader.read(65536):
                await ws.send_bytes(data)

        tasks = [asyncio.create_task(incoming()), asyncio.create_task(outgoing())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            writer.close()
            await ws.close()
        return ws
    if request.path.startswith("/desktop/"):
        name = request.path.removeprefix("/desktop/")
        path = (Path("/usr/share/novnc") / name).resolve()
        if not path.is_relative_to("/usr/share/novnc") or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers=headers)
    raise web.HTTPNotFound()


def probe_command(device, preset):
    if preset == "wsl-d3d12":
        return ["env", "GALLIUM_DRIVER=d3d12", "glxinfo", "-B"]
    if device:
        return ["/opt/VirtualGL/bin/vglrun", "-d", "egl0", "-c", "proxy", "glxinfo", "-B"]
    return ["glxinfo", "-B"]


def probe_accepts(name, device, preset):
    if not device:
        return True
    if not name or "llvmpipe" in name:
        return False
    if preset == "wsl-d3d12":
        return "D3D12" in name and device.casefold() in name.casefold()
    return True


def ensure_account(passwd=Path("/etc/passwd"), group=Path("/etc/group")):
    uid, gid = os.getuid(), os.getgid()
    try:
        if not any(line.split(":")[2:3] == [str(gid)] for line in group.read_text().splitlines()):
            with group.open("a") as file:
                file.write(f"host{gid}:x:{gid}:\n")
        if not any(line.split(":")[2:3] == [str(uid)] for line in passwd.read_text().splitlines()):
            with passwd.open("a") as file:
                file.write(f"host{uid}:x:{uid}:{gid}::{STATE / 'home'}:/bin/bash\n")
    except OSError:
        pass


def main():
    ensure_account()
    STATE.chmod(0o700)
    for path in (STATE / "home", STATE / "runtime"):
        path.mkdir(exist_ok=True, mode=0o700)
    (STATE / "openbox.xml").write_text(
        '<openbox_config xmlns="http://openbox.org/3.4/rc"><theme><keepBorder>no</keepBorder></theme><applications><application class="*"><decor>no</decor><position force="yes"><x>0</x><y>0</y></position></application></applications></openbox_config>'
    )
    processes = []
    for args in (
        ["Xvfb", ":99", "-screen", "0", "1280x720x24", "-nolisten", "tcp"],
        ["openbox", "--config-file", str(STATE / "openbox.xml")],
        [
            "x11vnc",
            "-display",
            ":99",
            "-localhost",
            "-nopw",
            "-forever",
            "-shared",
            "-viewonly",
            "-nosel",
            "-rfbport",
            "5900",
        ],
    ):
        if processes:
            for _ in range(100):
                if subprocess.run(["xdpyinfo"], capture_output=True).returncode == 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Display failed to become ready")
        log = (STATE / f"{args[0]}.log").open("w")
        processes.append(subprocess.Popen(args, stdout=log, stderr=log))
    device = os.getenv("GAMECUA_RENDER_DEVICE")
    preset = os.getenv("GAMECUA_GRAPHICS_PRESET")
    renderer = subprocess.run(probe_command(device, preset), capture_output=True, text=True)
    (STATE / "render-probe.json").write_text(
        json.dumps(
            {"stdout": renderer.stdout, "stderr": renderer.stderr, "exit": renderer.returncode}
        )
    )
    renderer_name = next(
        (
            line
            for line in renderer.stdout.splitlines()
            if line.startswith("OpenGL renderer string:")
        ),
        "",
    )
    if renderer.returncode or not probe_accepts(renderer_name, device, preset):
        raise RuntimeError("Requested rendering backend failed its OpenGL readiness probe")
    (STATE / "ready.json").write_text(
        json.dumps(
            {
                "resolution": [1280, 720],
                "rendering": renderer.stdout,
                "render_probe_exit": renderer.returncode,
            }
        )
    )
    (STATE / "dependencies.json").write_text(
        json.dumps(
            {
                "python": subprocess.check_output(["python", "--version"], text=True).strip(),
                "python_packages": subprocess.check_output(
                    ["python", "-m", "pip", "freeze"], text=True
                ),
                "system_packages": subprocess.check_output(["dpkg-query", "-W"], text=True),
            }
        )
    )
    app = web.Application(client_max_size=4096)
    app.router.add_route("*", "/{tail:.*}", handle)
    try:
        web.run_app(app, host="0.0.0.0", port=8080, access_log=None, print=None)
    finally:
        for process in reversed(processes):
            process.send_signal(signal.SIGTERM)
        for name in ("steam-qr.png",):
            (STATE / name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
