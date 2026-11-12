"""Read-only native base-game checkpoints through the official game's local tuner channel."""

import logging
import socket
import struct
import time

QUERY = r"""
local ok,err=pcall(function()
 local id=Game.GetLocalPlayer()
 local p=Players[id]
 if p==nil then error('Missing native local player') end
 local c=PlayerConfigurations[id]
 local difficulty=GameInfo.Difficulties[c:GetHandicapTypeID()]
 local era=GameInfo.Eras[GameConfiguration.GetStartEra()]
 local winner,victory=Game.GetWinningTeam()
 local victoryRow=victory~=nil and GameInfo.Victories[victory] or nil
 local cities=0
 for _ in p:GetCities():Members() do cities=cities+1 end
 print('GBASE_CONFIG|'..c:GetCivilizationTypeName()..'|'..tostring(GameConfiguration.GetValue('RULESET'))..'|'..difficulty.DifficultyType..'|'..era.EraType..'|'..tostring(#PlayerManager.GetAliveMajorIDs())..'|'..tostring(#Modding.GetActiveMods()))
 for _,mod in ipairs(Modding.GetActiveMods()) do print('GBASE_MOD|'..tostring(mod.Id)) end
 print('GBASE_STATE|'..tostring(Game.GetCurrentGameTurn())..'|'..tostring(id)..'|'..tostring(p:GetTeam())..'|'..tostring(p:IsAlive())..'|'..tostring(cities)..'|'..tostring(winner==nil and -1 or winner)..'|'..(victoryRow and victoryRow.VictoryType or 'NONE'))
 for row in GameInfo.Victories() do
  if row.VictoryType~='VICTORY_DEFAULT' and Game.IsVictoryEnabled(row.VictoryType) then print('GBASE_VICTORY|'..row.VictoryType) end
 end
 for _,name in ipairs({'PROJECT_LAUNCH_EARTH_SATELLITE','PROJECT_LAUNCH_MOON_LANDING','PROJECT_LAUNCH_MARS_REACTOR','PROJECT_LAUNCH_MARS_HABITATION','PROJECT_LAUNCH_MARS_HYDROPONICS'}) do
  local row=GameInfo.Projects[name]
  if row==nil then error('Missing base-game project '..name) end
  print('GBASE_PROJECT|'..name..'|'..tostring(p:GetStats():GetNumProjectsAdvanced(row.Index)))
 end
 for row in GameInfo.Technologies() do if p:GetTechs():HasTech(row.Index) then print('GBASE_TECH|'..row.TechnologyType) end end
 for _,city in p:GetCities():Members() do
  print('GBASE_CITY|'..tostring(city:GetID())..'|'..tostring(city:GetOwner()))
  for row in GameInfo.Buildings() do
   if city:GetBuildings():HasBuilding(row.Index) then print('GBASE_BUILDING|'..tostring(city:GetID())..'|'..tostring(city:GetOwner())..'|'..row.BuildingType..'|'..tostring(city:GetBuildings():IsPillaged(row.Index))) end
  end
  for _,district in city:GetDistricts():Members() do
   local row=GameInfo.Districts[district:GetType()]
   local plot=Map.GetPlot(district:GetX(),district:GetY()):GetIndex()
   print('GBASE_DISTRICT|'..tostring(city:GetID())..'|'..tostring(city:GetOwner())..'|'..row.DistrictType..'|'..tostring(district:IsComplete())..'|'..tostring(city:GetDistricts():IsPillaged(district:GetType(),plot)))
  end
 end
 for _,unit in p:GetUnits():Members() do
  print('GBASE_UNIT|'..tostring(unit:GetID())..'|'..tostring(unit:GetOwner())..'|'..GameInfo.Units[unit:GetType()].UnitType)
 end
 print('GBASE_COMPLETE|technologies,cities,buildings,districts,units')
end)
if not ok then print('GBASE_ERROR|'..tostring(err)) end
print('GBASE_END')
"""


