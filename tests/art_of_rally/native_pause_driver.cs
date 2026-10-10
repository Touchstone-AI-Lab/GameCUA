// Executes the actual bridge against synthetic states, including changes between Unity updates.
using System;
using System.IO;
using System.Reflection;
using UnityEngine;

public static class Driver
{
    static string directory;
    static NativePause bridge;
    static float fixedRemainder;
    static void Check(bool value) { if (!value) throw new Exception("Synthetic bridge assertion failed"); }
    static void Tick()
    {
        typeof(NativePause).GetMethod("LateUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(bridge, null);
    }
    static string Request(bool paused, bool transitions = true, float seconds = 0, bool abort = false)
    {
        string id = Guid.NewGuid().ToString();
        File.Delete(Path.Combine(directory, "ack.json"));
        File.WriteAllText(Path.Combine(directory, "request.json"), JsonUtility.ToJson(new NativePause.Request {
            binding = "synthetic", id = id, paused = paused, allow_transitions = transitions,
            step_seconds = seconds, abort_step = abort
        }));
        return id;
    }
    static NativePause.Ack Ack()
    {
        return JsonUtility.FromJson<NativePause.Ack>(File.ReadAllText(Path.Combine(directory, "ack.json")));
    }
    static NativePause.Step Step()
    {
        return JsonUtility.FromJson<NativePause.Step>(File.ReadAllText(Path.Combine(directory, "step.json")));
    }
    static EventManager Reset()
    {
        foreach (string name in new [] {"request.json", "ack.json", "step.json"})
            File.Delete(Path.Combine(directory, name));
        Time.time = Time.fixedTime = 100;
        Time.timeScale = 1;
        Time.fixedDeltaTime = 1f / 60f;
        Time.maximumDeltaTime = 0.5f;
        fixedRemainder = 0;
        var ev = new EventManager();
        GameEntryPoint.EventManager = ev;
        bridge = new NativePause();
        typeof(NativePause).GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(bridge, null);
        return ev;
    }
    static void Advance(float wallSeconds)
    {
        float elapsed = Math.Min(Time.maximumDeltaTime, wallSeconds) * Time.timeScale;
        Time.time += elapsed;
        fixedRemainder += elapsed;
        while (fixedRemainder >= Time.fixedDeltaTime)
        {
            Time.fixedTime += Time.fixedDeltaTime;
            fixedRemainder -= Time.fixedDeltaTime;
        }
        GameEntryPoint.EventManager.Update();
        Tick();
    }
    static string Begin(float seconds = 1)
    {
        Request(true); Tick(); Tick();
        Check(Ack().native_pause_owned && Ack().paused && Time.timeScale == 0);
        string id = Request(false, true, seconds); Tick();
        Check(Ack().error == null && Ack().step_id == id && Ack().id == id);
        Check(!Ack().paused && !Ack().native_pause_owned && Ack().native_status == 3 && Time.timeScale == 1);
        Check(Step().binding == "synthetic" && Step().id == id && Step().state == "running");
        Check(Step().start_unity_time == Time.time && Step().start_fixed_time == Time.fixedTime);
        Check(!File.Exists(Path.Combine(directory, "request.json")));
        return id;
    }
    static void Destroy()
    {
        typeof(NativePause).GetMethod("OnDestroy", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(bridge, null);
    }
    static void StepChecks()
    {
        var ev = Reset();
        Request(true); Tick(); Tick();
        Request(false); Tick(); Tick();
        Check(Time.maximumDeltaTime == 0.5f && !File.Exists(Path.Combine(directory, "step.json")));

        ev = Reset();
        string id = Begin();
        Advance(0.38f); Advance(0.40f);
        Check(Step().state == "running" && Math.Abs(Time.maximumDeltaTime - 0.22f) < 0.0001f);
        Advance(0.8f);
        Check(Step().state == "completed" && Step().id == id && Step().requested_seconds == 1);
        Check(Math.Abs(Step().elapsed_seconds - 1) < 0.0001f);
        Check(Math.Abs(Step().fixed_time - Step().start_fixed_time - 1) <= Time.fixedDeltaTime + 0.001f);
        Check(Step().native_status == 4 && Step().native_pause_owned && Step().time_scale == 0);
        Check(ev.status == 4 && ev.toggles == 3 && Time.maximumDeltaTime == 0.5f);
        float pausedTime = Time.time;
        Advance(10);
        Check(Time.time == pausedTime && ev.toggles == 3);
        id = Request(false, true, 0.2f); Tick();
        Advance(0.4f);
        Check(Step().state == "completed" && Step().id == id && Math.Abs(Step().elapsed_seconds - 0.2f) < 0.0001f);
        Check(Time.maximumDeltaTime == 0.5f);
        Destroy();
        Check(ev.status == 3 && Time.timeScale == 1);

        ev = Reset(); Begin(); Advance(0.8f);
        Request(true); Tick(); Tick();
        Check(Step().state == "cancelled" && Step().elapsed_seconds < 1);
        Check(Step().native_pause_owned && Step().native_status == 4 && Step().time_scale == 0);
        Check(Ack().paused && Ack().native_pause_owned && Time.maximumDeltaTime == 0.5f);
        Destroy(); Check(ev.status == 3);

        ev = Reset(); Begin(); Advance(0.4f);
        Request(false, true, 0, true); Tick(); Tick();
        Check(Step().state == "cancelled" && !Ack().paused && ev.status == 3);
        Check(!Step().native_pause_owned && Time.maximumDeltaTime == 0.5f);

        foreach (int status in new [] {0, 1, 2, 5, 6, 7, 8})
        {
            ev = Reset(); Begin(); Advance(0.4f);
            ev.status = status; Time.timeScale = 0.15f; Tick();
            Check(Step().state == "transition" && Step().native_status == status);
            Check(!Step().native_pause_owned && Time.maximumDeltaTime == 0.5f && ev.toggles == 2);
        }

        ev = Reset(); Begin(); Advance(0.4f);
        ev.status = 99; Tick();
        Check(Step().state == "error" && Step().error.Contains("Unknown native event status"));
        Check(Time.maximumDeltaTime == 0.5f && !Step().native_pause_owned);

        ev = Reset(); id = Begin(); Advance(0.4f);
        Request(false, true, 1); Tick();
        Check(Ack().error.Contains("already active") && Step().state == "error" && Step().id == id);
        Check(Time.maximumDeltaTime == 0.5f && ev.status == 4 && Step().native_pause_owned);
        Destroy(); Check(ev.status == 3);

        ev = Reset(); Request(false, true, 1); Tick();
        Check(Ack().error.Contains("owned paused") && ev.toggles == 0);
        ev.status = 4; Time.timeScale = 0;
        Request(true); Tick(); Tick();
        Request(false, true, 1); Tick();
        Check(Ack().error.Contains("owned paused") && ev.toggles == 0);
        Check(!File.Exists(Path.Combine(directory, "step.json")));

        foreach (float seconds in new [] {-1f, 0.19f, 3.01f})
        {
            ev = Reset(); Request(false, true, seconds); Tick();
            Check(Ack().error.Contains("Invalid native step request") && ev.toggles == 0);
        }
        ev = Reset(); Request(true, true, 1); Tick();
        Check(Ack().error.Contains("Invalid native step request") && ev.toggles == 0);

        ev = Reset(); Begin(); Advance(0.4f); Destroy();
        Check(Step().state == "cancelled" && Time.maximumDeltaTime == 0.5f && ev.status == 3);

        ev = Reset(); Begin(); Advance(0.4f);
        ev.status = 5; Time.timeScale = 0.15f;
        File.WriteAllText(Path.Combine(directory, "request.json"), "invalid JSON");
        Tick();
        Check(Step().state == "error" && Step().native_status == 5);
        Check(ev.status == 5 && ev.toggles == 2 && Time.maximumDeltaTime == 0.5f);
        Console.WriteLine("Synthetic native step checks passed; not live acceptance evidence.");
    }
    public static void Main(string[] args)
    {
        directory = args[0];
        Directory.CreateDirectory(directory);
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_PAUSE", directory);
        Environment.SetEnvironmentVariable("GAMECUA_RALLY_BINDING", "synthetic");
        bridge = new NativePause();
        typeof(NativePause).GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(bridge, null);
        var ev = new EventManager();
        GameEntryPoint.EventManager = ev;
        Request(true);
        Tick();
        Check(ev.status == 4 && ev.toggles == 1);
        ev.status = 5;
        Time.timeScale = 0.15f;
        Tick();
        Check(Ack().disposition == "transition_unfrozen" && !Ack().native_pause_owned && !Ack().paused);
        foreach (int status in new [] {5, 6, 7, 8, 0, 1, 2})
        {
            ev.status = status;
            Request(true);
            Tick();
            Check(Ack().native_status == status && Ack().disposition == "transition_unfrozen");
            Request(false);
            Tick();
            Check(Ack().disposition == "transition_unfrozen" && ev.toggles == 1);
        }
        ev = new EventManager();
        GameEntryPoint.EventManager = ev;
        Time.timeScale = 1;
        Request(true);
        Tick(); Tick();
        Check(Ack().paused && Ack().native_pause_owned && ev.status == 4);
        Request(false);
        Tick(); Tick();
        Check(!Ack().paused && !Ack().native_pause_owned && ev.status == 3 && ev.toggles == 2);
        ev.status = 4;
        Time.timeScale = 0;
        Request(true); Tick(); Tick();
        Check(Ack().paused && !Ack().native_pause_owned);
        Request(false); Tick(); Tick();
        Check(ev.status == 4 && ev.toggles == 2 && !Ack().native_pause_owned);
        ev.status = 99;
        Request(true); Tick();
        Check(Ack().error.Contains("Unknown native event status"));
        ev.status = 5;
        Time.timeScale = 2;
        Request(true); Tick();
        Check(Ack().error.Contains("Unexpected transition time scale"));
        Time.timeScale = 0.15f;
        Request(true, false); Tick();
        Check(Ack().error.Contains("Cannot pause outside"));
        GameEntryPoint.EventManager = null;
        Request(true); Tick();
        Check(!File.Exists(Path.Combine(directory, "ack.json")));
        GameEntryPoint.EventManager = new EventManager();
        Time.timeScale = 1;
        Tick(); Tick();
        Check(Ack().paused);
        GameEntryPoint.EventManager = new EventManager();
        Request(false); Tick();
        Check(Ack().error.Contains("owner changed") && GameEntryPoint.EventManager.toggles == 0);
        Console.WriteLine("Synthetic native bridge transition checks passed; not live acceptance evidence.");
        StepChecks();
    }
}
