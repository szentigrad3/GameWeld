use anyhow::{anyhow, Context, Result};
use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
use wand_core::{
    GameInstall, LaunchPlan, ProcessInfo, ProcessProbe, ProcessRole, ProtonTool,
};

fn read_proc(path: &Path) -> Vec<u8> {
    fs::read(path).unwrap_or_default()
}

fn parent_pid(proc_dir: &Path) -> Option<u32> {
    let status = fs::read_to_string(proc_dir.join("status")).ok()?;
    status.lines().find_map(|line| {
        line.strip_prefix("PPid:")
            .and_then(|value| value.trim().parse::<u32>().ok())
    })
}

fn proc_exe(proc_dir: &Path) -> Option<PathBuf> {
    fs::read_link(proc_dir.join("exe")).ok()
}

fn windows_executable(args: &[String]) -> Option<String> {
    args.iter()
        .filter_map(|part| {
            let part = part.trim_matches('"');
            if !part.to_ascii_lowercase().ends_with(".exe") {
                return None;
            }

            Some(
                part.rsplit(|ch| ch == '/' || ch == '\\')
                    .next()
                    .unwrap_or(part)
                    .to_owned(),
            )
        })
        .last()
}

fn classify(comm: &str, cmdline: &str, windows_exe: Option<&str>) -> (ProcessRole, i32) {
    let all = format!("{comm} {cmdline}").to_ascii_lowercase();

    const HELPERS: &[&str] = &[
        "wineserver",
        "services.exe",
        "explorer.exe",
        "winedevice.exe",
        "plugplay.exe",
        "rpcss.exe",
        "steamwebhelper",
        "pressure-vessel",
        "steam-runtime",
        "bwrap",
        "reaper",
        "proton waitforexitandrun",
        "wand.exe",
        "wemod.exe",
        "trainerhost_x64.exe",
        "trainerhost_x86.exe",
        "trainerhost.exe",
        "chrome_crashpad_handler.exe",
        "crashpad_handler.exe",
        "wineboot.exe",
        "svchost.exe",
        "conhost.exe",
        "winemenubuilder.exe",
        "iscriptevaluator.exe",
        "legacycompat",
        "wandauxiliaryservice.exe",
        "tabtip.exe",
        "xalia.exe",
    ];

    const LAUNCHERS: &[&str] = &[
        "launcher.exe",
        "launch.exe",
        "start.exe",
        "cmd.exe",
        "steam.exe",
        "start_protected_game",
        "easyanticheat",
        "eac_launcher",
        "battleye",
        "beservice",
        "crashreport",
        "crashpad",
        "rundll32.exe",
        "proton run ",
    ];

    if HELPERS.iter().any(|needle| all.contains(needle)) {
        return (ProcessRole::Helper, -100);
    }

    if all.contains("--type=renderer")
        || all.contains("--type=gpu-process")
        || all.contains("--type=utility")
        || all.contains("--type=zygote")
        || all.contains("--type=crashpad-handler")
    {
        return (ProcessRole::Helper, -100);
    }

    if LAUNCHERS.iter().any(|needle| all.contains(needle)) {
        return (ProcessRole::Launcher, -20);
    }

    if let Some(exe) = windows_exe {
        let exe = exe.to_ascii_lowercase();

        if HELPERS.iter().any(|needle| exe.contains(needle)) {
            return (ProcessRole::Helper, -100);
        }

        if LAUNCHERS.iter().any(|needle| exe.contains(needle)) {
            return (ProcessRole::Launcher, -20);
        }

        return (ProcessRole::GameCandidate, 100);
    }

    if all.contains("wine64-preloader") || all.contains("wine-preloader") {
        // A Wine preloader proves only that Wine is active, not that the game
        // executable itself has appeared.
        return (ProcessRole::Unknown, 0);
    }

    (ProcessRole::Unknown, 0)
}

fn env_pair_matches(env_bytes: &[u8], expected: &str) -> bool {
    env_bytes
        .split(|byte| *byte == 0)
        .filter_map(|part| std::str::from_utf8(part).ok())
        .any(|pair| pair == expected)
}

fn wine_z_path(path: &Path) -> String {
    let mut output = String::from("Z:");
    for component in path.to_string_lossy().split('/') {
        if component.is_empty() {
            continue;
        }
        output.push('\\');
        output.push_str(component);
    }
    output
}

fn collect_processes<F>(mut associated: F) -> Vec<ProcessInfo>
where
    F: FnMut(&Path, &[u8], &[String], &str) -> bool,
{
    let mut result = Vec::new();

    let Ok(entries) = fs::read_dir("/proc") else {
        return result;
    };

    for entry in entries.flatten() {
        let file_name = entry.file_name();
        let Some(pid_text) = file_name.to_str() else {
            continue;
        };
        let Ok(pid) = pid_text.parse::<u32>() else {
            continue;
        };

        let proc_dir = entry.path();
        let env_bytes = read_proc(&proc_dir.join("environ"));

        let comm = fs::read_to_string(proc_dir.join("comm"))
            .unwrap_or_default()
            .trim()
            .to_owned();

        let cmdline_args = read_proc(&proc_dir.join("cmdline"))
            .split(|byte| *byte == 0)
            .filter(|part| !part.is_empty())
            .map(|part| String::from_utf8_lossy(part).into_owned())
            .collect::<Vec<_>>();

        let cmdline = cmdline_args.join(" ");

        if !associated(&proc_dir, &env_bytes, &cmdline_args, &cmdline) {
            continue;
        }

        let windows_executable = windows_executable(&cmdline_args);
        let (role, score) = classify(
            &comm,
            &cmdline,
            windows_executable.as_deref(),
        );

        result.push(ProcessInfo {
            pid,
            parent_pid: parent_pid(&proc_dir),
            comm,
            cmdline,
            exe: proc_exe(&proc_dir),
            windows_executable,
            role,
            score,
        });
    }

    result.sort_by(|left, right| {
        right
            .score
            .cmp(&left.score)
            .then_with(|| left.pid.cmp(&right.pid))
    });
    result
}

pub fn session_processes(app_id: u32) -> Vec<ProcessInfo> {
    let wanted = app_id.to_string();

    collect_processes(|_proc_dir, env_bytes, _args, _cmdline| {
        env_pair_matches(env_bytes, &format!("SteamAppId={wanted}"))
            || env_pair_matches(env_bytes, &format!("SteamGameId={wanted}"))
            || env_pair_matches(env_bytes, &format!("STEAM_COMPAT_APP_ID={wanted}"))
    })
}

fn process_associated_with_game(
    proc_dir: &Path,
    env_bytes: &[u8],
    cmdline: &str,
    game: &GameInstall,
) -> bool {
    let wanted = game.app_id.to_string();

    if env_pair_matches(env_bytes, &format!("SteamAppId={wanted}"))
        || env_pair_matches(env_bytes, &format!("SteamGameId={wanted}"))
        || env_pair_matches(env_bytes, &format!("STEAM_COMPAT_APP_ID={wanted}"))
        || env_pair_matches(
            env_bytes,
            &format!("STEAM_COMPAT_DATA_PATH={}", game.compatdata_dir.display()),
        )
        || env_pair_matches(
            env_bytes,
            &format!("WINEPREFIX={}", game.prefix_dir.display()),
        )
        || env_pair_matches(
            env_bytes,
            &format!("STEAM_COMPAT_INSTALL_PATH={}", game.install_dir.display()),
        )
    {
        return true;
    }

    if let Ok(cwd) = fs::read_link(proc_dir.join("cwd")) {
        if cwd.starts_with(&game.install_dir) {
            return true;
        }
    }

    let cmdline_lower = cmdline.to_ascii_lowercase();
    let unix_install = game.install_dir.display().to_string().to_ascii_lowercase();
    if !unix_install.is_empty() && cmdline_lower.contains(&unix_install) {
        return true;
    }

    let windows_install = wine_z_path(&game.install_dir).to_ascii_lowercase();
    !windows_install.is_empty() && cmdline_lower.contains(&windows_install)
}

