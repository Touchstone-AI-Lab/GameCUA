// Read-only development observer; it never changes native game fields or sends inputs.
using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Collections.Generic;
using BepInEx;
using HarmonyLib;
using UnityEngine;

[BepInPlugin("org.touchstone.artofrally.coverage", "Art of Rally Coverage Observer", "0.1.0")]
public sealed class CoverageObserver : BaseUnityPlugin
{
    static readonly BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    static StreamWriter output;
    static int sequence;
    static Assembly game;
    static string binding;
    static int tick;
    static bool loadingEvents;
    static long ownerCounter;
    static readonly Dictionary<object, Owner> owners = new Dictionary<object, Owner>();

    sealed class Owner
    {
        public string id;
        public int stage;
    }

    public sealed class GateState
    {
        public bool player;
        public bool eligible;
        public int status;
    }

    [Serializable]
    public sealed class Geometry
    {
        public Vector3[] points;
        public int start;
        public int last;
        public bool forward;
    }

    [Serializable]
    public sealed class Coverage
    {
        public string observer = loadingEvents ? "art-of-rally-coverage-observer-2" : "art-of-rally-coverage-observer-1";
        public string eventKind;
        public string geometry;
        public string geometry_hash;
        public string route_owner;
        public int route_stage_index;
        public int tick;
        public bool gate_player;
        public bool gate_accepted;
        public int gate_before_status;
    }
    string auditPath;
    float auditAt;

    [Serializable]
    public sealed class StageIdentity
    {
        public int area;
        public string stage;
        public string scene;
        public string weather;
        public bool forward;
    }

    [Serializable]
    public sealed class Sample
    {
        [NonSerialized] public Coverage coverage;
        public int schema_version = 1;
        public string sampling = "all_native_physics_and_boundaries_v1";
        public string binding;
        public int sequence;
        public string source;
        public double utc_seconds;
        public double monotonic_seconds;
        public float unity_time;
        public float delta_time;
        public float fixed_time;
        public float maximum_delta_time;
        public int status;
        public string mode;
        public string stage;
        public string scene;
        public string weather;
        public bool forward;
        public int stage_index;
        public int stage_count;
        [NonSerialized] public StageIdentity[] stage_plan;
        public string vehicle;
        public int current;
        public int start;
        public int last;
        public int count;
        public bool resetting;
        public bool debug;
        public bool finish_gate;
        public string stage_time;
        public string penalties;
        public string detected;
        public string terminal_damage;
        public long result_time_ms;
        public double result_time_seconds_native;
        public bool player_retired;
        public Vector3 position;
        public Vector3 velocity;
        public string error;
    }

    static object Field(object value, string name)
    {
        if (value == null) throw new InvalidOperationException("Missing native instance: " + name);
        FieldInfo f = value.GetType().GetField(name, Flags);
        if (f == null) throw new MissingFieldException(value.GetType().Name, name);
        return f.GetValue(value);
    }

    static string Serialize(Sample sample)
    {
        string raw = JsonUtility.ToJson(sample);
        string coverage = sample.coverage == null ? "null" : JsonUtility.ToJson(sample.coverage).Replace("\"eventKind\":", "\"event\":");
        string plan = sample.stage_plan == null ? "null" : "[" + String.Join(",", Array.ConvertAll(sample.stage_plan, stage => JsonUtility.ToJson(stage))) + "]";
        return raw.Substring(0, raw.Length - 1) + ",\"coverage\":" + coverage + ",\"stage_plan\":" + plan + "}";
    }

    public static long ResultMilliseconds(object value, out double seconds)
    {
        if (value == null) throw new InvalidOperationException("Missing native result time");
        seconds = Convert.ToDouble(value, CultureInfo.InvariantCulture);
        if (Double.IsNaN(seconds) || Double.IsInfinity(seconds) || seconds < 0 || seconds >= Int64.MaxValue / 1000.0)
            throw new InvalidOperationException("Invalid native result time");
        return checked((long)Math.Floor(seconds * 1000.0));
    }

