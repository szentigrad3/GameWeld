"""Explicit-consent, original Win64 v2 IPC lab; never access running games.

This uses the exact Batch77 fixture SHA-256, protocol and bounded supervisor.
It does not verify or launch third-party trainers. No Steam or Proton launch.
"""
import hashlib
import os
import secrets
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from . import helpers

PROBE_BYTES=4096
PROBE_NAME='gameweld_sidecar_probe_v2.exe'
PROBE_SHA256='2c2aef90efc160aebb94d8c687641d0ca650a119145323949ff829029f472541'
MAX_STDOUT=4096
MAX_STDERR=16384
READY=b'GW77_READY\n'
COMMANDS=('PING','STATUS','STOP')
PREFIXES=('GW77_PONG ','GW77_STATUS OK ','GW77_STOPPED ')
STAGES=('ready','pong','status','stopped')


def frame(command, nonce):
    if command not in COMMANDS or len(nonce)!=16 or not all(c in '0123456789abcdef' for c in nonce):
        raise ValueError('invalid_protocol_command')
    return (command+' '+nonce+'\n').encode('ascii')


def expected_reply(index,nonce):
    return (PREFIXES[index]+nonce+'\n').encode('ascii')


def fixture_default_path():
    return Path.home()/'Downloads'/'gameweld-b77-native-lab'/'fixtures'/PROBE_NAME


def _probe_bytes(fixture):
    path=Path(fixture)
    if path.name!=PROBE_NAME or path.is_symlink():
        raise ValueError('fixture_name_or_link_invalid')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_CLOEXEC',0))
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size!=PROBE_BYTES:
            raise ValueError('fixture_size_invalid')
        payload=os.read(fd,PROBE_BYTES+1)
        if len(payload)!=PROBE_BYTES or hashlib.sha256(payload).hexdigest()!=PROBE_SHA256:
            raise ValueError('fixture_hash_invalid')
        if payload[:2]!=b'MZ':raise ValueError('fixture_format_invalid')
        pe=int.from_bytes(payload[0x3c:0x40],'little')
        if not 0<=pe<=len(payload)-26 or payload[pe:pe+6]!=b'PE\0\0\x64\x86':
            raise ValueError('fixture_format_invalid')
        return payload
    finally:os.close(fd)


def preflight(fixture=None):
    if fixture is None:fixture=fixture_default_path()
    try:_probe_bytes(fixture);pinned=True
    except (OSError,ValueError,IndexError):pinned=False
    return {'operation':'gameweld-ipc-preflight','schema_version':1,
            'pinned_fixture_verified':pinned,'system_wine_available':_find_wine() is not None,
            'safe_to_attach':False,'game_memory_accessed':False,'trainer_launched':False,
            'steam_modified':False,'raw_paths_disclosed':False,'fixture_process_started':False}


def _find_wine():
    candidate=shutil.which('wine') or shutil.which('wine64')
    if not candidate:return None
    try:
        path=Path(candidate).resolve(strict=True)
        if path.is_file() and os.access(path,os.X_OK):return str(path)
    except (OSError,RuntimeError):pass
    return None


def _environment(root):
    # Do not inherit the ambient Steam/Proton/Wine environment.
    for sub in ('home','config','cache','data','tmp'):
        (root/sub).mkdir(mode=0o700)
    env={'HOME':str(root/'home'),'XDG_CONFIG_HOME':str(root/'config'),
         'XDG_CACHE_HOME':str(root/'cache'),'XDG_DATA_HOME':str(root/'data'),
         'TMPDIR':str(root/'tmp'),'WINEPREFIX':str(root/'prefix'),
         'WINEARCH':'win64','WINEDEBUG':'-all','PATH':os.defpath,'LC_ALL':'C'}
    for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
        val=os.environ.get(key)
        if val and len(val)<1024 and '\0' not in val and '\n' not in val:env[key]=val
    auth=os.environ.get('XAUTHORITY')
    if auth and os.path.isabs(auth) and len(auth)<2048 and '\n' not in auth:
        try:
            st=os.lstat(auth)
            if stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o022:
                env['XAUTHORITY']=auth
        except OSError:pass
    return env