pub fn session_processes_for_game(game: &GameInstall) -> Vec<ProcessInfo> {
    collect_processes(|proc_dir, env_bytes, _args, cmdline| {
        process_associated_with_game(proc_dir, env_bytes, cmdline, game)
    })
}

fn is_wand_owned_process(process: &ProcessInfo) -> bool {
    let Some(executable) = process.windows_executable.as_deref() else {
        return false;
    };

    matches!(
        executable.to_ascii_lowercase().as_str(),
        "wand.exe"
            | "wemod.exe"
            | "wandauxiliaryservice.exe"
            | "trainerhost.exe"
            | "trainerhost_x64.exe"
            | "trainerhost_x86.exe"
    )
}

pub fn wand_owned_processes_for_game(game: &GameInstall) -> Vec<ProcessInfo> {
    session_processes_for_game(game)
        .into_iter()
        .filter(is_wand_owned_process)
        .collect()
}

pub fn cleanup_wand_processes_for_game(game: &GameInstall) -> Result<Vec<u32>> {
    let processes = wand_owned_processes_for_game(game);
    let pids = processes.iter().map(|process| process.pid).collect::<Vec<_>>();

    for pid in &pids {
        if process_alive(*pid) {
            let _ = Command::new("kill")
                .arg("-TERM")
                .arg(pid.to_string())
                .status();
        }
    }

    if !pids.is_empty() {
        std::thread::sleep(std::time::Duration::from_millis(900));
    }

    for pid in &pids {
        if process_alive(*pid) {
            let _ = Command::new("kill")
                .arg("-KILL")
                .arg(pid.to_string())
                .status();
        }
    }

    if !pids.is_empty() {
        std::thread::sleep(std::time::Duration::from_millis(150));
    }

    let survivors = pids
        .iter()
        .copied()
        .filter(|pid| process_alive(*pid))
        .collect::<Vec<_>>();

    if !survivors.is_empty() {
        return Err(anyhow!(
            "could not stop stale Wand/WeMod processes for AppID {}: {:?}",
            game.app_id,
            survivors
        ));
    }

    Ok(pids)
}

fn probe_from_candidates(app_id: u32, candidates: Vec<ProcessInfo>) -> ProcessProbe {
    let best_candidate_pid = candidates
        .iter()
        .find(|process| {
            process.role == ProcessRole::GameCandidate
                && process.score >= 100
        })
        .map(|process| process.pid);

    ProcessProbe {
        app_id,
        candidates,
        best_candidate_pid,
    }
}

pub fn process_probe(app_id: u32) -> ProcessProbe {
    probe_from_candidates(app_id, session_processes(app_id))
}

pub fn process_probe_game(game: &GameInstall) -> ProcessProbe {
    probe_from_candidates(game.app_id, session_processes_for_game(game))
}

fn process_matches_game_executable(process: &ProcessInfo, game_exe: &Path) -> bool {
    let expected = game_exe
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or_default();

    if expected.is_empty() {
        return false;
    }

    if process.comm.eq_ignore_ascii_case(expected) {
        return true;
    }

    if process
        .windows_executable
        .as_deref()
        .map(|value| value.eq_ignore_ascii_case(expected))
        .unwrap_or(false)
    {
        return true;
    }

    let unix = game_exe.display().to_string().to_ascii_lowercase();
    if !unix.is_empty() && process.cmdline.to_ascii_lowercase().contains(&unix) {
        return true;
    }

    let wine = wine_z_path(game_exe).to_ascii_lowercase();
    !wine.is_empty() && process.cmdline.to_ascii_lowercase().contains(&wine)
}

pub fn process_probe_exact_game(
    game: &GameInstall,
    game_exe: &Path,
) -> ProcessProbe {
    let candidates = session_processes_for_game(game)
        .into_iter()
        .filter(|process| {
            process.role == ProcessRole::GameCandidate
                && process.score >= 100
                && process_matches_game_executable(process, game_exe)
        })
        .collect();

    probe_from_candidates(game.app_id, candidates)
}

pub fn likely_exact_game_running(
    game: &GameInstall,
    game_exe: &Path,
) -> bool {
    process_probe_exact_game(game, game_exe)
        .best_candidate_pid
        .is_some()
}

pub fn likely_game_running(app_id: u32) -> bool {
    process_probe(app_id).best_candidate_pid.is_some()
}

pub fn likely_game_running_for_game(game: &GameInstall) -> bool {
    process_probe_game(game).best_candidate_pid.is_some()
}

pub fn proton_environment(
    game: &GameInstall,
    steam_root: &Path,
) -> Vec<(String, String)> {
    vec![
        (
            "STEAM_COMPAT_CLIENT_INSTALL_PATH".into(),
            steam_root.display().to_string(),
        ),
        (
            "STEAM_COMPAT_DATA_PATH".into(),
            game.compatdata_dir.display().to_string(),
        ),
        (
            "WINEPREFIX".into(),
            game.prefix_dir.display().to_string(),
        ),
        (
            "STEAM_COMPAT_APP_ID".into(),
            game.app_id.to_string(),
        ),
        ("SteamAppId".into(), game.app_id.to_string()),
        ("SteamGameId".into(), game.app_id.to_string()),
        (
            "STEAM_COMPAT_LIBRARY_PATHS".into(),
            game.library_root.display().to_string(),
        ),
        (
            "STEAM_COMPAT_INSTALL_PATH".into(),
            game.install_dir.display().to_string(),
        ),
    ]
}

fn command_exists(name: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

pub fn steam_binary() -> Result<PathBuf> {
    command_exists("steam")
        .or_else(|| command_exists("steam-runtime"))
        .ok_or_else(|| anyhow!("Steam executable not found in PATH"))
}

pub fn system_wine_binary() -> Result<PathBuf> {
    if let Some(override_path) = std::env::var_os("WAND_WINE_BIN")
        .map(PathBuf::from)
    {
        if override_path.is_file() {
            return Ok(override_path);
        }

        return Err(anyhow!(
            "WAND_WINE_BIN points to a missing file: {}",
            override_path.display()
        ));
    }

    command_exists("wine")
        .or_else(|| command_exists("wine64"))
        .ok_or_else(|| anyhow!(
            "system Wine executable not found in PATH; install Wine or set WAND_WINE_BIN"
        ))
}

pub fn build_system_wine_launch_plan(
    game: &GameInstall,
    proton: &ProtonTool,
    executable: &Path,
    args: &[String],
) -> Result<LaunchPlan> {
    let executable = fs::canonicalize(executable)
        .with_context(|| format!(
            "Windows executable does not exist: {}",
            executable.display()
        ))?;

    if !game.prefix_dir.exists() {
        return Err(anyhow!(
            "Wine/Proton prefix does not exist: {}",
            game.prefix_dir.display()
        ));
    }

    let wine = system_wine_binary()?;
    let mut command = vec![
        wine.display().to_string(),
        executable.display().to_string(),
    ];
    command.extend(args.iter().cloned());

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        // Keep the resolved Proton metadata because this is still the game's
        // selected runtime, even though the provider executable itself is
        // launched by system Wine.
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer: executable,
        command,
        // Deliberately do NOT inject SteamAppId/SteamGameId here. Provider
        // processes must never masquerade as the selected Steam game.
        environment: vec![
            (
                "WINEPREFIX".into(),
                game.prefix_dir.display().to_string(),
            ),
        ],
    })
}

