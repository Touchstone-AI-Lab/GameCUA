GSSequence <- 0;
GSGenerationFile <- "gs-" + GSNonce + "-generation.txt";
GSPreviousGeneration <- FileToString(GSGenerationFile);
GSGeneration <- GSPreviousGeneration != null ? GSPreviousGeneration.tointeger() + 1 : 1;
StringToFile(GSGenerationFile, GSGeneration.tostring());
GSStats <- { kills = 0, specials = 0, heals = 0, revives = 0, shots = 0, bot_kills = 0 };
GSStatsFile <- "gs-" + GSNonce + "-stats.txt";
GSPreviousStats <- FileToString(GSStatsFile);
if (GSPreviousStats != null) {
 local values = split(GSPreviousStats, ",");
 local index = 0;
 foreach (key in ["kills", "specials", "heals", "revives", "shots", "bot_kills"]) {
  GSStats[key] = values[index++].tointeger();
 }
}
GSHuman <- function(id) {
 if (id <= 0) return false;
 local player = GetPlayerFromUserID(id);
 return player != null && player == GetListenServerHost() && player.IsSurvivor() && !IsPlayerABot(player);
}
GSJson <- function(value) {
 local kind = typeof value;
 if (kind == "null") return "null";
 if (kind == "bool") return value ? "true" : "false";
 if (kind == "integer" || kind == "float") return value.tostring();
 if (kind == "string") return "\"" + value + "\"";
 local text = "{";
 local first = true;
 foreach (key, entry in value) {
  if (!first) text += ",";
  first = false;
  text += "\"" + key + "\":" + GSJson(entry);
 }
 return text + "}";
}
GSWrite <- function(kind, extra = {}) {
 local host = GetListenServerHost();
 local alive = host != null && host.IsSurvivor() && !IsPlayerABot(host) && host.GetHealth() > 0;
 local bots = 0;
 local humans = 0;
 local player = null;
 while ((player = Entities.FindByClassname(player, "player")) != null) {
  if (player.IsSurvivor() && IsPlayerABot(player)) bots++;
  if (player.IsSurvivor() && !IsPlayerABot(player)) humans++;
 }
 local pos = host != null ? host.GetOrigin() : Vector(0, 0, 0);
 local row = {
  humans = humans, con_enable = Convars.GetFloat("con_enable"), developer = Convars.GetFloat("developer"),
  schema = 1, session = GSNonce, kind = kind, time = Time(), map = Director.GetMapName(),
  mode = Convars.GetStr("mp_gamemode"), difficulty = Convars.GetStr("z_difficulty"),
  cheats = Convars.GetFloat("sv_cheats"), human_alive = alive,
  fps_max = Convars.GetFloat("fps_max"), gpu_level = Convars.GetFloat("gpu_level"),
  aa = Convars.GetFloat("mat_antialias"), hdr = Convars.GetFloat("mat_hdr_level"), queue = Convars.GetFloat("mat_queue_mode"),
  host_timescale = Convars.GetFloat("host_timescale"), host_framerate = Convars.GetFloat("host_framerate"),
  kills = GSStats.kills, specials = GSStats.specials, heals = GSStats.heals,
  revives = GSStats.revives, shots = GSStats.shots, bot_kills = GSStats.bot_kills, bots = bots,
  x = pos.x, y = pos.y, z = pos.z, health = host != null ? host.GetHealth() : 0
 };
 foreach (key, value in extra) row[key] <- value;
 StringToFile(GSStatsFile, GSStats.kills + "," + GSStats.specials + "," + GSStats.heals + "," + GSStats.revives + "," + GSStats.shots + "," + GSStats.bot_kills);
 row.generation <- GSGeneration;
 row.sequence <- GSSequence++;
 StringToFile("gs-" + GSNonce + "-" + GSGeneration + "-" + row.sequence + ".json", GSJson(row) + "\n");
}
GSObserverScope <- {};
GSObserverScope.OnGameEvent_infected_death <- function(p) {
 if ("attacker" in p && GSHuman(p.attacker)) {
  GSStats.kills++;
  GSWrite("kill", { attacker = p.attacker, human = true });
 } else if ("attacker" in p && p.attacker > 0) {
  local player = GetPlayerFromUserID(p.attacker);
  if (player != null && player.IsSurvivor() && IsPlayerABot(player)) GSStats.bot_kills++;
 }
}
GSObserverScope.OnGameEvent_weapon_fire <- function(p) {
 if ("userid" in p && GSHuman(p.userid)) { GSStats.shots++; GSWrite("fire"); }
}
GSObserverScope.OnGameEvent_player_death <- function(p) {
 if ("attacker" in p && GSHuman(p.attacker) && "userid" in p && p.userid > 0) {
  local victim = GetPlayerFromUserID(p.userid);
  if (victim != null && NetProps.GetPropInt(victim, "m_iTeamNum") == 3) {
   GSStats.specials++;
   GSWrite("special_kill", { attacker = p.attacker, human = true });
  }
 }
 if ("userid" in p && GSHuman(p.userid)) GSWrite("human_death", { human = true });
}
GSObserverScope.OnGameEvent_heal_success <- function(p) {
 if ("userid" in p && GSHuman(p.userid) && "health_restored" in p && p.health_restored > 0) {
  GSStats.heals++;
  GSWrite("heal", { human = true, restored = p.health_restored });
 }
}
GSObserverScope.OnGameEvent_revive_success <- function(p) {
 if ("userid" in p && GSHuman(p.userid)) {
  GSStats.revives++;
  GSWrite("revive", { human = true });
 }
}
GSObserverScope.OnGameEvent_map_transition <- function(p) { GSWrite("chapter_complete"); }
GSObserverScope.OnGameEvent_finale_start <- function(p) { GSWrite("finale_start"); }
GSObserverScope.OnGameEvent_finale_win <- function(p) { GSWrite("campaign_complete"); }
GSObserverScope.OnGameEvent_mission_lost <- function(p) { GSWrite("mission_lost"); }
GSObserve <- SpawnEntityFromTable("logic_script", { targetname = "gamecua_read_only_observer" });
GSObserve.ValidateScriptScope();
GSObserve.GetScriptScope().GSObserveThink <- function() {
 if (GetListenServerHost() != null) ::__CollectGameEventCallbacks(::GSObserverScope);
 ::GSWrite("sample");
 return 0.25;
}
AddThinkToEnt(GSObserve, "GSObserveThink");
GSWrite("ready");
