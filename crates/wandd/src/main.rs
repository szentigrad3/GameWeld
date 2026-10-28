use anyhow::{Context, Result};
use std::{
    fs,
    io::Write,
    os::unix::fs::{DirBuilderExt, FileTypeExt, MetadataExt, PermissionsExt},
    path::{Path, PathBuf},
    sync::Arc,
};
use tar::{Builder as TarBuilder, Header};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    net::{UnixListener, UnixStream},
    sync::Mutex,
    time::{sleep, Duration, Instant},
};
use uuid::Uuid;
use wand_core::{
    DaemonStatus, InspectResult, ProviderBootstrapResult, ProviderFlow, Request, Response, SessionEventBatch, SessionRecord, SessionState,
};
use wand_provider_api::ProviderRegistry;
use wand_provider_generic::GenericExeProvider;
use wand_provider_wemod::WeModProvider;
use wand_state::StateStore;

const DEFAULT_PROVIDER: &str = "generic-exe";

fn socket_path() -> PathBuf {
    if let Some(value) = std::env::var_os("WAND_SOCKET_PATH") {
        return PathBuf::from(value);
    }

    if let Some(value) = std::env::var_os("XDG_RUNTIME_DIR") {
        return PathBuf::from(value).join("wand/wand.sock");
    }
    PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
        .join(".cache/wand-runtime/wand.sock")
}

fn context() -> Result<(
    PathBuf,
    Vec<wand_core::SteamLibrary>,
    Vec<wand_core::GameInstall>,
    Vec<wand_core::ProtonTool>,
)> {
    let root = wand_steam::primary_steam_root()?;
    let libraries = wand_steam::discover_libraries(&root)?;
    let games = wand_steam::discover_games(&libraries)?;
    let tools = wand_steam::discover_proton_tools(&root, &libraries)?;
    Ok((root, libraries, games, tools))
}

fn find_game(
    games: &[wand_core::GameInstall],
    app_id: u32,
) -> Option<wand_core::GameInstall> {
    games.iter().find(|game| game.app_id == app_id).cloned()
}

fn append_tar_bytes<W: Write>(
    tar: &mut TarBuilder<W>,
    name: &str,
    bytes: &[u8],
) -> Result<()> {
    let mut header = Header::new_gnu();
    header.set_mode(0o600);
    header.set_size(bytes.len() as u64);
    header.set_cksum();
    tar.append_data(&mut header, name, bytes)?;
    Ok(())
}

#[derive(Clone)]
struct App {
    store: StateStore,
    active: Arc<Mutex<Vec<Uuid>>>,
    providers: Arc<ProviderRegistry>,
}

fn sanitize_graphical_environment(
    values: Vec<(String, String)>,
) -> Vec<(String, String)> {
    const ALLOWED: &[&str] = &[
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "XDG_SESSION_TYPE",
    ];

    values
        .into_iter()
        .filter(|(key, value)| {
            ALLOWED.contains(&key.as_str())
                && !value.contains('\0')
                && value.len() <= 4096
        })
        .collect()
}

impl App {
    fn log(
        &self,
        level: &str,
        event: &str,
        message: &str,
        fields: serde_json::Value,
    ) {
        let _ = self
            .store
            .append_log(level, event, message, fields);
    }

    fn provider_id_for(
        &self,
        app_id: u32,
        explicit: Option<String>,
    ) -> String {
        explicit
            .or_else(|| {
                self.store
                    .load_profile(app_id)
                    .and_then(|profile| profile.provider_id)
            })
            .or_else(|| {
                let preferences = self.store.load_preferences();
                if preferences.default_provider.is_empty() {
                    None
                } else {
                    Some(preferences.default_provider)
                }
            })
            .unwrap_or_else(|| DEFAULT_PROVIDER.into())
    }

    async fn begin_session(
        &self,
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    ) -> Result<SessionRecord> {
        let (_, _, games, _) = context()?;
        let game = find_game(&games, app_id)
            .ok_or_else(|| anyhow::anyhow!("Steam AppID {app_id} is not installed"))?;

        let provider_id = self.provider_id_for(app_id, provider);
        self.providers.get(&provider_id)?;

        let mut session = SessionRecord::new(
            app_id,
            game.name.clone(),
            provider_id,
            trainer,
        );
        session.transition(
            SessionState::Preparing,
            "session queued; resolving provider and Steam/Proton context",
        );
        self.store.save_session(&session)?;
        self.log("info", "session.created", "managed session created", serde_json::json!({"session_id": session.id, "app_id": app_id, "provider": session.provider_id}));

        let session_id = session.id;
        let app = self.clone();
        tokio::spawn(async move {
            app.run_session(
                session_id,
                proton,
                launch_game,
                timeout_secs,
                args,
            )
            .await;
        });

        Ok(session)
    }

