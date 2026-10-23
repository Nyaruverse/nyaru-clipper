from __future__ import annotations

import fcntl
import json
import os
import selectors
import signal
import sqlite3
import stat
import subprocess
from pathlib import Path
from typing import Final

from unified_crash_fixture import CrashCase


BOUNDARIES: Final = {
    'controls-before': ('recovery_thaw_snapshot.py', 'thaw_snapshot', 'restore_controls(controls, journal)', 1),
    'controls-after': ('recovery_thaw_snapshot.py', 'thaw_snapshot', 'return thaw_database(', 1),
    'withdraw-before-commit': ('recovery_thaw.py', 'thaw_database', 'connection.commit()', 1),
    'withdraw-after-commit': ('recovery_thaw.py', 'thaw_database', 'supervisor.thaw(', 1),
    'old-partial': ('frozen_recovery_guard.py', 'thaw', 'os.chflags(path, entry.flags)', 2),
    'old-restored': ('frozen_recovery_guard.py', 'thaw', 'observed = self._inventory()', 1),
    'thawed-before-receipt': ('recovery_thaw.py', 'thaw_database', 'output.mkdir(', 1),
    'reseal-before': ('recovery_thaw_snapshot.py', 'reseal_controls', 'seal(roots,', 1),
    'reseal-partial': ('recovery_protection.py', 'seal', 'os.chflags(path,', 2),
}

PROGRAM: Final = '''import json,linecache,os,runpy,signal,sys
module,function,anchor,occurrence=json.loads(sys.argv.pop(1))
seen=0
def guard(event,args):
    if event == 'import' and (args[0] == 'app' or args[0].startswith('app.') or args[0] in ('torch','whisperx')):
        raise RuntimeError('candidate import prohibited')
    if event in ('socket.connect','subprocess.Popen'):
        raise RuntimeError('network or child prohibited')
def trace(frame,event,arg):
    global seen
    if event == 'line' and frame.f_code.co_filename.endswith('/'+module) and frame.f_code.co_name == function:
        line=linecache.getline(frame.f_code.co_filename,frame.f_lineno).strip()
        if line.startswith(anchor):
            seen += 1
            if seen == occurrence:
                print(json.dumps({'pid':os.getpid(),'module':module,'function':function,'line':frame.f_lineno,'source':line,'occurrence':seen}),flush=True)
                while True: signal.pause()
    return trace
sys.addaudithook(guard)
sys.settrace(trace)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
'''

def command(case: CrashCase, output: str) -> list[str]:
    return [str(case.bundle.parent / 'runtime/bin/python3.11'), '-I', '-S', '-B',
        '-c', PROGRAM, json.dumps(['unused', '', '', 1]), str(case.bundle.parent / 'reader.py'),
        '--mode', 'thaw', '--manifest', str(case.recipe), '--bundle', str(case.bundle),
        '--output-root', str(case.root / output)]

def observe(case: CrashCase, label: str) -> Path:
    with sqlite3.connect(case.database.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
        group = connection.execute('SELECT state,new_writes FROM migrationgroup WHERE id=?', (case.group,)).fetchone()
        bindings = connection.execute('SELECT state FROM taskbinding WHERE root_group_id=?', (case.group,)).fetchall()
    denied = False
    try:
        with (case.old / 'forbidden').open('xb'):
            pass
    except PermissionError:
        denied = True
    else:
        (case.old / 'forbidden').unlink()
    write_denials = {}
    for path in sorted(case.old.rglob('*')):
        if path.is_file():
            try:
                descriptor = os.open(path, os.O_WRONLY)
            except PermissionError:
                write_denials[str(path)] = True
            else:
                os.close(descriptor)
                write_denials[str(path)] = False
    receipt = case.root / f'{label}.json'
    receipt.write_text(json.dumps({'group': group, 'bindings': bindings, 'old_create_denied': denied, 'old_file_write_denied': write_denials,
        'old_modes': {str(path): [stat.S_IMODE(path.stat().st_mode), path.stat().st_flags] for path in [case.old, *case.old.rglob('*')]},
        'paths': {str(path): {'inode': path.stat().st_ino, 'mode': stat.S_IMODE(path.stat().st_mode),
            'flags': path.stat().st_flags} for path in [case.database, case.old, case.root / 'host-guard/.heavy.lock', *case.locks]},
        'thaw_allowed': (case.guard / 'thaw-allowed.json').exists(),
        'thawed': (case.guard / 'thawed.json').exists()}, indent=2))
    return receipt

def kill_at(case: CrashCase, boundary: str) -> None:
    invocation = command(case, 'interrupted')
    invocation[6] = json.dumps(BOUNDARIES[boundary])
    (case.root / 'invocation.json').write_text(json.dumps(invocation))
    with (case.root / 'child.stderr').open('w') as errors, subprocess.Popen(invocation,
            stdout=subprocess.PIPE, stderr=errors, text=True) as child:
        assert child.stdout is not None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                assert selector.select(timeout=60), 'boundary handshake timed out'
                handshake = child.stdout.readline()
            (case.root / 'handshake.json').write_text(handshake)
            assert handshake, (case.root / 'child.stderr').read_text()
            observed = json.loads(handshake)
            assert observed['pid'] == child.pid
            lock_held = []
            for lock in case.locks:
                with lock.open('rb') as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        lock_held.append(True)
                    else:
                        lock_held.append(False)
            (case.root / 'paused-locks.json').write_text(json.dumps(lock_held))
            if boundary in {'withdraw-before-commit', 'withdraw-after-commit', 'old-partial', 'old-restored'}:
                assert all(lock_held)
            os.kill(child.pid, signal.SIGKILL)
            result = child.wait(timeout=10)
            (case.root / 'kill.json').write_text(json.dumps({'pid': child.pid, 'signal': signal.SIGKILL, 'returncode': result}))
            assert result == -signal.SIGKILL
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
