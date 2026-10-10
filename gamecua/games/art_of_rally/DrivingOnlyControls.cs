// Opt-in development control restriction; automatic recovery and native timing remain unchanged.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using HarmonyLib;
using UnityEngine;

[BepInPlugin("org.touchstone.artofrally.drivingonly", "Art of Rally Driving Only Controls", "0.1.0")]
public sealed class DrivingOnlyControls : BaseUnityPlugin
{
    const string Policy = "art-of-rally-driving-only-v1";
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    static Assembly game;

    [Serializable]
    public sealed class Ready
    {
        public string policy = Policy;
        public string binding;
        public string[] patches;
    }

    void Awake()
    {
        if (Environment.GetEnvironmentVariable("GAMECUA_RALLY_CONTROL_POLICY") != Policy) return;
        game = Assembly.Load("Assembly-CSharp");
        var patcher = new Harmony("org.touchstone.artofrally.drivingonly");
        var installed = new List<string>();
        foreach (string target in new [] {"PauseScreen.RecoverCar", "PauseScreen.ResetCar", "PauseScreen.Restart", "ShortcutManager.DoAction", "PauseScreen.UpdateMe", "PauseScreen.PauseStage"})
        {
            string[] parts = target.Split(new char[] {'.'});
            bool found = false;
            string prefix = parts[1] == "UpdateMe" || parts[1] == "PauseStage" ? "AllowMenu" : "BlockManualReset";
            foreach (MethodInfo method in game.GetType(parts[0], true).GetMethods(Flags | BindingFlags.DeclaredOnly))
                if (method.Name == parts[1])
                {
                    patcher.Patch(method, prefix: new HarmonyMethod(typeof(DrivingOnlyControls), prefix));
                    found = true;
                }
            if (!found) throw new MissingMethodException(target);
            installed.Add(target);
        }
        string directory = Environment.GetEnvironmentVariable("GAMECUA_RALLY_PAUSE");
        File.WriteAllText(Path.Combine(directory, "control-policy.json"), JsonUtility.ToJson(new Ready {
            binding = Environment.GetEnvironmentVariable("GAMECUA_RALLY_BINDING"), patches = installed.ToArray()
        }));
        Logger.LogInfo("Development driving-only controls installed; result and next-stage navigation remain enabled");
    }

    static bool BlockManualReset()
    {
        return false;
    }

    static bool AllowMenu()
    {
        object ev = game.GetType("GameEntryPoint", true).GetProperty("EventManager", Flags).GetValue(null, null);
        if (ev == null) return false;
        int status = Convert.ToInt32(ev.GetType().GetField("status", Flags).GetValue(ev));
        return status >= 5 && status <= 7;
    }
}