    async fn run_session(
        &self,
        id: Uuid,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    ) {
        let result: Result<()> = async {
            let mut session = self
                .store
                .load_session(id)
                .ok_or_else(|| anyhow::anyhow!("session {id} not found"))?;

            let (root, _, games, tools) = context()?;
            let game = find_game(&games, session.app_id)
                .ok_or_else(|| anyhow::anyhow!(
                    "Steam AppID {} is not installed",
                    session.app_id
                ))?;

            let provider_impl = self.providers.get(&session.provider_id)?;
            let descriptor = provider_impl.descriptor();

            let health = provider_impl.probe_game(&game);
            if !health.available {
                anyhow::bail!(
                    "provider {} is unavailable: {} — {}",
                    session.provider_id,
                    health.status,
                    health.details.join(" ")
                );
            }

            let preferred_proton = proton.or_else(|| {
                self.store
                    .load_profile(session.app_id)
                    .and_then(|profile| profile.preferred_proton)
            });

            let (selected, reason) =
                wand_steam::choose_proton(
                    &game,
                    &root,
                    &tools,
                    preferred_proton.as_deref(),
                )?;

            let selected = selected
                .ok_or_else(|| anyhow::anyhow!(
                    "could not resolve Proton: {reason}"
                ))?;

            let provider_runtime_note =
                if descriptor.capabilities.iter().any(|value| value == "proton-runinprefix") {
                    format!(
                        "provider {} ready; game-first mode will launch Steam normally, then join Wand to the active prefix with {} runinprefix",
                        session.provider_id,
                        selected.display_name
                    )
                } else if descriptor.capabilities.iter().any(|value| value == "single-proton-session") {
                    format!(
                        "provider {} ready; Wand Native will launch Wand and the game together inside one {} session without a Steam wrapper",
                        session.provider_id,
                        selected.display_name
                    )
                } else if descriptor.capabilities.iter().any(|value| value == "steam-command-wrapper") {
                    format!(
                        "provider {} ready; legacy Steam %command% wrapper mode",
                        session.provider_id
                    )
                } else if descriptor.capabilities.iter().any(|value| value == "system-wine") {
                    format!(
                        "provider {} ready; Wand uses system Wine in the game prefix; game remains on {}",
                        session.provider_id,
                        selected.display_name
                    )
                } else {
                    format!(
                        "provider {} ready; using {}",
                        session.provider_id,
                        selected.display_name
                    )
                };

            session.transition(
                SessionState::Preparing,
                provider_runtime_note,
            );
            self.store.save_session(&session)?;

            match descriptor.flow {
                ProviderFlow::AfterGame => {
                    let mut processes =
                        wand_runtime::process_probe_game(&game).candidates;

                    if !wand_runtime::likely_game_running_for_game(&game)
                        && launch_game
                    {
                        session.transition(
                            SessionState::LaunchingGame,
                            if descriptor.id == "wemod" {
                                "launching game normally through native Steam before starting Wand"
                            } else {
                                "launching game through Steam"
                            },
                        );
                        self.store.save_session(&session)?;
                        wand_runtime::launch_game(&game, false)?;

                        session.transition(
                            SessionState::WaitingForGame,
                            if descriptor.id == "wemod" {
                                "waiting for the actual game executable before joining Wand to the running Proton prefix"
                            } else {
                                "waiting for a positively identified Steam/Proton game process"
                            },
                        );
                        self.store.save_session(&session)?;

                        let deadline =
                            Instant::now() + Duration::from_secs(timeout_secs);

                        while !wand_runtime::likely_game_running_for_game(&game)
                            && Instant::now() < deadline
                        {
                            sleep(Duration::from_millis(500)).await;
                        }

                        processes =
                            wand_runtime::process_probe_game(&game).candidates;
                    }

                    if !wand_runtime::likely_game_running_for_game(&game) {
                        anyhow::bail!(
                            "no positively identified Steam/Proton game process detected"
                        );
                    }

                    session.game_processes = processes;
                    session.transition(
                        SessionState::GameDetected,
                        if descriptor.id == "wemod" {
                            "actual Steam/Proton game executable detected; waiting briefly for the Wine session to stabilize"
                        } else {
                            "Steam/Proton game process detected"
                        },
                    );
                    self.store.save_session(&session)?;

                    if descriptor.id == "wemod" {
                        // Do not join during the first instant of Proton game
                        // startup. The real-world Resonance test showed that
                        // starting Wand immediately can stall game initialization.
                        sleep(Duration::from_secs(8)).await;

                        let stable_probe =
                            wand_runtime::process_probe_game(&game);
                        if stable_probe.best_candidate_pid.is_none() {
                            anyhow::bail!(
                                "game process disappeared during the startup stabilization window"
                            );
                        }
                        session.game_processes = stable_probe.candidates;
                    }

                    session.transition(
                        SessionState::StartingTrainer,
                        if descriptor.id == "wemod" {
                            format!(
                                "joining Wand to the already-running {} Wine server with native renderer settings and DWriteCore compatibility",
                                selected.display_name
                            )
                        } else {
                            format!(
                                "starting provider {} after the game",
                                session.provider_id
                            )
                        },
                    );
                    self.store.save_session(&session)?;

                    let plan = provider_impl.prepare(
                        &root,
                        &game,
                        &selected,
                        &session.trainer,
                        &args,
                    )?;

                    session.trainer_pid =
                        provider_impl.launch(&plan, false)?;
                }

                ProviderFlow::InteractiveBeforeGame => {
                    let single_session_mode = descriptor
                        .capabilities
                        .iter()
                        .any(|value| value == "single-proton-session");

                    let exact_game_exe = if single_session_mode {
                        Some(wand_runtime::discover_game_executable(&game)?)
                    } else {
                        None
                    };

                    let initial_probe = if let Some(game_exe) = exact_game_exe.as_ref() {
                        wand_runtime::process_probe_exact_game(&game, game_exe)
                    } else {
                        wand_runtime::process_probe_game(&game)
                    };

                    if let Some(pid) = initial_probe.best_candidate_pid {
                        let blocker = initial_probe
                            .candidates
                            .iter()
                            .find(|process| process.pid == pid);
                        if let Some(process) = blocker {
                            anyhow::bail!(
                                "the actual game executable is already running (PID {}, {}, {}). Close it before starting the managed one-Proton-session Wand/game launch.",
                                process.pid,
                                process.comm,
                                process.windows_executable.as_deref().unwrap_or("unknown executable")
                            );
                        }
                        anyhow::bail!(
                            "the actual game executable is already running as PID {pid}. Close it before starting the managed one-Proton-session Wand/game launch."
                        );
                    }

                    if single_session_mode {
                        let stale_wand_pids =
                            wand_runtime::cleanup_wand_processes_for_game(&game)?;
                        if !stale_wand_pids.is_empty() {
                            session.transition(
                                SessionState::Preparing,
                                format!(
                                    "cleaned {} stale Wand/WeMod process(es) from this game prefix before starting the new one-Proton session: {:?}",
                                    stale_wand_pids.len(),
                                    stale_wand_pids
                                ),
                            );
                            self.store.save_session(&session)?;
                        }
                    }

                    let baseline_game_pids: std::collections::BTreeSet<u32> =
                        initial_probe
                            .candidates
                            .iter()
                            .filter(|process| {
                                process.role == wand_core::ProcessRole::GameCandidate
                                    && process.score >= 100
                            })
                            .map(|process| process.pid)
                            .collect();

                    let wrapper_mode = descriptor
                        .capabilities
                        .iter()
                        .any(|value| value == "steam-command-wrapper");

                    if single_session_mode {
                        session.transition(
                            SessionState::LaunchingGame,
                            format!(
                                "starting a clean Wand + game session inside one {}; Windows children receive Steam AppID identity and Steam Launch Options are not used",
                                selected.display_name
                            ),
                        );
                        self.store.save_session(&session)?;

                        let plan = provider_impl.prepare(
                            &root,
                            &game,
                            &selected,
                            &session.trainer,
                            &args,
                        )?;

                        session.trainer_pid = provider_impl.launch(&plan, false)?;
                        session.transition(
                            SessionState::WaitingForGame,
                            "one Proton session started; waiting for the real game executable while Wand initializes in the same Wine session",
                        );
                    } else if wrapper_mode {
                        session.trainer_pid = None;

                        if launch_game {
                            session.transition(
                                SessionState::LaunchingGame,
                                "launching native Steam; the configured Wand Steam wrapper must intercept %command% and start Wand plus the game inside one Proton invocation",
                            );
                            self.store.save_session(&session)?;

                            wand_runtime::launch_game(&game, false)?;

                            session.transition(
                                SessionState::WaitingForGame,
                                "Steam launch requested. Waiting for the real game executable from the same wrapped Proton command; Wand should open from the wrapper automatically.",
                            );
                        } else {
                            session.transition(
                                SessionState::WaitingForGame,
                                "Steam wrapper mode is ready. Launch this game from native Steam; the configured launch option will start Wand and the game together.",
                            );
                        }
                    } else {
                        session.transition(
                            SessionState::StartingTrainer,
                            format!(
                                "starting provider {} before the game",
                                session.provider_id
                            ),
                        );
                        self.store.save_session(&session)?;

                        let plan = provider_impl.prepare(
                            &root,
                            &game,
                            &selected,
                            &session.trainer,
                            &args,
                        )?;

                        session.trainer_pid =
                            provider_impl.launch(&plan, false)?;

                        session.transition(
                            SessionState::WaitingForGame,
                            "provider started; waiting for the real game executable",
                        );
                    }

                    self.store.save_session(&session)?;

                    let interactive_timeout = timeout_secs.max(600);
                    let deadline =
                        Instant::now() + Duration::from_secs(interactive_timeout);

                    let mut detected_probe = None;

                    while Instant::now() < deadline {
                        let probe = if let Some(game_exe) = exact_game_exe.as_ref() {
                            wand_runtime::process_probe_exact_game(&game, game_exe)
                        } else {
                            wand_runtime::process_probe_game(&game)
                        };
                        let has_new_game = probe.candidates.iter().any(|process| {
                            process.role == wand_core::ProcessRole::GameCandidate
                                && process.score >= 100
                                && !baseline_game_pids.contains(&process.pid)
                        });

                        if has_new_game {
                            detected_probe = Some(probe);
                            break;
                        }

                        sleep(Duration::from_millis(500)).await;
                    }

                    let detected_probe = detected_probe.ok_or_else(|| {
                        anyhow::anyhow!(
                            "timed out waiting for the game after {} seconds. No new positively identified game executable appeared.",
                            interactive_timeout
                        )
                    })?;

                    session.game_processes = detected_probe.candidates;

                    session.transition(
                        SessionState::GameDetected,
                        if single_session_mode {
                            "game executable detected from the same direct Proton session as Wand; no Steam wrapper was used"
                        } else if wrapper_mode {
                            "game executable detected from wrapped Steam/Proton launch; Wand and the game now share one Proton context"
                        } else {
                            "game executable detected after provider prelaunch"
                        },
                    );
                    self.store.save_session(&session)?;
                }
            }

            session.transition(
                SessionState::Running,
                if descriptor.id == "wemod" {
                    "game and Wand are running; activate the trainer/mods from Wand"
                } else {
                    "provider session active"
                },
            );
            self.store.save_session(&session)?;

            self.log(
                "info",
                "session.running",
                "trainer session reached running state",
                serde_json::json!({
                    "session_id": session.id,
                    "app_id": session.app_id,
                    "provider": session.provider_id,
                    "provider_pid": session.trainer_pid,
                }),
            );

            self.active.lock().await.push(session.id);

            let monitor = self.clone();
            tokio::spawn(async move {
                monitor.monitor_session(id).await;
            });

            Ok(())
        }
        .await;

        if let Err(error) = result {
            if let Some(mut session) = self.store.load_session(id) {
                session.fail(format!("{error:#}"));
                let _ = self.store.save_session(&session);
                self.log(
                    "error",
                    "session.failed",
                    "managed session failed",
                    serde_json::json!({
                        "session_id": id,
                        "app_id": session.app_id,
                        "provider": session.provider_id,
                        "error": format!("{error:#}"),
                    }),
                );
            }
            self.active.lock().await.retain(|value| *value != id);
        }
    }

