#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / 'scripts/gameweld-lutris-provider.py'
SESSION = ROOT / 'scripts/gameweld-lutris-session.sh'
UI = ROOT / 'crates/wand-ui/appimage-gtk3/gameweld-native-040.c'
BUILD = ROOT / 'scripts/build-gameweld-0.8.0-dev1-appimage.sh'
passed = failed = 0


def check(ok: bool, name: str, detail: str = '') -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f'PASS {passed}: {name}')
    else:
        failed += 1
        print(f"FAIL: {name}{': ' + detail if detail else ''}")


def make_exec(path: Path, body: str = '#!/bin/sh\nexit 0\n') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)


def make_prefix(path: Path) -> None:
    (path / 'drive_c/windows').mkdir(parents=True, exist_ok=True)
    (path / 'dosdevices').mkdir(parents=True, exist_ok=True)
    (path / 'system.reg').write_text('WINE REGISTRY Version 2\n')


def proc_entry(root: Path, pid: int, *, env: dict[str, str], argv: list[str], comm: str, ppid: int = 1, exe: Path | None = None) -> None:
    d = root / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'environ').write_bytes(b'\0'.join(f'{k}={v}'.encode() for k, v in env.items()) + b'\0')
    (d / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv) + b'\0')
    (d / 'comm').write_text(comm + '\n')
    (d / 'stat').write_text(f'{pid} ({comm}) S {ppid} 0 0 0 0\n')
    (d / 'ns').mkdir(exist_ok=True)
    if exe is not None:
        (d / 'exe').symlink_to(exe)


def marker(appid: str, trainer: Path) -> str:
    import re
    base = re.sub(r'[^A-Za-z0-9_.-]', '_', trainer.name)
    return f'gameweld-lutris-{appid}-{base}'


