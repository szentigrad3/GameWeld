use anyhow::{anyhow, Result};
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Arc;
use wand_core::{
    GameInstall, LaunchPlan, ProviderDescriptor, ProviderHealth, ProviderImportResult, ProviderSource, ProtonTool,
};

pub trait TrainerProvider: Send + Sync {
    fn descriptor(&self) -> ProviderDescriptor;

    fn probe(&self) -> ProviderHealth;

    fn probe_game(&self, _game: &GameInstall) -> ProviderHealth {
        self.probe()
    }

    fn discover_sources(
        &self,
        _games: &[GameInstall],
    ) -> Result<Vec<ProviderSource>> {
        Ok(Vec::new())
    }

    fn import_runtime(
        &self,
        _game: &GameInstall,
        _source: &Path,
        _replace: bool,
    ) -> Result<ProviderImportResult> {
        Err(anyhow!(
            "provider {} does not support runtime import",
            self.descriptor().id
        ))
    }

    fn prepare_bootstrap(
        &self,
        _steam_root: &Path,
        _game: &GameInstall,
        _proton: &ProtonTool,
        _installer: &Path,
        _args: &[String],
    ) -> Result<LaunchPlan> {
        Err(anyhow!(
            "provider {} does not support runtime bootstrap",
            self.descriptor().id
        ))
    }

    fn prepare(
        &self,
        steam_root: &Path,
        game: &GameInstall,
        proton: &ProtonTool,
        trainer: &Path,
        args: &[String],
    ) -> Result<LaunchPlan>;

    fn launch(
        &self,
        plan: &LaunchPlan,
        dry_run: bool,
    ) -> Result<Option<u32>>;

    fn stop(&self, pid: u32) -> Result<()>;
}

#[derive(Default)]
pub struct ProviderRegistry {
    providers: BTreeMap<String, Arc<dyn TrainerProvider>>,
}

impl ProviderRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register<P>(&mut self, provider: P)
    where
        P: TrainerProvider + 'static,
    {
        let provider = Arc::new(provider);
        let id = provider.descriptor().id;
        self.providers.insert(id, provider);
    }

    pub fn get(&self, id: &str) -> Result<Arc<dyn TrainerProvider>> {
        self.providers
            .get(id)
            .cloned()
            .ok_or_else(|| anyhow!("trainer provider {id:?} is not installed"))
    }

    pub fn descriptors(&self) -> Vec<ProviderDescriptor> {
        self.providers
            .values()
            .map(|provider| provider.descriptor())
            .collect()
    }

    pub fn health(
        &self,
        id: Option<&str>,
        game: Option<&GameInstall>,
    ) -> Result<Vec<ProviderHealth>> {
        let probe = |provider: &Arc<dyn TrainerProvider>| {
            if let Some(game) = game {
                provider.probe_game(game)
            } else {
                provider.probe()
            }
        };

        match id {
            Some(id) => {
                let provider = self.get(id)?;
                Ok(vec![probe(&provider)])
            }
            None => Ok(self.providers.values().map(probe).collect()),
        }
    }
}