    async fn start_session(
        &self,
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    ) -> Result<SessionRecord> {
        let initial = self
            .begin_session(
                app_id,
                trainer,
                provider,
                proton,
                launch_game,
                timeout_secs,
                args,
            )
            .await?;

        loop {
            let session = self
                .store
                .load_session(initial.id)
                .ok_or_else(|| anyhow::anyhow!(
                    "session {} disappeared",
                    initial.id
                ))?;

            if matches!(
                session.state,
                SessionState::Running
                    | SessionState::Stopped
                    | SessionState::Failed
            ) {
                return Ok(session);
            }

            sleep(Duration::from_millis(250)).await;
        }
    }

    async fn monitor_session(&self, id: Uuid) {
        loop {
            sleep(Duration::from_secs(1)).await;

            let Some(mut session) = self.store.load_session(id) else {
                self.active.lock().await.retain(|value| *value != id);
                return;
            };

            if session.state != SessionState::Running {
                self.active.lock().await.retain(|value| *value != id);
                return;
            }

            let game_alive = session
                .game_processes
                .iter()
                .filter(|process| {
                    process.role == wand_core::ProcessRole::GameCandidate
                        && process.score >= 100
                })
                .any(|process| wand_runtime::process_alive(process.pid));
            let trainer_alive = session
                .trainer_pid
                .map(wand_runtime::process_alive)
                .unwrap_or(false);

            let provider = match self.providers.get(&session.provider_id) {
                Ok(provider) => provider,
                Err(_) => {
                    session.fail(format!(
                        "provider {} is no longer registered",
                        session.provider_id
                    ));
                    let _ = self.store.save_session(&session);
                    self.active.lock().await.retain(|value| *value != id);
                    return;
                }
            };
            let descriptor = provider.descriptor();

            if descriptor.requires_provider_pid_alive && !trainer_alive {
                session.transition(
                    SessionState::Stopped,
                    "provider launch process exited",
                );
                let _ = self.store.save_session(&session);
                self.active.lock().await.retain(|value| *value != id);
                return;
            }

            if !game_alive {
                if let Some(pid) = session.trainer_pid {
                    let _ = provider.stop(pid);
                }

                session.transition(
                    SessionState::Stopped,
                    "game exited; Wand stopped the provider process it owns",
                );
                let _ = self.store.save_session(&session);
                self.active.lock().await.retain(|value| *value != id);
                return;
            }
        }
    }