#[cfg(test)]
const SYSTEM_WINE_PROVIDER_USES_NULL_STDIO: bool = true;

pub fn run_system_wine_launch_plan(
    plan: &LaunchPlan,
    dry_run: bool,
) -> Result<Option<u32>> {
    if dry_run {
        return Ok(None);
    }

    let wine = plan
        .command
        .first()
        .ok_or_else(|| anyhow!("system Wine launch plan has no command"))?;

    let mut command = Command::new(wine);
    command.arg(&plan.trainer);

    for extra in plan.command.iter().skip(2) {
        command.arg(extra);
    }

    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);

    if let Some(parent) = plan.trainer.parent() {
        command.current_dir(parent);
    }

    // Electron/Node under Wine can fail while constructing process.stdout
    // when fd 1/2 are inherited from wandd's systemd journal stream. In that
    // case Node treats the inherited descriptor as a socket/pipe and Wine may
    // report `open EFAULT` from createWritableStdioStream/new Socket.
    //
    // A desktop-launched Wand has no useful console anyway, so give the
    // provider clean null stdio. This also prevents Wine/Electron noise from
    // flooding the user-service journal.
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command
        .spawn()
        .context("launching provider through system Wine with detached stdio")?;

    Ok(Some(child.id()))
}

fn normalized_exe_stem(path: &Path) -> String {
    path.file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric())
        .flat_map(|ch| ch.to_lowercase())
        .collect()
}

fn normalized_game_name(name: &str) -> String {
    name.chars()
        .filter(|ch| ch.is_ascii_alphanumeric())
        .flat_map(|ch| ch.to_lowercase())
        .collect()
}

fn obvious_non_game_exe(name: &str) -> bool {
    let value = name.to_ascii_lowercase();
    [
        "launcher",
        "crash",
        "report",
        "unins",
        "uninstall",
        "setup",
        "redist",
        "vc_redist",
        "dxsetup",
        "easyanticheat",
        "eac",
        "battleye",
        "beservice",
        "unitycrashhandler",
        "prereq",
        "helper",
        "updater",
    ]
    .iter()
    .any(|needle| value.contains(needle))
}

fn collect_game_exes(root: &Path, depth: usize, output: &mut Vec<PathBuf>) {
    if depth > 3 {
        return;
    }

    let Ok(entries) = fs::read_dir(root) else {
        return;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        let Ok(file_type) = entry.file_type() else {
            continue;
        };

        if file_type.is_dir() {
            let name = entry.file_name().to_string_lossy().to_ascii_lowercase();
            if ["redist", "redistributable", "support", "installer", "__installer"]
                .iter()
                .any(|needle| name.contains(needle))
            {
                continue;
            }
            collect_game_exes(&path, depth + 1, output);
        } else if file_type.is_file()
            && path
                .extension()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case("exe"))
                .unwrap_or(false)
        {
            output.push(path);
        }
    }
}

pub fn discover_game_executable(game: &GameInstall) -> Result<PathBuf> {
    if let Some(explicit) = std::env::var_os("WAND_GAME_EXE").map(PathBuf::from) {
        if explicit.is_file() {
            return fs::canonicalize(&explicit).or(Ok(explicit));
        }
        return Err(anyhow!(
            "WAND_GAME_EXE points to a missing file: {}",
            explicit.display()
        ));
    }

    let mut candidates = Vec::new();
    collect_game_exes(&game.install_dir, 0, &mut candidates);

    let wanted = normalized_game_name(&game.name);
    let first_word = game
        .name
        .split(|ch: char| !ch.is_ascii_alphanumeric())
        .find(|part| part.len() >= 4)
        .map(|part| part.to_ascii_lowercase())
        .unwrap_or_default();

    let mut scored = candidates
        .into_iter()
        .filter_map(|path| {
            let file_name = path.file_name()?.to_str()?.to_owned();
            if obvious_non_game_exe(&file_name) {
                return None;
            }

            let stem = normalized_exe_stem(&path);
            let relative = path.strip_prefix(&game.install_dir).ok();
            let depth = relative
                .map(|value| value.components().count().saturating_sub(1))
                .unwrap_or(9);

            let mut score = 0i32;
            if depth == 0 {
                score += 80;
            } else if depth == 1 {
                score += 35;
            } else if depth == 2 {
                score += 10;
            }

            if !stem.is_empty() && wanted.contains(&stem) {
                score += 100;
            }
            if !first_word.is_empty() && stem.contains(&first_word) {
                score += 80;
            }

            if let Ok(meta) = fs::metadata(&path) {
                if meta.len() >= 5 * 1024 * 1024 {
                    score += 20;
                }
                if meta.len() >= 50 * 1024 * 1024 {
                    score += 10;
                }
            }

            Some((score, path))
        })
        .collect::<Vec<_>>();

    scored.sort_by(|left, right| {
        right
            .0
            .cmp(&left.0)
            .then_with(|| left.1.cmp(&right.1))
    });

    let Some((score, path)) = scored.into_iter().next() else {
        return Err(anyhow!(
            "could not find a Windows game executable under {}. Set WAND_GAME_EXE to the real game .exe.",
            game.install_dir.display()
        ));
    };

    if score < 30 {
        return Err(anyhow!(
            "could not confidently identify the game executable under {}. Best candidate was {} (score {}). Set WAND_GAME_EXE explicitly.",
            game.install_dir.display(),
            path.display(),
            score
        ));
    }

    fs::canonicalize(&path).or(Ok(path))
}

fn windows_path_from_prefix_drive(path: &Path, prefix_dir: &Path) -> Option<String> {
    let canonical_path = fs::canonicalize(path).ok()?;
    let dosdevices = prefix_dir.join("dosdevices");
    let entries = fs::read_dir(&dosdevices).ok()?;

    let mut matches: Vec<(usize, char, PathBuf)> = Vec::new();

    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().to_ascii_lowercase();

        if name.len() != 2 || !name.ends_with(':') {
            continue;
        }

        let drive = name.chars().next()?;
        if !drive.is_ascii_alphabetic() || drive == 'z' {
            continue;
        }

        let Ok(target) = fs::canonicalize(entry.path()) else {
            continue;
        };

        if canonical_path == target || canonical_path.starts_with(&target) {
            matches.push((
                target.components().count(),
                drive.to_ascii_uppercase(),
                target,
            ));
        }
    }

    matches.sort_by(|left, right| {
        right
            .0
            .cmp(&left.0)
            .then_with(|| left.1.cmp(&right.1))
    });

    let (_, drive, target) = matches.into_iter().next()?;
    let relative = canonical_path.strip_prefix(&target).ok()?;

    let mut value = format!("{drive}:\\");
    let relative_text = relative.to_string_lossy().replace('/', "\\");
    if !relative_text.is_empty() {
        value.push_str(relative_text.trim_start_matches('\\'));
    }

    Some(value)
}