def parse(lines):
    """Turn the native query's printed lines into one checkpoint state."""
    rows = [line.split("|") for line in lines]
    if any(row[0] == "GBASE_ERROR" for row in rows):
        raise ValueError("Native base-game query failed")
    config = next(row[1:] for row in rows if row[0] == "GBASE_CONFIG")
    turn, player, team, alive, cities, winner, victory = next(
        row[1:] for row in rows if row[0] == "GBASE_STATE"
    )
    state = {
        "source": "official_game_read_only_tuner",
        "civilization": config[0],
        "ruleset": config[1],
        "difficulty": config[2],
        "start_era": config[3],
        "major_players": int(config[4]),
        "active_mods": int(config[5]),
        "active_mod_ids": [],
        "turn": int(turn),
        "native_player_id": int(player),
        "team_id": int(team),
        "alive": alive == "true",
        "cities": int(cities),
        "winning_team": int(winner),
        "victory_type": victory,
        "projects": {},
        "technologies": [],
        "city_inventory": [],
        "buildings": [],
        "districts": [],
        "units": [],
        "enabled_victories": [],
    }
    for kind, *part in rows:
        if kind == "GBASE_MOD":
            state["active_mod_ids"].append(part[0].lower())
        elif kind == "GBASE_PROJECT":
            state["projects"][part[0]] = int(part[1])
        elif kind == "GBASE_TECH":
            state["technologies"].append(part[0])
        elif kind == "GBASE_VICTORY":
            state["enabled_victories"].append(part[0])
        elif kind == "GBASE_CITY":
            state["city_inventory"].append({"id": int(part[0]), "owner": int(part[1])})
        elif kind == "GBASE_BUILDING":
            state["buildings"].append(
                {
                    "city": int(part[0]),
                    "owner": int(part[1]),
                    "type": part[2],
                    "pillaged": part[3] == "true",
                }
            )
        elif kind == "GBASE_DISTRICT":
            state["districts"].append(
                {
                    "city": int(part[0]),
                    "owner": int(part[1]),
                    "type": part[2],
                    "complete": part[3] == "true",
                    "pillaged": part[4] == "true",
                }
            )
        elif kind == "GBASE_UNIT":
            state["units"].append({"id": int(part[0]), "owner": int(part[1]), "type": part[2]})
    return state


class NativeChannelError(RuntimeError):
    """The local tuner connection closed or sent an unreadable frame."""


class NativeBaseGame:
    """Client for the game's read-only tuner socket on 127.0.0.1:4318."""

    def __init__(self):
        self.socket = None
        self.state_index = None

    def close(self):
        if self.socket is not None:
            self.socket.close()
        self.socket = None
        self.state_index = None

    def send(self, tag, payload):
        raw = payload.encode() + b"\x00"
        self.socket.sendall(struct.pack("<Ii", len(raw), tag) + raw)

    def receive(self):
        def exact(count):
            result = bytearray()
            while len(result) < count:
                piece = self.socket.recv(count - len(result))
                if not piece:
                    raise NativeChannelError("Native tuner channel closed")
                result.extend(piece)
            return bytes(result)

        length, tag = struct.unpack("<Ii", exact(8))
        if not 0 < length <= 1024 * 1024:
            raise NativeChannelError(f"Invalid native tuner message size: {length}, tag: {tag}")
        return tag, exact(length).rstrip(b"\x00").decode("utf-8")

    def connect(self):
        self.close()
        self.socket = socket.create_connection(("127.0.0.1", 4318), timeout=3)
        self.socket.settimeout(3)
        self.send(4, "APP:")
        self.receive()
        self.send(4, "LSQ:")
        _, raw = self.receive()
        parts = [item.strip() for item in raw.replace("\n", "\x00").split("\x00") if item.strip()]
        states = {}
        for i in range(len(parts) - 1):
            if parts[i].isdigit():
                states.setdefault(parts[i + 1], int(parts[i]))
        if "InGame" not in states:
            self.close()
            raise RuntimeError("Native read-only tuner channel has no InGame state")
        self.state_index = states["InGame"]

    def read(self):
        for attempt in range(2):
            try:
                return self.query()
            except (NativeChannelError, OSError) as error:
                self.close()
                if attempt:
                    raise
                logging.getLogger(__name__).warning(
                    "Native tuner channel reconnecting once after %s: %s",
                    type(error).__name__,
                    error,
                )

    def query(self):
        if self.socket is None:
            self.connect()
        self.send(3, "CMD:" + str(self.state_index) + ":" + QUERY)
        lines = []
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Native base-game checkpoint timed out")
            self.socket.settimeout(remaining)
            _, message = self.receive()
            if message.startswith("ERR:"):
                raise ValueError("Native base-game query rejected")
            offset = message.find("GBASE_")
            if offset < 0:
                continue
            line = message[offset:].strip()
            if line == "GBASE_END":
                return parse(lines)
            lines.append(line)
