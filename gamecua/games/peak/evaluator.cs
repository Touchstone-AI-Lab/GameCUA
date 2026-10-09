// Read-only PEAK runtime sampling. No hooks, game-state writes, inputs or scoring rules.
using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using BepInEx;
using UnityEngine;
using UnityEngine.SceneManagement;

[BepInPlugin("org.gamecua.peak.observer", "GameCUA Native Observer", "1.0.0")]
public sealed class PeakNativeObserver : BaseUnityPlugin
{
    private Assembly game;
    private StreamWriter output;
    private string binding;
    private float nextSample;
    private long sequence;
    private string lastRunId = "";

    [Serializable]
    public sealed class Sample
    {
        public int schema_version = 1;
        public string evaluator_version = "peak-native-observer-1";
        public string binding;
        public long sequence;
        public double unix_time;
        public string scene;
        public string game_version;
        public string run_id;
        public string raw_run_id;
        public bool run_started;
        public bool in_airport;
        public bool character_present;
        public bool stats_initialized;
        public bool dead;
        public bool passed_out;
        public bool climbing;
        public bool won;
        public bool lost;
        public string segment;
        public float height_meters;
        public float native_peak_units;
        public float run_seconds;
        public float stamina;
        public string error;
    }

    private void Awake()
    {
        binding = Environment.GetEnvironmentVariable("GAMECUA_PEAK_BINDING");
        string path = Environment.GetEnvironmentVariable("GAMECUA_PEAK_EVIDENCE");
        if (String.IsNullOrEmpty(binding) || String.IsNullOrEmpty(path))
        {
            enabled = false;
            return;
        }
        foreach (Assembly candidate in AppDomain.CurrentDomain.GetAssemblies())
            if (candidate.GetName().Name == "Assembly-CSharp") game = candidate;
        if (game == null) throw new InvalidOperationException("Native PEAK assembly unavailable");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        output = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read));
        output.AutoFlush = true;
    }

    private static object Read(object value, string name)
    {
        if (value == null) return null;
        Type type = value as Type ?? value.GetType();
        BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance | BindingFlags.FlattenHierarchy;
        FieldInfo field = type.GetField(name, flags);
        if (field != null) return field.GetValue(value is Type ? null : value);
        PropertyInfo property = type.GetProperty(name, flags);
        if (property != null) return property.GetValue(value is Type ? null : value, null);
        throw new MissingMemberException(type.FullName, name);
    }

    private object Static(string type, string member)
    {
        Type native = game.GetType(type, true);
        return Read(native, member);
    }

    private static bool Flag(object value, string name)
    {
        object raw = Read(value, name);
        return raw != null && Convert.ToBoolean(raw, CultureInfo.InvariantCulture);
    }

    private static float Number(object value, string name)
    {
        object raw = Read(value, name);
        return raw == null ? 0 : Convert.ToSingle(raw, CultureInfo.InvariantCulture);
    }

    private void Update()
    {
        if (output == null || Time.realtimeSinceStartup < nextSample) return;
        nextSample = Time.realtimeSinceStartup + 0.5f;
        Sample sample = new Sample();
        sample.binding = binding;
        sample.sequence = ++sequence;
        sample.unix_time = (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds;
        sample.scene = SceneManager.GetActiveScene().name;
        sample.game_version = Application.version;
        sample.run_id = "";
        sample.raw_run_id = "";
        sample.segment = "";
        try
        {
            object character = Static("Character", "localCharacter");
            object run = Static("RunManager", "Instance");
            object map = Static("MapHandler", "Instance");
            if (run != null)
            {
                sample.raw_run_id = Convert.ToString(Read(run, "RunId"), CultureInfo.InvariantCulture);
                if (sample.raw_run_id != Guid.Empty.ToString()) lastRunId = sample.raw_run_id;
                sample.run_id = lastRunId;
                sample.run_started = Flag(run, "runStarted");
                sample.run_seconds = Number(run, "TimeSinceRunStarted");
            }
            if (map != null) sample.segment = Convert.ToString(Read(map, "currentSegment"), CultureInfo.InvariantCulture);
            if (character != null)
            {
                sample.character_present = true;
                sample.in_airport = sample.scene == "Airport";
                object data = Read(character, "data");
                sample.dead = Flag(data, "dead");
                sample.passed_out = Flag(data, "passedOut");
                sample.climbing = Flag(data, "isClimbingAnything");
                sample.stamina = Number(data, "_stam");
                object stats = Read(Read(character, "refs"), "stats");
                sample.stats_initialized = Flag(stats, "IsInitialized");
                sample.height_meters = Number(stats, "heightInMeters");
                sample.native_peak_units = Number(stats, "peakHeightInUnits");
                sample.won = Flag(stats, "won");
                sample.lost = Flag(stats, "lost");
            }
        }
        catch (Exception exception)
        {
            sample.error = exception.GetType().Name + ": " + exception.Message;
        }
        output.WriteLine(JsonUtility.ToJson(sample));
    }

    private void OnDestroy()
    {
        if (output != null) output.Dispose();
    }
}
