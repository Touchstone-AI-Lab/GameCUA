// Synthetic native APIs for observer callback verification; never game evidence.
using System;
using System.Reflection;
using System.Web.Script.Serialization;

namespace BepInEx
{
    public class BaseUnityPlugin { public Log Logger = new Log(); }
    public class Log { public void LogInfo(string value) { } }
    public class BepInPlugin : Attribute
    {
        public BepInPlugin(string id, string name, string version) { }
    }
}

#if !REAL_HARMONY
namespace HarmonyLib
{
    public class Harmony
    {
        public Harmony(string id) { }
        public void Patch(MethodInfo target, HarmonyMethod prefix = null, HarmonyMethod postfix = null) { }
    }
    public class HarmonyMethod { public HarmonyMethod(Type type, string name) { } }
    public static class AccessTools
    {
        public static MethodInfo Method(Type type, string name) { return type.GetMethod(name); }
    }
}
#endif

namespace UnityEngine
{
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float value) { x = value; y = z = 0; }
    }
    public class Transform
    {
        public Transform parent;
        public bool IsChildOf(Transform other) { return this == other || parent == other; }
    }
    public class GameObject { public Transform transform = new Transform(); }
    public class Collider
    {
        public Transform transform = new Transform();
        public string tag = "Car";
        public bool CompareTag(string value) { return tag == value; }
    }
    public class Rigidbody { public Vector3 position, velocity; }
    public static class Time
    {
        public static float time, deltaTime = 0.02f, fixedTime, maximumDeltaTime = 0.33f, realtimeSinceStartup;
    }
    public static class JsonUtility
    {
        public static string ToJson(object value)
        {
            var fields = new System.Collections.Generic.Dictionary<string, object>();
            foreach (FieldInfo field in value.GetType().GetFields())
                if (!field.IsNotSerialized && (field.FieldType.IsValueType || field.FieldType == typeof(string) || field.FieldType.IsArray))
                    fields[field.Name] = field.GetValue(value);
            return new JavaScriptSerializer().Serialize(fields);
        }
    }
}

public class Stage
{
    public int Area;
    public string Name, SceneConstant, Weather = "Rain";
    public bool IsForwardStage = true;
}
public class Rally
{
    public int CurrentStageIndex, StageCount = 5;
    public Stage[] StageList = new Stage[5];
    public Stage GetCurrentStage() { return StageList[CurrentStageIndex]; }
}
public class Car { public string prefabName = "synthetic-car"; }
public class Results { public double[] StageTimes = new double[5]; }
public class Driver
{
    public bool isPlayer = true, hasRetiredThisStage;
    public Results[] RallyResults = new [] {new Results()};
}
public class Season
{
    public int CurrentRallyIndex;
    public Car SelectedCar = new Car();
    public Driver[] DriverList = new [] {new Driver()};
}
public static class GameModeManager
{
    public static string GameMode = "synthetic-mode";
    public static Rally rally = new Rally();
    public static Season season = new Season();
    public static Rally GetRallyDataCurrentGameMode() { return rally; }
    public static Season GetSeasonDataCurrentGameMode() { return season; }
}
public class PlayerManager
{
    public UnityEngine.GameObject PlayerObject = new UnityEngine.GameObject();
    public UnityEngine.Rigidbody playerRigidBody = new UnityEngine.Rigidbody();
}
public class OutOfBoundsManager
{
    public UnityEngine.Vector3[] _cachedWaypoints = new UnityEngine.Vector3[6];
    public int StartingWaypointIndex, CurrentWaypointIndex, LastWaypointIndex = 4, NumberOfWaypoints = 6;
    public bool isResettingInProgress, isForwardStage = true;
    public void Start() { }
    public bool recoverOnPhysics;
    public int resets;
    public void FixedUpdate() { if (recoverOnPhysics) SetResettingInProgress(true); }
    public void SetResettingInProgress(bool value) { isResettingInProgress = value; }
    public void CancelCarReset() { }
    public void HardReset() { resets++; }
    public void AutomaticRecovery() { HardReset(); }
}
public class StageTimerManager
{
    public double StageTime, TotalTimePenalties;
    public bool Detected, _isTerminalDamaged;
    public void Update() { }
    public void Reset() { }
    public void OnStageOver() { }
}
public class StageSceneManager { public void SetRestartStage() { } }
public class TimingGate
{
    public bool isFinishGate = true;
    public void OnTriggerEnter(UnityEngine.Collider collider) { }
}
public class EventManager
{
    public int status = 2;
    public bool IsDebugWin;
    public PlayerManager playerManager = new PlayerManager();
    public OutOfBoundsManager outOfBoundsManager = new OutOfBoundsManager();
    public StageTimerManager stageTimerManager = new StageTimerManager();
}
public static class GameEntryPoint
{
    public static EventManager EventManager { get; set; }
}

public class PauseScreen
{
    public int menuCalls, resetCalls;
    public void UpdateMe() { menuCalls++; }
    public void PauseStage() { menuCalls++; }
    public void RecoverCar() { resetCalls++; }
    public void RecoverCar(float penalty) { resetCalls++; }
    public static void ResetCar() { GameEntryPoint.EventManager.outOfBoundsManager.HardReset(); }
    public void Restart() { resetCalls++; }
}
public class ShortcutManager
{
    public void DoAction() { GameEntryPoint.EventManager.outOfBoundsManager.HardReset(); }
}
public class NativeStageNavigation
{
    public void TogglePause() { GameEntryPoint.EventManager.status = GameEntryPoint.EventManager.status == 3 ? 4 : 3; }
    public void Results() { GameEntryPoint.EventManager.status = 6; }
    public void Continue() { GameEntryPoint.EventManager.status = 7; }
    public void NextStage() { GameModeManager.rally.CurrentStageIndex++; GameEntryPoint.EventManager.status = 2; }
}
