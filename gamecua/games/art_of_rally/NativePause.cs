// Native pause and opt-in bounded simulation steps preserve owned game transitions.
using System;
using System.IO;
using System.Reflection;
using BepInEx;
using UnityEngine;

[BepInPlugin("org.touchstone.artofrally.pause", "Art of Rally Native Pause", "0.4.0")]
public sealed class NativePause : BaseUnityPlugin
{
    string directory;
    string binding;
    string pending;
    bool requested;
    bool owned;
    object owner;
    object stepOwner;
    Step step;
    bool stepping;
    bool capOwned;
    float originalMaximumDeltaTime;
    int nativeStatus = -1;
    Assembly game;
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;

    [Serializable]
    public sealed class Request
    {
        public string binding;
        public string id;
        public bool paused;
        public bool allow_transitions;
        public float step_seconds;
        public bool abort_step;
    }

    [Serializable]
    public sealed class Ack
    {
        public string binding;
        public string id;
        public bool paused;
        public float unity_time;
        public float time_scale;
        public int native_status;
        public bool native_pause_owned;
        public string error;
        public string disposition;
        public string step_id;
    }

    [Serializable]
    public sealed class Step
    {
        public string binding;
        public string id;
        public string state;
        public float requested_seconds;
        public float start_unity_time;
        public float start_fixed_time;
        public float unity_time;
        public float fixed_time;
        public float elapsed_seconds;
        public int native_status;
        public float time_scale;
        public bool native_pause_owned;
        public string error;
    }

    void Awake()
    {
        directory = Environment.GetEnvironmentVariable("GAMECUA_RALLY_PAUSE");
        binding = Environment.GetEnvironmentVariable("GAMECUA_RALLY_BINDING");
        game = Assembly.Load("Assembly-CSharp");
    }

    void LateUpdate()
    {
        if (String.IsNullOrEmpty(directory)) return;
        string path = Path.Combine(directory, "request.json");
        Request request = null;
        object ev = null;
        bool cancelledStep = false;
        try
        {
            if (File.Exists(path))
            {
                request = JsonUtility.FromJson<Request>(File.ReadAllText(path));
                if (request.binding != binding) request = null;
            }
            if (request == null && !stepping) return;
            ev = game.GetType("GameEntryPoint").GetProperty("EventManager", Flags).GetValue(null, null);
            if (ev == null)
            {
                if (stepping) throw new InvalidOperationException("Native step owner disappeared");
                return;
            }
            Type t = ev.GetType();
            int status = Convert.ToInt32(t.GetField("status", Flags).GetValue(ev));
            nativeStatus = status;
            if (status < 0 || status > 8)
                throw new InvalidOperationException("Unknown native event status: " + status);
            if (owned && !System.Object.ReferenceEquals(owner, ev))
                throw new InvalidOperationException("Native pause owner changed");
            if (request != null)
            {
                if (Single.IsNaN(request.step_seconds) || Single.IsInfinity(request.step_seconds)
                    || request.step_seconds < 0 || (request.step_seconds > 0
                        && (request.step_seconds < 0.2f || request.step_seconds > 3
                            || request.paused || request.abort_step || String.IsNullOrEmpty(request.id))))
                    throw new InvalidOperationException("Invalid native step request");
                if (stepping && request.step_seconds > 0)
                    throw new InvalidOperationException("Another native step is already active");
                if (stepping && (request.paused || request.abort_step))
                {
                    FinishStep("cancelled", null);
                    cancelledStep = true;
                }
            }
            if (stepping)
            {
                if (status != 3 && status != 4)
                {
                    ValidateTransitionScale();
                    owned = false;
                    owner = null;
                    FinishStep("transition", null);
                }
                else
                {
                    if (!System.Object.ReferenceEquals(stepOwner, ev) || status != 3 || Time.timeScale != 1)
                        throw new InvalidOperationException("Native running step lost its owned driving state");
                    if (!Finite(Time.time) || !Finite(Time.fixedTime)
                        || Time.time < step.start_unity_time || Time.fixedTime < step.start_fixed_time)
                        throw new InvalidOperationException("Native step clock regressed");
                    if (Time.time - step.start_unity_time >= step.requested_seconds - 0.00001f)
                    {
                        Pause(ev, t, true);
                        status = nativeStatus = Convert.ToInt32(t.GetField("status", Flags).GetValue(ev));
                        if (status != 4 || Time.timeScale != 0 || !owned)
                            throw new InvalidOperationException("Native step failed to pause at its boundary");
                        FinishStep("completed", null);
                    }
                    else
                    {
                        BoundNextFrame();
                        WriteStep("running", null);
                    }
                }
            }
            if (request == null) return;
            if (request.step_seconds > 0)
            {
                if (!owned || !System.Object.ReferenceEquals(owner, ev) || status != 4 || Time.timeScale != 0)
                    throw new InvalidOperationException("Native step requires an owned paused stage");
                if (!Finite(Time.time) || !Finite(Time.fixedTime) || !Finite(Time.fixedDeltaTime)
                    || Time.fixedDeltaTime <= 0 || !Finite(Time.maximumDeltaTime)
                    || Time.maximumDeltaTime < Time.fixedDeltaTime)
                    throw new InvalidOperationException("Native step clock configuration is invalid");
                step = new Step {
                    binding = binding, id = request.id, state = "running", requested_seconds = request.step_seconds,
                    start_unity_time = Time.time, start_fixed_time = Time.fixedTime
                };
                originalMaximumDeltaTime = Time.maximumDeltaTime;
                capOwned = stepping = true;
                stepOwner = ev;
                pending = request.id;
                requested = false;
                Pause(ev, t, false);
                t.GetMethod("Update", Flags).Invoke(ev, null);
                nativeStatus = Convert.ToInt32(t.GetField("status", Flags).GetValue(ev));
                if (nativeStatus != 3 || Time.timeScale != 1)
                    throw new InvalidOperationException("Native step did not resume driving");
                BoundNextFrame();
                WriteStep("running", null);
                WriteAck(request, null);
                File.Delete(path);
                return;
            }
            if (request.allow_transitions && status != 3 && status != 4)
            {
                ValidateTransitionScale();
                owned = false;
                owner = null;
                pending = null;
                if (cancelledStep) WriteStep("cancelled", null);
                WriteAck(request, null, "transition_unfrozen");
                File.Delete(path);
                return;
            }
            if (pending != request.id)
            {
                if (request.paused && status != 3 && status != 4)
                    throw new InvalidOperationException("Cannot pause outside owned underway stage");
                if (!request.paused && status != 3 && status != 4)
                    throw new InvalidOperationException("Cannot resume an unowned native pause");
                pending = request.id;
                requested = request.paused;
                if ((requested && status == 3) || (!requested && owned && status == 4))
                    Pause(ev, t, requested);
                if (cancelledStep)
                {
                    nativeStatus = Convert.ToInt32(t.GetField("status", Flags).GetValue(ev));
                    WriteStep("cancelled", null);
                }
                return;
            }
            if ((requested && status == 4 && Time.timeScale == 0) || (!requested && ((status == 3 && Time.timeScale == 1) || (!owned && status == 4 && Time.timeScale == 0))))
            {
                WriteAck(request, null);
                File.Delete(path);
            }
        }
        catch (Exception e)
        {
            string error = e.GetType().Name + ": " + e.Message;
            if (stepping)
            {
                RestoreCap();
                if (ev == null)
                {
                    try { ev = game.GetType("GameEntryPoint").GetProperty("EventManager", Flags).GetValue(null, null); }
                    catch (Exception) { }
                }
                if (ev != null && System.Object.ReferenceEquals(stepOwner, ev))
                {
                    try
                    {
                        nativeStatus = Convert.ToInt32(ev.GetType().GetField("status", Flags).GetValue(ev));
                        if (nativeStatus == 3)
                        {
                            Pause(ev, ev.GetType(), true);
                            nativeStatus = Convert.ToInt32(ev.GetType().GetField("status", Flags).GetValue(ev));
                        }
                    }
                    catch (Exception cleanup) { error += "; pause cleanup: " + cleanup.GetType().Name; }
                }
                FinishStep("error", error);
            }
            if (request != null)
            {
                WriteAck(request, error);
                File.Delete(path);
            }
        }
    }

