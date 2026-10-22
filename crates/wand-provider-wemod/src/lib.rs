use anyhow::{anyhow, Context, Result};
use std::{
    cmp::Ordering,
    fs,
    path::{Path, PathBuf},
};
use wand_core::{
    GameInstall, LaunchPlan, ProviderDescriptor, ProviderFlow, ProviderHealth,
    ProviderImportResult, ProviderSource, ProtonTool,
};
use wand_provider_api::TrainerProvider;

#[derive(Debug, Default)]
pub struct WeModProvider;

#[derive(Debug, Clone)]
struct RuntimeCandidate {
    exe: PathBuf,
    product: &'static str,
    version: Vec<u32>,
}

fn parse_app_version(name: &str) -> Vec<u32> {
    name.strip_prefix("app-")
        .unwrap_or(name)
        .split('.')
        .map(|part| part.parse::<u32>().unwrap_or(0))
        .collect()
}

fn compare_versions(left: &[u32], right: &[u32]) -> Ordering {
    let count = left.len().max(right.len());
    for index in 0..count {
        let l = *left.get(index).unwrap_or(&0);
        let r = *right.get(index).unwrap_or(&0);
        match l.cmp(&r) {
            Ordering::Equal => {}
            other => return other,
        }
    }
    Ordering::Equal
}

fn version_from_ancestors(path: &Path, stop: &Path) -> Vec<u32> {
    let mut cursor = path.parent();

    while let Some(current) = cursor {
        if current == stop {
            break;
        }

        if let Some(name) = current.file_name().and_then(|value| value.to_str()) {
            if name.starts_with("app-") {
                return parse_app_version(name);
            }
        }

        cursor = current.parent();
    }

    Vec::new()
}

fn scan_runtime_tree(
    out: &mut Vec<RuntimeCandidate>,
    root: &Path,
    product: &'static str,
    exe_name: &str,
) {
    if !root.is_dir() {
        return;
    }

    let wanted = exe_name.to_ascii_lowercase();
    let mut stack = vec![root.to_path_buf()];
    let mut visited = 0usize;

    while let Some(dir) = stack.pop() {
        // Keep discovery bounded in case a malformed prefix contains a huge
        // symlinked or unrelated tree.
        if visited >= 20_000 {
            break;
        }
        visited += 1;

        let Ok(entries) = fs::read_dir(&dir) else {
            continue;
        };

        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(file_type) = entry.file_type() else {
                continue;
            };

            if file_type.is_symlink() {
                continue;
            }

            if file_type.is_dir() {
                stack.push(path);
                continue;
            }

            if !file_type.is_file() {
                continue;
            }

            let matches = path
                .file_name()
                .and_then(|value| value.to_str())
                .map(|value| value.to_ascii_lowercase() == wanted)
                .unwrap_or(false);

            if matches {
                out.push(RuntimeCandidate {
                    version: version_from_ancestors(&path, root),
                    exe: path,
                    product,
                });
            }
        }
    }
}

fn prefix_candidates(game: &GameInstall) -> Vec<RuntimeCandidate> {
    prefix_runtime_candidates(&game.prefix_dir)
}

fn prefix_runtime_candidates(prefix: &Path) -> Vec<RuntimeCandidate> {
    let mut out = Vec::new();
    let users = prefix.join("drive_c/users");

    if let Ok(entries) = fs::read_dir(&users) {
        for entry in entries.flatten() {
            let user = entry.path();
            if !user.is_dir() {
                continue;
            }

            let local = user.join("AppData/Local");
            scan_runtime_tree(
                &mut out,
                &local.join("Wand"),
                "Wand",
                "Wand.exe",
            );
            scan_runtime_tree(
                &mut out,
                &local.join("WeMod"),
                "WeMod",
                "WeMod.exe",
            );
        }
    }

    out
}

fn best_prefix_runtime(prefix: &Path) -> Option<RuntimeCandidate> {
    best_candidate(prefix_runtime_candidates(prefix))
}