fn batch_safe_windows_path(path: &Path, prefix_dir: &Path) -> Result<String> {
    let value = windows_path_from_prefix_drive(path, prefix_dir)
        .unwrap_or_else(|| wine_z_path(path));

    if value.contains(['\r', '\n', '"', '%', '!', '&', '|', '<', '>', '^', '(', ')']) {
        return Err(anyhow!(
            "path contains characters unsupported by the one-session batch launcher: {}",
            path.display()
        ));
    }
    Ok(value)
}

fn batch_safe_arg(value: &str) -> Result<String> {
    if value.contains(['\r', '\n', '"', '%', '!', '&', '|', '<', '>', '^', '(', ')']) {
        return Err(anyhow!(
            "argument contains characters unsupported by the one-session batch launcher: {value:?}"
        ));
    }
    Ok(format!("\"{value}\""))
}

fn one_session_state_dir() -> PathBuf {
    std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .map(|home| PathBuf::from(home).join(".local/state"))
        })
        .unwrap_or_else(std::env::temp_dir)
        .join("wand")
        .join("one-session")
}

/// Experimental direct DeckCheatz/Proton route. The wrapper is first in argv
/// just like DeckCheatz's Steam '%command%' recipe, but this does NOT recreate
/// Steam's Linux Runtime container, Steam client supervisor, Steam API, or DRM.
///
/// Plan creation is READ ONLY. Refuse ambiguous game executables rather than
/// silently choosing the top scoring .exe when Steam metadata is insufficient.
pub fn build_native_wrapper_launch_plan(
    game: &GameInstall,
    steam_root: &Path,
    proton: &ProtonTool,
    wrapper: &Path,
    wrapper_log: &Path,
) -> Result<LaunchPlan> {
    let wrapper = fs::canonicalize(wrapper)
        .with_context(|| format!("wrapper does not exist: {}", wrapper.display()))?;
    if !wrapper.is_file() || fs::metadata(&wrapper)?.permissions().mode() & 0o111 == 0 {
        return Err(anyhow!(
            "DeckCheatz wrapper must be an executable regular file: {}",
            wrapper.display()
        ));
    }

    if !proton.proton_script.is_file()
        || fs::metadata(&proton.proton_script)?.permissions().mode() & 0o111 == 0
    {
        return Err(anyhow!(
            "selected Proton launcher is missing or not executable: {}",
            proton.proton_script.display()
        ));
    }
    if !steam_root.join("steamapps").is_dir() {
        return Err(anyhow!("Steam client root does not have steamapps: {}", steam_root.display()));
    }
    if !game.compatdata_dir.is_dir() || !game.prefix_dir.is_dir() {
        return Err(anyhow!(
            "Proton compatdata/prefix missing for AppID {}. Run it through Steam once first.",
            game.app_id
        ));
    }
    if !wrapper_log.is_absolute() || wrapper_log.file_name().is_none() {
        return Err(anyhow!("DeckCheatz log must be an absolute file path"));
    }
    if wrapper_log.is_symlink() || wrapper_log.is_dir() {
        return Err(anyhow!("Refusing symlinked or directory DeckCheatz log"));
    }

    let canonical_install = fs::canonicalize(&game.install_dir)
        .context("resolving Steam game installation")?;
    if std::env::var_os("WAND_GAME_EXE").is_none() {
        let mut possible = Vec::new();
        collect_game_exes(&game.install_dir, 0, &mut possible);
        possible.retain(|file| {
            file.file_name()
                .and_then(|name| name.to_str())
                .map(|name| !obvious_non_game_exe(name))
                .unwrap_or(false)
        });
        if possible.len() > 1 {
            return Err(anyhow!(
                "more than one plausible Windows game executable ({} found). \
                 Set WAND_GAME_EXE explicitly after reviewing the Steam game directory.",
                possible.len()
            ));
        }
    }
    let game_exe = discover_game_executable(game)?;
    if !game_exe.starts_with(&canonical_install)
        || !game_exe.extension()
            .and_then(|e| e.to_str())
            .map(|e| e.eq_ignore_ascii_case("exe"))
            .unwrap_or(false)
    {
        return Err(anyhow!(
            "Windows game executable must be within selected install directory: {}",
            game_exe.display()
        ));
    }

    let command = vec![
        wrapper.display().to_string(),
        proton.proton_script.display().to_string(),
        "waitforexitandrun".into(),
        game_exe.display().to_string(),
    ];

    let mut environment = proton_environment(game, steam_root);
    environment.extend([
        ("STEAM_COMPAT_TOOL_PATHS".into(), proton.root.display().to_string()),
        ("SteamOverlayGameId".into(), game.app_id.to_string()),
        ("WINEDLLOVERRIDES".into(), "version=n,b".into()),
        ("WEMOD_LOG".into(), wrapper_log.display().to_string()),
        ("WAND_WRAPPER_GAME_EXE".into(), game_exe.display().to_string()),
    ]);
    environment.sort_by(|left, right| left.0.cmp(&right.0));

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer: wrapper,
        command,
        environment,
    })
}

/// Returns None for a dry-run; no directories or log files are created.
/// Launch is experimental and opt-in; the resulting PID is only the spawned
/// wrapper, not confirmation that Steam API or WeMod attachment worked.
pub fn run_native_wrapper_launch_plan(
    plan: &LaunchPlan,
    game_install_dir: &Path,
    dry_run: bool,
) -> Result<Option<u32>> {
    let (program, args) = plan.command
        .split_first()
        .ok_or_else(|| anyhow!("native DeckCheatz wrapper plan has no command"))?;

    if plan.command.len() < 4 || plan.command[2] != "waitforexitandrun"
        || program != &plan.trainer.display().to_string()
        || plan.command[1] != plan.proton.proton_script.display().to_string()
    {
        return Err(anyhow!("native DeckCheatz wrapper command has an unexpected layout"));
    }
    let canonical_install = fs::canonicalize(game_install_dir)
        .context("selected Steam install directory is missing")?;
    let game_exe = fs::canonicalize(&plan.command[3])
        .context("planned Windows game executable no longer exists")?;
    if !game_exe.starts_with(&canonical_install) {
        return Err(anyhow!("selected game executable escaped the Steam installation"));
    }
    if dry_run {
        return Ok(None);
    }

    if likely_game_running(plan.app_id) {
        return Err(anyhow!(
            "Steam AppID {} already has a running game; refusing duplicate direct launch",
            plan.app_id
        ));
    }
    let mut command = Command::new(program);
    command.args(args);
    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);
    command.current_dir(game_exe.parent().unwrap_or(&canonical_install));

    let log_dir = one_session_state_dir().join("native-wrapper");
    if log_dir.is_symlink() {
        return Err(anyhow!("refusing symlinked native wrapper log directory"));
    }
    fs::create_dir_all(&log_dir)
        .with_context(|| format!("creating {}", log_dir.display()))?;
    let meta = fs::symlink_metadata(&log_dir)?;
    if !meta.is_dir() || meta.uid() != unsafe { libc_geteuid() } {
        return Err(anyhow!("native wrapper log directory has unexpected ownership/type"));
    }
    fs::set_permissions(&log_dir, fs::Permissions::from_mode(0o700))
        .context("protecting native wrapper log directory")?;

    let nanos = SystemTime::now().duration_since(UNIX_EPOCH)
        .context("invalid clock for wrapper launch log")?.as_nanos();
    let log_path = log_dir.join(format!(
        "appid-{}-{}-{}.log", plan.app_id, std::process::id(), nanos
    ));
    let log = fs::OpenOptions::new().write(true).create_new(true).open(&log_path)
        .with_context(|| format!("creating one-time log {}", log_path.display()))?;
    let log_err = log.try_clone().context("cloning native wrapper log output")?;
    command
        .stdin(Stdio::null())
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(log_err))
        .env("WAND_WRAPPER_LAUNCH_LOG_PATH", &log_path)
        // Separate process group: closing GameWeld will not signal the game.
        .process_group(0);

    let child = command.spawn().context("launching game via DeckCheatz + Proton")?;
    Ok(Some(child.id()))
}

