"""Read-only native Lua 5.1 panel checks run on the licensed game's own Lua sources."""

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

GROUP_PANELS = {
    "1-1": 4,
    "1-2": 4,
    "1-3": 5,
    "1-4": 6,
    "2-1": 4,
    "2-2": 6,
    "2-3": 6,
    "2-4": 6,
    "2-5": 7,
    "2-6": 5,
    "2-7": 5,
    "2-8": 5,
    "2-9": 8,
    "3-1": 8,
    "3-2": 7,
    "3-3": 6,
    "4-1": 8,
}
BOOT = r"""
package.path='';package.cpath=''
local function noop() end
local function forbidden() error('External side effects disabled during native assessment') end
print=noop
io={open=forbidden};os={execute=forbidden,remove=forbidden,rename=forbidden}
dofile=forbidden;loadfile=forbidden
love={audio={newSource=function()return {setVolume=noop,stop=noop,play=noop}end},graphics={newImage=function()return {}end,newFont=function()return {}end},mouse={newCursor=function()return {}end},timer={getTime=function()return 0 end}}
menu={level_solve=forbidden};save=forbidden
mute=2;version='1.2.3';screenWidth=1280;screenHeight=720
require('check');require('graph/worldcolor');require('level')
JSON=require('JSON')
"""
MAP = r"""
love.filesystem={lines=function(name)
 local i=0;return function() i=i+1;return map_rows[i] end
end}
require('readcsv')
local csv_rows=ReadCSV('map.csv')
menu_panel={}
for x=1,len(csv_rows[1]) do
 menu_panel[x]={}
 for y=1,len(csv_rows) do menu_panel[x][y]=csv_rows[y][x] end
end
"""
CHECK = r"""
local out={}
for _,state in ipairs(payload.states) do
 status=nil;currentLevel=payload.group;level_lines=state.lines
 level_time={};last_panel={};select={x=1,y=3};puzzle_reveal={{[3]=0}};reveal={};gamestate='ready'
 package.loaded['level/'..currentLevel]=nil
 level.loadlevel()
 local passed={}
 for i=1,panel_cnt do passed[i]=PanelVictory(i) end
 table.insert(out,{id=state.id,passed=passed})
end
return JSON:encode({states=out,runtime=_VERSION,jit_version=jit and jit.version or 'none'})
"""


def lua_string(text):
    equals = "="
    while "]" + equals + "]" in text:
        equals += "="
    return "[" + equals + "[" + text + "]" + equals + "]"


class NativePanels:
    def __init__(self, game=None):
        game = Path(game or os.environ.get("UNDERSTAND_NATIVE_GAME", ""))
        with zipfile.ZipFile(game / "understand.exe") as archive:
            sources = {
                name[:-4]: archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith(".lua")
            }
            rows = archive.read("map.csv").decode().splitlines()
        self.metadata = {}
        self.preload = (
            "\n".join(
                f"package.preload[{json.dumps(name)}]=function() return assert(loadstring("
                f"{lua_string(source)},{json.dumps('@native/' + name + '.lua')}))() end"
                for name, source in sources.items()
            )
            + BOOT
            + f"\nlocal map_rows=JSON:decode({lua_string(json.dumps(rows))})\n"
            + MAP
        )
        runtime = os.environ.get("UNDERSTAND_LUA") or shutil.which("luajit") or "lua5.1"
        self.command = [
            runtime,
            "-e",
            "local r,w=io.read,io.write;local f=assert(loadstring(r('*a')));w(f())",
        ]

    def evaluate(self, group, states):
        payload = json.dumps({"group": group, "states": states})
        script = f"{self.preload}\nlocal payload=JSON:decode({lua_string(payload)})\n{CHECK}"
        result = subprocess.run(
            self.command, input=script.encode(), capture_output=True, timeout=90
        )
        if result.returncode:
            raise RuntimeError(
                "Native Lua assessment failed: " + result.stderr.decode(errors="replace")[:500]
            )
        decoded = json.loads(result.stdout)
        self.metadata.update({key: decoded[key] for key in ("runtime", "jit_version")})
        return decoded["states"]
