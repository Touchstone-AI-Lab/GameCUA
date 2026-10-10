// Synthetic native calls exercise real Harmony restrictions and unrestricted stage navigation.
using System;
using System.Reflection;

public static class DrivingOnlyDriver
{
    static void Invoke(object instance, string method, Type[] types, params object[] args)
    {
        instance.GetType().GetMethod(method, types).Invoke(instance, args);
    }
    static void Check(bool value)
    {
        if (!value) throw new Exception("Driving-only control invariant failed");
    }
    public static void Main(string[] args)
    {
        bool enabled = args[1] == "enabled";
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_CONTROL_POLICY", enabled ? "art-of-rally-driving-only-v1" : "");
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_PAUSE", args[0]);
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_BINDING", "synthetic-controls");
        var ev = new EventManager();
        GameEntryPoint.EventManager = ev;
        typeof(DrivingOnlyControls).GetMethod("Awake", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(new DrivingOnlyControls(), null);
        var menu = new PauseScreen();
        var shortcuts = new ShortcutManager();
        var navigation = new NativeStageNavigation();
        for (int stage = 0; stage < 5; stage++)
        {
            foreach (int status in new [] {0, 1, 2, 3, 4, 5, 6, 7, 8, -1, 99})
            {
                ev.status = status;
                int before = menu.menuCalls;
                Invoke(menu, "UpdateMe", Type.EmptyTypes);
                Invoke(menu, "PauseStage", Type.EmptyTypes);
                Check(menu.menuCalls == before + (!enabled || (status >= 5 && status <= 7) ? 2 : 0));
                before = menu.resetCalls;
                Invoke(menu, "RecoverCar", Type.EmptyTypes);
                Invoke(menu, "RecoverCar", new [] {typeof(float)}, 5f);
                Invoke(menu, "Restart", Type.EmptyTypes);
                Check(menu.resetCalls == before + (enabled ? 0 : 3));
                before = ev.outOfBoundsManager.resets;
                typeof(PauseScreen).GetMethod("ResetCar").Invoke(null, null);
                Invoke(shortcuts, "DoAction", Type.EmptyTypes);
                Check(ev.outOfBoundsManager.resets == before + (enabled ? 0 : 2));
            }
            int resets = ev.outOfBoundsManager.resets;
            Invoke(ev.outOfBoundsManager, "AutomaticRecovery", Type.EmptyTypes);
            Check(ev.outOfBoundsManager.resets == resets + 1);
            ev.status = 3;
            Invoke(navigation, "TogglePause", Type.EmptyTypes);
            Check(ev.status == 4);
            Invoke(navigation, "TogglePause", Type.EmptyTypes);
            Check(ev.status == 3);
            ev.status = 5;
            Invoke(navigation, "Results", Type.EmptyTypes);
            Check(ev.status == 6);
            Invoke(navigation, "Continue", Type.EmptyTypes);
            Check(ev.status == 7);
            Invoke(navigation, "NextStage", Type.EmptyTypes);
            Check(ev.status == 2 && GameModeManager.rally.CurrentStageIndex == stage + 1);
        }
        Console.WriteLine("Driving-only controls and five stage transitions passed: " + args[1]);
    }
}