// POSIX process identity is only needed to validate ownership of log output.
// Prefer libc's real/effective UID through the standard getuid environment
// rather than hard-code a public-writable state directory.
#[cfg(unix)]
unsafe fn libc_geteuid() -> u32 {
    extern "C" { fn geteuid() -> u32; }
    geteuid()
}

pub fn build_one_proton_session_launch_plan(
    game: &GameInstall,
    steam_root: &Path,
    proton: &ProtonTool,
    wand_exe: &Path,
    wand_args: &[String],
) -> Result<LaunchPlan> {
    if !proton.proton_script.is_file() {
        return Err(anyhow!(
            "selected Proton script does not exist: {}",
            proton.proton_script.display()
        ));
    }

    if !game.compatdata_dir.exists() || !game.prefix_dir.exists() {
        return Err(anyhow!(
            "Proton compatdata/prefix does not exist for AppID {}. Launch the game through Steam once before using Wand Native.",
            game.app_id
        ));
    }

    let wand_exe = fs::canonicalize(wand_exe).with_context(|| {
        format!("Wand/WeMod executable does not exist: {}", wand_exe.display())
    })?;
    let game_exe = discover_game_executable(game)?;

    let wand_win = batch_safe_windows_path(&wand_exe, &game.prefix_dir)?;
    let game_win = batch_safe_windows_path(&game_exe, &game.prefix_dir)?;
    let wand_dir_win = batch_safe_windows_path(
        wand_exe.parent().ok_or_else(|| anyhow!("Wand executable has no parent directory"))?,
        &game.prefix_dir,
    )?;
    let game_dir_win = batch_safe_windows_path(
        game_exe.parent().ok_or_else(|| anyhow!("game executable has no parent directory"))?,
        &game.prefix_dir,
    )?;

    let mut wand_arg_text = String::new();
    for arg in wand_args {
        wand_arg_text.push(' ');
        wand_arg_text.push_str(&batch_safe_arg(arg)?);
    }

    let dir = one_session_state_dir();
    fs::create_dir_all(&dir)
        .with_context(|| format!("creating {}", dir.display()))?;
    let batch = dir.join(format!("appid-{}-launch.bat", game.app_id));
    let stage_log = dir.join(format!("appid-{}-stage.txt", game.app_id));
    let stage_win = batch_safe_windows_path(&stage_log, &game.prefix_dir)?;

    let body = format!(
        "@echo off\r\n\
@title Wand Native One Proton Session\r\n\
set \"SteamAppId={app_id}\"\r\n\
set \"SteamGameId={app_id}\"\r\n\
set \"SteamOverlayGameId={app_id}\"\r\n\
set \"STEAM_COMPAT_APP_ID={app_id}\"\r\n\
echo batch-start > \"{stage_win}\"\r\n\
echo SteamAppId=%SteamAppId%>> \"{stage_win}\"\r\n\
echo SteamGameId=%SteamGameId%>> \"{stage_win}\"\r\n\
echo wand={wand_win}>> \"{stage_win}\"\r\n\
echo game={game_win}>> \"{stage_win}\"\r\n\
echo starting-wand>> \"{stage_win}\"\r\n\
start \"\" /D \"{wand_dir_win}\" \"{wand_win}\"{wand_arg_text}\r\n\
echo starting-game>> \"{stage_win}\"\r\n\
start \"\" /D \"{game_dir_win}\" \"{game_win}\"\r\n\
echo dispatched>> \"{stage_win}\"\r\n\
exit /b 0\r\n",
        app_id = game.app_id,
    );

    fs::write(&batch, body)
        .with_context(|| format!("writing {}", batch.display()))?;
    let _ = fs::remove_file(&stage_log);

    let command = vec![
        proton.proton_script.display().to_string(),
        "waitforexitandrun".into(),
        batch.display().to_string(),
    ];

    let mut environment = proton_environment(game, steam_root);
    environment.push((
        "WAND_ONE_SESSION_GAME_EXE".into(),
        game_exe.display().to_string(),
    ));
    environment.push((
        "WAND_ONE_SESSION_GAME_WINDOWS_PATH".into(),
        game_win.clone(),
    ));
    environment.push((
        "WAND_ONE_SESSION_WAND_WINDOWS_PATH".into(),
        wand_win.clone(),
    ));
    environment.push((
        "WAND_ONE_SESSION_STAGE_LOG".into(),
        stage_log.display().to_string(),
    ));

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer: batch,
        command,
        environment,
    })
}

pub fn run_one_proton_session_launch_plan(
    plan: &LaunchPlan,
    game_install_dir: &Path,
    dry_run: bool,
) -> Result<Option<u32>> {
    if dry_run {
        return Ok(None);
    }

    let mut command = Command::new(&plan.proton.proton_script);
    command.arg("waitforexitandrun").arg(&plan.trainer);

    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);
    command.current_dir(game_install_dir);
    command.stdin(Stdio::null());

    let log_dir = one_session_state_dir();
    fs::create_dir_all(&log_dir)
        .with_context(|| format!("creating {}", log_dir.display()))?;
    let log_path = log_dir.join(format!("appid-{}-proton.log", plan.app_id));
    let mut log = fs::File::create(&log_path)
        .with_context(|| format!("creating {}", log_path.display()))?;

    let diag_mode = plan
        .environment
        .iter()
        .find(|(key, _)| key == "WAND_AUX_DIAGNOSTICS_ACTIVE")
        .map(|(_, value)| value.as_str())
        .unwrap_or("off");
    let winedebug = plan
        .environment
        .iter()
        .find(|(key, _)| key == "WINEDEBUG")
        .map(|(_, value)| value.as_str())
        .unwrap_or("(unset)");
    let game_windows_path = plan
        .environment
        .iter()
        .find(|(key, _)| key == "WAND_ONE_SESSION_GAME_WINDOWS_PATH")
        .map(|(_, value)| value.as_str())
        .unwrap_or("(unknown)");
    let wand_windows_path = plan
        .environment
        .iter()
        .find(|(key, _)| key == "WAND_ONE_SESSION_WAND_WINDOWS_PATH")
        .map(|(_, value)| value.as_str())
        .unwrap_or("(unknown)");

    let _ = writeln!(log, "=== Wand Native one-session launch ===");
    let _ = writeln!(log, "AppID: {}", plan.app_id);
    let _ = writeln!(log, "Game: {}", plan.game_name);
    let _ = writeln!(log, "Proton: {}", plan.proton.proton_script.display());
    let _ = writeln!(log, "Prefix: {}", plan.prefix_dir.display());
    let _ = writeln!(log, "Game Windows path: {game_windows_path}");
    let _ = writeln!(log, "Wand Windows path: {wand_windows_path}");
    let _ = writeln!(log, "Aux diagnostics: {diag_mode}");
    let _ = writeln!(log, "WINEDEBUG: {winedebug}");
    let _ = writeln!(log, "======================================");
    let _ = log.flush();

    let log_err = log.try_clone()
        .with_context(|| format!("cloning {}", log_path.display()))?;
    command.stdout(Stdio::from(log));
    command.stderr(Stdio::from(log_err));

    let child = command.spawn().with_context(|| {
        format!(
            "launching Wand and {} together through one Proton session",
            plan.game_name
        )
    })?;

    Ok(Some(child.id()))
}

