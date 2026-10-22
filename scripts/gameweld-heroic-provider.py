#!/usr/bin/env python3
import json, os, sys, pathlib, shutil, tempfile, hashlib
from urllib.parse import quote

HOME = pathlib.Path(os.environ.get('HOME','~')).expanduser()

def canonical_root(path):
    p=pathlib.Path(path).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p

def root_scope(path):
    return hashlib.sha256(str(canonical_root(path)).encode('utf-8','surrogateescape')).hexdigest()[:12]

def roots():
    out=[]
    preferred=os.environ.get('GAMEWELD_HEROIC_ROOT','').strip()
    if preferred:
        out.append(pathlib.Path(preferred).expanduser())
    xdg=os.environ.get('XDG_CONFIG_HOME')
    if xdg:
        out.append(pathlib.Path(xdg)/'heroic')
    out += [HOME/'.config/heroic', HOME/'.var/app/com.heroicgameslauncher.hgl/config/heroic']
    seen=set(); r=[]
    for p in out:
        try: q=p.resolve()
        except Exception: q=p
        s=str(q)
        if s not in seen and p.exists(): seen.add(s); r.append(p)
    return r

def load_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default

def file_sha256(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def game_settings(root, appid):
    p=root/'GamesConfig'/f'{appid}.json'
    j=load_json(p,{}) or {}
    s=j.get(appid,j if isinstance(j,dict) else {})
    if not isinstance(s,dict): s={}
    wv=s.get('wineVersion') if isinstance(s.get('wineVersion'),dict) else {}
    return {
        'prefix': str(s.get('winePrefix') or ''),
        'wine_type': str(wv.get('type') or ''),
        'wine_bin': str(wv.get('bin') or ''),
        'wine_name': str(wv.get('name') or ''),
        'target_exe': str(s.get('targetExe') or ''),
    }

def icon_for(root, appid, install=''):
    for ext in ('.jpg','.png','.jpeg','.webp'):
        p=root/'icons'/f'{appid}{ext}'
        if p.is_file(): return str(p)
    if install:
        for p in pathlib.Path(install).glob(f'goggame-{appid}.ico'):
            if p.is_file(): return str(p)
    return ''

def gog_info(appid, install):
    if not install: return {}, ''
    p=pathlib.Path(install)/f'goggame-{appid}.info'
    j=load_json(p,{}) or {}
    title=str(j.get('name') or j.get('title') or '')
    exe=''
    tasks=j.get('playTasks') or []
    if isinstance(tasks,list):
        for t in tasks:
            if isinstance(t,dict) and t.get('isPrimary') and t.get('path'):
                exe=str(t['path']); break
        if not exe:
            for t in tasks:
                if isinstance(t,dict) and t.get('path'):
                    exe=str(t['path']); break
    return j,title or pathlib.Path(install).name,exe

def largest_exe(install):
    if not install or not pathlib.Path(install).is_dir(): return ''
    best=None
    try:
        for p in pathlib.Path(install).rglob('*.exe'):
            low=p.name.lower()
            if any(x in low for x in ('unins','uninstall','crashreport','crashpad','easyanticheat','eac_launcher','vc_redist','vcredist','dxsetup','battleye','beservice')):
                continue
            try: sz=p.stat().st_size
            except OSError: continue
            if best is None or sz>best[0]: best=(sz,p)
    except Exception: pass
    return str(best[1]) if best else ''

def emit(game, seen):
    key=(game.get('runner',''),game.get('appid',''))
    if not key[1] or key in seen: return
    seen.add(key)
    install=game.get('install_dir','')
    exe=game.get('executable','')
    if exe and install and not os.path.isabs(exe): exe=os.path.join(install,exe)
    if not exe and install: exe=largest_exe(install)
    game['executable']=exe
    game['provider']='heroic'
    game['key']=f"heroic:{game.get('runner','unknown')}:{game['appid']}"
    print(json.dumps(game,ensure_ascii=False,separators=(',',':')))

def discover():
    seen=set()
    for root in roots():
        # Epic / Legendary - current Heroic path plus legacy standalone Legendary path.
        candidates=[root/'legendaryConfig/legendary/installed.json']
        if root == HOME/'.config/heroic': candidates.append(HOME/'.config/legendary/installed.json')
        for p in candidates:
            j=load_json(p,{}) or {}
            if not isinstance(j,dict): continue
            for appid,meta in j.items():
                if not isinstance(meta,dict) or meta.get('is_dlc'): continue
                platform=str(meta.get('platform') or '')
                if platform and platform.lower() not in ('windows','win32'): continue
                install=str(meta.get('install_path') or '')
                s=game_settings(root,str(appid))
                emit({
                    'runner':'legendary','appid':str(appid),'name':str(meta.get('title') or appid),
                    'install_dir':install,'executable':str(meta.get('executable') or s['target_exe']),
                    'prefix':s['prefix'],'wine_type':s['wine_type'],'wine_bin':s['wine_bin'],'wine_name':s['wine_name'],
                    'art_path':icon_for(root,str(appid),install),'heroic_root':str(root)
                },seen)
        # GOG - electron-store file: {"installed":[...]}
        p=root/'gog_store/installed.json'; j=load_json(p,{}) or {}
        arr=j.get('installed',[]) if isinstance(j,dict) else (j if isinstance(j,list) else [])
        for meta in arr:
            if not isinstance(meta,dict) or meta.get('is_dlc'): continue
            appid=str(meta.get('appName') or meta.get('app_name') or meta.get('id') or '')
            if not appid: continue
            platform=str(meta.get('platform') or '')
            if platform and platform.lower() in ('linux','osx','mac'): continue
            install=str(meta.get('install_path') or meta.get('path') or '')
            info,title,gogexe=gog_info(appid,install); s=game_settings(root,appid)
            emit({
                'runner':'gog','appid':appid,'name':str(meta.get('title') or title or appid),
                'install_dir':install,'executable':str(meta.get('executable') or gogexe or s['target_exe']),
                'prefix':s['prefix'],'wine_type':s['wine_type'],'wine_bin':s['wine_bin'],'wine_name':s['wine_name'],
                'art_path':icon_for(root,appid,install),'heroic_root':str(root)
            },seen)
        # Amazon / Nile
        ip=root/'nile_config/nile/installed.json'; installed=load_json(ip,[]) or []
        lp=root/'nile_config/nile/library.json'; library=load_json(lp,[]) or []
        titles={}
        if isinstance(library,list):
            for item in library:
                try:
                    prod=item.get('product',{}); pid=str(prod.get('id') or ''); title=str(prod.get('title') or prod.get('productDetail',{}).get('title') or '')
                    if pid: titles[pid]=title
                except Exception: pass
        if isinstance(installed,list):
            for meta in installed:
                if not isinstance(meta,dict): continue
                appid=str(meta.get('id') or meta.get('appName') or '')
                if not appid: continue
                install=str(meta.get('path') or meta.get('install_path') or '')
                s=game_settings(root,appid)
                emit({
                    'runner':'nile','appid':appid,'name':str(meta.get('title') or titles.get(appid) or pathlib.Path(install).name or appid),
                    'install_dir':install,'executable':str(meta.get('executable') or s['target_exe']),
                    'prefix':s['prefix'],'wine_type':s['wine_type'],'wine_bin':s['wine_bin'],'wine_name':s['wine_name'],
                    'art_path':icon_for(root,appid,install),'heroic_root':str(root)
                },seen)


def game_config_path(appid):
    # When the UI supplied the Heroic root that discovered this game, never
    # silently fall through to another Heroic installation containing the same
    # app id.  This protects Flatpak/native parallel installs and test profiles.
    preferred=os.environ.get('GAMEWELD_HEROIC_ROOT','').strip()
    if preferred:
        root=canonical_root(preferred)
        p=root/'GamesConfig'/f'{appid}.json'
        return (root,p) if p.is_file() else (None,None)
    for root in roots():
        p=root/'GamesConfig'/f'{appid}.json'
        if p.is_file():
            return root,p
    return None,None

def preflight(appid):
    root,p=game_config_path(appid)
    if p is None:
        print(json.dumps({'ok':False,'state':'missing-config','appid':appid,'heroic_root':os.environ.get('GAMEWELD_HEROIC_ROOT',''),'message':'Selected game config was not found under the exact Heroic installation.'},ensure_ascii=False))
        return 4
    j=load_json(p,{}) or {}
    nested=appid in j and isinstance(j.get(appid),dict) if isinstance(j,dict) else False
    settings=j.get(appid,{}) if nested else (j if isinstance(j,dict) else {})
    if not isinstance(settings,dict): settings={}
    wv=settings.get('wineVersion') if isinstance(settings.get('wineVersion'),dict) else {}
    payload={
        'ok':True,'state':'ready','appid':appid,'heroic_root':str(root),'scope':root_scope(root),
        'config_path':str(p),'config_sha256':file_sha256(p),
        'prefix':str(settings.get('winePrefix') or ''),'target_exe':str(settings.get('targetExe') or ''),
        'wine_type':str(wv.get('type') or ''),'wine_bin':str(wv.get('bin') or ''),'wine_name':str(wv.get('name') or ''),
        'wine_wayland':bool(settings.get('enableWineWayland',False)),
    }
    print(json.dumps(payload,ensure_ascii=False))
    return 0

def ensure_umu_nsenter(appid):
    root,p=game_config_path(appid)
    if p is None:
        print(json.dumps({'ok':False,'state':'missing-config','appid':appid,'message':'Heroic GamesConfig file not found'}))
        return 4
    j=load_json(p,{}) or {}
    if not isinstance(j,dict):
        print(json.dumps({'ok':False,'state':'invalid-config','appid':appid,'path':str(p)}))
        return 5
    nested = appid in j and isinstance(j.get(appid),dict)
    settings = j[appid] if nested else j
    envs=settings.get('enviromentOptions')
    if not isinstance(envs,list): envs=[]
    changed=False
    found=False
    cleaned=[]
    for item in envs:
        if not isinstance(item,dict):
            cleaned.append(item); continue
        key=str(item.get('key') or '')
        if key=='UMU_CONTAINER_NSENTER':
            if found:
                changed=True
                continue
            found=True
            if str(item.get('value') or '')!='1':
                item=dict(item); item['value']='1'; changed=True
        cleaned.append(item)
    if not found:
        cleaned.append({'key':'UMU_CONTAINER_NSENTER','value':'1'}); changed=True
    if cleaned != envs:
        settings['enviromentOptions']=cleaned; changed=True
    if nested: j[appid]=settings
    else: j=settings
    backup_dir=pathlib.Path(os.environ.get('XDG_STATE_HOME',str(HOME/'.local/state')))/'gameweld'/'heroic-config-backups'
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/f'{appid}.json'
    if changed and not backup.exists():
        try: shutil.copy2(p,backup)
        except Exception: pass
    if changed:
        tmp=p.with_name(p.name+f'.gameweld-{os.getpid()}.tmp')
        tmp.write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        os.replace(tmp,p)
    print(json.dumps({'ok':True,'state':'enabled' if changed else 'already-enabled','appid':appid,'path':str(p),'backup':str(backup) if backup.exists() else ''},ensure_ascii=False))
    return 0

def nsenter_status(appid):
    root,p=game_config_path(appid)
    if p is None:
        print(json.dumps({'ok':False,'enabled':False,'state':'missing-config','appid':appid}))
        return 4
    j=load_json(p,{}) or {}
    s=j.get(appid,j if isinstance(j,dict) else {})
    envs=s.get('enviromentOptions',[]) if isinstance(s,dict) else []
    enabled=any(isinstance(x,dict) and str(x.get('key') or '')=='UMU_CONTAINER_NSENTER' and str(x.get('value') or '')=='1' for x in envs if isinstance(envs,list))
    print(json.dumps({'ok':True,'enabled':enabled,'state':'enabled' if enabled else 'disabled','appid':appid,'path':str(p)},ensure_ascii=False))
    return 0



def _atomic_write_json(path, obj):
    tmp=path.with_name(path.name+f'.gameweld-{os.getpid()}.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(tmp,path)

def _session_runner_state_path(appid):
    state_dir=pathlib.Path(os.environ.get('XDG_STATE_HOME',str(HOME/'.local/state')))/'gameweld'/'heroic-session-runner'
    state_dir.mkdir(parents=True,exist_ok=True)
    legacy=state_dir/f'{appid}.json'
    preferred=os.environ.get('GAMEWELD_HEROIC_ROOT','').strip()
    if not preferred:
        return legacy
    try:
        scope=str(pathlib.Path(preferred).expanduser().resolve())
    except Exception:
        scope=str(pathlib.Path(preferred).expanduser())
    token=hashlib.sha256(scope.encode('utf-8','surrogateescape')).hexdigest()[:12]
    scoped=state_dir/f'{appid}-{token}.json'
    # Recover a stale pre-0.2.2 unscoped state once, then future sessions use
    # the exact Heroic-root-scoped state file.
    if not scoped.exists() and legacy.exists():
        return legacy
    return scoped

def restore_session_runner(appid):
    state=_session_runner_state_path(appid)
    if not state.is_file():
        print(json.dumps({'ok':True,'state':'nothing-to-restore','appid':appid}))
        return 0
    meta=load_json(state,{}) or {}
    cfg=pathlib.Path(str(meta.get('config_path') or ''))
    backup=pathlib.Path(str(meta.get('backup_path') or ''))
    if not cfg:
        print(json.dumps({'ok':False,'state':'invalid-state','appid':appid,'state_path':str(state)}))
        return 6
    if not backup.is_file():
        print(json.dumps({'ok':False,'state':'missing-backup','appid':appid,'state_path':str(state),'backup':str(backup)}))
        return 7
    expected=str(meta.get('original_sha256') or '')
    try:
        shutil.copy2(backup,cfg)
        actual=file_sha256(cfg) if cfg.is_file() else ''
        byte_exact=(not expected) or actual==expected
        if not byte_exact:
            print(json.dumps({'ok':False,'state':'restore-verify-failed','appid':appid,'path':str(cfg),'expected_sha256':expected,'actual_sha256':actual},ensure_ascii=False))
            return 9
        backup.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
    except Exception as e:
        print(json.dumps({'ok':False,'state':'restore-failed','appid':appid,'error':str(e),'path':str(cfg)}))
        return 8
    print(json.dumps({'ok':True,'state':'restored','appid':appid,'path':str(cfg),'byte_exact':True,'sha256':actual},ensure_ascii=False))
    return 0

def begin_session_runner(appid, proton_bin, wine_wayland=True):
    root,p=game_config_path(appid)
    if p is None:
        print(json.dumps({'ok':False,'state':'missing-config','appid':appid,'message':'Heroic GamesConfig file not found'}))
        return 4
    proton=pathlib.Path(proton_bin).expanduser()
    if not proton.is_file():
        print(json.dumps({'ok':False,'state':'missing-proton','appid':appid,'proton':str(proton)}))
        return 5

    # Recover an interrupted prior temporary session before taking a new snapshot.
    state=_session_runner_state_path(appid)
    if state.is_file():
        rc=restore_session_runner(appid)
        if rc:
            return rc
        state=_session_runner_state_path(appid)

    j=load_json(p,{}) or {}
    if not isinstance(j,dict):
        print(json.dumps({'ok':False,'state':'invalid-config','appid':appid,'path':str(p)}))
        return 5
    nested = appid in j and isinstance(j.get(appid),dict)
    settings = j[appid] if nested else j
    if not isinstance(settings,dict):
        print(json.dumps({'ok':False,'state':'invalid-settings','appid':appid,'path':str(p)}))
        return 5

    state_dir=state.parent
    backup=state.with_suffix('.original.json')
    try:
        shutil.copy2(p,backup)
    except Exception as e:
        print(json.dumps({'ok':False,'state':'backup-failed','appid':appid,'error':str(e),'path':str(p)}))
        return 6

    old_wv=settings.get('wineVersion') if isinstance(settings.get('wineVersion'),dict) else {}
    wv=dict(old_wv)
    wv['bin']=str(proton)
    wv['name']=proton.parent.name or 'GE-Proton10-34'
    wv['type']='proton'
    settings['wineVersion']=wv
    # Wine-Wayland is part of the proven Heroic FLiNG compatibility session,
    # but Electron-based Wand/WeMod needs to be able to request the X11 path.
    # This remains session-only; the complete Heroic config is restored verbatim.
    settings['enableWineWayland']=bool(wine_wayland)

    # 0.2.2 Test 4: Heroic's Epic/Legendary backend may run Proton inside an
    # UMU pressure-vessel container.  A host-side Wine process cannot reliably
    # join that live wineserver and can remain queued until the game exits.
    # Enable the UMU launcher-service bridge as part of the SAME temporary
    # snapshot as the Proton/Wine-Wayland override.  Heroic consumes this at
    # game startup; restoring the JSON later does not tear down the already
    # running launcher service.
    envs=settings.get('enviromentOptions')
    if not isinstance(envs,list):
        envs=[]
    cleaned=[]
    found_nsenter=False
    for item in envs:
        if isinstance(item,dict) and str(item.get('key') or '')=='UMU_CONTAINER_NSENTER':
            if found_nsenter:
                continue
            item=dict(item)
            item['value']='1'
            found_nsenter=True
        cleaned.append(item)
    if not found_nsenter:
        cleaned.append({'key':'UMU_CONTAINER_NSENTER','value':'1'})
    settings['enviromentOptions']=cleaned
    if nested: j[appid]=settings
    else: j=settings
    try:
        _atomic_write_json(p,j)
        state.write_text(json.dumps({
            'appid':appid,
            'config_path':str(p),
            'backup_path':str(backup),
            'heroic_root':str(root),
            'original_sha256':file_sha256(backup),
            'proton':str(proton),
            'old_wine_version':old_wv,
            'old_enableWineWayland':load_json(backup,{}).get(appid,load_json(backup,{}) or {}).get('enableWineWayland') if isinstance(load_json(backup,{}),dict) else None
        },indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    except Exception as e:
        try:
            shutil.copy2(backup,p)
        except Exception:
            pass
        print(json.dumps({'ok':False,'state':'write-failed','appid':appid,'error':str(e),'path':str(p)}))
        return 7
    print(json.dumps({
        'ok':True,'state':'temporary-runner-enabled','appid':appid,'path':str(p),
        'proton':str(proton),'wineWayland':bool(wine_wayland),'restore_state':str(state)
    },ensure_ascii=False))
    return 0



def _is_gameweld_wand_runner(wv):
    if not isinstance(wv,dict):
        return False
    blob=' '.join(str(wv.get(k) or '') for k in ('bin','name','type')).lower()
    return ('ge-proton-wand-sha256' in blob or 'proton.wand-real' in blob or 'proton.wand-autolaunch' in blob)

def _settings_from_document(j, appid):
    if not isinstance(j,dict):
        return None, False
    nested=appid in j and isinstance(j.get(appid),dict)
    settings=j[appid] if nested else j
    return (settings if isinstance(settings,dict) else None), nested

def _non_wand_wine_version_from_backup(path, appid):
    j=load_json(path,{}) or {}
    settings,_=_settings_from_document(j,appid)
    if not isinstance(settings,dict):
        return None, None
    wv=settings.get('wineVersion') if isinstance(settings.get('wineVersion'),dict) else None
    if not wv or _is_gameweld_wand_runner(wv):
        return None, None
    return dict(wv), settings.get('enableWineWayland')

def _fallback_native_runtime():
    override=os.environ.get('GAMEWELD_HEROIC_BASE_RUNTIME','').strip()
    candidates=[]
    if override:
        candidates.append(pathlib.Path(override).expanduser())
    candidates += [
        pathlib.Path('/usr/share/steam/compatibilitytools.d/proton-cachyos-native/proton'),
        HOME/'.steam/steam/compatibilitytools.d/proton-cachyos-native/proton',
        HOME/'.local/share/Steam/compatibilitytools.d/proton-cachyos-native/proton',
    ]
    for c in candidates:
        try:
            if c.is_file() and os.access(c,os.X_OK):
                return {'bin':str(c),'name':c.parent.name,'type':'proton'}
        except Exception:
            pass
    return None

def recover_stale_wand_runner(appid):
    root,p=game_config_path(appid)
    if p is None:
        print(json.dumps({'ok':False,'state':'missing-config','appid':appid}))
        return 4
    j=load_json(p,{}) or {}
    settings,nested=_settings_from_document(j,appid)
    if not isinstance(settings,dict):
        print(json.dumps({'ok':False,'state':'invalid-settings','appid':appid,'path':str(p)}))
        return 5
    current=settings.get('wineVersion') if isinstance(settings.get('wineVersion'),dict) else {}
    if not _is_gameweld_wand_runner(current):
        print(json.dumps({'ok':True,'state':'not-stale','appid':appid,'path':str(p),'wineVersion':current},ensure_ascii=False))
        return 0

    # A real interrupted temporary session has the authoritative byte-exact
    # restore state. Restore that first rather than guessing.
    state=_session_runner_state_path(appid)
    if state.is_file():
        rc=restore_session_runner(appid)
        return rc

    # Older builds could restore the JSON while a still-running Heroic process
    # later wrote its in-memory temporary runner back to disk. Recover only the
    # GameWeld-owned Wand provider residue, preserving every unrelated setting.
    backup_dir=pathlib.Path(os.environ.get('XDG_STATE_HOME',str(HOME/'.local/state')))/'gameweld'/'heroic-config-backups'
    backup=backup_dir/f'{appid}.json'
    replacement=None; replacement_wayland=None; source=''
    if backup.is_file():
        replacement,replacement_wayland=_non_wand_wine_version_from_backup(backup,appid)
        if replacement:
            source=str(backup)
    if replacement is None:
        replacement=_fallback_native_runtime()
        source='fallback-runtime' if replacement else ''
    if replacement is None:
        print(json.dumps({
            'ok':False,'state':'stale-wand-runner-unrecoverable','appid':appid,'path':str(p),
            'current_wineVersion':current,
            'message':'Heroic is still configured to use GameWeld temporary GE-Proton-Wand-SHA256, but no safe original runner could be recovered.'
        },ensure_ascii=False))
        return 10

    recovery_dir=pathlib.Path(os.environ.get('XDG_STATE_HOME',str(HOME/'.local/state')))/'gameweld'/'heroic-stale-runner-recovery'
    recovery_dir.mkdir(parents=True,exist_ok=True)
    stale_backup=recovery_dir/f'{appid}-stale-{os.getpid()}.json'
    try:
        shutil.copy2(p,stale_backup)
        settings['wineVersion']=replacement
        if replacement_wayland is not None:
            settings['enableWineWayland']=bool(replacement_wayland)
        if nested: j[appid]=settings
        else: j=settings
        _atomic_write_json(p,j)
    except Exception as e:
        print(json.dumps({'ok':False,'state':'stale-runner-recovery-failed','appid':appid,'error':str(e),'path':str(p)},ensure_ascii=False))
        return 11
    print(json.dumps({
        'ok':True,'state':'recovered-stale-gameweld-runner','appid':appid,'path':str(p),
        'wineVersion':replacement,'source':source,'stale_backup':str(stale_backup)
    },ensure_ascii=False))
    return 0

def uri(appid, runner, alt_exe='', args=None):
    gui_raw=os.environ.get('GAMEWELD_HEROIC_PROTOCOL_GUI','false').strip().lower()
    gui='true' if gui_raw in ('1','true','yes','on') else 'false'
    q=[('appName',appid),('runner',runner),('gui',gui)]
    if alt_exe: q.append(('altExe',alt_exe))
    for a in args or []: q.append(('arg',a))
    return 'heroic://launch?' + '&'.join(f'{quote(str(k),safe="")}={quote(str(v),safe="")}' for k,v in q)

def main():
    if len(sys.argv)<2 or sys.argv[1] in ('list','discover'):
        discover(); return 0
    if sys.argv[1]=='uri' and len(sys.argv)>=4:
        print(uri(sys.argv[2],sys.argv[3],sys.argv[4] if len(sys.argv)>4 else '',sys.argv[5:])); return 0
    if sys.argv[1]=='ensure-nsenter' and len(sys.argv)>=3:
        return ensure_umu_nsenter(sys.argv[2])
    if sys.argv[1]=='nsenter-status' and len(sys.argv)>=3:
        return nsenter_status(sys.argv[2])
    if sys.argv[1]=='preflight' and len(sys.argv)>=3:
        return preflight(sys.argv[2])
    if sys.argv[1]=='recover-stale-wand-runner' and len(sys.argv)>=3:
        return recover_stale_wand_runner(sys.argv[2])
    if sys.argv[1]=='session-runner-begin' and len(sys.argv)>=4:
        wine_wayland=True
        if len(sys.argv)>=5:
            wine_wayland=str(sys.argv[4]).strip().lower() not in ('0','false','no','off','x11')
        return begin_session_runner(sys.argv[2],sys.argv[3],wine_wayland)
    if sys.argv[1]=='session-runner-restore' and len(sys.argv)>=3:
        return restore_session_runner(sys.argv[2])
    return 2
if __name__=='__main__': raise SystemExit(main())
