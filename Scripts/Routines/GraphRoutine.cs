using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using BabbleCalibration.Scripts.Elements;
using BabbleCalibration.Scripts.RoutineInterfaces;
using Godot;
using Godot.Collections;
using OverlaySDK.Packets;

namespace BabbleCalibration.Scripts.Routines;

public partial class GraphRoutine : RoutineBase
{
    private ElementBase _element;
    private GraphRoutineInterface _interface;
    private readonly Stopwatch _stopwatch = new();
    private readonly List<Vector2> _points = [];

    private string _metric = "";

    private bool _overlayMode = false;
    private Curve _overlayCurve = ResourceLoader.Load<Curve>("res://Assets/OverlayModeGraphCurve.tres");
    private float _overlayCurrentTime = 0;
    
    public override void Initialize(IBackend backend, Dictionary args = null)
    {
        base.Initialize(backend, args);

        _overlayMode = backend.IsOverlay;
        //_overlayMode = true;
        
        _stopwatch.Start();

        if (_overlayMode)
        {
            (_element, _interface) = this.Load<GraphRoutineInterface>("res://Scenes/Routines/GraphRoutine.tscn");
            _element.ElementTransform = Transform3D.Identity.TranslatedLocal(Vector3.Forward + (Vector3.Down * 0.25f));
        }
        else
        {
            (_element, _interface) = this.Load<GraphRoutineInterface>("res://Scenes/Routines/GraphRoutine.tscn", true);
            _element.ElementTransform = Transform3D.Identity.TranslatedLocal(Vector3.Forward + (Vector3.Down * 0.25f));
        }
        _element.ElementWidth = 0.75f;
        _interface.EpochBar.Visible = false;
        _interface.EpochText.Text = MainScene.Instance.Tr("GraphTitle");
        _interface.BatchText.Text = MainScene.Instance.Tr("GraphDesktopHint");
        _interface.BatchBar.Indeterminate = true;
        _interface.LossText.Text = MainScene.Instance.Tr("GraphWaitingMetrics");
        _interface.TimeText.Text = string.Format(MainScene.Instance.Tr("GraphElapsed"), "0:00");
    }
    

    public override void Update(float delta)
    {
        base.Update(delta);
        _interface.TimeText.Text = string.Format(MainScene.Instance.Tr("GraphElapsed"), _stopwatch.Elapsed.ToString(@"m\:ss"));
        if (!_overlayMode) return;
        var faceTarget = Backend.HeadTransform().TranslatedLocal(Vector3.Forward + (Vector3.Down * 0.25f));
        var floorTarget = OriginOffset * new Transform3D(new Basis(new Quaternion(Vector3.Forward, Vector3.Down)), Vector3.Up * 0.0025f);

        var transform =
            faceTarget.InterpolateWith(floorTarget, _overlayCurve.Sample(Mathf.Clamp(_overlayCurrentTime, 0, _overlayCurve.MaxDomain)));

        _element.ElementTransform = transform;
        _overlayCurrentTime = Mathf.Clamp(_overlayCurrentTime + delta, 0, _overlayCurve.MaxDomain);
    }

    public void ShowStage(string stage)
    {
        _interface.EpochText.Text = MainScene.Instance.Tr(stage switch
        {
            "preparing" => "GraphStagePreparing",
            "expressiontraining" => "GraphStageExpressionTraining",
            "gazetraining" => "GraphStageGazeTraining",
            "exporting" => "GraphStageExporting",
            "checkingmodel" => "GraphStageCheckingModel",
            _ => "GraphTitle"
        });
        _interface.BatchText.Text = MainScene.Instance.Tr("GraphDesktopHint");
        _interface.BatchBar.Indeterminate = true;
        _interface.LossText.Text = MainScene.Instance.Tr("GraphWaitingMetrics");
    }

    public void Handle(TrainerProgressReportPacket packet)
    {
        if (!double.IsFinite(packet.Loss) || packet.TargetProgress <= 0 || packet.CurrentProgress < 0) return;
        var loss = (float)packet.Loss;
        _interface.LossText.Text = $"{packet.ProgressName}: {loss:F6}";
        _interface.BatchText.Text = string.Format(MainScene.Instance.Tr("GraphSteps"), packet.CurrentProgress, packet.TargetProgress);
        _interface.BatchBar.Indeterminate = false;
        _interface.BatchBar.MaxValue = packet.TargetProgress;
        _interface.BatchBar.Value = packet.CurrentProgress;
        // Different stages and metrics are not comparable losses on one continuous curve.
        if (_metric != packet.ProgressName) { _points.Clear(); _metric = packet.ProgressName; }
        _points.Add(new Vector2((float)_stopwatch.Elapsed.TotalSeconds, loss));
        if (_points.Count > 32) _points.RemoveAt(0);
        _interface.Graph.Points = _points.ToArray();
        _interface.Graph.QueueRedraw();
        if (MainScene.Instance.CapturePhaseDiagnostics)
            GD.Print("TRAINING_PROGRESS " + System.Text.Json.JsonSerializer.Serialize(new
            { metric = _interface.LossText.Text, steps = _interface.BatchText.Text, stage = _interface.EpochText.Text }));
    }
}