pub fn launch_game(game: &GameInstall, dry_run: bool) -> Result<Vec<String>> {
    let steam = steam_binary()?;
    let command = vec![
        steam.display().to_string(),
        "-applaunch".into(),
        game.app_id.to_string(),
    ];

    if !dry_run {
        Command::new(&steam)
            .arg("-applaunch")
            .arg(game.app_id.to_string())
            .env_remove("DESKTOP_STARTUP_ID")
            .env_remove("XDG_ACTIVATION_TOKEN")
            .env_remove("GIO_LAUNCHED_DESKTOP_FILE")
            .env_remove("GIO_LAUNCHED_DESKTOP_FILE_PID")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .context("launching game through Steam")?;
    }

    Ok(command)
}

fn proc_environment(pid: u32) -> Vec<(String, String)> {
    let bytes = read_proc(&PathBuf::from(format!("/proc/{pid}/environ")));

    bytes
        .split(|byte| *byte == 0)
        .filter(|part| !part.is_empty())
        .filter_map(|part| std::str::from_utf8(part).ok())
        .filter_map(|pair| {
            let (key, value) = pair.split_once('=')?;
            Some((key.to_owned(), value.to_owned()))
        })
        .collect()
}

fn proton_wine_binary(proton: &ProtonTool) -> Result<PathBuf> {
    let candidates = [
        proton.root.join("files/bin/wine"),
        proton.root.join("files/bin/wine64"),
        proton.root.join("files/lib/wine/x86_64-unix/wine"),
    ];

    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .ok_or_else(|| {
            anyhow!(
                "could not find Wine binary inside selected Proton tool {}",
                proton.root.display()
            )
        })
}

fn proton_wineserver_binary(proton: &ProtonTool) -> Result<PathBuf> {
    let candidates = [
        proton.root.join("files/bin/wineserver"),
        proton.root.join("files/lib/wine/x86_64-unix/wineserver"),
    ];

    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .ok_or_else(|| {
            anyhow!(
                "could not find wineserver binary inside selected Proton tool {}",
                proton.root.display()
            )
        })
}

fn keep_live_wine_environment(key: &str) -> bool {
    if key == "PROTON_USE_X11_EXCLUSIVE" || key == "WAND_ELECTRON_RENDERER" || key == "WAND_WINDOW_BACKEND" {
        return false;
    }

    key == "WINEPREFIX"
        || key == "WINELOADER"
        || key == "WINESERVER"
        || key == "WINEDEBUG"
        || key == "WINEDLLOVERRIDES"
        || key == "WINEESYNC"
        || key == "WINEFSYNC"
        || key == "WINEARCH"
        || key == "WINE_DISABLE_VULKAN_OPWR"
        || key == "LD_LIBRARY_PATH"
        || key == "STEAM_COMPAT_CLIENT_INSTALL_PATH"
        || key == "STEAM_COMPAT_DATA_PATH"
        || key == "STEAM_COMPAT_APP_ID"
        || key == "STEAM_COMPAT_INSTALL_PATH"
        || key == "STEAM_COMPAT_LIBRARY_PATHS"
        || key == "SteamAppId"
        || key == "SteamGameId"
        || key.starts_with("PROTON_")
        || key.starts_with("DXVK_")
        || key.starts_with("VKD3D_")
}

fn sanitized_live_wine_environment(
    pid: u32,
    game: &GameInstall,
    steam_root: &Path,
    wine: &Path,
    wineserver: &Path,
) -> Vec<(String, String)> {
    let mut env: HashMap<String, String> = proc_environment(pid)
        .into_iter()
        .filter(|(key, _)| keep_live_wine_environment(key))
        .collect();

    // These values define which Wine server we join. Always force them to the
    // selected game's exact prefix and selected Proton tool.
    env.insert(
        "WINEPREFIX".into(),
        game.prefix_dir.display().to_string(),
    );
    env.insert("WINELOADER".into(), wine.display().to_string());
    env.insert("WINESERVER".into(), wineserver.display().to_string());

    env.insert(
        "STEAM_COMPAT_CLIENT_INSTALL_PATH".into(),
        steam_root.display().to_string(),
    );
    env.insert(
        "STEAM_COMPAT_DATA_PATH".into(),
        game.compatdata_dir.display().to_string(),
    );
    env.insert("STEAM_COMPAT_APP_ID".into(), game.app_id.to_string());
    env.insert("SteamAppId".into(), game.app_id.to_string());
    env.insert("SteamGameId".into(), game.app_id.to_string());
    env.insert(
        "STEAM_COMPAT_INSTALL_PATH".into(),
        game.install_dir.display().to_string(),
    );
    env.insert(
        "STEAM_COMPAT_LIBRARY_PATHS".into(),
        game.library_root.display().to_string(),
    );

    let mut values = env.into_iter().collect::<Vec<_>>();
    values.sort_by(|left, right| left.0.cmp(&right.0));
    values
}

pub fn build_active_wineserver_launch_plan(
    game: &GameInstall,
    steam_root: &Path,
    proton: &ProtonTool,
    executable: &Path,
    args: &[String],
) -> Result<LaunchPlan> {
    let executable = fs::canonicalize(executable)
        .with_context(|| {
            format!(
                "Windows executable does not exist: {}",
                executable.display()
            )
        })?;

    let probe = process_probe_game(game);
    let pid = probe.best_candidate_pid.ok_or_else(|| {
        anyhow!(
            "cannot join active Wine server because no real game candidate is running for AppID {}",
            game.app_id
        )
    })?;

    let wine = proton_wine_binary(proton)?;
    let wineserver = proton_wineserver_binary(proton)?;

    let mut command = vec![
        wine.display().to_string(),
        executable.display().to_string(),
    ];
    command.extend(args.iter().cloned());

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer: executable,
        command,
        environment: sanitized_live_wine_environment(
            pid,
            game,
            steam_root,
            &wine,
            &wineserver,
        ),
    })
}

pub fn run_active_wineserver_launch_plan(
    plan: &LaunchPlan,
    dry_run: bool,
) -> Result<Option<u32>> {
    if dry_run {
        return Ok(None);
    }

    let wine = PathBuf::from(
        plan.command
            .first()
            .ok_or_else(|| anyhow!("active Wine launch plan has no command"))?,
    );

    let mut command = Command::new(&wine);
    command.arg(&plan.trainer);

    for extra in plan.command.iter().skip(2) {
        command.arg(extra);
    }

    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);

    if let Some(parent) = plan.trainer.parent() {
        command.current_dir(parent);
    }

    // Wand is Electron. Null stdio prevents the old Node/Electron EFAULT
    // failure and also prevents journal-pipe inheritance.
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command
        .spawn()
        .context(
            "launching Wand directly into the active Steam/Proton Wine server",
        )?;

    Ok(Some(child.id()))
}