    static void ReadStageResult(Sample s)
    {
        Type gm = game.GetType("GameModeManager");
        s.mode = gm.GetField("GameMode",Flags).GetValue(null).ToString();
        object rally = gm.GetMethod("GetRallyDataCurrentGameMode",Flags).Invoke(null,null);
        object stage = rally.GetType().GetMethod("GetCurrentStage",Flags).Invoke(rally,null);
        s.stage_index = Convert.ToInt32(Field(rally,"CurrentStageIndex"));
        s.stage_count = Convert.ToInt32(Field(rally,"StageCount"));
        IList stages = (IList)Field(rally,"StageList");
        s.stage_plan = new StageIdentity[stages.Count];
        for (int i = 0; i < stages.Count; i++)
            s.stage_plan[i] = new StageIdentity {
                area = Convert.ToInt32(Field(stages[i],"Area")),
                stage = Field(stages[i],"Name").ToString(),
                scene = Field(stages[i],"SceneConstant").ToString(),
                weather = Field(stages[i],"Weather").ToString(),
                forward = Convert.ToBoolean(Field(stages[i],"IsForwardStage"))
            };
        s.stage = Field(stage,"Name").ToString();
        s.scene = Field(stage,"SceneConstant").ToString();
        s.weather = Field(stage,"Weather").ToString();
        s.forward = Convert.ToBoolean(Field(stage,"IsForwardStage"));
        object season = gm.GetMethod("GetSeasonDataCurrentGameMode",Flags).Invoke(null,null);
        s.vehicle = Field(Field(season,"SelectedCar"),"prefabName").ToString();
        IList drivers = (IList)Field(season,"DriverList");
        int playerCount = 0;
        foreach (object driver in drivers)
        {
            if (!Convert.ToBoolean(Field(driver,"isPlayer"))) continue;
            playerCount++;
            s.player_retired = Convert.ToBoolean(Field(driver,"hasRetiredThisStage"));
            IList results = (IList)Field(driver,"RallyResults");
            int rallyIndex = Convert.ToInt32(Field(season,"CurrentRallyIndex"));
            IList times = (IList)Field(results[rallyIndex],"StageTimes");
            int stageIndex = Convert.ToInt32(Field(rally,"CurrentStageIndex"));
            s.result_time_ms = ResultMilliseconds(times[stageIndex], out s.result_time_seconds_native);
        }
        if (playerCount != 1) throw new InvalidOperationException("Native result lacks unique player");
    }