    async fn stop_session(&self, id: Uuid) -> Result<SessionRecord> {
        let mut session = self
            .store
            .load_session(id)
            .ok_or_else(|| anyhow::anyhow!("session {id} not found"))?;

        session.transition(
            SessionState::Stopping,
            "stopping Wand-owned provider process",
        );
        self.store.save_session(&session)?;

        if let Some(pid) = session.trainer_pid {
            let provider = self.providers.get(&session.provider_id)?;
            if let Err(error) = provider.stop(pid) {
                session.fail(format!(
                    "failed to stop provider process PID {pid}: {error:#}"
                ));
                self.store.save_session(&session)?;
                return Ok(session);
            }
        }

        session.transition(SessionState::Stopped, "session stopped");
        self.store.save_session(&session)?;
        self.active.lock().await.retain(|value| *value != id);
        Ok(session)
    }

    async fn reconcile_sessions(&self) -> Result<Vec<SessionRecord>> {
        let mut changed = Vec::new();
        let sessions = self.store.load_sessions()?;
        let mut active_ids = Vec::new();

        for mut session in sessions {
            if !matches!(
                session.state,
                SessionState::Running
                    | SessionState::StartingTrainer
                    | SessionState::GameDetected
                    | SessionState::WaitingForGame
                    | SessionState::LaunchingGame
            ) {
                continue;
            }

            let game_alive = context()
                .ok()
                .and_then(|(_, _, games, _)| {
                    find_game(&games, session.app_id)
                        .map(|game| wand_runtime::likely_game_running_for_game(&game))
                })
                .unwrap_or_else(|| {
                    session
                        .game_processes
                        .iter()
                        .filter(|process| {
                            process.role == wand_core::ProcessRole::GameCandidate
                                && process.score >= 100
                        })
                        .any(|process| wand_runtime::process_alive(process.pid))
                });
            let trainer_alive = session
                .trainer_pid
                .map(wand_runtime::process_alive)
                .unwrap_or(false);

            let requires_provider_pid_alive = self
                .providers
                .get(&session.provider_id)
                .map(|provider| provider.descriptor().requires_provider_pid_alive)
                .unwrap_or(true);

            if game_alive
                && (trainer_alive || !requires_provider_pid_alive)
            {
                session.transition(
                    SessionState::Running,
                    if trainer_alive {
                        "daemon restart reconciliation: game and provider launch process are still running"
                    } else {
                        "daemon restart reconciliation: game is running; provider does not require its original launch PID to remain alive"
                    },
                );
                active_ids.push(session.id);
            } else if game_alive {
                session.transition(
                    SessionState::Stopped,
                    "daemon restart reconciliation: game is running but required provider process is no longer alive",
                );
            } else if trainer_alive {
                session.transition(
                    SessionState::Running,
                    "daemon restart reconciliation: provider launch process is alive but game is not currently visible",
                );
                active_ids.push(session.id);
            } else {
                session.transition(
                    SessionState::Stopped,
                    "daemon restart reconciliation: game and provider launch process have exited",
                );
            }

            self.store.save_session(&session)?;
            changed.push(session);
        }

        *self.active.lock().await = active_ids.clone();

        for id in active_ids {
            let monitor = self.clone();
            tokio::spawn(async move {
                monitor.monitor_session(id).await;
            });
        }

        Ok(changed)
    }