pub fn build_proton_runinprefix_launch_plan(
    game: &GameInstall,
    steam_root: &Path,
    proton: &ProtonTool,
    executable: &Path,
    args: &[String],
) -> Result<LaunchPlan> {
    let executable = fs::canonicalize(executable)
        .with_context(|| format!(
            "Windows executable does not exist: {}",
            executable.display()
        ))?;

    if !game.compatdata_dir.exists() || !game.prefix_dir.exists() {
        return Err(anyhow!(
            "Proton compatdata/prefix does not exist for AppID {}. Launch the game through Steam first.",
            game.app_id
        ));
    }

    if !proton.proton_script.is_file() {
        return Err(anyhow!(
            "selected Proton script does not exist: {}",
            proton.proton_script.display()
        ));
    }

    let mut command = vec![
        proton.proton_script.display().to_string(),
        "runinprefix".into(),
        executable.display().to_string(),
    ];
    command.extend(args.iter().cloned());

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer: executable,
        command,
        environment: proton_environment(game, steam_root),
    })
}

pub fn run_proton_runinprefix_launch_plan(
    plan: &LaunchPlan,
    dry_run: bool,
) -> Result<Option<u32>> {
    if dry_run {
        return Ok(None);
    }

    let mut command = Command::new(&plan.proton.proton_script);
    command.arg("runinprefix").arg(&plan.trainer);

    for extra in plan.command.iter().skip(3) {
        command.arg(extra);
    }

    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);

    if let Some(parent) = plan.trainer.parent() {
        command.current_dir(parent);
    }

    // Wand is an Electron desktop application. Give it detached/null stdio so
    // Electron/Node never inherits wandd's systemd journal descriptors.
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command
        .spawn()
        .context("launching provider inside the already-running Proton prefix with runinprefix")?;

    Ok(Some(child.id()))
}

pub fn build_launch_plan(
    game: &GameInstall,
    steam_root: &Path,
    proton: &ProtonTool,
    trainer: &Path,
    args: &[String],
) -> Result<LaunchPlan> {
    let trainer = fs::canonicalize(trainer)
        .with_context(|| format!("trainer does not exist: {}", trainer.display()))?;

    if !game.compatdata_dir.exists() {
        return Err(anyhow!(
            "compatdata does not exist: {}. Launch the game through Steam at least once first.",
            game.compatdata_dir.display()
        ));
    }

    let mut command = vec![
        proton.proton_script.display().to_string(),
        "run".into(),
        trainer.display().to_string(),
    ];
    command.extend(args.iter().cloned());

    Ok(LaunchPlan {
        app_id: game.app_id,
        game_name: game.name.clone(),
        proton: proton.clone(),
        compatdata_dir: game.compatdata_dir.clone(),
        prefix_dir: game.prefix_dir.clone(),
        trainer,
        command,
        environment: proton_environment(game, steam_root),
    })
}

pub fn run_launch_plan(
    plan: &LaunchPlan,
    dry_run: bool,
) -> Result<Option<u32>> {
    if dry_run {
        return Ok(None);
    }

    let mut command = Command::new(&plan.proton.proton_script);
    command.arg("run").arg(&plan.trainer);

    for extra in plan.command.iter().skip(3) {
        command.arg(extra);
    }

    let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
    command.envs(env);

    if let Some(parent) = plan.trainer.parent() {
        command.current_dir(parent);
    }

    command
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    let child = command
        .spawn()
        .context("launching trainer through Proton")?;
    Ok(Some(child.id()))
}

pub fn process_alive(pid: u32) -> bool {
    PathBuf::from(format!("/proc/{pid}")).exists()
}

