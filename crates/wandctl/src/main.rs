use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::{path::PathBuf, process::Command as ProcessCommand};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;
use uuid::Uuid;
use wand_core::{GameProfile, Preferences, Request, Response};

#[derive(Debug, Parser)]
#[command(name = "wandctl", version, about = "Wand Native control utility")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}


#[derive(Debug, Subcommand)]
enum ProtonCommand {
    /// Create or refresh the Wand-compatible Proton tool.
    Install,
    /// Show where the Wand-compatible Proton tool is installed.
    Status,
    /// Verify the patched crypt32 payload and Steam manifest.
    Verify,
    /// Remove the generated Wand-compatible Proton tool.
    Remove,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// One-command setup for the Wand-compatible Proton tool.
    Setup,
    /// Manage the Wand-compatible Proton tool locally (wandd is not required).
    Proton {
        #[command(subcommand)]
        command: ProtonCommand,
    },
    /// Check the newest Tophat telemetry for TrainerLib health.
    TrainerHealth {
        /// Optional Steam AppID. If omitted, use the newest Wand Tophat trace found.
        app_id: Option<u32>,
    },
    Ping,
    Status,
    Games,
    Protons,
    Providers,
    ProviderHealth { #[arg(long)] provider: Option<String>, #[arg(long)] app_id: Option<u32> },
    ProviderSources { provider: String },
    ImportProviderRuntime {
        provider: String,
        app_id: u32,
        source: PathBuf,
        #[arg(long)]
        replace: bool,
    },
    BootstrapProviderRuntime {
        provider: String,
        app_id: u32,
        installer: PathBuf,
        #[arg(long)]
        proton: Option<String>,
        #[arg(last = true)]
        args: Vec<String>,
    },
    Processes { app_id: u32 },
    Preferences,
    SetPreferences {
        #[arg(long, default_value = "generic-exe")] default_provider: String,
        #[arg(long, default_value_t = true)] launch_game_automatically: bool,
        #[arg(long)] diagnostics_directory: Option<PathBuf>,
        #[arg(long)] onboarding_complete: bool,
    },
    Logs { #[arg(long, default_value_t = 100)] lines: usize },
    Inspect {
        app_id: u32,
        #[arg(long)]
        proton: Option<String>,
    },
    LaunchGame {
        app_id: u32,
        #[arg(long)]
        dry_run: bool,
    },
    RunTrainer {
        app_id: u32,
        trainer: PathBuf,
        #[arg(long)]
        provider: Option<String>,
        #[arg(long)]
        proton: Option<String>,
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        force: bool,
        #[arg(last = true)]
        args: Vec<String>,
    },
    StartSession {
        app_id: u32,
        trainer: PathBuf,
        #[arg(long)]
        provider: Option<String>,
        #[arg(long)]
        proton: Option<String>,
        #[arg(long)]
        no_launch_game: bool,
        #[arg(long, default_value_t = 120)]
        timeout_secs: u64,
        #[arg(last = true)]
        args: Vec<String>,
    },
    BeginSession {
        app_id: u32,
        trainer: PathBuf,
        #[arg(long)]
        provider: Option<String>,
        #[arg(long)]
        proton: Option<String>,
        #[arg(long)]
        no_launch_game: bool,
        #[arg(long, default_value_t = 120)]
        timeout_secs: u64,
        #[arg(last = true)]
        args: Vec<String>,
    },
    Sessions,
    Session {
        id: Uuid,
    },
    WatchSession {
        id: Uuid,
        #[arg(long, default_value_t = 0)]
        after: usize,
        #[arg(long, default_value_t = 30)]
        timeout_secs: u64,
    },
    StopSession {
        id: Uuid,
    },
    Reconcile,
    SetProfile {
        app_id: u32,
        #[arg(long)]
        provider: Option<String>,
        #[arg(long)]
        proton: Option<String>,
        #[arg(long)]
        trainer: Option<PathBuf>,
        #[arg(long)]
        auto_launch_trainer: bool,
        #[arg(last = true)]
        trainer_args: Vec<String>,
    },
    Profiles,
    ExportDiagnostics {
        id: Uuid,
        destination: PathBuf,
    },
}

fn graphical_session_environment() -> Vec<(String, String)> {
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

    ALLOWED
        .iter()
        .filter_map(|key| {
            std::env::var(key)
                .ok()
                .map(|value| ((*key).to_string(), value))
        })
        .collect()
}

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

fn request(command: Command) -> Request {
    match command {
        Command::Setup | Command::Proton { .. } | Command::TrainerHealth { .. } => {
            unreachable!("local wandctl command passed to wandd request mapper")
        }
        Command::Ping => Request::Ping,
        Command::Status => Request::Status,
        Command::Games => Request::Games,
        Command::Protons => Request::Protons,
        Command::Providers => Request::Providers,
        Command::ProviderHealth { provider, app_id } => {
            Request::ProviderHealth { provider, app_id }
        }
        Command::ProviderSources { provider } => {
            Request::ProviderSources { provider }
        }
        Command::ImportProviderRuntime {
            provider,
            app_id,
            source,
            replace,
        } => Request::ImportProviderRuntime {
            provider,
            app_id,
            source,
            replace,
        },
        Command::BootstrapProviderRuntime {
            provider,
            app_id,
            installer,
            proton,
            args,
        } => Request::BootstrapProviderRuntime {
            provider,
            app_id,
            installer,
            proton,
            graphical_environment: graphical_session_environment(),
            args,
        },
        Command::Processes { app_id } => Request::Processes { app_id },
        Command::Preferences => Request::Preferences,
        Command::SetPreferences {
            default_provider,
            launch_game_automatically,
            diagnostics_directory,
            onboarding_complete,
        } => Request::SetPreferences {
            preferences: Preferences {
                onboarding_complete,
                default_provider,
                launch_game_automatically,
                diagnostics_directory,
            },
        },
        Command::Logs { lines } => Request::Logs { lines },
        Command::Inspect { app_id, proton } => {
            Request::Inspect { app_id, proton }
        }
        Command::LaunchGame { app_id, dry_run } => {
            Request::LaunchGame { app_id, dry_run }
        }
        Command::RunTrainer {
            app_id,
            trainer,
            provider,
            proton,
            dry_run,
            force,
            args,
        } => Request::RunTrainer {
            app_id,
            trainer,
            provider,
            proton,
            dry_run,
            force,
            args,
        },
        Command::StartSession {
            app_id,
            trainer,
            provider,
            proton,
            no_launch_game,
            timeout_secs,
            args,
        } => Request::StartSession {
            app_id,
            trainer,
            provider,
            proton,
            launch_game: !no_launch_game,
            timeout_secs,
            args,
        },
        Command::BeginSession {
            app_id,
            trainer,
            provider,
            proton,
            no_launch_game,
            timeout_secs,
            args,
        } => Request::BeginSession {
            app_id,
            trainer,
            provider,
            proton,
            launch_game: !no_launch_game,
            timeout_secs,
            args,
        },
        Command::Sessions => Request::Sessions,
        Command::Session { id } => Request::Session { id },
        Command::WatchSession {
            id,
            after,
            timeout_secs,
        } => Request::WatchSession {
            id,
            after,
            timeout_secs,
        },
        Command::StopSession { id } => {
            Request::StopSession { id }
        }
        Command::Reconcile => Request::ReconcileSessions,
        Command::SetProfile {
            app_id,
            provider,
            proton,
            trainer,
            auto_launch_trainer,
            trainer_args,
        } => Request::SetProfile {
            profile: GameProfile {
                app_id,
                provider_id: provider,
                preferred_proton: proton,
                trainer,
                trainer_args,
                auto_launch_trainer,
            },
        },
        Command::Profiles => Request::Profiles,
        Command::ExportDiagnostics { id, destination } => {
            Request::ExportDiagnostics { id, destination }
        }
    }
}

fn data_home() -> PathBuf {
    std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
                .join(".local/share")
        })
        .join("wand-native")
}

