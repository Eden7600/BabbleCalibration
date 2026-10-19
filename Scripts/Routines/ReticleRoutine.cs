using BabbleCalibration.Scripts.Elements;
using Godot;
using Godot.Collections;
using OverlaySDK.Packets;

namespace BabbleCalibration.Scripts.Routines;

/// <summary>Mirrors Baballonia's RampSchedule; both must stay identical.</summary>
public static class RampSchedule
{
    // Hold 0 for 0.5 s, rise for 1.5 s, hold 1 for 0.5 s, fall for 1.5 s.
    public static float Intensity(float seconds)
    {
        var t = Mathf.PosMod(seconds, 4f);
        return t < 0.5f ? 0 : t < 2 ? (t - 0.5f) / 1.5f : t < 2.5f ? 1 : (4 - t) / 1.5f;
    }
}

public class ReticleRoutine : RoutineBase
{
    private bool _sounds = true;
    private bool _sendPose = true;
    private bool _checkSpeed = true;
    public override bool PlaySounds => _sounds;
    protected float Height;
    protected Transform3D Transform = Transform3D.Identity;
    protected ElementBase Element;
    protected ProgressCircle Interface;
    protected Quaternion PreviousHeadRotation = Quaternion.Identity;
    protected float Speed;
    protected virtual bool SpeedCheck => true;
    private float _slowTimer;
    private bool _ramp;
    private float _elapsed;
    private const int ToneRate = 22050;
    private AudioStreamPlayer _tone;
    private AudioStreamGeneratorPlayback _tonePlayback;
    private float _tonePhase;
    public bool MotionWarning { get; private set; }

    public override void Initialize(IBackend backend, Dictionary args = null)
    {
        var time = 10f;
        if (args is not null)
        {
            if (args.TryGetValue("time", out var value)) time = value.AsSingle();
            if (args.TryGetValue("sounds", out value)) _sounds = value.AsBool();
            if (args.TryGetValue("send_pose", out value)) _sendPose = value.AsBool();
            if (args.TryGetValue("speed_check", out value)) _checkSpeed = value.AsBool();
            if (args.TryGetValue("ramp", out value)) _ramp = value.AsBool();
            if (args.TryGetValue("tone", out value) && value.AsBool()) StartTone();
        }
        base.Initialize(backend, args);
        Height = backend.HeadTransform().Origin.Y;
        PreviousHeadRotation = backend.HeadTransform().Basis.GetRotationQuaternion();
        Interface = MainScene.Instance.StartMeasurementProgress(time);
        Interface.CenterColor = Colors.White;
        Interface.PivotOffset = Interface.Size / 2;
        Interface.Scale = Vector2.One;
        Transform = MainScene.Instance.MeasurementTargetTransform;
        // Instructions belong to the preceding reading phase; fixation phases create no text element.
    }

    // Closed eyes cannot see the ring, so lid ramps also play a tone whose pitch follows the schedule.
    private void StartTone()
    {
        _tone = new AudioStreamPlayer { Stream = new AudioStreamGenerator { MixRate = ToneRate, BufferLength = 0.05f }, VolumeDb = -18 };
        MainScene.Instance.AddChild(_tone);
        _tone.Play();
        _tonePlayback = (AudioStreamGeneratorPlayback)_tone.GetStreamPlayback();
    }

    private void FillTone(float intensity)
    {
        var step = 220f * Mathf.Pow(2f, intensity) / ToneRate; // one octave, 220 to 440 Hz
        for (var n = _tonePlayback.GetFramesAvailable(); n > 0; n--)
        {
            var sample = 0.5f * Mathf.Sin(_tonePhase * Mathf.Tau);
            _tonePlayback.PushFrame(new Vector2(sample, sample));
            _tonePhase = (_tonePhase + step) % 1f;
        }
    }

    public override void End()
    {
        _tone?.QueueFree();
        _tone = null;
        _tonePlayback = null;
        base.End();
    }

    private static float Damp(float a, float b, float lambda, float dt) => Mathf.Lerp(a, b, 1 - Mathf.Exp(-lambda * dt));

    public override void Update(float delta)
    {
        base.Update(delta);
        if (_ramp && !IsEnded)
        {
            // The ring's size is the target intensity the user follows; frames are labeled from the same schedule.
            _elapsed += delta;
            var intensity = RampSchedule.Intensity(_elapsed);
            Interface.Scale = Vector2.One * (0.4f + 0.6f * intensity);
            if (_tonePlayback is not null) FillTone(intensity);
        }
        if (IsEnded || !_sendPose) return;
        var headTransform = Backend.HeadTransform();
        if (SpeedCheck && _checkSpeed && delta > 0)
        {
            var currentRotation = headTransform.Basis.GetRotationQuaternion();
            var rotationDelta = PreviousHeadRotation.Inverse() * currentRotation;
            var currentSpeed = rotationDelta.AngleTo(Quaternion.Identity) / delta;
            PreviousHeadRotation = currentRotation;
            Speed = Damp(Speed, currentSpeed, 2, delta);
            _slowTimer = Speed < 0.1f ? _slowTimer + delta : 0;
            MotionWarning = Speed > 2 || _slowTimer >= 2;
            // The ring is guidance, not a pose-validity gate. Continue labeling stationary frames.
            Interface.CenterColor = MotionWarning ? Colors.Red : Colors.White;
        }
        var packet = new HmdPositionalDataPacket();
        (packet.RoutinePitch, packet.RoutineYaw, packet.RoutineDistance) = TransformToReticle(headTransform);
        (packet.RightEyePitch, packet.RightEyeYaw, _) = TransformToReticle(Backend.EyeTransform(false));
        (packet.LeftEyePitch, packet.LeftEyeYaw, _) = TransformToReticle(Backend.EyeTransform(true));
        MainScene.Instance.SendPacket(packet);

        (float Pitch, float Yaw, float Distance) TransformToReticle(Transform3D transform)
        {
            var angleTo = (transform.AffineInverse() * Transform).Origin;
            var lookAt = Basis.LookingAt(angleTo, Vector3.Up);
            var euler = lookAt.GetRotationQuaternion().GetEuler();
            return (Mathf.RadToDeg(euler.X), Mathf.RadToDeg(euler.Y), transform.Origin.DistanceTo(Transform.Origin));
        }
    }
}