    async fn watch_session(
        &self,
        id: Uuid,
        after: usize,
        timeout_secs: u64,
    ) -> Result<SessionEventBatch> {
        let deadline = Instant::now() + Duration::from_secs(timeout_secs.min(60));

        loop {
            let session = self
                .store
                .load_session(id)
                .ok_or_else(|| anyhow::anyhow!("session {id} not found"))?;

            if session.events.len() > after || Instant::now() >= deadline {
                let start = after.min(session.events.len());
                return Ok(SessionEventBatch {
                    session_id: id,
                    state: session.state,
                    events: session.events[start..].to_vec(),
                    next_index: session.events.len(),
                });
            }

            sleep(Duration::from_millis(250)).await;
        }
    }

    fn export_diagnostics_archive(
        &self,
        id: Uuid,
        destination: PathBuf,
    ) -> Result<PathBuf> {
        let session = self
            .store
            .load_session(id)
            .ok_or_else(|| anyhow::anyhow!("session {id} not found"))?;

        fs::create_dir_all(&destination)?;
        let archive_path = destination.join(format!("wand-diagnostics-{id}.tar.zst"));

        let file = fs::File::create(&archive_path)?;
        let encoder = zstd::stream::write::Encoder::new(file, 6)?;
        let mut tar = TarBuilder::new(encoder);

        append_tar_bytes(
            &mut tar,
            "session.json",
            &serde_json::to_vec_pretty(&session)?,
        )?;

        let (root, libraries, games, tools) = context()?;
        append_tar_bytes(
            &mut tar,
            "steam-root.txt",
            root.display().to_string().as_bytes(),
        )?;
        append_tar_bytes(
            &mut tar,
            "libraries.json",
            &serde_json::to_vec_pretty(&libraries)?,
        )?;
        append_tar_bytes(
            &mut tar,
            "games.json",
            &serde_json::to_vec_pretty(&games)?,
        )?;
        append_tar_bytes(
            &mut tar,
            "protons.json",
            &serde_json::to_vec_pretty(&tools)?,
        )?;
        append_tar_bytes(
            &mut tar,
            "providers.json",
            &serde_json::to_vec_pretty(&self.providers.descriptors())?,
        )?;
        append_tar_bytes(
            &mut tar,
            "provider-health.json",
            &serde_json::to_vec_pretty(&self.providers.health(None, None)?)?,
        )?;
        append_tar_bytes(
            &mut tar,
            "preferences.json",
            &serde_json::to_vec_pretty(&self.store.load_preferences())?,
        )?;
        let current_processes = find_game(&games, session.app_id)
            .map(|game| wand_runtime::process_probe_game(&game))
            .unwrap_or_else(|| wand_runtime::process_probe(session.app_id));
        append_tar_bytes(
            &mut tar,
            "current-processes.json",
            &serde_json::to_vec_pretty(&current_processes)?,
        )?;

        if let Some(profile) = self.store.load_profile(session.app_id) {
            append_tar_bytes(
                &mut tar,
                "profile.json",
                &serde_json::to_vec_pretty(&profile)?,
            )?;
        }

        let daemon_log = self.store.root().join("wandd.jsonl");
        if daemon_log.is_file() {
            append_tar_bytes(
                &mut tar,
                "wandd.jsonl",
                &fs::read(&daemon_log)?,
            )?;
        }

        let encoder = tar.into_inner()?;
        encoder.finish()?;
        Ok(archive_path)
    }

