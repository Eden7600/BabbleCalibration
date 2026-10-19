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


READY = 'ready:reliable-eye-training:4'
POSITIONAL = {'gaze', 'gazecheck', 'gazeexpr', 'open', 'widen', 'squint', 'brow'}
INTRO = ('When text disappears, start the action and continue until the second tone. '
         'With both eyes open, watch the target and move your head slowly; red means adjust speed.')


def check_diagnostics(output, blocks, overview):
    phases = {}
    sounds = {}
    for line in output.splitlines():
        if line.startswith('CAPTURE_PHASE '):
            event = json.loads(line.removeprefix('CAPTURE_PHASE '))
            phases.setdefault(event['routine'], []).append(event)
        if line.startswith('CAPTURE_SOUND '):
            event = json.loads(line.removeprefix('CAPTURE_SOUND '))
            sounds.setdefault(event['routine'], []).append(event['cue'])

    intro_events = phases.get(overview, [])
    assert [event['boundary'] for event in intro_events] == ['start', 'end'], intro_events
    assert len(INTRO.split()) <= 30 and 1 <= sum(c in '.!?' for c in INTRO) <= 2
    assert all(event['labels'] == [INTRO] for event in intro_events), intro_events
    assert not sounds.get(overview), sounds.get(overview)
    for name, events in phases.items():
        if name != overview:
            assert all(INTRO not in ' '.join(event['labels']) for event in events), name

    baseline = None
    fresh_target = None
    for routine, steps in blocks:
        block_target = None
        for phase, name in steps:
            events = phases.get(name, [])
            assert [event['boundary'] for event in events] == ['start', 'end'], (name, events)
            for event in events:
                assert event['target_visible'], event
                assert event['target'] == event['rendered_target'], event
                if phase == 'instruction':
                    text = ' '.join(event['labels'])
                    assert 1 <= len(text.split()) <= 11, (name, text)
                    assert 1 <= sum(c in '.!?' for c in text) <= 2, (name, text)
                    assert 'ring turns red' not in text and 'watch the target' not in text.lower(), (name, text)
                    assert not any(character.isdigit() for character in text), (name, text)
                    assert text == ' '.join(events[0]['labels']), f'Instruction changed during {name}'
                else:
                    assert not event['labels'], f'Text visible during {name}: {event["labels"]}'
                    if block_target is None:
                        block_target = event['target']
                    assert event['target'] == block_target, f'Target moved during {name}'
            expected_cues = ['start', 'end'] if phase == 'capture' else []
            assert sounds.get(name, []) == expected_cues, (name, sounds.get(name))
        if baseline is None:
            baseline = block_target
        if routine == 'gazecheck':
            if fresh_target is None:
                fresh_target = block_target
                offset = [new - old for old, new in zip(baseline, fresh_target)]
                assert all(abs(actual - expected) < 1e-5
                           for actual, expected in zip(offset, [.35, .2, 0])), offset
            assert block_target == fresh_target, 'Fresh-check retry moved the target again'
        else:
            assert block_target == baseline, 'Normal repetition moved the world-fixed target'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable')
    parser.add_argument('--project')
    parser.add_argument('--overview', choices=['quick', 'full'], default='quick')
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    command = [str(Path(args.executable).resolve()), '--headless', '--use-debug',
               '--capture-phase-diagnostics', '--xr-mode', 'off', '--max-fps', '60',
               '--baballonia-locale=en']
    if args.project:
        command += ['--path', str(Path(args.project).resolve())]
    args.log.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
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

                def finish(expected, require_gaze=False, forbid_gaze=False, timeout=10):
                    nonlocal buffer
                    deadline = time.monotonic() + timeout
                    gaze = False
                    started = time.monotonic()
                    last_gaze = None
                    while time.monotonic() < deadline:
                        try:
                            packet, end = decoder.raw_decode(buffer.lstrip())
                            buffer = buffer.lstrip()[end:]
                        except json.JSONDecodeError:
                            try:
                                chunk = connection.recv(65536)
                            except socket.timeout:
                                continue
                            assert chunk, f'Overlay disconnected during {expected}'
                            buffer += chunk.decode('utf-8')
                            continue
                        if packet['PacketName'] == 'HmdPositionalDataPacket':
                            gaze = True
                            last_gaze = time.monotonic() - started
                        if packet['PacketName'] == 'RoutineFinishedPacket':
                            name = packet['PacketData']['RoutineName']
                            if name == READY and expected != READY:
                                continue
                            assert name == expected, (expected, name)
                            assert not require_gaze or gaze, f'No positional data during {expected}'
                            assert not forbid_gaze or not gaze, f'Unexpected positional data during {expected}'
                            return last_gaze
                    raise AssertionError(f'No completion for {expected}')

                finish(READY)
                overview = ('gazetutorial' if args.overview == 'full' else 'gazetutorialshort') + '#overview'
                send('RunVariableLenghtRoutinePacket', RoutineName=overview, Time='00:00:00.2500000')
                finish(overview, forbid_gaze=True, timeout=60)
                # Repetitions/retries get the same three phases with different correlation IDs.
                routines = ['gaze', 'gazeexpr', 'open', 'blink', 'winkleft', 'winkright',
                            'widen', 'squint', 'brow', 'squint', 'gazecheck', 'gazecheck']
                for index, routine in enumerate(routines):
                    steps = []
                    for phase, prefix in [('instruction', 'instruction-'), ('settle', 'settle-'),
                                          ('capture', '')]:
                        completion_id = f'{prefix}{routine}#smoke-{index}-{phase}'
                        steps.append((phase, completion_id))
                        # Long enough to trigger the stationary/slow-speed visual feedback path.
                        duration = '00:00:02.2500000' if phase == 'capture' and index == 0 else '00:00:00.2500000'
                        send('RunVariableLenghtRoutinePacket', RoutineName=completion_id, Time=duration)
                        positional = phase == 'capture' and routine in POSITIONAL
                        last_gaze = finish(completion_id, require_gaze=positional, forbid_gaze=not positional)
                        if phase == 'capture' and index == 0:
                            assert last_gaze is not None and last_gaze > 2.1, 'Red ring stopped sending current poses'
                    blocks.append((routine, steps))
                send('RunFixedLenghtRoutinePacket', RoutineName='trainer-expressiontraining')
                send('TrainerProgressReportPacket', ProgressName='Batch', CurrentProgress=1,
                     TargetProgress=2, Loss=0.1)
                time.sleep(.1)
                for routine in ['training-complete', 'training-failed', 'training-cancelled', 'verification-complete']:
                    name = routine + '#terminal'
                    send('RunVariableLenghtRoutinePacket', RoutineName=name, Time='00:00:00.2500000')
                    finish(name, forbid_gaze=True)
                # The optional desktop subscriber closes its socket after the terminal display.
                connection.shutdown(socket.SHUT_RDWR)
                connection.close()
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
    check_diagnostics(output, blocks, overview)
    first_gaze_end = [json.loads(line.split('CAPTURE_PHASE ', 1)[1]) for line in output.splitlines()
                      if 'CAPTURE_PHASE ' in line and 'gaze#smoke-0-capture' in line and '"boundary":"end"' in line]
    assert len(first_gaze_end) == 1 and first_gaze_end[0]['motion_warning'], first_gaze_end
    progress = [json.loads(line.removeprefix('TRAINING_PROGRESS ')) for line in output.splitlines()
                if line.startswith('TRAINING_PROGRESS ')]
    assert len(progress) == 1 and progress[0]['steps'] == 'Steps: 1/2' and progress[0]['stage'] == 'Training expressions', progress
    for routine, expected in [('training-complete', 'Training finished.'), ('training-failed', 'Training failed;'),
                              ('training-cancelled', 'Training cancelled.'), ('verification-complete', 'Fresh headset check saved;')]:
        events = [json.loads(line.split('CAPTURE_PHASE ', 1)[1]) for line in output.splitlines()
                  if 'CAPTURE_PHASE ' in line and routine + '#terminal' in line]
        assert [event['boundary'] for event in events] == ['start', 'end'], events
        assert all(not event['target_visible'] and expected in ' '.join(event['labels']) for event in events), events
        for event in events:
            text = ' '.join(event['labels'])
            assert len(text.split()) <= 30 and 1 <= sum(c in '.!?' for c in text) <= 2, (routine, text)

    print('PASS: v4 readiness; one concise shared briefing; 12 concise instruction/settle/capture blocks; text-free fixation; '
          'stable target including fresh-check retry; recording-only audio and gaze; desktop training handoff; correlated completion; clean shutdown')
    if errors:
        print('Headless renderer/resource warnings recorded in', args.log)


if __name__ == '__main__':
    main()
