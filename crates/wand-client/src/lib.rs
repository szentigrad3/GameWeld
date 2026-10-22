use anyhow::{anyhow, Context, Result};
use serde::de::DeserializeOwned;
use std::{
    io::{BufRead, BufReader, Write},
    os::unix::net::UnixStream,
    path::{Path, PathBuf},
    time::Duration,
};
use uuid::Uuid;
use wand_core::{
    DaemonStatus, GameInstall, GameProfile, InspectResult, LogRecord, Preferences, ProcessProbe, ProviderBootstrapResult, ProviderDescriptor, ProviderHealth, ProviderImportResult, ProviderSource, ProtonTool,
    Request, Response, SessionRecord,
};

#[derive(Debug, Clone)]
pub struct WandClient {
    socket: PathBuf,
}

impl Default for WandClient {
    fn default() -> Self {
        Self::new(default_socket_path())
    }
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

impl WandClient {
    pub fn new(socket: PathBuf) -> Self {
        Self { socket }
    }

    pub fn socket_path(&self) -> &Path {
        &self.socket
    }

    fn exchange(&self, request: &Request) -> Result<Response> {
        let mut stream = UnixStream::connect(&self.socket)
            .with_context(|| {
                format!(
                    "connecting to {}. Is wandd running?",
                    self.socket.display()
                )
            })?;

        stream
            .set_read_timeout(Some(Duration::from_secs(65)))
            .context("setting Wand socket timeout")?;

        let mut bytes = serde_json::to_vec(request)?;
        bytes.push(b'\n');
        stream.write_all(&bytes)?;
        stream.flush()?;

        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line)?;
        if line.trim().is_empty() {
            return Err(anyhow!("wandd closed the connection without a response"));
        }

        let response: Response = serde_json::from_str(&line)?;
        if !response.ok {
            return Err(anyhow!(
                "{}",
                response
                    .message
                    .unwrap_or_else(|| "unknown wandd error".into())
            ));
        }
        Ok(response)
    }

    pub fn request<T: DeserializeOwned>(&self, request: Request) -> Result<T> {
        let response = self.exchange(&request)?;
        serde_json::from_value(response.data).context("decoding wandd response")
    }

    pub fn ping(&self) -> Result<String> {
        let response = self.exchange(&Request::Ping)?;
        Ok(response.message.unwrap_or_else(|| "pong".into()))
    }

    pub fn status(&self) -> Result<DaemonStatus> {
        self.request(Request::Status)
    }

    pub fn games(&self) -> Result<Vec<GameInstall>> {
        self.request(Request::Games)
    }

    pub fn protons(&self) -> Result<Vec<ProtonTool>> {
        self.request(Request::Protons)
    }

    pub fn providers(&self) -> Result<Vec<ProviderDescriptor>> {
        self.request(Request::Providers)
    }

    pub fn provider_health(
        &self,
        provider: Option<String>,
        app_id: Option<u32>,
    ) -> Result<Vec<ProviderHealth>> {
        self.request(Request::ProviderHealth { provider, app_id })
    }

    pub fn provider_sources(
        &self,
        provider: String,
    ) -> Result<Vec<ProviderSource>> {
        self.request(Request::ProviderSources { provider })
    }

    pub fn import_provider_runtime(
        &self,
        provider: String,
        app_id: u32,
        source: PathBuf,
        replace: bool,
    ) -> Result<ProviderImportResult> {
        self.request(Request::ImportProviderRuntime {
            provider,
            app_id,
            source,
            replace,
        })
    }

    pub fn bootstrap_provider_runtime(
        &self,
        provider: String,
        app_id: u32,
        installer: PathBuf,
        proton: Option<String>,
        args: Vec<String>,
    ) -> Result<ProviderBootstrapResult> {
        self.request(Request::BootstrapProviderRuntime {
            provider,
            app_id,
            installer,
            proton,
            graphical_environment: graphical_session_environment(),
            args,
        })
    }

    pub fn processes(&self, app_id: u32) -> Result<ProcessProbe> {
        self.request(Request::Processes { app_id })
    }

    pub fn preferences(&self) -> Result<Preferences> {
        self.request(Request::Preferences)
    }

    pub fn set_preferences(
        &self,
        preferences: Preferences,
    ) -> Result<Preferences> {
        self.request(Request::SetPreferences { preferences })
    }

    pub fn logs(&self, lines: usize) -> Result<Vec<LogRecord>> {
        self.request(Request::Logs { lines })
    }

    pub fn inspect(&self, app_id: u32) -> Result<InspectResult> {
        self.request(Request::Inspect {
            app_id,
            proton: None,
        })
    }

    pub fn begin_session(
        &self,
        app_id: u32,
        trainer: PathBuf,
        provider: Option<String>,
        proton: Option<String>,
        launch_game: bool,
        timeout_secs: u64,
        args: Vec<String>,
    ) -> Result<SessionRecord> {
        self.request(Request::BeginSession {
            app_id,
            trainer,
            provider,
            proton,
            launch_game,
            timeout_secs,
            args,
        })
    }

    pub fn session(&self, id: Uuid) -> Result<SessionRecord> {
        self.request(Request::Session { id })
    }

    pub fn sessions(&self) -> Result<Vec<SessionRecord>> {
        self.request(Request::Sessions)
    }

    pub fn stop_session(&self, id: Uuid) -> Result<SessionRecord> {
        self.request(Request::StopSession { id })
    }

    pub fn set_profile(&self, profile: GameProfile) -> Result<GameProfile> {
        self.request(Request::SetProfile { profile })
    }

    pub fn profiles(&self) -> Result<Vec<GameProfile>> {
        self.request(Request::Profiles)
    }

    pub fn export_diagnostics(
        &self,
        id: Uuid,
        destination: PathBuf,
    ) -> Result<PathBuf> {
        self.request(Request::ExportDiagnostics { id, destination })
    }
}

pub fn default_socket_path() -> PathBuf {
    if let Some(value) = std::env::var_os("WAND_SOCKET_PATH") {
        return PathBuf::from(value);
    }

    if let Some(value) = std::env::var_os("XDG_RUNTIME_DIR") {
        return PathBuf::from(value).join("wand/wand.sock");
    }

    PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
        .join(".cache/wand-runtime/wand.sock")
}
