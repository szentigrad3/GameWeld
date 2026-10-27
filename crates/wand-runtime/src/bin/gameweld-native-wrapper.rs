//! Explicit, private test harness for GameWeld's Rust native wrapper launch.
//! Preview is read-only. Launch requires two approvals and never edits Steam
//! Launch Options, chooses a Proton version by guesswork, or installs a prefix.
use anyhow::{anyhow, bail, Context, Result};
use std::env;
use std::path::PathBuf;
use wand_runtime::{build_native_wrapper_launch_plan, run_native_wrapper_launch_plan};
use wand_steam::{
    choose_proton, discover_games, discover_libraries, discover_proton_tools,
    primary_steam_root,
};

#[derive(Default, Debug)]
struct Options {
    appid: Option<u32>,
    wrapper: Option<PathBuf>,
    proton: Option<String>,
    game_exe: Option<PathBuf>,
    steam_root: Option<PathBuf>,
    preview: bool,
    launch: bool,
    approve: bool,
    game_closed: bool,
}

fn parse<I: IntoIterator<Item = String>>(args: I) -> Result<Options> {
    let mut result = Options::default();
    let mut iter = args.into_iter();
    while let Some(flag) = iter.next() {
        match flag.as_str() {
            "--appid" => {
                let raw = iter.next().ok_or_else(|| anyhow!("missing --appid value"))?;
                if raw.is_empty() || raw.starts_with('0') ||
                    !raw.bytes().all(|c| c.is_ascii_digit()) {
                    bail!("invalid Steam AppID");
                }
                result.appid = Some(raw.parse::<u32>().context("invalid Steam AppID")?);
            },
            "--wrapper" => result.wrapper = Some(PathBuf::from(
                iter.next().ok_or_else(|| anyhow!("missing --wrapper value"))?)),
            "--proton" => result.proton = Some(
                iter.next().ok_or_else(|| anyhow!("missing --proton value"))?),
            "--steam-root" => result.steam_root = Some(PathBuf::from(
                iter.next().ok_or_else(|| anyhow!("missing --steam-root value"))?)),
            "--game-exe" => result.game_exe = Some(PathBuf::from(
                iter.next().ok_or_else(|| anyhow!("missing --game-exe value"))?)),
            "--preview" => result.preview = true,
            "--launch" => result.launch = true,
            "--approve-experimental" => result.approve = true,
            "--acknowledge-game-closed" => result.game_closed = true,
            _ => bail!("unsupported native wrapper option: {flag}"),
        }
    }
    if result.preview == result.launch {
        bail!("specify exactly one of --preview or --launch");
    }
    if result.appid.is_none() || result.wrapper.is_none() {
        bail!("both --appid and --wrapper are required");
    }
    if result.launch && !(result.approve && result.game_closed) {
        bail!("native launch requires explicit risk approval and closed-game acknowledgement");
    }
    if result.preview && (result.approve || result.game_closed) {
        bail!("read-only preview does not accept launch consent flags");
    }
    Ok(result)
}

fn execute(args: Options) -> Result<()> {
    let id = args.appid.context("missing app ID")?;
    let steam_root = match args.steam_root {
        Some(path) => std::fs::canonicalize(path).context("Steam root unavailable")?,
        None => primary_steam_root()?,
    };
    let libraries = discover_libraries(&steam_root)?;
    let games = discover_games(&libraries)?;
    let game = games.iter().find(|game| game.app_id == id)
        .ok_or_else(|| anyhow!("Steam AppID {id} not found in this Steam installation"))?;
    let proton_tools = discover_proton_tools(&steam_root, &libraries)?;
    let (proton, reason) = choose_proton(
        game, &steam_root, &proton_tools, args.proton.as_deref())?;
    let proton = proton.ok_or_else(|| anyhow!(
        "No unambiguous Proton selection for AppID {id}: {reason}. Set GAMEWELD_NATIVE_PROTON to the selected Proton path or tool ID."))?;
    let wrapper = args.wrapper.context("missing wrapper")?;
    let wrapper_log = wrapper.parent().ok_or_else(|| anyhow!("wrapper has no directory"))?
        .join("wemod.log");
    if let Some(game_exe) = args.game_exe {
        if !game_exe.is_absolute() {
            bail!("explicit game EXE must be an absolute path");
        }
        // This applies to this process only; the Rust builder validates the
        // resolved EXE is inside the selected Steam game's install directory.
        env::set_var("WAND_GAME_EXE", game_exe);
    }
    let plan = build_native_wrapper_launch_plan(
        game, &steam_root, &proton, &wrapper, &wrapper_log)?;
    println!("NATIVE_WRAPPER_MODE={}", if args.preview {"PREVIEW"} else {"EXPERIMENTAL_LAUNCH"});
    println!("APPID={id}");
    println!("GAME={}", game.name);
    println!("PROTON={}", proton.display_name);
    println!("WRAPPER={}", plan.trainer.display());
    println!("GAME_EXE={}", plan.command[3]);
    println!("STEAM_LAUNCH_OPTIONS_MODIFIED=false");
    if args.preview {
        let _ = run_native_wrapper_launch_plan(&plan, &game.install_dir, true)?;
        println!("PREVIEW_OK=1");
        println!("GAME_SPAWNED=false");
    } else {
        println!("WARNING=Direct Proton invocation does not recreate Steam Runtime, Steam API or DRM.");
        let pid = run_native_wrapper_launch_plan(&plan, &game.install_dir, false)?
            .ok_or_else(|| anyhow!("native launch did not spawn a child"))?;
        println!("NATIVE_WRAPPER_SPAWNED_PID={pid}");
        println!("TRAINER_ATTACHMENT_VERIFIED=false");
        println!("GAME_START_VERIFIED=false");
    }
    Ok(())
}

fn main() {
    let result = parse(env::args().skip(1)).and_then(execute);
    if let Err(err) = result {
        eprintln!("NATIVE_WRAPPER_BLOCKED={err:#}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn args(items: &[&str]) -> Result<Options> {
        parse(items.iter().map(|s| (*s).to_owned()))
    }
    #[test]
    fn preview_requires_explicit_game_and_wrapper() {
        assert!(args(&["--preview"]).is_err());
        assert!(args(&["--preview", "--appid", "3008130", "--wrapper", "/tmp/wemod"]).is_ok());
        assert!(args(&["--preview", "--appid", "3008130;touch /tmp/file", "--wrapper", "/tmp/wemod"]).is_err());
    }
    #[test]
    fn live_launch_needs_two_consents() {
        let base = ["--launch", "--appid", "3008130", "--wrapper", "/tmp/wemod"];
        assert!(args(&base).is_err());
        let mut full = base.to_vec();
        full.extend(["--approve-experimental", "--acknowledge-game-closed"]);
        assert!(args(&full).is_ok());
        full.push("--preview");
        assert!(args(&full).is_err());
    }
    #[test]
    fn preview_rejects_launch_consent_and_unrecognized_flags() {
        assert!(args(&["--preview", "--appid", "2353250", "--wrapper", "/tmp/wemod",
            "--approve-experimental"]).is_err());
        assert!(args(&["--preview", "--appid", "2353250", "--wrapper", "/tmp/wemod",
            "--shell"]).is_err());
    }
}