    void Awake()
    {
        loadingEvents = Environment.GetEnvironmentVariable("GAMECUA_RALLY_LOADING_EVENTS") == "1";
        string path = Environment.GetEnvironmentVariable("GAMECUA_RALLY_OBSERVER");
        binding = Environment.GetEnvironmentVariable("GAMECUA_RALLY_BINDING");
        if (String.IsNullOrEmpty(path) || String.IsNullOrEmpty(binding)) return;
        output = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read));
        output.AutoFlush = true;
        game = Assembly.Load("Assembly-CSharp");
        auditPath = Environment.GetEnvironmentVariable("GAMECUA_RALLY_RESULT_AUDIT");
        Harmony patcher = new Harmony("org.touchstone.artofrally.coverage");
        Patch(patcher, "OutOfBoundsManager", "SetResettingInProgress", "BeforeRecovery", "AfterRecovery");
        foreach (string pair in new [] {"OutOfBoundsManager:FixedUpdate", "StageTimerManager:Update", "StageTimerManager:Reset", "StageSceneManager:SetRestartStage", "StageTimerManager:OnStageOver"})
        {
            string[] parts = pair.Split(new char[] {':'});
            MethodInfo method = AccessTools.Method(game.GetType(parts[0], true), parts[1]);
            if (method == null) throw new MissingMethodException(pair);
            patcher.Patch(method, postfix: new HarmonyMethod(typeof(CoverageObserver), "AfterNative"));
        }
        Patch(patcher, "OutOfBoundsManager", "Start", null, "AfterStart");
        Patch(patcher, "OutOfBoundsManager", "CancelCarReset", null, "AfterCancel");
        Patch(patcher, "TimingGate", "OnTriggerEnter", "BeforeGate", "AfterGate");
        Logger.LogInfo("Read-only experimental coverage observer loaded");
    }

    void Update()
    {
        if (String.IsNullOrEmpty(auditPath) || File.Exists(auditPath) || Time.realtimeSinceStartup < auditAt) return;
        auditAt = Time.realtimeSinceStartup + 1;
        try
        {
            Sample sample = new Sample();
            sample.binding = binding;
            sample.source = "DevelopmentResultAudit";
            sample.utc_seconds = (DateTime.UtcNow - new DateTime(1970,1,1)).TotalSeconds;
            sample.monotonic_seconds = (double)System.Diagnostics.Stopwatch.GetTimestamp() / System.Diagnostics.Stopwatch.Frequency;
            ReadStageResult(sample);
            if (sample.result_time_ms <= 0) return;
            using (FileStream file = new FileStream(auditPath, FileMode.CreateNew, FileAccess.Write))
            using (StreamWriter writer = new StreamWriter(file)) writer.Write(Serialize(sample));
        }
        catch (Exception e) { File.WriteAllText(auditPath + ".error", e.GetType().Name + ": " + e.Message); }
    }

    static void Patch(Harmony patcher, string type, string method, string prefix, string postfix)
    {
        MethodInfo target = AccessTools.Method(game.GetType(type, true), method);
        if (target == null) throw new MissingMethodException(type, method);
        patcher.Patch(target,
            prefix: prefix == null ? null : new HarmonyMethod(typeof(CoverageObserver), prefix),
            postfix: new HarmonyMethod(typeof(CoverageObserver), postfix));
    }

    static void AfterStart(object __instance)
    {
        Sample sample = new Sample();
        ReadStageResult(sample);
        owners[__instance] = new Owner { id = (++ownerCounter).ToString(CultureInfo.InvariantCulture), stage = sample.stage_index };
    }

    static void BeforeRecovery(object __instance, out bool __state)
    {
        __state = Convert.ToBoolean(Field(__instance, "isResettingInProgress"));
    }

    static void AfterRecovery(MethodBase __originalMethod, object __instance, bool __state)
    {
        if (!owners.ContainsKey(__instance)) return;
        bool active = Convert.ToBoolean(Field(__instance, "isResettingInProgress"));
        if (active != __state) Emit(__originalMethod, __instance, active ? "recovery_begin" : "recovery_end", null);
    }

    static void AfterCancel(MethodBase __originalMethod, object __instance)
    {
        Emit(__originalMethod, __instance, "recovery_cancel", null);
    }

    static void BeforeGate(object __instance, Collider __0, out GateState __state)
    {
        __state = new GateState();
        object ev = game.GetType("GameEntryPoint").GetProperty("EventManager", Flags).GetValue(null, null);
        if (ev == null) return;
        __state.status = Convert.ToInt32(Field(ev, "status"));
        GameObject car = (GameObject)Field(Field(ev, "playerManager"), "PlayerObject");
        __state.player = __0 != null && __0.CompareTag("Car") && __0.transform.IsChildOf(car.transform);
        __state.eligible = __state.player && (__state.status == 3 || __state.status == 4)
            && Convert.ToBoolean(Field(__instance, "isFinishGate"))
            && !Convert.ToBoolean(Field(Field(ev, "outOfBoundsManager"), "isResettingInProgress"));
    }

    static void AfterGate(MethodBase __originalMethod, object __instance, GateState __state)
    {
        Emit(__originalMethod, __instance, "sample", __state);
    }

    static void AfterNative(MethodBase __originalMethod, object __instance)
    {
        string kind = __originalMethod.DeclaringType.Name == "OutOfBoundsManager" ? "physics" : "sample";
        if (kind == "physics") tick++;
        Emit(__originalMethod, __instance, kind, null);
    }

    static void Emit(MethodBase __originalMethod, object __instance, string eventKind, GateState gate)
    {
        Sample s = new Sample();
        s.binding = binding;
        s.source = __originalMethod.DeclaringType.Name + "." + __originalMethod.Name;
        s.utc_seconds = (DateTime.UtcNow - new DateTime(1970,1,1)).TotalSeconds;
        s.monotonic_seconds = (double)System.Diagnostics.Stopwatch.GetTimestamp() / System.Diagnostics.Stopwatch.Frequency;
        s.unity_time = Time.time;
        s.delta_time = Time.deltaTime;
        s.fixed_time = Time.fixedTime;
        s.maximum_delta_time = Time.maximumDeltaTime;
        try
        {
            object ev = game.GetType("GameEntryPoint").GetProperty("EventManager", Flags).GetValue(null, null);
            if (ev == null) return;
            s.status = Convert.ToInt32(Field(ev,"status"));
            s.finish_gate = gate != null && gate.eligible && s.status >= 5;
            s.debug = Convert.ToBoolean(Field(ev,"IsDebugWin"));
            object player = Field(ev,"playerManager");
            Rigidbody body = (Rigidbody)Field(player,"playerRigidBody");
            s.position = body.position;
            s.velocity = body.velocity;
            object route = Field(ev,"outOfBoundsManager");
            if (route == null) return;
            s.current = Convert.ToInt32(Field(route,"CurrentWaypointIndex"));
            s.start = Convert.ToInt32(Field(route,"StartingWaypointIndex"));
            s.last = Convert.ToInt32(Field(route,"LastWaypointIndex"));
            s.count = Convert.ToInt32(Field(route,"NumberOfWaypoints"));
            s.resetting = Convert.ToBoolean(Field(route,"isResettingInProgress"));
            object timer = Field(ev,"stageTimerManager");
            s.stage_time = Field(timer,"StageTime").ToString();
            s.penalties = Field(timer,"TotalTimePenalties").ToString();
            s.detected = Field(timer,"Detected").ToString();
            s.terminal_damage = Field(timer,"_isTerminalDamaged").ToString();
            ReadStageResult(s);
            if (!owners.ContainsKey(route) && loadingEvents && s.source == "StageTimerManager.Reset"
                && s.status == 0 && s.current == 0 && s.start == 0 && s.last == 0 && s.count == 0
                && !s.resetting && !s.debug && !s.finish_gate && s.stage_time == "0" && s.penalties == "0"
                && s.detected == "False" && s.terminal_damage == "False" && !s.player_retired && s.result_time_ms == 0)
            {
                s.coverage = new Coverage {
                    eventKind = "route_loading", geometry = "", geometry_hash = "", route_owner = "",
                    route_stage_index = s.stage_index, tick = tick, gate_before_status = -1
                };
                s.sequence = ++sequence;
                output.WriteLine(Serialize(s));
                return;
            }
            if (!owners.ContainsKey(route)) throw new InvalidOperationException("Uninitialized native route owner");
            Geometry geometry = new Geometry {
                points = (Vector3[])Field(route, "_cachedWaypoints"), start = s.start, last = s.last,
                forward = Convert.ToBoolean(Field(route, "isForwardStage"))
            };
            string rawGeometry = JsonUtility.ToJson(geometry);
            string geometryHash;
            using (SHA256 hash = SHA256.Create())
                geometryHash = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(rawGeometry))).Replace("-", "").ToLowerInvariant();
            s.coverage = new Coverage {
                eventKind = eventKind, geometry = s.status == 2 ? rawGeometry : "",
                geometry_hash = geometryHash, route_owner = owners[route].id,
                route_stage_index = owners[route].stage, tick = tick,
                gate_player = gate != null && gate.player, gate_accepted = s.finish_gate,
                gate_before_status = gate == null ? -1 : gate.status
            };
        }
        catch (Exception e) { s.error = e.GetType().Name + ": " + e.Message; }
        s.sequence = ++sequence;
        output.WriteLine(Serialize(s));
    }
}