    static bool Finite(float value)
    {
        return !Single.IsNaN(value) && !Single.IsInfinity(value);
    }

    static void ValidateTransitionScale()
    {
        if (!Finite(Time.timeScale) || Time.timeScale < 0 || Time.timeScale > 1)
            throw new InvalidOperationException("Unexpected transition time scale");
    }

    void Pause(object ev, Type t, bool paused)
    {
        t.GetMethod("ToggleStagePaused", Flags).Invoke(ev, new object[] {null});
        object hud = t.GetField("hudManager", Flags).GetValue(ev);
        hud.GetType().GetMethod("ShowStageHud", Flags).Invoke(hud, null);
        if (paused) t.GetMethod("Update", Flags).Invoke(ev, null);
        owned = paused;
        owner = owned ? ev : null;
    }

    void BoundNextFrame()
    {
        float remaining = step.requested_seconds - (Time.time - step.start_unity_time);
        Time.maximumDeltaTime = Math.Max(Time.fixedDeltaTime, Math.Min(originalMaximumDeltaTime, remaining));
    }

    void RestoreCap()
    {
        if (!capOwned) return;
        Time.maximumDeltaTime = originalMaximumDeltaTime;
        capOwned = false;
    }

    void FinishStep(string state, string error)
    {
        RestoreCap();
        stepping = false;
        stepOwner = null;
        WriteStep(state, error);
    }

    void WriteStep(string state, string error)
    {
        step.state = state;
        step.unity_time = Time.time;
        step.fixed_time = Time.fixedTime;
        step.elapsed_seconds = Time.time - step.start_unity_time;
        step.native_status = nativeStatus;
        step.time_scale = Time.timeScale;
        step.native_pause_owned = owned;
        step.error = error;
        Write("step.json", JsonUtility.ToJson(step));
    }

    void Write(string name, string raw)
    {
        string target = Path.Combine(directory, name);
        File.WriteAllText(target + ".tmp", raw);
        if (File.Exists(target)) File.Delete(target);
        File.Move(target + ".tmp", target);
    }

    void WriteAck(Request request, string error, string disposition = "driving")
    {
        Ack ack = new Ack {binding = binding, id = request.id, paused = disposition == "driving" && requested, unity_time = Time.time, time_scale = Time.timeScale, native_status = nativeStatus, native_pause_owned = owned, error = error, disposition = disposition, step_id = request.step_seconds > 0 ? request.id : null};
        Write("ack.json", JsonUtility.ToJson(ack));
    }

    void OnDestroy()
    {
        RestoreCap();
        try
        {
            if (stepping) FinishStep("cancelled", "Native pause bridge destroyed during step");
        }
        finally
        {
            if (owned)
            {
                object ev = game.GetType("GameEntryPoint").GetProperty("EventManager", Flags).GetValue(null, null);
                if (ev != null && System.Object.ReferenceEquals(owner, ev) && Convert.ToInt32(ev.GetType().GetField("status", Flags).GetValue(ev)) == 4)
                    ev.GetType().GetMethod("ToggleStagePaused", Flags).Invoke(ev, new object[] {null});
            }
        }
    }
}