fn central_candidates() -> Vec<RuntimeCandidate> {
    let mut out = Vec::new();

    if let Some(path) = std::env::var_os("WAND_WEMOD_EXE").map(PathBuf::from) {
        if path.is_file() {
            let product = if path
                .file_name()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case("Wand.exe"))
                .unwrap_or(false)
            {
                "Wand"
            } else {
                "WeMod"
            };

            out.push(RuntimeCandidate {
                exe: path,
                product,
                version: Vec::new(),
            });
        }
    }

    let Some(home) = std::env::var_os("HOME").map(PathBuf::from) else {
        return out;
    };

    let root = home.join(".local/share/wand/wemod-runtime");
    scan_runtime_tree(&mut out, &root.join("Wand"), "Wand", "Wand.exe");
    scan_runtime_tree(&mut out, &root.join("WeMod"), "WeMod", "WeMod.exe");

    if root.join("Wand.exe").is_file() {
        out.push(RuntimeCandidate {
            exe: root.join("Wand.exe"),
            product: "Wand",
            version: Vec::new(),
        });
    }

    if root.join("WeMod.exe").is_file() {
        out.push(RuntimeCandidate {
            exe: root.join("WeMod.exe"),
            product: "WeMod",
            version: Vec::new(),
        });
    }

    out
}

fn best_candidate(mut candidates: Vec<RuntimeCandidate>) -> Option<RuntimeCandidate> {
    candidates.sort_by(|left, right| {
        compare_versions(&right.version, &left.version)
            .then_with(|| right.product.cmp(left.product))
    });
    candidates.into_iter().next()
}

fn find_runtime(game: &GameInstall) -> Option<RuntimeCandidate> {
    let game_specific = prefix_candidates(game);
    if !game_specific.is_empty() {
        return best_candidate(game_specific);
    }

    best_candidate(central_candidates())
}

const DWRITECORE_VERSION: &str = "2.1.0";

fn shared_dwritecore_path() -> Option<PathBuf> {
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    Some(
        home.join(".local/share/wand/dwritecore")
            .join(DWRITECORE_VERSION)
            .join("DWriteCore.dll"),
    )
}

fn runtime_dwritecore_path(executable: &Path) -> Option<PathBuf> {
    executable
        .parent()
        .map(|parent| parent.join("DWriteCore.dll"))
}

fn dwritecore_health(executable: &Path) -> String {
    let runtime = runtime_dwritecore_path(executable);
    let shared = shared_dwritecore_path();

    if runtime.as_ref().is_some_and(|path| path.is_file()) {
        return format!(
            "DWriteCore compatibility: installed beside {}",
            executable
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or("Wand/WeMod")
        );
    }

    if shared.as_ref().is_some_and(|path| path.is_file()) {
        return "DWriteCore compatibility: shared Microsoft runtime ready; it will be placed beside Wand on launch".into();
    }

    "DWriteCore compatibility: missing; rerun scripts/install-dwritecore.sh".into()
}

fn ensure_dwritecore_for_runtime(executable: &Path) -> Result<PathBuf> {
    let source = shared_dwritecore_path().ok_or_else(|| {
        anyhow!("HOME is unavailable; cannot resolve the shared DWriteCore runtime")
    })?;

    if !source.is_file() {
        return Err(anyhow!(
            "Microsoft DWriteCore compatibility runtime is missing at {}. Run ./scripts/install-dwritecore.sh, then retry.",
            source.display()
        ));
    }

    let target = runtime_dwritecore_path(executable).ok_or_else(|| {
        anyhow!(
            "cannot resolve the directory containing {}",
            executable.display()
        )
    })?;

    // Existing valid-looking app-local DWriteCore is left alone. This mirrors
    // the established WeMod launcher workaround and avoids replacing a DLL
    // while an Electron child may still have it mapped.
    if target
        .metadata()
        .map(|meta| meta.is_file() && meta.len() > 1024 * 1024)
        .unwrap_or(false)
    {
        return Ok(target);
    }

    fs::copy(&source, &target).with_context(|| {
        format!(
            "installing DWriteCore compatibility runtime from {} to {}",
            source.display(),
            target.display()
        )
    })?;

    Ok(target)
}

fn runtime_description(candidate: &RuntimeCandidate) -> String {
    let version = if candidate.version.is_empty() {
        "unknown".into()
    } else {
        candidate
            .version
            .iter()
            .map(u32::to_string)
            .collect::<Vec<_>>()
            .join(".")
    };

    format!(
        "{} runtime {} at {}",
        candidate.product,
        version,
        candidate.exe.display()
    )
}


fn select_windows_user(prefix: &Path) -> Option<PathBuf> {
    let users = prefix.join("drive_c/users");
    let steamuser = users.join("steamuser");
    if steamuser.is_dir() {
        return Some(steamuser);
    }

    fs::read_dir(&users)
        .ok()?
        .flatten()
        .map(|entry| entry.path())
        .find(|path| {
            path.is_dir()
                && path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .map(|name| {
                        !matches!(
                            name.to_ascii_lowercase().as_str(),
                            "public" | "default" | "default user" | "all users"
                        )
                    })
                    .unwrap_or(false)
        })
}

