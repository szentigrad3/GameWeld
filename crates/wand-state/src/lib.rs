use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};
use uuid::Uuid;
use wand_core::{
    GameProfile, LogRecord, Preferences, SessionRecord,
};

#[derive(Debug, Clone)]
pub struct StateStore {
    root: PathBuf,
}

impl StateStore {
    pub fn new(root: PathBuf) -> Result<Self> {
        fs::create_dir_all(root.join("profiles"))?;
        fs::create_dir_all(root.join("sessions"))?;
        fs::create_dir_all(root.join("diagnostics"))?;
        Ok(Self { root })
    }

    pub fn default() -> Result<Self> {
        let base = std::env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("HOME")
                    .map(|home| PathBuf::from(home).join(".local/state"))
            })
            .unwrap_or_else(|| PathBuf::from("."));

        Self::new(base.join("wand"))
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn save_profile(&self, profile: &GameProfile) -> Result<()> {
        let path = self
            .root
            .join("profiles")
            .join(format!("{}.json", profile.app_id));

        fs::write(&path, serde_json::to_vec_pretty(profile)?)
            .with_context(|| format!("writing {}", path.display()))
    }

    pub fn load_profile(&self, app_id: u32) -> Option<GameProfile> {
        let path = self
            .root
            .join("profiles")
            .join(format!("{app_id}.json"));

        serde_json::from_slice(&fs::read(path).ok()?).ok()
    }

    pub fn load_profiles(&self) -> Result<Vec<GameProfile>> {
        let mut out = Vec::new();

        for entry in fs::read_dir(self.root.join("profiles"))? {
            let path = entry?.path();
            if path.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }

            if let Ok(profile) =
                serde_json::from_slice::<GameProfile>(&fs::read(&path)?)
            {
                out.push(profile);
            }
        }

        out.sort_by_key(|profile| profile.app_id);
        Ok(out)
    }

    pub fn save_session(&self, session: &SessionRecord) -> Result<()> {
        let path = self
            .root
            .join("sessions")
            .join(format!("{}.json", session.id));

        fs::write(&path, serde_json::to_vec_pretty(session)?)
            .with_context(|| format!("writing {}", path.display()))
    }

    pub fn load_session(&self, id: Uuid) -> Option<SessionRecord> {
        let path = self
            .root
            .join("sessions")
            .join(format!("{id}.json"));

        serde_json::from_slice(&fs::read(path).ok()?).ok()
    }

    pub fn load_sessions(&self) -> Result<Vec<SessionRecord>> {
        let mut out = Vec::new();

        for entry in fs::read_dir(self.root.join("sessions"))? {
            let path = entry?.path();
            if path.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }

            if let Ok(session) =
                serde_json::from_slice::<SessionRecord>(&fs::read(&path)?)
            {
                out.push(session);
            }
        }

        out.sort_by_key(|session| session.created_at);
        Ok(out)
    }

    pub fn load_preferences(&self) -> Preferences {
        let path = self.root.join("preferences.json");

        fs::read(&path)
            .ok()
            .and_then(|bytes| serde_json::from_slice(&bytes).ok())
            .unwrap_or_default()
    }

    pub fn save_preferences(&self, preferences: &Preferences) -> Result<()> {
        let path = self.root.join("preferences.json");

        fs::write(&path, serde_json::to_vec_pretty(preferences)?)
            .with_context(|| format!("writing {}", path.display()))
    }

    pub fn append_log(
        &self,
        level: &str,
        event: &str,
        message: &str,
        fields: serde_json::Value,
    ) -> Result<()> {
        use std::io::Write;

        let path = self.root.join("wandd.jsonl");
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .with_context(|| format!("opening {}", path.display()))?;

        let record = LogRecord {
            timestamp: chrono::Utc::now(),
            level: level.into(),
            event: event.into(),
            message: message.into(),
            fields,
        };

        writeln!(file, "{}", serde_json::to_string(&record)?)?;
        Ok(())
    }

    pub fn tail_logs(&self, lines: usize) -> Result<Vec<LogRecord>> {
        let path = self.root.join("wandd.jsonl");
        if !path.is_file() {
            return Ok(Vec::new());
        }

        let text = fs::read_to_string(&path)?;
        let keep = lines.clamp(1, 2000);
        let all: Vec<&str> = text.lines().collect();
        let start = all.len().saturating_sub(keep);

        Ok(all[start..]
            .iter()
            .filter_map(|line| serde_json::from_str::<LogRecord>(line).ok())
            .collect())
    }
}