fn local_script(name: &str) -> Result<PathBuf> {
    if let Some(root) = std::env::var_os("WAND_NATIVE_ROOT") {
        let appimage = PathBuf::from(root).join("scripts").join(name);
        if appimage.is_file() {
            return Ok(appimage);
        }
    }
    let installed = data_home().join("scripts").join(name);
    if installed.is_file() {
        return Ok(installed);
    }

    let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("scripts")
        .join(name);
    if source.is_file() {
        return Ok(source);
    }

    anyhow::bail!(
        "Wand Native helper script '{}' is not installed. Run ./install.sh from the release bundle.",
        name
    )
}

fn run_local_script(name: &str, args: &[String]) -> Result<()> {
    let script = local_script(name)?;
    let status = ProcessCommand::new(&script)
        .args(args)
        .status()
        .with_context(|| format!("running {}", script.display()))?;
    if status.success() {
        Ok(())
    } else {
        anyhow::bail!("{} exited with status {}", script.display(), status)
    }
}

fn run_local(command: &Command) -> Option<Result<()>> {
    match command {
        Command::Setup => Some(run_local_script(
            "wand-proton-manager.sh",
            &["install".to_string()],
        )),
        Command::Proton { command } => {
            let action = match command {
                ProtonCommand::Install => "install",
                ProtonCommand::Status => "status",
                ProtonCommand::Verify => "verify",
                ProtonCommand::Remove => "remove",
            };
            Some(run_local_script(
                "wand-proton-manager.sh",
                &[action.to_string()],
            ))
        }
        Command::TrainerHealth { app_id } => {
            let args = app_id
                .iter()
                .map(|id| id.to_string())
                .collect::<Vec<_>>();
            Some(run_local_script("wand-trainer-health.sh", &args))
        }
        _ => None,
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(result) = run_local(&cli.command) {
        return result;
    }

    let socket = socket_path();

    let stream = UnixStream::connect(&socket)
        .await
        .with_context(|| {
            format!(
                "connecting to {}. Is wandd running?",
                socket.display()
            )
        })?;

    let (reader, mut writer) = stream.into_split();
    let mut bytes = serde_json::to_vec(&request(cli.command))?;
    bytes.push(b'\n');
    writer.write_all(&bytes).await?;
    writer.flush().await?;

    let mut line = String::new();
    BufReader::new(reader).read_line(&mut line).await?;
    let response: Response = serde_json::from_str(&line)?;

    if response.ok {
        if let Some(message) = response.message {
            println!("{message}");
        }
        if !response.data.is_null() {
            println!(
                "{}",
                serde_json::to_string_pretty(&response.data)?
            );
        }
        Ok(())
    } else {
        anyhow::bail!(
            "{}",
            response
                .message
                .unwrap_or_else(|| "unknown wandd error".into())
        )
    }
}