fn infer_prefix_from_source(source: &Path) -> Option<PathBuf> {
    let source = fs::canonicalize(source).ok()?;

    if source.join("drive_c/users").is_dir() {
        return Some(source);
    }

    let mut cursor = if source.is_file() {
        source.parent()?.to_path_buf()
    } else {
        source
    };

    loop {
        if cursor.join("drive_c/users").is_dir() {
            return Some(cursor);
        }

        if !cursor.pop() {
            break;
        }
    }

    None
}

fn copy_tree(source: &Path, destination: &Path) -> Result<()> {
    fs::create_dir_all(destination)
        .with_context(|| format!("creating {}", destination.display()))?;

    for entry in fs::read_dir(source)
        .with_context(|| format!("reading {}", source.display()))?
    {
        let entry = entry?;
        let from = entry.path();
        let to = destination.join(entry.file_name());
        let file_type = entry.file_type()?;

        if file_type.is_dir() {
            copy_tree(&from, &to)?;
        } else if file_type.is_file() {
            if let Some(parent) = to.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(&from, &to).with_context(|| {
                format!("copying {} -> {}", from.display(), to.display())
            })?;
        }
    }

    Ok(())
}

fn runtime_product_in_prefix(
    prefix: &Path,
) -> Option<(&'static str, PathBuf, PathBuf, RuntimeCandidate)> {
    let candidate = best_prefix_runtime(prefix)?;
    let user = select_windows_user(prefix)?;
    let local = user.join("AppData/Local");
    let roaming = user.join("AppData/Roaming");

    let (local_root, roaming_root) = if candidate.product == "Wand" {
        (local.join("Wand"), roaming.join("Wand"))
    } else {
        (local.join("WeMod"), roaming.join("WeMod"))
    };

    Some((
        candidate.product,
        local_root,
        roaming_root,
        candidate,
    ))
}

fn import_from_prefix(
    game: &GameInstall,
    source_prefix: &Path,
    replace: bool,
) -> Result<ProviderImportResult> {
    let target_prefix = fs::canonicalize(&game.prefix_dir)
        .unwrap_or_else(|_| game.prefix_dir.clone());
    let source_prefix = fs::canonicalize(source_prefix)
        .unwrap_or_else(|_| source_prefix.to_path_buf());

    if source_prefix == target_prefix {
        return Err(anyhow!(
            "source prefix and target game prefix are the same"
        ));
    }

    let (product, source_local, source_roaming, source_candidate) =
        runtime_product_in_prefix(&source_prefix).ok_or_else(|| {
            anyhow!(
                "no runnable Wand.exe/WeMod.exe runtime found in source prefix {}",
                source_prefix.display()
            )
        })?;

    if !source_candidate.exe.is_file() {
        return Err(anyhow!(
            "detected source runtime disappeared before import: {}",
            source_candidate.exe.display()
        ));
    }

    let target_user = select_windows_user(&game.prefix_dir).ok_or_else(|| {
        anyhow!(
            "could not locate a Windows user directory in {}",
            game.prefix_dir.display()
        )
    })?;

    let target_local = target_user.join("AppData/Local").join(product);
    let target_roaming = target_user.join("AppData/Roaming").join(product);

    if !replace && target_local.exists() {
        return Err(anyhow!(
            "target runtime already exists at {}. Re-run with replace enabled if you intend to overwrite/merge it.",
            target_local.display()
        ));
    }

    if replace && target_local.exists() {
        fs::remove_dir_all(&target_local).with_context(|| {
            format!("removing {}", target_local.display())
        })?;
    }

    if replace && target_roaming.exists() {
        fs::remove_dir_all(&target_roaming).with_context(|| {
            format!("removing {}", target_roaming.display())
        })?;
    }

    copy_tree(&source_local, &target_local)?;

    let mut copied_paths = vec![target_local.clone()];

    if source_roaming.is_dir() {
        copy_tree(&source_roaming, &target_roaming)?;
        copied_paths.push(target_roaming.clone());
    }

    let provider = WeModProvider;
    let health = provider.probe_game(game);

    if !health.available {
        return Err(anyhow!(
            "runtime copy completed but the target prefix still has no runnable Wand.exe/WeMod.exe. Source executable was {}",
            source_candidate.exe.display()
        ));
    }

    Ok(ProviderImportResult {
        provider_id: "wemod".into(),
        app_id: game.app_id,
        source: source_prefix,
        copied_paths,
        health,
    })
}

