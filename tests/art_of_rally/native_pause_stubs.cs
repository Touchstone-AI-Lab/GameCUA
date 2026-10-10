// Synthetic native API doubles; never game evidence or acceptance fixtures.
using System;
using System.Web.Script.Serialization;

namespace BepInEx
{
    public class BaseUnityPlugin { }
    public class BepInPlugin : Attribute
    {
        public BepInPlugin(string id, string name, string version) { }
    }
}

namespace UnityEngine
{
    public static class Time
    {
        public static float time;
        public static float timeScale = 1;
        public static float fixedTime;
        public static float fixedDeltaTime = 1f / 60f;
        public static float maximumDeltaTime = 1;
    }
    public static class JsonUtility
    {
        public static string ToJson(object value) { return new JavaScriptSerializer().Serialize(value); }
        public static T FromJson<T>(string value) { return new JavaScriptSerializer().Deserialize<T>(value); }
    }
}

public class Hud
{
    public void ShowStageHud() { }
}

public class EventManager
{
    public int status = 3;
    public int toggles;
    public Hud hudManager = new Hud();
    public void ToggleStagePaused(object unused)
    {
        toggles++;
        status = status == 3 ? 4 : 3;
        UnityEngine.Time.timeScale = status == 4 ? 0 : 1;
    }
    public void Update() { }
}

public static class GameEntryPoint
{
    public static EventManager EventManager { get; set; }
}