def run_session(args: list[str], proc_root: Path, state_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env['GAMEWELD_PROC_ROOT'] = str(proc_root)
    env['XDG_STATE_HOME'] = str(state_root)
    return subprocess.run([str(SESSION), *args], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)


# 1-2 syntax checks.
check(subprocess.run([sys.executable, '-m', 'py_compile', str(PROVIDER)]).returncode == 0, 'Lutris provider compiles')
check(subprocess.run(['bash', '-n', str(SESSION)]).returncode == 0, 'Lutris live-session helper passes bash -n')

# 3-6 provider: preserve Test 3 resolver, but enable launch only for fully resolved entries.
with tempfile.TemporaryDirectory(prefix='gameweld-lutris-test4-provider-') as td:
    t = Path(td); home = t/'home'; cfg=t/'config/lutris'; data=t/'data/lutris'; games=cfg/'games'
    home.mkdir(); games.mkdir(parents=True); data.mkdir(parents=True)
    umu=data/'runtime/umu/umu-run'; make_exec(umu)
    pfx=t/'Battle.net'; make_prefix(pfx)
    exe=pfx/'drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe'; exe.parent.mkdir(parents=True); exe.write_bytes(b'MZbattle')
    (games/'battle-net-613.yml').write_text("""name: Battle.net\nrunner: wine\ngame:\n  exe: 'C:\\\\Program Files (x86)\\\\Battle.net\\\\Battle.net Launcher.exe'\nwine:\n  version: Proton-GE Latest\n""")
    db=data/'pga.db'; con=sqlite3.connect(db); con.execute('CREATE TABLE games (id INTEGER, name TEXT, slug TEXT, runner TEXT, configpath TEXT, directory TEXT, installed INTEGER)'); con.execute('INSERT INTO games VALUES (613, ?, ?, ?, ?, ?, 1)', ('Battle.net','battle-net','wine','battle-net-613',str(pfx))); con.commit(); con.close()
    env={**os.environ,'HOME':str(home),'XDG_DATA_HOME':str(home/'.local/share'),'GAMEWELD_LUTRIS_CONFIG_ROOT':str(cfg),'GAMEWELD_LUTRIS_DATA_ROOT':str(data),'PATH':'/usr/bin:/bin'}
    cp=subprocess.run([sys.executable,str(PROVIDER),'list'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]; row=rows[0] if rows else {}
    check(cp.returncode == 0 and row.get('prefix') == str(pfx) and row.get('executable') == str(exe), 'Battle.net prefix + Windows target recovery preserved', repr(row))
    check(row.get('wine_bin') == str(umu.resolve()) and row.get('wine_type') == 'lutris-umu-proton', 'Proton-GE Latest still resolves through concrete Lutris UMU', repr(row))
    check(row.get('resolution_state') == 'resolved' and row.get('launch_supported') is True and row.get('session_handoff_supported') is True, 'fully resolved Lutris entry is Test 4 launch/handoff eligible', repr(row))
    umu.rename(umu.with_suffix('.off'))
    try:
        cp2=subprocess.run([sys.executable,str(PROVIDER),'list'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        r2=[json.loads(x) for x in cp2.stdout.splitlines() if x.strip()][0]
    finally:
        umu.with_suffix('.off').rename(umu)
    check(r2.get('resolution_state') == 'partial-runtime' and r2.get('launch_supported') is False, 'unresolved Lutris entry remains fail-closed', repr(r2))

# 7-9 classic Wine exact-prefix same-session handoff.
with tempfile.TemporaryDirectory(prefix='gameweld-lutris-test4-wine-') as td:
    t=Path(td); proc=t/'proc'; proc.mkdir(); state=t/'state'; pfx=t/'prefix'; make_prefix(pfx)
    game=pfx/'drive_c/Game/Game.exe'; game.parent.mkdir(parents=True); game.write_bytes(b'MZgame')
    trainer=t/'Trainer.exe'; trainer.write_bytes(b'MZtrainer')
    wine=t/'wine'; make_exec(wine)
    proc_entry(proc,100,env={'WINEPREFIX':str(pfx)},argv=[str(game)],comm='Game.exe')
    proc_entry(proc,101,env={'WINEPREFIX':str(pfx),'GAMEWELD_LUTRIS_TRAINER_MARKER':marker('701',trainer)},argv=[str(trainer)],comm='Trainer.exe')
    cp=run_session(['trainer','701','Classic Fixture','lutris:rungameid/701',str(pfx),'lutris-wine',str(wine),'',str(game),str(game.parent),str(trainer),'wine-ge'],proc,state)
    result=(state/'gameweld/lutris-701.result').read_text() if (state/'gameweld/lutris-701.result').exists() else ''
    check(cp.returncode == 0 and 'launch_path=lutris-live-wine' in result, 'classic Wine trainer reuses exact live Lutris prefix', cp.stderr+'\n'+result)
    check('game_pid=100' in result and 'trainer_pid=101' in result, 'classic Wine handoff confirms game and trainer process ownership', result)
    check('summary=Trainer joined the selected live Lutris compatibility session' in result, 'classic Wine result records same-session confirmation', result)

# 10-12 UMU/Proton exact runtime-service ownership; unrelated service must not be selected.
with tempfile.TemporaryDirectory(prefix='gameweld-lutris-test4-umu-') as td:
    t=Path(td); proc=t/'proc'; proc.mkdir(); state=t/'state'; pfx=t/'prefix'; make_prefix(pfx)
    game=pfx/'drive_c/Game/Game.exe'; game.parent.mkdir(parents=True); game.write_bytes(b'MZgame')
    trainer=t/'Trainer.exe'; trainer.write_bytes(b'MZtrainer')
    umu=t/'umu-run'; make_exec(umu)
    proton_root=t/'GE-Proton10-34'; make_exec(proton_root/'proton'); make_exec(proton_root/'files/bin/wine')
    runtime=t/'runtime/bin'; service=runtime/'steam-runtime-launcher-service'; client=runtime/'steam-runtime-launch-client'; make_exec(service); make_exec(client)
    other=t/'other-prefix'; make_prefix(other)
    proc_entry(proc,300,env={'WINEPREFIX':str(pfx),'PROTONPATH':str(proton_root)},argv=[str(game)],comm='Game.exe')
    proc_entry(proc,150,env={'WINEPREFIX':str(other)},argv=[str(service),'--bus-name=:1.22'],comm='steam-runtime-launcher-service',exe=service)
    proc_entry(proc,200,env={'WINEPREFIX':str(pfx)},argv=[str(service),'--bus-name=:1.77'],comm='steam-runtime-launcher-service',exe=service)
    proc_entry(proc,301,env={'WINEPREFIX':str(pfx),'GAMEWELD_LUTRIS_TRAINER_MARKER':marker('702',trainer)},argv=[str(trainer)],comm='Trainer.exe')
    cp=run_session(['trainer','702','UMU Fixture','lutris:rungameid/702',str(pfx),'lutris-umu-proton',str(umu),str(proton_root),str(game),str(game.parent),str(trainer),'Proton-GE Latest'],proc,state)
    result=(state/'gameweld/lutris-702.result').read_text() if (state/'gameweld/lutris-702.result').exists() else ''
    check(cp.returncode == 0 and 'launch_path=lutris-umu-live-container' in result, 'UMU trainer handoff re-enters proven live container service', cp.stderr+'\n'+result)
    check('runtime_bus=:1.77' in result and 'trainer_pid=301' in result, 'UMU handoff selects exact same-prefix bus and confirms trainer', result)
    check(':1.22' not in result, 'unrelated runtime service is rejected rather than guessed', result)

# 13 fail closed when live UMU runtime service cannot be proven.
with tempfile.TemporaryDirectory(prefix='gameweld-lutris-test4-noservice-') as td:
    t=Path(td); proc=t/'proc'; proc.mkdir(); state=t/'state'; pfx=t/'prefix'; make_prefix(pfx)
    game=pfx/'drive_c/Game/Game.exe'; game.parent.mkdir(parents=True); game.write_bytes(b'MZgame')
    trainer=t/'Trainer.exe'; trainer.write_bytes(b'MZtrainer'); umu=t/'umu-run'; make_exec(umu)
    proton=t/'GE-Proton'; make_exec(proton/'proton'); make_exec(proton/'files/bin/wine')
    proc_entry(proc,400,env={'WINEPREFIX':str(pfx),'PROTONPATH':str(proton)},argv=[str(game)],comm='Game.exe')
    cp=run_session(['trainer','703','No Service','lutris:rungameid/703',str(pfx),'lutris-umu-proton',str(umu),str(proton),str(game),str(game.parent),str(trainer),'GE-Proton'],proc,state)
    result=(state/'gameweld/lutris-703.result').read_text() if (state/'gameweld/lutris-703.result').exists() else ''
    check(cp.returncode == 8 and 'reason=live-runtime-service-unproven' in result, 'UMU trainer handoff fails closed without proven live service', cp.stderr+'\n'+result)

# 14 native UI/build integration advertises Test4 path and keeps advanced providers closed.
ui=UI.read_text(errors='replace'); build=BUILD.read_text(errors='replace') if BUILD.exists() else ''
required=[
    '0.8.0 Dev 1 • Game & Trainer Management',
    '0.8.0 Dev 1',
    'spawn_lutris_normal', 'spawn_lutris_trainer', 'lutris_session_ready',
    'gameweld-lutris-session.sh',
    'lutris_test4_extended_blocked',
    'same-prefix live session',
]
build_required=['X-AppImage-Version=0.8.0-dev1','gameweld-lutris-session.sh','RELEASE-NOTES-0.8.0-dev1.md']
check(all(x in ui for x in required) and all(x in build for x in build_required), 'native UI and AppImage build retain Test 4 live-session helper and fail-closed boundary')

print(f'\nGameWeld 0.8.0 Dev 1 inherited Lutris live-session regression: {passed}/14 PASS' if failed == 0 else f'\nGameWeld 0.8.0 Dev 1 inherited Lutris live-session regression: {passed} PASS, {failed} FAIL')
raise SystemExit(0 if failed == 0 and passed == 14 else 1)
