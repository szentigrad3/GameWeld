use anyhow::{bail, Context, Result};
use std::fs;
use std::io::{Read, Seek, SeekFrom, Write};
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use uuid::Uuid;
use wand_core::{
    GameProfile, LogRecord, Preferences, SessionRecord,
};

const MAX_TAIL_BYTES: u64 = 1024 * 1024;
static TEMP_SEQUENCE: AtomicU64 = AtomicU64::new(0);

/// Persist state via an exclusive 0600 temporary file in the target directory.
/// Readers see the old complete JSON file until rename has finished.
fn write_json_atomic(path: &Path, data: &[u8]) -> Result<()> {
    let directory = path.parent()
        .with_context(|| format!("no parent for {}", path.display()))?;
    let name = path.file_name()
        .with_context(|| format!("no filename for {}", path.display()))?;
    let temp_name = format!(".{}.{}.{}.tmp",
        name.to_string_lossy(), std::process::id(),
        TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed));
    let temporary = directory.join(temp_name);
    let write = (|| -> Result<()> {
        let mut file = fs::OpenOptions::new()
            .write(true).create_new(true).mode(0o600).open(&temporary)?;
        file.write_all(data)?;
        file.sync_all()?;
        fs::rename(&temporary, path)?;
        Ok(())
    })();
    if write.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    write.with_context(|| format!("atomically saving {}", path.display()))
}

fn secure_state_directory(path: &Path) -> Result<()> {
    if let Ok(meta) = fs::symlink_metadata(path) {
        if meta.file_type().is_symlink() || !meta.is_dir() {
            bail!("refusing symlinked or non-directory state path: {}", path.display());
        }
    }
    fs::create_dir_all(path)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .with_context(|| format!("securing {}", path.display()))
}

#[derive(Debug, Clone)]
pub struct StateStore {
    root: PathBuf,
}

impl StateStore {
    pub fn new(root: PathBuf) -> Result<Self> {
        secure_state_directory(&root)?;
        secure_state_directory(&root.join("profiles"))?;
        secure_state_directory(&root.join("sessions"))?;
        secure_state_directory(&root.join("diagnostics"))?;
        Ok(Self { root })
    }

    pub fn default() -> Result<Self> {
        let base = std::env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("HOME")
                    .map(|home| PathBuf::from(home).join(".local/state"))
            });
        let Some(base) = base else {
            bail!("XDG_STATE_HOME and HOME are unset; refusing to save state in working directory");
        };
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

        write_json_atomic(&path, &serde_json::to_vec_pretty(profile)?)
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

        write_json_atomic(&path, &serde_json::to_vec_pretty(session)?)
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

        write_json_atomic(&path, &serde_json::to_vec_pretty(preferences)?)
    }

    pub fn append_log(
        &self,
        level: &str,
        event: &str,
        message: &str,
        fields: serde_json::Value,
    ) -> Result<()> {
        let path = self.root.join("wandd.jsonl");
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .mode(0o600)
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

        let mut file = fs::File::open(&path)?;
        let len = file.metadata()?.len();
        let offset = len.saturating_sub(MAX_TAIL_BYTES);
        file.seek(SeekFrom::Start(offset))?;
        let mut bytes = Vec::new();
        file.take(MAX_TAIL_BYTES).read_to_end(&mut bytes)?;
        let text = String::from_utf8_lossy(&bytes);
        let keep = lines.clamp(1, 2000);
        let mut all: Vec<&str> = text.lines().collect();
        if offset > 0 && !all.is_empty() {
            all.remove(0); // first line may be truncated at the window boundary
        }
        let start = all.len().saturating_sub(keep);

        Ok(all[start..]
            .iter()
            .filter_map(|line| serde_json::from_str::<LogRecord>(line).ok())
            .collect())
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sessions_are_written_atomically_and_privately() {
        let root = std::env::temp_dir().join(format!("wand-state-{}", Uuid::new_v4()));
        let store = StateStore::new(root.clone()).unwrap();
        let record = SessionRecord::new(
            3008130, "Fixture Game".into(), "generic-exe".into(), "/test.exe".into());
        store.save_session(&record).unwrap();
        store.save_session(&record).unwrap();
        let path = root.join("sessions").join(format!("{}.json", record.id));
        assert_eq!(store.load_session(record.id).unwrap().id, record.id);
        assert_eq!(fs::metadata(&root).unwrap().permissions().mode() & 0o777, 0o700);
        assert_eq!(fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        let leftovers = fs::read_dir(root.join("sessions")).unwrap().filter_map(Result::ok)
            .filter(|entry| entry.path().extension().and_then(|ext| ext.to_str()) != Some("json"))
            .count();
        assert_eq!(leftovers, 0);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn symlinked_state_directory_is_refused() {
        let outer = std::env::temp_dir().join(format!("wand-state-link-{}", Uuid::new_v4()));
        let target = outer.join("target");
        fs::create_dir_all(&target).unwrap();
        let link = outer.join("link");
        std::os::unix::fs::symlink(&target, &link).unwrap();
        assert!(StateStore::new(link).is_err());
        fs::remove_dir_all(outer).unwrap();
    }

    #[test]
    fn logs_are_private_and_tail_remains_bounded() {
        let root = std::env::temp_dir().join(format!("wand-state-log-{}", Uuid::new_v4()));
        let store = StateStore::new(root.clone()).unwrap();
        let body = "x".repeat(1024);
        for _ in 0..1200 {
            store.append_log("info", "fixture", &body, serde_json::json!({})).unwrap();
        }
        let path = root.join("wandd.jsonl");
        assert_eq!(fs::metadata(path).unwrap().permissions().mode() & 0o777, 0o600);
        let tail = store.tail_logs(5).unwrap();
        assert_eq!(tail.len(), 5);
        assert!(tail.iter().all(|line| line.event == "fixture"));
        fs::remove_dir_all(root).unwrap();
    }
}