def _run_once_v2(wine, fixture, timeout, *, cancel_event=None):
    """Run the hash-pinned v2 PE only, on a private prefix, fail closed."""
    nonce=secrets.token_hex(8)  # never serialized to reports
    stage=0;started=False;reaped=False;timed_out=False;output_limit=False
    stopped=False;exit_zero=False;cleanup=False;error='not_started'
    stdout_bytes=0;stderr_bytes=0;linebuf=bytearray();timestamps=[];roundtrips={};sent_at={}
    began=time.monotonic();deadline=began+timeout
    active_helpers=None; helper_review=None
    launcher_spawn_ms=None; ready_wait_ms=None; launched_at=None
    temp=tempfile.TemporaryDirectory(prefix='gameweld77-ipc-wine-')
    process=None
    try:
        root=Path(temp.name);env=_environment(root)
        probe=root/PROBE_NAME
        fd=os.open(probe,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            mv=memoryview(fixture)
            while mv:
                count=os.write(fd,mv)
                if count<=0:raise OSError('write_failed')
                mv=mv[count:]
        finally:os.close(fd)
        spawn_began=time.monotonic()
        process=subprocess.Popen([wine,str(probe)],cwd=str(root),env=env,
             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
             close_fds=True,start_new_session=True,bufsize=0)
        launched_at=time.monotonic()
        launcher_spawn_ms=round((launched_at-spawn_began)*1000,3)
        started=True
        sel=selectors.DefaultSelector()
        try:
            sel.register(process.stdout,selectors.EVENT_READ,'stdout')
            sel.register(process.stderr,selectors.EVENT_READ,'stderr')
            error='protocol_incomplete'
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    error='cancelled';break
                remain=deadline-time.monotonic()
                if remain<=0:timed_out=True;error='timeout';break
                if process.poll() is not None and not sel.get_map():break
                for key,_ in sel.select(min(0.15,remain)):
                    part=os.read(key.fileobj.fileno(),1024)
                    if not part:
                        sel.unregister(key.fileobj);continue
                    if key.data=='stderr':
                        stderr_bytes+=len(part)
                        if stderr_bytes>MAX_STDERR:output_limit=True;error='stderr_limit';break
                        continue
                    stdout_bytes+=len(part)
                    if stdout_bytes>MAX_STDOUT:output_limit=True;error='stdout_limit';break
                    linebuf.extend(part)
                    while b'\n' in linebuf:
                        line,sep,remaining=linebuf.partition(b'\n')
                        linebuf=bytearray(remaining)
                        line=bytes(line)+b'\n'
                        expected=READY if stage==0 else expected_reply(stage-1,nonce) if stage<=3 else None
                        if expected is None or line.replace(b'\r\n',b'\n')!=expected:
                            error='unexpected_protocol_response';break
                        stage+=1
                        observed_at=time.monotonic()
                        timestamps.append(round((observed_at-began)*1000))
                        if stage == 1:
                            ready_wait_ms=round(max(0,observed_at-(launched_at or began))*1000,3)
                            try:active_helpers=helpers.snapshot_active(env['WINEPREFIX'],
                                owned_pgid=process.pid)
                            except (OSError, ValueError):active_helpers=None
                        if stage>1 and stage-2 in sent_at:
                            roundtrips[COMMANDS[stage-2].lower()]=round((observed_at-sent_at[stage-2])*1000,3)
                        if stage<=3:
                            try:
                                process.stdin.write(frame(COMMANDS[stage-1],nonce))
                                process.stdin.flush()
                                sent_at[stage-1]=time.monotonic()
                                if stage==3:process.stdin.close()
                            except (BrokenPipeError,OSError,ValueError):
                                error='stdin_unavailable';break
                    if error in ('unexpected_protocol_response','stdin_unavailable'):break
                if output_limit or error in ('unexpected_protocol_response','stdin_unavailable'):break
            if process.poll() is not None:exit_zero=process.returncode==0
            stopped=stage==4 and not linebuf
            if stopped and exit_zero and not timed_out and not output_limit and error=='protocol_incomplete':error='none'
        finally:sel.close()
    except (OSError,ValueError) as exc:
        error='fixture_or_launcher_error'
    finally:
        if process is not None:
            if process.poll() is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except (ProcessLookupError,OSError):
                    try:process.kill()
                    except OSError:pass
            try:process.wait(timeout=3);reaped=True
            except (OSError,subprocess.TimeoutExpired):reaped=False
            for pipe in (process.stdin,process.stdout,process.stderr):
                try:pipe.close()
                except (OSError,ValueError,AttributeError):pass
        try:helper_review=helpers.review(active_helpers)
        except (OSError, ValueError):helper_review={'state':'review_failed','all_detached_helpers_reaped_verified':False,'raw_process_details_disclosed':False}
        try:temp.cleanup();cleanup=True
        except OSError:cleanup=False
    all_good=all((started,stage==4,stopped,exit_zero,reaped,cleanup)) and not timed_out and not output_limit
    return {'state':'owned_win64_v2_protocol_verified' if all_good else 'owned_win64_v2_protocol_failed',
        'fixture_process_started':started,'protocol_stages_completed':stage,
        'ready_verified':stage>=1,'ping_pong_verified':stage>=2,'status_verified':stage>=3,
        'stop_ack_verified':stage>=4,'launcher_exit_zero':exit_zero,
        'owned_launcher_reaped':reaped,'temporary_prefix_cleanup_verified':cleanup,
        'milestone_elapsed_ms':dict(zip(STAGES,timestamps)),
        'roundtrip_ms':roundtrips,
        'startup_elapsed_ms':timestamps[0] if timestamps else None,
        'launcher_spawn_ms':launcher_spawn_ms,
        'wine_ready_wait_ms':ready_wait_ms,
        'post_ready_session_ms':round(max(0,(time.monotonic()-began)*1000-timestamps[0]),3) if timestamps else None,
        'session_elapsed_ms':round((time.monotonic()-began)*1000),
        'observed_helper_review':helper_review,
        'timeout_reached':timed_out,'output_limit_reached':output_limit,
        'error_category':error if not all_good else 'none',
        'stdout_bytes_observed':stdout_bytes,'stderr_bytes_observed':stderr_bytes,
        'probe_challenge_disclosed':False,'raw_paths_disclosed':False,
        'raw_stdout_disclosed':False,'raw_stderr_disclosed':False,
        'detached_wine_helpers_reaped_verified':False}


def run_probe(*, consent=False, fixture=None, timeout=75, cancel_event=None):
    """A single owned, isolated session; no arbitrary binary can pass the SHA gate."""
    base={'operation':'gameweld-ipc-fixture','schema_version':1,'fixture_only':True,
          'trainer_launched':False,'game_memory_accessed':False,'steam_modified':False,
          'safe_to_attach':False,'game_process_accessed':False,
          'detached_wine_helpers_reaped_verified':False,'raw_paths_disclosed':False}
    if consent is not True:
        return {**base,'state':'consent_required','fixture_process_started':False}
    if type(timeout) not in (float,int) or not 10<=timeout<=120:
        raise ValueError('invalid_timeout')
    try:payload=_probe_bytes(fixture if fixture is not None else fixture_default_path())
    except (OSError,ValueError,IndexError):
        return {**base,'state':'fixture_integrity_failed','fixture_process_started':False}
    wine=_find_wine()
    if wine is None:return {**base,'state':'system_wine_unavailable','fixture_process_started':False}
    result=_run_once_v2(wine,payload,timeout,cancel_event=cancel_event)
    return {**base,**result}


def run_benchmark(*, consent=False, fixture=None, timeout=75, runs=2, cancel_event=None):
    """Run 1-3 fresh, hash-pinned isolated sessions, stopping at first failure."""
    if type(runs) is not int or not 1 <= runs <= 3:
        raise ValueError('invalid_run_count')
    base={'operation':'gameweld-ipc-benchmark','schema_version':1,'runs_requested':runs,
          'trainer_launched':False,'game_memory_accessed':False,'steam_modified':False,
          'safe_to_attach':False,'raw_paths_disclosed':False,
          'detached_wine_helpers_reaped_verified':False}
    if consent is not True:
        return {**base,'state':'consent_required','runs_completed':0,'attempts':[]}
    attempts=[]
    for _ in range(runs):
        if cancel_event is not None and cancel_event.is_set():
            break
        attempt=run_probe(consent=True,fixture=fixture,timeout=timeout,
                          cancel_event=cancel_event)
        attempts.append(attempt)
        if attempt.get('state') != 'owned_win64_v2_protocol_verified':
            break
    success=len(attempts)==runs and all(
        a.get('state')=='owned_win64_v2_protocol_verified' for a in attempts)
    startups=[a['startup_elapsed_ms'] for a in attempts if a.get('startup_elapsed_ms') is not None]
    ipc_metrics={key:[a.get('roundtrip_ms',{}).get(key) for a in attempts
                      if isinstance(a.get('roundtrip_ms',{}).get(key), (int,float))]
                 for key in ('ping','status','stop')}
    cancelled = cancel_event is not None and cancel_event.is_set()
    return {**base,'state':'isolated_ipc_benchmark_verified' if success else
            'isolated_ipc_benchmark_cancelled' if cancelled else 'isolated_ipc_benchmark_failed',
            'runs_completed':len(attempts),'all_protocols_verified':success,
            'startup_elapsed_ms':startups,
            'startup_min_ms':min(startups) if startups else None,
            'startup_max_ms':max(startups) if startups else None,
            'startup_mean_ms':round(sum(startups)/len(startups),1) if startups else None,
            'roundtrip_ms_by_command':ipc_metrics,
            'launcher_spawn_ms':[a.get('launcher_spawn_ms') for a in attempts],
            'wine_ready_wait_ms':[a.get('wine_ready_wait_ms') for a in attempts],
            'attempts':attempts}