    async fn handle(&self, req: Request) -> Response {
        let result: Result<Response> = async {
            match req {
                Request::Ping => Ok(Response::message("pong")),


                Request::Status => {
                    let steam_root = wand_steam::primary_steam_root().ok();
                    let (game_count, provider_count) = if let Some(root) = &steam_root {
                        let libraries = wand_steam::discover_libraries(root)?;
                        let games = wand_steam::discover_games(&libraries)?;
                        (games.len(), self.providers.descriptors().len())
                    } else {
                        (0, self.providers.descriptors().len())
                    };

                    Ok(Response::ok(DaemonStatus {
                        version: env!("CARGO_PKG_VERSION").into(),
                        steam_root,
                        game_count,
                        provider_count,
                        persisted_session_count: self.store.load_sessions()?.len(),
                        onboarding_complete: self.store.load_preferences().onboarding_complete,
                    }))
                }

                Request::Games => {
                    let (_, _, games, _) = context()?;
                    Ok(Response::ok(games))
                }

                Request::Protons => {
                    let (root, libraries, _, _) = context()?;
                    Ok(Response::ok(
                        wand_steam::discover_proton_tools(&root, &libraries)?,
                    ))
                }

                Request::Providers => {
                    Ok(Response::ok(self.providers.descriptors()))
                }

                Request::ProviderSources { provider } => {
                    let (_, _, games, _) = context()?;
                    let provider = self.providers.get(&provider)?;
                    Ok(Response::ok(provider.discover_sources(&games)?))
                }

                Request::ImportProviderRuntime {
                    provider,
                    app_id,
                    source,
                    replace,
                } => {
                    let (_, _, games, _) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;

                    let provider_impl = self.providers.get(&provider)?;
                    let result = provider_impl.import_runtime(
                        &game,
                        &source,
                        replace,
                    )?;

                    self.log(
                        "info",
                        "provider.runtime_imported",
                        "provider runtime imported into game prefix",
                        serde_json::json!({
                            "provider": provider,
                            "app_id": app_id,
                            "source": source,
                            "copied_paths": &result.copied_paths,
                        }),
                    );

                    Ok(Response::ok(result))
                }

                Request::BootstrapProviderRuntime {
                    provider,
                    app_id,
                    installer,
                    proton,
                    graphical_environment,
                    args,
                } => {
                    let (root, _, games, tools) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;

                    if wand_runtime::likely_game_running(app_id) {
                        anyhow::bail!(
                            "Steam AppID {app_id} appears to be running. Close the game before installing the WeMod/Wand runtime into its prefix."
                        );
                    }

                    let profile = self.store.load_profile(app_id);
                    let preferred = proton.or_else(|| {
                        profile.and_then(|value| value.preferred_proton)
                    });

                    let (selected, reason) = wand_steam::choose_proton(
                        &game,
                        &root,
                        &tools,
                        preferred.as_deref(),
                    )?;

                    let selected = selected.ok_or_else(|| {
                        anyhow::anyhow!(
                            "could not resolve Proton for bootstrap: {reason}"
                        )
                    })?;

                    let provider_impl = self.providers.get(&provider)?;
                    let mut plan = provider_impl.prepare_bootstrap(
                        &root,
                        &game,
                        &selected,
                        &installer,
                        &args,
                    )?;

                    for pair in sanitize_graphical_environment(
                        graphical_environment,
                    ) {
                        if !plan
                            .environment
                            .iter()
                            .any(|(key, _)| key == &pair.0)
                        {
                            plan.environment.push(pair);
                        }
                    }

                    let launch_pid = provider_impl.launch(&plan, false)?;
                    let health_after_launch = provider_impl.probe_game(&game);

                    self.log(
                        "info",
                        "provider.bootstrap_started",
                        "provider runtime installer launched",
                        serde_json::json!({
                            "provider": &provider,
                            "app_id": app_id,
                            "installer": &installer,
                            "proton": &selected.tool_id,
                            "launch_pid": launch_pid,
                            "initial_health": &health_after_launch.status,
                        }),
                    );

                    Ok(Response::ok(ProviderBootstrapResult {
                        provider_id: provider,
                        app_id,
                        installer: plan.trainer,
                        proton: selected,
                        launch_pid,
                        health_after_launch,
                    }))
                }

                Request::ProviderHealth { provider, app_id } => {
                    let game = if let Some(app_id) = app_id {
                        let (_, _, games, _) = context()?;
                        Some(
                            find_game(&games, app_id)
                                .ok_or_else(|| anyhow::anyhow!(
                                    "Steam AppID {app_id} is not installed"
                                ))?
                        )
                    } else {
                        None
                    };

                    Ok(Response::ok(
                        self.providers.health(
                            provider.as_deref(),
                            game.as_ref(),
                        )?,
                    ))
                }

                Request::Processes { app_id } => {
                    let (_, _, games, _) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;
                    Ok(Response::ok(wand_runtime::process_probe_game(&game)))
                }

                Request::Preferences => {
                    Ok(Response::ok(self.store.load_preferences()))
                }

                Request::SetPreferences { preferences } => {
                    self.providers.get(&preferences.default_provider)?;
                    self.store.save_preferences(&preferences)?;
                    self.log(
                        "info",
                        "preferences.saved",
                        "Wand preferences saved",
                        serde_json::json!({
                            "onboarding_complete": preferences.onboarding_complete,
                            "default_provider": preferences.default_provider,
                            "launch_game_automatically": preferences.launch_game_automatically,
                        }),
                    );
                    Ok(Response::ok(preferences))
                }

                Request::Logs { lines } => {
                    Ok(Response::ok(self.store.tail_logs(lines)?))
                }

                Request::Inspect { app_id, proton } => {
                    let (root, _, games, tools) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;

                    let profile = self.store.load_profile(app_id);
                    let preferred = proton.or_else(|| {
                        profile
                            .as_ref()
                            .and_then(|value| value.preferred_proton.clone())
                    });

                    let (selected, reason) =
                        wand_steam::choose_proton(
                            &game,
                            &root,
                            &tools,
                            preferred.as_deref(),
                        )?;

                    Ok(Response::ok(InspectResult {
                        game,
                        proton: selected,
                        proton_reason: reason,
                        running_processes: wand_runtime::process_probe(app_id).candidates,
                        profile,
                    }))
                }

                Request::LaunchGame { app_id, dry_run } => {
                    let (_, _, games, _) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;
                    Ok(Response::ok(
                        wand_runtime::launch_game(&game, dry_run)?,
                    ))
                }

                Request::RunTrainer {
                    app_id,
                    trainer,
                    provider,
                    proton,
                    dry_run,
                    force,
                    args,
                } => {
                    let (root, _, games, tools) = context()?;
                    let game = find_game(&games, app_id)
                        .ok_or_else(|| anyhow::anyhow!(
                            "Steam AppID {app_id} is not installed"
                        ))?;

                    if !force && !wand_runtime::likely_game_running(app_id) {
                        anyhow::bail!(
                            "no running Steam/Proton session detected for AppID {app_id}"
                        );
                    }

                    let profile = self.store.load_profile(app_id);
                    let provider_id = provider
                        .or_else(|| {
                            profile
                                .as_ref()
                                .and_then(|value| value.provider_id.clone())
                        })
                        .unwrap_or_else(|| DEFAULT_PROVIDER.into());

                    let preferred = proton.or_else(|| {
                        profile.and_then(|value| value.preferred_proton)
                    });

                    let (selected, reason) =
                        wand_steam::choose_proton(
                            &game,
                            &root,
                            &tools,
                            preferred.as_deref(),
                        )?;
                    let selected = selected.ok_or_else(|| {
                        anyhow::anyhow!("could not resolve Proton: {reason}")
                    })?;

                    let provider_impl = self.providers.get(&provider_id)?;
                    let plan = provider_impl.prepare(
                        &root,
                        &game,
                        &selected,
                        &trainer,
                        &args,
                    )?;
                    let pid = provider_impl.launch(&plan, dry_run)?;

                    Ok(Response::ok(serde_json::json!({
                        "provider": provider_id,
                        "pid": pid,
                        "plan": plan,
                        "dry_run": dry_run
                    })))
                }

                Request::StartSession {
                    app_id,
                    trainer,
                    provider,
                    proton,
                    launch_game,
                    timeout_secs,
                    args,
                } => Ok(Response::ok(
                    self.start_session(
                        app_id,
                        trainer,
                        provider,
                        proton,
                        launch_game,
                        timeout_secs,
                        args,
                    )
                    .await?,
                )),

                Request::BeginSession {
                    app_id,
                    trainer,
                    provider,
                    proton,
                    launch_game,
                    timeout_secs,
                    args,
                } => Ok(Response::ok(
                    self.begin_session(
                        app_id,
                        trainer,
                        provider,
                        proton,
                        launch_game,
                        timeout_secs,
                        args,
                    )
                    .await?,
                )),

                Request::Sessions => {
                    Ok(Response::ok(self.store.load_sessions()?))
                }

                Request::Session { id } => {
                    Ok(Response::ok(
                        self.store
                            .load_session(id)
                            .ok_or_else(|| anyhow::anyhow!(
                                "session {id} not found"
                            ))?,
                    ))
                }

                Request::WatchSession {
                    id,
                    after,
                    timeout_secs,
                } => Ok(Response::ok(
                    self.watch_session(id, after, timeout_secs).await?,
                )),

                Request::StopSession { id } => {
                    Ok(Response::ok(self.stop_session(id).await?))
                }

                Request::ReconcileSessions => {
                    Ok(Response::ok(self.reconcile_sessions().await?))
                }

                Request::SetProfile { profile } => {
                    if let Some(provider) = &profile.provider_id {
                        self.providers.get(provider)?;
                    }
                    self.store.save_profile(&profile)?;
                    Ok(Response::ok(profile))
                }

                Request::Profiles => {
                    Ok(Response::ok(self.store.load_profiles()?))
                }

                Request::ExportDiagnostics { id, destination } => {
                    Ok(Response::ok(
                        self.export_diagnostics_archive(id, destination)?,
                    ))
                }
            }
        }
        .await;

        match result {
            Ok(value) => value,
            Err(error) => Response::error(format!("{error:#}")),
        }
    }
}

