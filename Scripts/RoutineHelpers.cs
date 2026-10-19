using Godot;
using Godot.Collections;

namespace BabbleCalibration.Scripts;

public static class RoutineHelpers
{
    public static Dictionary LabelRoutineArgs(string text, bool head = false, Transform3D? transform = null, bool sounds = false)
    {
        return new Dictionary
        {
            {"text", text },
            {"head", head },
            {"transform", transform ?? Transform3D.Identity.TranslatedLocal(Vector3.Forward + Vector3.Up) },
            {"sounds", sounds }
        };
    }
    
    public static Dictionary FilePathRoutineArgs(string filePath, string text, bool head = false, Transform3D? transform = null, bool sounds = false)
    {
        return new Dictionary
        {
            {"path", filePath },
            {"text", text },
            {"head", head },
            {"transform", transform ?? Transform3D.Identity.TranslatedLocal(Vector3.Forward + Vector3.Up) },
            {"sounds", sounds },
        };
    }
    
    public static Dictionary FilePathTimeRoutineArgs(string filePath, string text, float time, bool head = false, Transform3D? transform = null, bool sounds = false)
    {
        return new Dictionary
        {
            {"path", filePath },
            {"text", text },
            {"head", head },
            {"time", time },
            {"transform", transform ?? Transform3D.Identity.TranslatedLocal(Vector3.Forward + Vector3.Up) },
            {"sounds", sounds },
        };
    }
    
    public static Dictionary LabelTimerRoutineArgs(string text, float time, bool head = false,
        Transform3D? transform = null, bool sounds = false, bool showProgress = false,
        bool showTestText = false, string winkSide = "")
    {
        return new Dictionary
        {
            {"text", text },
            {"head", head },
            {"transform", transform ?? Transform3D.Identity.TranslatedLocal(Vector3.Forward + Vector3.Up) },
            {"time", time },
            {"sounds", sounds },
            {"show_progress", showProgress },
            {"show_test_text", showTestText },
            {"wink_side", winkSide },
        };
    }
    
    public static Dictionary TimeArgs(float time, bool sounds = false)
    {
        return new Dictionary
        {
            {"time", time },
            {"sounds", sounds },
        };
    }

    public static Dictionary MeasurementArgs(float time, bool positional, bool sounds, bool ramp = false, bool tone = false) => new()
    {
        {"time", time}, {"send_pose", positional}, {"speed_check", positional}, {"sounds", sounds}, {"ramp", ramp}, {"tone", tone}
    };

    public static Dictionary TimeTextArgs(float time, string text, bool sounds = false)
    {
        return new Dictionary
        {
            {"time", time },
            {"text", text },
            {"sounds", sounds },
        };
    }
}
