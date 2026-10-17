"""Exercise the real overlay TCP protocol without a headset (Python standard library only).

python tests/smoke_overlay.py /path/to/BabbleCalibration.x86_64.exe --log smoke.log
python tests/smoke_overlay.py /path/to/godot --project . --log smoke.log
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable')
    parser.add_argument('--project')
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    command = [str(Path(args.executable).resolve()), '--headless', '--use-debug',
               '--xr-mode', 'off', '--max-fps', '60', '--baballonia-locale=en']
    if args.project:
        command += ['--path', str(Path(args.project).resolve())]
    args.log.parent.mkdir(parents=True, exist_ok=True)
    # Binding first fails cleanly if a real calibration already owns the port.
    with socket.socket() as server, args.log.open('w', encoding='utf-8') as log:
        server.bind(('127.0.0.1', 2425))
        server.listen(1)
        server.settimeout(20)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(10)
                buffer = ''
                decoder = json.JSONDecoder()

                def send(name, **data):
                    connection.sendall(json.dumps({'PacketName': name, 'PacketData': data}).encode())

                def finish(expected, require_gaze=False):
                    nonlocal buffer
                    deadline = time.monotonic() + 10
                    gaze = False
                    while time.monotonic() < deadline:
                        try:
                            packet, end = decoder.raw_decode(buffer.lstrip())
                            buffer = buffer.lstrip()[end:]
                        except json.JSONDecodeError:
                            chunk = connection.recv(65536)
                            assert chunk, f'Overlay disconnected during {expected}'
                            buffer += chunk.decode('utf-8')
                            continue
                        if packet['PacketName'] == 'HmdPositionalDataPacket':
                            gaze = True
                        if packet['PacketName'] == 'RoutineFinishedPacket':
                            name = packet['PacketData']['RoutineName']
                            if name == 'ready' and expected != 'ready':
                                continue
                            assert name == expected, (expected, name)
                            assert not require_gaze or gaze, f'No positional data during {expected}'
                            return
                    raise AssertionError(f'No completion for {expected}')

                finish('ready')
                routines = ['gazetutorialshort', 'gaze', 'gazeexprtutorial', 'gazeexpr',
                            'blinktutorial', 'blink', 'winklefttutorial', 'winkleft',
                            'winkrighttutorial', 'winkright', 'widentutorial', 'widen',
                            'squinttutorial', 'squint', 'browtutorial', 'brow']
                for routine in routines:
                    send('RunVariableLenghtRoutinePacket', RoutineName=routine, Time='00:00:00.2500000')
                    finish(routine, routine in {'gaze', 'gazeexpr', 'widen', 'squint', 'brow'})
                send('RunFixedLenghtRoutinePacket', RoutineName='trainer')
                send('TrainerProgressReportPacket', ProgressName='Batch', CurrentProgress=1,
                     TargetProgress=2, Loss=0.1)
                send('RunFixedLenghtRoutinePacket', RoutineName='close')
                assert process.wait(timeout=10) == 0, 'Overlay exited with an error'
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    output = args.log.read_text(encoding='utf-8', errors='replace')
    # Godot's dummy renderer/native OpenVR addon reports these on headless shutdown.
    known_headless = {'ERROR: Parameter "material" is null.',
                      'ERROR: 2 resources still in use at exit (run with --verbose for details).'}
    errors = [line.strip() for line in output.splitlines() if 'ERROR:' in line]
    assert all(line in known_headless for line in errors) and 'Unhandled exception' not in output, output
    print('PASS: readiness, 16 routines, gaze packets, training handoff, and clean shutdown')
    if errors:
        print('Headless renderer/resource warnings recorded in', args.log)


if __name__ == '__main__':
    main()