fn make_source(
    path: PathBuf,
    label: String,
    details: Vec<String>,
) -> ProviderSource {
    ProviderSource {
        provider_id: "wemod".into(),
        source_id: path.display().to_string(),
        display_name: label,
        path,
        details,
    }
}


fn set_plan_environment(plan: &mut LaunchPlan, key: &str, value: Option<String>) {
    plan.environment.retain(|(existing, _)| existing != key);

    if let Some(value) = value {
        plan.environment.push((key.into(), value));
    }

    plan.environment.sort_by(|left, right| left.0.cmp(&right.0));
}

fn managed_rendering_description() -> String {
    "Wand renderer: native Electron/Chromium settings inside the same managed Proton session as the game; DWriteCore is the only renderer compatibility layer".into()
}

fn aux_diagnostics_mode() -> Option<String> {
    let value = std::env::var("WAND_AUX_DIAGNOSTICS").ok()?;
    let value = value.trim().to_ascii_lowercase();

    match value.as_str() {
        "" | "0" | "false" | "off" | "no" => None,
        "deep" | "server" => Some("deep".into()),
        "tophat" | "network" | "trainer" => Some("tophat".into()),
        "plugin" | "loader" | "clr" => Some("plugin".into()),
        _ => Some("basic".into()),
    }
}

fn aux_diagnostics_winedebug(mode: &str) -> String {
    let basic = "-all,+timestamp,+pid,+tid,+process,+thread,+seh,+debugstr,+loaddll";

    match mode {
        "deep" => format!("{basic},+server"),
        "tophat" => format!(
            "{basic},+winsock,+schannel,+winhttp,+wininet,+crypt,+wintrust"
        ),
        // WinTrust and localhost IPC are already proven working. Keep this
        // trace focused on PE/module loading and CLR hosting.
        "plugin" => format!("{basic},+module,+mscoree"),
        _ => basic.into(),
    }
}


impl TrainerProvider for WeModProvider {
    fn descriptor(&self) -> ProviderDescriptor {
        ProviderDescriptor {
            id: "wemod".into(),
            name: "WeMod / Wand".into(),
            description:
                "Starts Wand and the real game executable together inside one selected-Proton session, with no Steam launch-option wrapper and Microsoft's DWriteCore compatibility runtime."
                    .into(),
            capabilities: vec![
                "same-prefix".into(),
                "single-proton-session".into(),
                "no-steam-wrapper".into(),
                "prelaunch-wand-cleanup".into(),
                "windows-steam-identity".into(),
                "canonical-windows-paths".into(),
                "aux-service-diagnostics".into(),
                "tophat-runtime-diagnostics".into(),
                "plugin-loader-diagnostics".into(),
                "wand-profile-normalization".into(),
                "dwritecore-compat".into(),
                "same-proton-context".into(),
                "wand-runtime-detection".into(),
                "wemod-runtime-detection".into(),
                "manual-game-library-fallback".into(),
                "installer-bootstrap".into(),
            ],
            requires_windows_bridge: false,
            requires_trainer_path: false,
            requires_provider_pid_alive: false,
            flow: ProviderFlow::InteractiveBeforeGame,
        }
    }

    fn probe(&self) -> ProviderHealth {
        if let Some(candidate) = best_candidate(central_candidates()) {
            return ProviderHealth {
                id: "wemod".into(),
                available: true,
                status: "ready".into(),
                details: vec![
                    runtime_description(&candidate),
                    "A per-game prefix runtime will take precedence when present.".into(),
                ],
            };
        }

        ProviderHealth {
            id: "wemod".into(),
            available: true,
            status: "game-prefix-probe-required".into(),
            details: vec![
                "No central Wand/WeMod runtime override was found.".into(),
                "Select a Steam game so Wand can inspect that game's Proton prefix.".into(),
                "WAND_WEMOD_EXE can point at an existing Wand.exe or WeMod.exe runtime.".into(),
            ],
        }
    }