async fn serve_client(stream: UnixStream, app: App) -> Result<()> {
    let (reader, mut writer) = stream.into_split();
    let mut lines = BufReader::new(reader).lines();

    while let Some(line) = lines.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }

        let response = match serde_json::from_str::<Request>(&line) {
            Ok(request) => app.handle(request).await,
            Err(error) => Response::error(format!(
                "invalid request: {error}"
            )),
        };

        let mut bytes = serde_json::to_vec(&response)?;
        bytes.push(b'\n');
        writer.write_all(&bytes).await?;
        writer.flush().await?;
    }

    Ok(())
}

/// Ensure socket setup cannot change another owner's directory or unlink
/// a live daemon. Caller binds under a restrictive umask after this check.
fn prepare_socket(path: &Path) -> Result<()> {
    use anyhow::{bail, Context};

    if !path.is_absolute() {
        bail!("daemon socket path must be absolute");
    }
    let parent = path.parent().context("socket path has no parent")?;
    // DirBuilder sets 0700 at creation, not by chmod'ing an existing dir.
    // Existing 0775/0777 parents are intentionally rejected.
    if !parent.exists() {
        fs::DirBuilder::new().recursive(true).mode(0o700).create(parent)?;
    }
    let directory = fs::symlink_metadata(parent)?;
    if directory.file_type().is_symlink() || !directory.is_dir() {
        bail!("socket parent is a symlink or not a directory: {}", parent.display());
    }
    if directory.uid() != unsafe { libc::geteuid() } {
        bail!("socket parent is not owned by this user: {}", parent.display());
    }
    if directory.permissions().mode() & 0o077 != 0 {
        bail!("socket parent must be private (0700); refusing to chmod {}", parent.display());
    }
    match fs::symlink_metadata(path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(err) => return Err(err).context("inspecting existing daemon socket"),
        Ok(existing) => {
            if existing.file_type().is_symlink() || !existing.file_type().is_socket() {
                bail!("refusing to remove a non-socket or symlink: {}", path.display());
            }
            if existing.uid() != unsafe { libc::geteuid() } {
                bail!("refusing another user's socket: {}", path.display());
            }
            // An established listener proves the socket is live; never unlink.
            match std::os::unix::net::UnixStream::connect(path) {
                Ok(_) => bail!("a daemon is already listening at {}", path.display()),
                Err(err) if err.kind() == std::io::ErrorKind::ConnectionRefused => {
                    fs::remove_file(path).context("removing stale daemon socket")?;
                }
                Err(err) => {
                    return Err(err).context(
                        "cannot safely determine whether existing socket is in use");
                }
            }
        }
    }
    Ok(())
}

