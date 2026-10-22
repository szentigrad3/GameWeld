use anyhow::Result;
use std::path::Path;
use wand_core::{
    GameInstall, LaunchPlan, ProviderDescriptor, ProviderFlow, ProviderHealth, ProtonTool,
};
use wand_provider_api::TrainerProvider;

#[derive(Debug, Default)]
pub struct GenericExeProvider;

impl TrainerProvider for GenericExeProvider {
    fn descriptor(&self) -> ProviderDescriptor {
        ProviderDescriptor {
            id: "generic-exe".into(),
            name: "Generic Windows Trainer".into(),
            description:
                "Runs a Windows trainer executable with the game's selected Proton compatdata."
                    .into(),
            capabilities: vec![
                "windows-exe".into(),
                "proton-compatdata".into(),
                "dry-run".into(),
                "owned-process-stop".into(),
            ],
            requires_windows_bridge: false,
            requires_trainer_path: true,
            requires_provider_pid_alive: true,
            flow: ProviderFlow::AfterGame,
        }
    }

    fn probe(&self) -> ProviderHealth {
        ProviderHealth {
            id: "generic-exe".into(),
            available: true,
            status: "ready".into(),
            details: vec![
                "No provider-specific Windows service is required.".into(),
                "A usable Proton tool is resolved per game at launch time.".into(),
            ],
        }
    }

    fn prepare(
        &self,
        steam_root: &Path,
        game: &GameInstall,
        proton: &ProtonTool,
        trainer: &Path,
        args: &[String],
    ) -> Result<LaunchPlan> {
        wand_runtime::build_launch_plan(
            game,
            steam_root,
            proton,
            trainer,
            args,
        )
    }

    fn launch(
        &self,
        plan: &LaunchPlan,
        dry_run: bool,
    ) -> Result<Option<u32>> {
        wand_runtime::run_launch_plan(plan, dry_run)
    }

    fn stop(&self, pid: u32) -> Result<()> {
        wand_runtime::terminate_owned_process(pid)
    }
}