    fn probe_game(&self, game: &GameInstall) -> ProviderHealth {
        match find_runtime(game) {
            Some(candidate) => ProviderHealth {
                id: "wemod".into(),
                available: true,
                status: "ready".into(),
                details: vec![
                    runtime_description(&candidate),
                    "Steam Launch Options stay empty; no wrapper is used.".into(),
                    "Wand Native starts one selected-Proton session containing both Wand and the real game executable.".into(),
                    "Wand is started first inside that Wine session with a normalized Windows profile matching its install user; the original Proton profile is restored before the game is dispatched from the same Windows batch using canonical prefix DOS-drive paths.".into(),
                    managed_rendering_description(),
                    match aux_diagnostics_mode() {
                        Some(mode) => format!("Auxiliary-service Wine diagnostics: {mode} mode enabled"),
                        None => "Auxiliary-service Wine diagnostics: disabled (normal mode)".into(),
                    },
                    dwritecore_health(&candidate.exe),
                    "Steam may remain open for client/API services, but Wand Native owns this managed Proton launch.".into(),
                ],
            },
            None => ProviderHealth {
                id: "wemod".into(),
                available: false,
                status: "runtime-missing".into(),
                details: vec![
                    format!(
                        "No Wand.exe/WeMod.exe installation was found inside {}",
                        game.prefix_dir.display()
                    ),
                    "Searches recursively under drive_c/users/*/AppData/Local/Wand for Wand.exe.".into(),
                    "Also searches recursively under drive_c/users/*/AppData/Local/WeMod for WeMod.exe.".into(),
                    "Wand does not download proprietary WeMod files automatically; use runtime import/bootstrap.".into(),
                ],
            },
        }
    }

    fn discover_sources(
        &self,
        games: &[GameInstall],
    ) -> Result<Vec<ProviderSource>> {
        let mut sources = Vec::new();
        let mut seen = std::collections::BTreeSet::new();

        if let Some(prefix) = std::env::var_os("WAND_WEMOD_SOURCE_PREFIX")
            .map(PathBuf::from)
        {
            if let Some(candidate) = best_prefix_runtime(&prefix) {
                let canonical = fs::canonicalize(&prefix).unwrap_or(prefix);
                if seen.insert(canonical.clone()) {
                    sources.push(make_source(
                        canonical,
                        "WAND_WEMOD_SOURCE_PREFIX".into(),
                        vec![
                            "Explicit source prefix from environment.".into(),
                            runtime_description(&candidate),
                        ],
                    ));
                }
            }
        }

        if let Some(home) = std::env::var_os("HOME").map(PathBuf::from) {
            for candidate in [
                home.join(".wine"),
                home.join(".local/share/wand/wemod-prefix"),
                home.join(".local/share/wand/prefix"),
            ] {
                if let Some(runtime) = best_prefix_runtime(&candidate) {
                    let canonical =
                        fs::canonicalize(&candidate).unwrap_or(candidate);
                    if seen.insert(canonical.clone()) {
                        sources.push(make_source(
                            canonical.clone(),
                            format!("Existing Wine prefix: {}", canonical.display()),
                            vec![
                                "Detected runnable Wand/WeMod runtime.".into(),
                                runtime_description(&runtime),
                            ],
                        ));
                    }
                }
            }
        }

        for game in games {
            if let Some(runtime) = best_prefix_runtime(&game.prefix_dir) {
                let canonical = fs::canonicalize(&game.prefix_dir)
                    .unwrap_or_else(|_| game.prefix_dir.clone());

                if seen.insert(canonical.clone()) {
                    sources.push(make_source(
                        canonical,
                        format!("{} (Steam AppID {})", game.name, game.app_id),
                        vec![
                            "Existing Steam compatdata prefix containing a runnable Wand/WeMod executable.".into(),
                            runtime_description(&runtime),
                            "Local and Roaming AppData can be imported into another game prefix.".into(),
                        ],
                    ));
                }
            }
        }

        Ok(sources)
    }

    fn import_runtime(
        &self,
        game: &GameInstall,
        source: &Path,
        replace: bool,
    ) -> Result<ProviderImportResult> {
        let source_prefix = infer_prefix_from_source(source).ok_or_else(|| {
            anyhow!(
                "could not infer a Wine/Proton prefix from {}. Select the prefix directory containing drive_c/users.",
                source.display()
            )
        })?;

        import_from_prefix(game, &source_prefix, replace)
    }