/// Umask is process-wide, so change it only for this startup bind and
/// restore it immediately even when bind fails.
struct SocketBindUmask(libc::mode_t);
impl SocketBindUmask {
    fn private() -> Self { Self(unsafe { libc::umask(0o177) }) }
}
impl Drop for SocketBindUmask {
    fn drop(&mut self) { unsafe { libc::umask(self.0); } }
}

#[cfg(test)]
mod socket_tests {
    use super::*;
    use std::os::unix::net::UnixListener as StdUnixListener;

    fn root() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("wand-socket-test-{}", Uuid::new_v4()));
        fs::DirBuilder::new().mode(0o700).create(&dir).unwrap();
        dir
    }

    #[test]
    fn private_parent_created_without_changing_ancestors() {
        let dir = root();
        let parent = dir.join("daemon");
        let socket = parent.join("wand.sock");
        prepare_socket(&socket).unwrap();
        assert!(parent.is_dir());
        assert_eq!(fs::metadata(parent).unwrap().permissions().mode() & 0o777, 0o700);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn existing_non_socket_is_never_deleted() {
        let dir = root();
        let socket = dir.join("wand.sock");
        fs::write(&socket, b"unrelated").unwrap();
        assert!(prepare_socket(&socket).is_err());
        assert_eq!(fs::read(&socket).unwrap(), b"unrelated");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn live_socket_remains_and_stale_socket_is_removed() {
        let dir = root();
        let socket = dir.join("wand.sock");
        let listener = StdUnixListener::bind(&socket).unwrap();
        assert!(prepare_socket(&socket).is_err());
        assert!(socket.exists());
        drop(listener);
        prepare_socket(&socket).unwrap();
        assert!(!socket.exists());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn existing_group_writable_directory_not_chmoded() {
        let dir = root();
        let parent = dir.join("shared");
        fs::create_dir(&parent).unwrap();
        fs::set_permissions(&parent, fs::Permissions::from_mode(0o775)).unwrap();
        assert!(prepare_socket(&parent.join("wand.sock")).is_err());
        assert_eq!(fs::metadata(&parent).unwrap().permissions().mode() & 0o777, 0o775);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn symlinked_socket_parent_is_refused() {
        let dir = root();
        let real = dir.join("real");
        fs::create_dir(&real).unwrap();
        let link = dir.join("alias");
        std::os::unix::fs::symlink(&real, &link).unwrap();
        assert!(prepare_socket(&link.join("wand.sock")).is_err());
        fs::remove_dir_all(dir).unwrap();
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let socket = socket_path();
    prepare_socket(&socket)?;

    let permissions_guard = SocketBindUmask::private();
    let listener = UnixListener::bind(&socket)
        .with_context(|| format!("binding {}", socket.display()))?;
    drop(permissions_guard);
    fs::set_permissions(
        &socket,
        fs::Permissions::from_mode(0o600),
    )?;

    let mut registry = ProviderRegistry::new();
    registry.register(GenericExeProvider);
    registry.register(WeModProvider);

    let app = App {
        store: StateStore::default()?,
        active: Arc::new(Mutex::new(Vec::new())),
        providers: Arc::new(registry),
    };

    eprintln!("wandd 0.1.15 listening on {}", socket.display());
    eprintln!("state: {}", app.store.root().display());
    app.log("info", "daemon.started", "wandd started", serde_json::json!({"version": env!("CARGO_PKG_VERSION"), "socket": socket}));

    let reconciled = app.reconcile_sessions().await?;
    if !reconciled.is_empty() {
        eprintln!(
            "reconciled {} persisted session(s)",
            reconciled.len()
        );
    }

    loop {
        let (stream, _) = listener.accept().await?;
        let app = app.clone();
        tokio::spawn(async move {
            if let Err(error) = serve_client(stream, app).await {
                eprintln!("client error: {error:#}");
            }
        });
    }
}
