// Real Harmony patches with synthetic native methods exercise Mono setter inlining.
using System;
using System.Reflection;
using UnityEngine;

public static class RecoveryHookDriver
{
    public static void Main(string[] args)
    {
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_OBSERVER", args[0]);
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_BINDING", "synthetic-hook-order");
        var ev = new EventManager();
        GameEntryPoint.EventManager = ev;
        for (int i = 0; i < 5; i++)
            GameModeManager.rally.StageList[i] = new Stage {Name = "stage-" + i, SceneConstant = i.ToString()};
        for (int i = 0; i < 6; i++) ev.outOfBoundsManager._cachedWaypoints[i] = new Vector3(i * 2);
        typeof(CoverageObserver).GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(new CoverageObserver(), null);
        var route = ev.outOfBoundsManager;
        typeof(OutOfBoundsManager).GetMethod("Start").Invoke(route, null);
        var physics = typeof(OutOfBoundsManager).GetMethod("FixedUpdate");
        physics.Invoke(route, null);
        ev.status = 3;
        route.recoverOnPhysics = true;
        physics.Invoke(route, null);
        physics.Invoke(route, null);
        typeof(OutOfBoundsManager).GetMethod("SetResettingInProgress").Invoke(route, new object[] {false});
        route.recoverOnPhysics = false;
        physics.Invoke(route, null);
    }
}