    fn prepare_bootstrap(
        &self,
        steam_root: &Path,
        game: &GameInstall,
        proton: &ProtonTool,
        installer: &Path,
        args: &[String],
    ) -> Result<LaunchPlan> {
        let is_exe = installer
            .extension()
            .and_then(|value| value.to_str())
            .map(|value| value.eq_ignore_ascii_case("exe"))
            .unwrap_or(false);

        if !is_exe {
            return Err(anyhow!(
                "WeMod/Wand bootstrap currently expects a Windows .exe installer: {}",
                installer.display()
            ));
        }

        wand_runtime::build_proton_runinprefix_launch_plan(
            game,
            steam_root,
            proton,
            installer,
            args,
        )
        .with_context(|| {
            format!(
                "preparing WeMod/Wand installer {} for Steam AppID {}",
                installer.display(),
                game.app_id
            )
        })
    }

    fn prepare(
        &self,
        steam_root: &Path,
        game: &GameInstall,
        proton: &ProtonTool,
        _trainer: &Path,
        args: &[String],
    ) -> Result<LaunchPlan> {
        let candidate = find_runtime(game).ok_or_else(|| {
            anyhow!(
                "WeMod/Wand runtime is missing for Steam AppID {}. \
                 Install/import a runtime into this game's prefix or set WAND_WEMOD_EXE.",
                game.app_id
            )
        })?;

        let dwritecore = ensure_dwritecore_for_runtime(&candidate.exe)?;

        let mut plan = wand_runtime::build_one_proton_session_launch_plan(
            game,
            steam_root,
            proton,
            &candidate.exe,
            args,
        )
        .with_context(|| {
            format!(
                "preparing one-Proton-session {} runtime {}",
                candidate.product,
                candidate.exe.display()
            )
        })?;

        set_plan_environment(
            &mut plan,
            "WAND_DWRITECORE_PATH",
            Some(dwritecore.to_string_lossy().into_owned()),
        );

        if let Some(mode) = aux_diagnostics_mode() {
            set_plan_environment(
                &mut plan,
                "WAND_AUX_DIAGNOSTICS_ACTIVE",
                Some(mode.clone()),
            );
            set_plan_environment(
                &mut plan,
                "WINEDEBUG",
                Some(aux_diagnostics_winedebug(&mode)),
            );
        }

        Ok(plan)
    }

    fn launch(
        &self,
        plan: &LaunchPlan,
        dry_run: bool,
    ) -> Result<Option<u32>> {
        wand_runtime::run_one_proton_session_launch_plan(
            plan,
            &plan
                .environment
                .iter()
                .find(|(key, _)| key == "STEAM_COMPAT_INSTALL_PATH")
                .map(|(_, value)| PathBuf::from(value))
                .unwrap_or_else(|| PathBuf::from(".")),
            dry_run,
        )
    }

    fn stop(&self, pid: u32) -> Result<()> {
        wand_runtime::terminate_owned_process(pid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dwritecore_target_is_beside_runtime() {
        assert_eq!(
            runtime_dwritecore_path(Path::new("/tmp/Wand/app-12/WeMod.exe")),
            Some(PathBuf::from("/tmp/Wand/app-12/DWriteCore.dll"))
        );
    }

    #[test]
    fn version_sorting_is_numeric() {
        assert_eq!(
            compare_versions(&parse_app_version("app-12.10.0"), &parse_app_version("app-12.9.9")),
            Ordering::Greater
        );
    }

    #[test]
    fn parses_multi_part_versions() {
        assert_eq!(
            parse_app_version("app-12.52.0"),
            vec![12, 52, 0]
        );
    }

    #[test]
    fn recursive_scan_finds_flat_runtime() {
        let root = std::env::temp_dir().join(format!(
            "wand-provider-wemod-flat-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("Wand.exe"), b"test").unwrap();

        let mut found = Vec::new();
        scan_runtime_tree(&mut found, &root, "Wand", "Wand.exe");

        assert_eq!(found.len(), 1);
        assert!(found[0].version.is_empty());

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn recursive_scan_extracts_app_version() {
        let root = std::env::temp_dir().join(format!(
            "wand-provider-wemod-versioned-{}",
            std::process::id()
        ));
        let runtime = root.join("nested/app-12.53.1/resources");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&runtime).unwrap();
        fs::write(runtime.join("Wand.exe"), b"test").unwrap();

        let mut found = Vec::new();
        scan_runtime_tree(&mut found, &root, "Wand", "Wand.exe");

        assert_eq!(found.len(), 1);
        assert_eq!(found[0].version, vec![12, 53, 1]);

        let _ = fs::remove_dir_all(&root);
    }
}
