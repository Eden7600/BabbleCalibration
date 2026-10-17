# BabbleCalibration
Godot-based OpenVR/OpenXR eye tracking calibrator app.

## Eden7600 experimental companion

This branch includes Elreen's [PR #8](https://github.com/Project-Babble/BabbleCalibration/pull/8)
at `2a49be73c9885baba1777be60357c97de48637e8`, plus a headless protocol smoke test
and two Godot 4.6 compatibility fixes in the bundled OpenVR addon (export plugin name and shader hint).
Use it with [Eden7600/Baballonia](https://github.com/Eden7600/Baballonia/tree/feature/beyond2e-eye-expressions),
which integrates expression training, the matching wink routines from PR #262, and experimental pupil tracking.
See that fork's `EXPERIMENTAL-EYES.md` and `build-experimental.ps1` for the matched Windows build.

Build with .NET SDK 10 and Godot 4.6.1 .NET plus the matching Mono export templates.
The original Apache-2.0 license and bundled third-party notices still apply.

```powershell
dotnet build
& 'C:/tools/godot/Godot_console.exe' --headless --path . --import
python tests/smoke_overlay.py 'C:/tools/godot/Godot_console.exe' --project . --log smoke.log
```

The smoke test binds localhost port 2425, then launches the overlay in headless debug mode.
Close any real calibration session first. It checks readiness, 16 shortened routines (including
both winks and squints), gaze packets, training handoff, and shutdown. It records known Godot
dummy-renderer/shutdown warnings; other engine errors fail. It does not validate headset
rendering, gaze accuracy, or the readability/orientation of instructions inside a headset.
