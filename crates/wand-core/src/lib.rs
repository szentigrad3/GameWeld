use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SteamLibrary {
    pub path: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GameInstall {
    pub app_id: u32,
    pub name: String,
    pub install_dir: PathBuf,
    pub library_root: PathBuf,
    pub manifest: PathBuf,
    pub compatdata_dir: PathBuf,
    pub prefix_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtonTool {
    pub tool_id: String,
    pub display_name: String,
    pub root: PathBuf,
    pub proton_script: PathBuf,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum ProcessRole {
    GameCandidate,
    Launcher,
    Helper,
    #[default]
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    pub pid: u32,
    #[serde(default)]
    pub parent_pid: Option<u32>,
    pub comm: String,
    pub cmdline: String,
    #[serde(default)]
    pub exe: Option<PathBuf>,
    #[serde(default)]
    pub windows_executable: Option<String>,
    #[serde(default)]
    pub role: ProcessRole,
    #[serde(default)]
    pub score: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessProbe {
    pub app_id: u32,
    pub candidates: Vec<ProcessInfo>,
    pub best_candidate_pid: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SessionState {
    Idle,
    Preparing,
    LaunchingGame,
    WaitingForGame,
    GameDetected,
    StartingTrainer,
    Running,
    Stopping,
    Stopped,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionEvent {
    pub at: DateTime<Utc>,
    pub state: SessionState,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionEventBatch {
    pub session_id: Uuid,
    pub state: SessionState,
    pub events: Vec<SessionEvent>,
    pub next_index: usize,
}

fn default_requires_trainer_path() -> bool {
    true
}

fn default_requires_provider_pid_alive() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum ProviderFlow {
    #[default]
    AfterGame,
    InteractiveBeforeGame,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderDescriptor {
    pub id: String,
    pub name: String,
    pub description: String,
    #[serde(default)]
    pub capabilities: Vec<String>,
    #[serde(default)]
    pub requires_windows_bridge: bool,
    #[serde(default = "default_requires_trainer_path")]
    pub requires_trainer_path: bool,
    #[serde(default = "default_requires_provider_pid_alive")]
    pub requires_provider_pid_alive: bool,
    #[serde(default)]
    pub flow: ProviderFlow,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderHealth {
    pub id: String,
    pub available: bool,
    pub status: String,
    pub details: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderSource {
    pub provider_id: String,
    pub source_id: String,
    pub display_name: String,
    pub path: PathBuf,
    pub details: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderImportResult {
    pub provider_id: String,
    pub app_id: u32,
    pub source: PathBuf,
    pub copied_paths: Vec<PathBuf>,
    pub health: ProviderHealth,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderBootstrapResult {
    pub provider_id: String,
    pub app_id: u32,
    pub installer: PathBuf,
    pub proton: ProtonTool,
    pub launch_pid: Option<u32>,
    pub health_after_launch: ProviderHealth,
}

fn default_provider_id() -> String {
    "generic-exe".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionRecord {
    pub id: Uuid,
    pub app_id: u32,
    pub game_name: String,
    #[serde(default = "default_provider_id")]
    pub provider_id: String,
    pub trainer: PathBuf,
    pub state: SessionState,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub trainer_pid: Option<u32>,
    pub game_processes: Vec<ProcessInfo>,
    pub events: Vec<SessionEvent>,
    pub error: Option<String>,
}

impl SessionRecord {
    pub fn new(
        app_id: u32,
        game_name: String,
        provider_id: String,
        trainer: PathBuf,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            app_id,
            game_name,
            provider_id,
            trainer,
            state: SessionState::Idle,
            created_at: now,
            updated_at: now,
            trainer_pid: None,
            game_processes: Vec::new(),
            events: vec![SessionEvent {
                at: now,
                state: SessionState::Idle,
                message: "session created".into(),
            }],
            error: None,
        }
    }

    pub fn transition(&mut self, state: SessionState, message: impl Into<String>) {
        self.state = state.clone();
        self.updated_at = Utc::now();
        self.events.push(SessionEvent {
            at: self.updated_at,
            state,
            message: message.into(),
        });
    }

    pub fn fail(&mut self, message: impl Into<String>) {
        let message = message.into();
        self.error = Some(message.clone());
        self.transition(SessionState::Failed, message);
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GameProfile {
    pub app_id: u32,
    pub provider_id: Option<String>,
    pub preferred_proton: Option<String>,
    pub trainer: Option<PathBuf>,
    pub trainer_args: Vec<String>,
    pub auto_launch_trainer: bool,
}

fn default_provider() -> String {
    "generic-exe".into()
}

fn default_launch_game() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preferences {
    #[serde(default)]
    pub onboarding_complete: bool,
    #[serde(default = "default_provider")]
    pub default_provider: String,
    #[serde(default = "default_launch_game")]
    pub launch_game_automatically: bool,
    #[serde(default)]
    pub diagnostics_directory: Option<PathBuf>,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            onboarding_complete: false,
            default_provider: default_provider(),
            launch_game_automatically: true,
            diagnostics_directory: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectResult {
    pub game: GameInstall,
    pub proton: Option<ProtonTool>,
    pub proton_reason: String,
    pub running_processes: Vec<ProcessInfo>,
    pub profile: Option<GameProfile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LaunchPlan {
    pub app_id: u32,
    pub game_name: String,
    pub proton: ProtonTool,
    pub compatdata_dir: PathBuf,
    pub prefix_dir: PathBuf,
    pub trainer: PathBuf,
    pub command: Vec<String>,
    pub environment: Vec<(String, String)>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DaemonStatus {
    pub version: String,
    pub steam_root: Option<PathBuf>,
    pub game_count: usize,
    pub provider_count: usize,
    pub persisted_session_count: usize,
    #[serde(default)]
    pub onboarding_complete: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogRecord {
    pub timestamp: DateTime<Utc>,
    pub level: String,
    pub event: String,
    pub message: String,
    pub fields: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Request {
    Ping,
    Status,
    Games,
    Protons,
    Providers,
    ProviderHealth {
        provider: Option<String>,
        app_id: Option<u32>,
    },
    ProviderSources {
        provider: String,
    },
    ImportProviderRuntime {
        provider: String,
        app_id: u32,
        source: PathBuf,
        replace: bool,
    },
    BootstrapProviderRuntime {
        provider: String,
        app_id: u32,
        installer: PathBuf,
        proton: Option<String>,
        graphical_environment: Vec<(String, String)>,
        args: Vec<String>,
    },
    Processes {
        app_id: u32,
    },
    Preferences,
    SetPreferences {
        preferences: Preferences,
    },
    Logs {
        lines: usize,
    },
    Inspect {
        app_id: u32,
        proton: Option<String>,
    },
    LaunchGame {
        app_id: u32,
        dry_run: bool,
    },
    RunTrainer {
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        dry_run: bool,
        force: bool,
        args: Vec<String>,
    },
    StartSession {
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    },
    BeginSession {
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    },
    Sessions,
    Session {
        id: Uuid,
    },
    WatchSession {
        id: Uuid,
        after: usize,
        timeout_secs: u64,
    },
    StopSession {
        id: Uuid,
    },
    ReconcileSessions,
    SetProfile {
        profile: GameProfile,
    },
    Profiles,
    ExportDiagnostics {
        id: Uuid,
        destination: PathBuf,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response {
    pub ok: bool,
    pub message: Option<String>,
    pub data: serde_json::Value,
}

impl Response {
    pub fn ok<T: Serialize>(value: T) -> Self {
        Self {
            ok: true,
            message: None,
            data: serde_json::to_value(value).unwrap_or(serde_json::Value::Null),
        }
    }

    pub fn message(message: impl Into<String>) -> Self {
        Self {
            ok: true,
            message: Some(message.into()),
            data: serde_json::Value::Null,
        }
    }

    pub fn error(message: impl Into<String>) -> Self {
        Self {
            ok: false,
            message: Some(message.into()),
            data: serde_json::Value::Null,
        }
    }
}