pub fn terminate_owned_process(pid: u32) -> Result<()> {
    if !process_alive(pid) {
        return Ok(());
    }

    let status = Command::new("kill")
        .arg("-TERM")
        .arg(pid.to_string())
        .status()
        .context("sending SIGTERM to owned trainer process")?;

    if !status.success() {
        return Err(anyhow!("failed to terminate process {pid}"));
    }

    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;

    fn native_wrapper_fixture() -> (PathBuf, GameInstall, ProtonTool, PathBuf, PathBuf) {
        use std::sync::atomic::{AtomicU64, Ordering};
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "gameweld-native-wrapper-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let steam = root.join("Steam");
        let library = steam.join("steamapps");
        let install = library.join("common/Test Game");
        let compatdata = library.join("compatdata/3008130");
        let prefix = compatdata.join("pfx");
        fs::create_dir_all(&install).unwrap();
        fs::create_dir_all(&prefix).unwrap();
        let exe = install.join("TestGame.exe");
        fs::write(&exe, b"MZ-fake-windows-game").unwrap();
        let wrapper = root.join("deckcheatz/wemod");
        fs::create_dir_all(wrapper.parent().unwrap()).unwrap();
        fs::write(&wrapper, b"#!/bin/sh\nexit 0\n").unwrap();
        let proton_dir = steam.join("compatibilitytools.d/GE-Proton");
        fs::create_dir_all(&proton_dir).unwrap();
        let proton_script = proton_dir.join("proton");
        fs::write(&proton_script, b"#!/bin/sh\nexit 0\n").unwrap();
        for script in [&wrapper, &proton_script] {
            fs::set_permissions(script, fs::Permissions::from_mode(0o700)).unwrap();
        }
        let game = GameInstall {
            app_id: 3008130,
            name: "Test Game".into(),
            install_dir: install,
            library_root: steam.clone(),
            manifest: library.join("appmanifest_3008130.acf"),
            compatdata_dir: compatdata,
            prefix_dir: prefix,
        };
        let proton = ProtonTool {
            tool_id: "GE-Proton".into(),
            display_name: "GE-Proton".into(),
            root: proton_dir,
            proton_script,
            source: "test".into(),
        };
        let log = wrapper.parent().unwrap().join("wemod.log");
        (root, game, proton, wrapper, log)
    }

    #[test]
    fn one_session_batch_rejects_command_metacharacters_and_expansion() {
        for bad in [
            "hello&whoami", "hello|whoami", "a<b", "a>b", "hello^world",
            "(group)", "hello%USERNAME%", "hello!VAR!", "hello\"world",
            "line\nbreak", "line\rbreak",
        ] {
            assert!(batch_safe_arg(bad).is_err(), "unsafe argument accepted: {bad:?}");
            let path = PathBuf::from(format!("/tmp/{bad}"));
            assert!(batch_safe_windows_path(&path, Path::new("/tmp/wand-prefix")).is_err(),
                    "unsafe path accepted: {bad:?}");
        }
        assert_eq!(batch_safe_arg("--safe=game-1").unwrap(), "\"--safe=game-1\"");
        assert_eq!(batch_safe_windows_path(
            Path::new("/tmp/game/Game.exe"), Path::new("/tmp/wand-prefix")).unwrap(),
            r"Z:\tmp\game\Game.exe");
    }

    #[test]
    fn one_session_batch_keeps_wine_profile_instead_of_overriding_account() {
        // Regression guard for the hard-coded per-user Windows profile and
        // expansion of untrusted USERPROFILE content into generated CMD.
        let src = include_str!("lib.rs");
        assert!(!src.contains("USERPROFILE=C:"));
        assert!(!src.contains("WAND_SAVED_USERPROFILE"));
        assert!(!src.contains("echo wand-user=%USERPROFILE%"));
        assert!(!src.contains("echo game-user=%USERPROFILE%"));
    }

    #[test]
    fn direct_deckcheatz_plan_is_read_only_and_game_first_command_is_wrapped() {
        let (root, game, proton, wrapper, log) = native_wrapper_fixture();
        let steam = root.join("Steam");
        let plan = build_native_wrapper_launch_plan(
            &game, &steam, &proton, &wrapper, &log,
        ).unwrap();
        assert_eq!(plan.command, vec![
            wrapper.display().to_string(),
            proton.proton_script.display().to_string(),
            "waitforexitandrun".into(),
            game.install_dir.join("TestGame.exe").display().to_string(),
        ]);
        let env: HashMap<_, _> = plan.environment.iter().cloned().collect();
        assert_eq!(env["WINEDLLOVERRIDES"], "version=n,b");
        assert_eq!(env["WEMOD_LOG"], log.display().to_string());
        assert_eq!(env["SteamAppId"], "3008130");
        assert_eq!(env["SteamGameId"], "3008130");
        assert_eq!(env["SteamOverlayGameId"], "3008130");
        assert_eq!(env["STEAM_COMPAT_DATA_PATH"], game.compatdata_dir.display().to_string());
        assert!(!log.exists());
        assert_eq!(
            run_native_wrapper_launch_plan(&plan, &game.install_dir, true).unwrap(),
            None
        );
        assert!(!log.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn direct_deckcheatz_blocks_ambiguous_exe_and_untrusted_game_paths() {
        let (root, game, proton, wrapper, log) = native_wrapper_fixture();
        let steam = root.join("Steam");
        let alt = game.install_dir.join("OtherGame.exe");
        fs::write(&alt, b"MZ").unwrap();
        let rejected = build_native_wrapper_launch_plan(
            &game, &steam, &proton, &wrapper, &log,
        ).unwrap_err();
        assert!(rejected.to_string().contains("more than one plausible"));
        fs::remove_file(&alt).unwrap();
        let outside = root.join("outside.log");
        let link = wrapper.parent().unwrap().join("wemod.log");
        #[cfg(unix)]
        std::os::unix::fs::symlink(&outside, &link).unwrap();
        assert!(build_native_wrapper_launch_plan(
            &game, &steam, &proton, &wrapper, &link,
        ).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn direct_deckcheatz_rejects_invalid_launch_plan_before_dry_run() {
        let (root, game, proton, wrapper, log) = native_wrapper_fixture();
        let mut plan = build_native_wrapper_launch_plan(
            &game, &root.join("Steam"), &proton, &wrapper, &log,
        ).unwrap();
        plan.command.swap(0, 1);
        assert!(run_native_wrapper_launch_plan(
            &plan, &game.install_dir, true,
        ).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn live_wine_environment_keeps_compatibility_state() {
        assert!(keep_live_wine_environment("WINEPREFIX"));
        assert!(keep_live_wine_environment("WINESERVER"));
        assert!(keep_live_wine_environment("PROTON_NO_ESYNC"));
        assert!(keep_live_wine_environment("DXVK_CONFIG_FILE"));
        assert!(!keep_live_wine_environment("MANGOHUD"));
        assert!(!keep_live_wine_environment("LD_PRELOAD"));
    }

    #[test]
    fn proton_runinprefix_verb_is_stable() {
        assert_eq!("runinprefix", "runinprefix");
    }

    #[test]
    fn windows_executable_handles_windows_paths_with_spaces() {
        let args = vec![
            "wine".to_string(),
            r"C:\Program Files\Wand\Wand.exe".to_string(),
            "--type=renderer".to_string(),
        ];

        assert_eq!(
            windows_executable(&args).as_deref(),
            Some("Wand.exe")
        );
    }

    #[test]
    fn wand_is_never_a_game_candidate() {
        let (role, score) = classify(
            "Wand.exe",
            r"C:\Users\steamuser\AppData\Local\Wand\Wand.exe",
            Some("Wand.exe"),
        );

        assert_eq!(role, ProcessRole::Helper);
        assert!(score < 0);
    }

    #[test]
    fn electron_renderer_is_helper() {
        let (role, score) = classify(
            "wine64-preloader",
            r"Wand.exe --type=renderer",
            Some("Wand.exe"),
        );

        assert_eq!(role, ProcessRole::Helper);
        assert!(score < 0);
    }

    #[test]
    fn wine_preloader_alone_is_not_game() {
        let (role, score) = classify(
            "wine64-preloader",
            "wine64-preloader",
            None,
        );

        assert_eq!(role, ProcessRole::Unknown);
        assert_eq!(score, 0);
    }

    #[test]
    fn system_wine_provider_uses_detached_stdio() {
        assert!(SYSTEM_WINE_PROVIDER_USES_NULL_STDIO);
    }

    #[test]
    fn wineboot_is_helper_not_game() {
        let (role, score) = classify(
            "wineboot.exe",
            r"C:\windows\system32\wineboot.exe --init",
            Some("wineboot.exe"),
        );
        assert_eq!(role, ProcessRole::Helper);
        assert!(score < 0);
    }

    #[test]
    fn svchost_is_helper_not_game() {
        let (role, score) = classify(
            "svchost.exe",
            r"C:\windows\system32\svchost.exe -k LocalServiceNetworkRestricted",
            Some("svchost.exe"),
        );
        assert_eq!(role, ProcessRole::Helper);
        assert!(score < 0);
    }

    #[test]
    fn steam_legacycompat_evaluator_is_helper_not_game() {
        let (role, score) = classify(
            "python3",
            r"/mnt/games/Steam/compatibilitytools.d/Proton-GE/proton run /mnt/games/Steam/legacycompat/iscriptevaluator.exe legacycompat\evaluatorscript_2713000.vdf",
            Some("iscriptevaluator.exe"),
        );
        assert_eq!(role, ProcessRole::Helper);
        assert!(score < 0);
    }

    #[test]
    fn proton_python_game_launcher_is_not_final_game() {
        let (role, score) = classify(
            "python3",
            r"/mnt/games/Steam/compatibilitytools.d/Proton-GE/proton run Z:\mnt\games\Steam\steamapps\common\Example\Example.exe",
            Some("Example.exe"),
        );

        assert_eq!(role, ProcessRole::Launcher);
        assert!(score < 100);
    }

    #[test]
    fn wine_z_path_matches_game_install_shape() {
        assert_eq!(
            wine_z_path(Path::new("/mnt/games/Steam/steamapps/common/Resonance A Plague Tale Legacy")),
            r"Z:\mnt\games\Steam\steamapps\common\Resonance A Plague Tale Legacy"
        );
    }

    #[test]
    fn ordinary_windows_game_exe_is_candidate() {
        let (role, score) = classify(
            "wine64-preloader",
            r"Z:\Games\ExampleGame.exe",
            Some("ExampleGame.exe"),
        );

        assert_eq!(role, ProcessRole::GameCandidate);
        assert_eq!(score, 100);
    }
}
