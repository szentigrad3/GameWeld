# Provider API

Trainer-specific behaviour is isolated behind `TrainerProvider`.

0.0.7 adds provider capabilities and health.

```rust
pub trait TrainerProvider: Send + Sync {
    fn descriptor(&self) -> ProviderDescriptor;
    fn probe(&self) -> ProviderHealth;

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
```

`ProviderDescriptor` advertises:

- provider ID
- user-facing name
- description
- capabilities
- whether a Windows bridge is required

`ProviderHealth` reports:

- available / unavailable
- status string
- details

The first provider is `generic-exe`.

The next planned provider is `wand-provider-wemod`. It must report missing
authentication/runtime requirements through `probe()` rather than pushing those
conditions into `wandd`.
