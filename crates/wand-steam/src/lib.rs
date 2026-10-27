use anyhow::{anyhow, Context, Result};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use wand_core::{GameInstall, ProtonTool, SteamLibrary};

#[derive(Debug, Clone)]
enum Kv {
    String(String),
    Object(BTreeMap<String, Kv>),
}

fn tokenize(input: &str) -> Result<Vec<String>> {
    let bytes = input.as_bytes();
    let mut out = Vec::new();
    let mut i = 0usize;

    while i < bytes.len() {
        match bytes[i] {
            b' ' | b'\t' | b'\r' | b'\n' => {
                i += 1;
            }
            b'/' if i + 1 < bytes.len() && bytes[i + 1] == b'/' => {
                i += 2;
                while i < bytes.len() && bytes[i] != b'\n' {
                    i += 1;
                }
            }
            b'{' => {
                out.push("{".into());
                i += 1;
            }
            b'}' => {
                out.push("}".into());
                i += 1;
            }
            b'"' => {
                i += 1;
                let mut s = String::new();
                while i < bytes.len() {
                    match bytes[i] {
                        b'\\' if i + 1 < bytes.len() => {
                            let next = bytes[i + 1];
                            match next {
                                b'\\' => s.push('\\'),
                                b'"' => s.push('"'),
                                b'n' => s.push('\n'),
                                b't' => s.push('\t'),
                                other => {
                                    s.push('\\');
                                    s.push(other as char);
                                }
                            }
                            i += 2;
                        }
                        b'"' => {
                            i += 1;
                            break;
                        }
                        ch => {
                            s.push(ch as char);
                            i += 1;
                        }
                    }
                }
                out.push(s);
            }
            _ => {
                let start = i;
                while i < bytes.len()
                    && !bytes[i].is_ascii_whitespace()
                    && bytes[i] != b'{'
                    && bytes[i] != b'}'
                {
                    i += 1;
                }
                out.push(String::from_utf8_lossy(&bytes[start..i]).into_owned());
            }
        }
    }

    Ok(out)
}

fn parse_object(tokens: &[String], index: &mut usize, expect_close: bool) -> Result<BTreeMap<String, Kv>> {
    let mut obj = BTreeMap::new();

    while *index < tokens.len() {
        if tokens[*index] == "}" {
            if !expect_close {
                return Err(anyhow!("unexpected closing brace"));
            }
            *index += 1;
            return Ok(obj);
        }

        if tokens[*index] == "{" {
            return Err(anyhow!("unexpected opening brace"));
        }

        let key = tokens[*index].clone();
        *index += 1;

        if *index >= tokens.len() {
            obj.insert(key, Kv::String(String::new()));
            break;
        }

        let value = if tokens[*index] == "{" {
            *index += 1;
            Kv::Object(parse_object(tokens, index, true)?)
        } else if tokens[*index] == "}" {
            return Err(anyhow!("missing value for key {key:?}"));
        } else {
            let v = Kv::String(tokens[*index].clone());
            *index += 1;
            v
        };

        // For the Steam files we consume, first value wins for duplicate keys.
        obj.entry(key).or_insert(value);
    }

    if expect_close {
        Err(anyhow!("unterminated object"))
    } else {
        Ok(obj)
    }
}

fn parse_vdf_text(text: &str) -> Result<BTreeMap<String, Kv>> {
    let tokens = tokenize(text)?;
    let mut index = 0usize;
    parse_object(&tokens, &mut index, false)
}

fn parse_vdf_file(path: &Path) -> Result<BTreeMap<String, Kv>> {
    let text = fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    parse_vdf_text(&text)
        .with_context(|| format!("parsing {}", path.display()))
}

fn string_at<'a>(obj: &'a BTreeMap<String, Kv>, key: &str) -> Option<&'a str> {
    match obj.get(key) {
        Some(Kv::String(v)) => Some(v.as_str()),
        _ => None,
    }
}

fn object_at<'a>(obj: &'a BTreeMap<String, Kv>, key: &str) -> Option<&'a BTreeMap<String, Kv>> {
    match obj.get(key) {
        Some(Kv::Object(v)) => Some(v),
        _ => None,
    }
}

fn find_objects<'a>(
    obj: &'a BTreeMap<String, Kv>,
    wanted: &str,
    out: &mut Vec<&'a BTreeMap<String, Kv>>,
) {
    for (key, value) in obj {
        if key == wanted {
            if let Kv::Object(child) = value {
                out.push(child);
            }
        }
        if let Kv::Object(child) = value {
            find_objects(child, wanted, out);
        }
    }
}

fn canonical_if_exists(path: PathBuf) -> Option<PathBuf> {
    if !path.exists() {
        return None;
    }
    fs::canonicalize(&path).ok().or(Some(path))
}

pub fn steam_roots() -> Vec<PathBuf> {
    let Some(home) = std::env::var_os("HOME").map(PathBuf::from) else {
        return Vec::new();
    };

    let candidates = [
        home.join(".steam/root"),
        home.join(".steam/steam"),
        home.join(".local/share/Steam"),
        home.join(".var/app/com.valvesoftware.Steam/.local/share/Steam"),
    ];

    let mut seen = HashSet::new();
    let mut result = Vec::new();
    for path in candidates {
        if let Some(real) = canonical_if_exists(path) {
            if seen.insert(real.clone()) {
                result.push(real);
            }
        }
    }
    result
}

pub fn primary_steam_root() -> Result<PathBuf> {
    steam_roots()
        .into_iter()
        .next()
        .ok_or_else(|| anyhow!("no Steam installation found"))
}

pub fn discover_libraries(root: &Path) -> Result<Vec<SteamLibrary>> {
    let mut paths = vec![root.to_path_buf()];
    let file = root.join("steamapps/libraryfolders.vdf");

    if file.exists() {
        let data = parse_vdf_file(&file)?;
        let mut matches = Vec::new();
        find_objects(&data, "libraryfolders", &mut matches);

        for libraries in matches {
            for value in libraries.values() {
                if let Kv::Object(entry) = value {
                    if let Some(path) = string_at(entry, "path") {
                        paths.push(PathBuf::from(path));
                    }
                }
            }
        }
    }

    let mut seen = HashSet::new();
    let mut out = Vec::new();
    for path in paths {
        if let Some(real) = canonical_if_exists(path) {
            if seen.insert(real.clone()) {
                out.push(SteamLibrary { path: real });
            }
        }
    }
    Ok(out)
}

fn parse_app_manifest(path: &Path, library_root: &Path) -> Result<Option<GameInstall>> {
    let data = parse_vdf_file(path)?;
    let app = object_at(&data, "AppState")
        .or_else(|| object_at(&data, "appstate"));

    let Some(app) = app else {
        return Ok(None);
    };

    let Some(app_id) = string_at(app, "appid").and_then(|v| v.parse::<u32>().ok()) else {
        return Ok(None);
    };
    let name = string_at(app, "name")
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| format!("App {app_id}"));
    let Some(install_dir_name) = string_at(app, "installdir") else {
        return Ok(None);
    };

    let install_dir = library_root
        .join("steamapps/common")
        .join(install_dir_name);
    let compatdata_dir = library_root
        .join("steamapps/compatdata")
        .join(app_id.to_string());

    Ok(Some(GameInstall {
        app_id,
        name,
        install_dir,
        library_root: library_root.to_path_buf(),
        manifest: path.to_path_buf(),
        prefix_dir: compatdata_dir.join("pfx"),
        compatdata_dir,
    }))
}

pub fn discover_games(libraries: &[SteamLibrary]) -> Result<Vec<GameInstall>> {
    let mut by_app: HashMap<u32, GameInstall> = HashMap::new();

    for library in libraries {
        let steamapps = library.path.join("steamapps");
        if !steamapps.exists() {
            continue;
        }

        for entry in fs::read_dir(&steamapps)
            .with_context(|| format!("reading {}", steamapps.display()))?
        {
            let entry = entry?;
            let path = entry.path();
            let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
                continue;
            };
            if !(name.starts_with("appmanifest_") && name.ends_with(".acf")) {
                continue;
            }

            if let Ok(Some(game)) = parse_app_manifest(&path, &library.path) {
                by_app.insert(game.app_id, game);
            }
        }
    }

    let mut games: Vec<_> = by_app.into_values().collect();
    games.sort_by_key(|g| g.name.to_lowercase());
    Ok(games)
}

fn compat_tool_ids(path: &Path) -> Vec<(String, String)> {
    if !path.exists() {
        return Vec::new();
    }

    let Ok(data) = parse_vdf_file(path) else {
        return Vec::new();
    };

    let mut matches = Vec::new();
    find_objects(&data, "compat_tools", &mut matches);

    let mut result = Vec::new();
    for tools in matches {
        for (tool_id, value) in tools {
            match value {
                Kv::Object(meta) => {
                    let display = string_at(meta, "display_name")
                        .or_else(|| string_at(meta, "displayname"))
                        .or_else(|| string_at(meta, "name"))
                        .unwrap_or(tool_id);
                    result.push((tool_id.clone(), display.to_owned()));
                }
                _ => result.push((tool_id.clone(), tool_id.clone())),
            }
        }
    }
    result
}

pub fn discover_proton_tools(
    root: &Path,
    libraries: &[SteamLibrary],
) -> Result<Vec<ProtonTool>> {
    let mut locations: Vec<(PathBuf, &str)> = vec![
        (root.join("compatibilitytools.d"), "user"),
        (
            PathBuf::from(std::env::var("HOME").unwrap_or_default())
                .join(".local/share/Steam/compatibilitytools.d"),
            "user",
        ),
        (
            PathBuf::from("/usr/share/steam/compatibilitytools.d"),
            "system",
        ),
        (
            PathBuf::from("/usr/local/share/steam/compatibilitytools.d"),
            "system",
        ),
    ];

    for lib in libraries {
        locations.push((lib.path.join("steamapps/common"), "steam-library"));
    }

    let mut seen = HashSet::new();
    let mut out = Vec::new();

    for (location, source) in locations {
        if !location.exists() {
            continue;
        }

        let Ok(entries) = fs::read_dir(&location) else {
            continue;
        };

        for entry in entries.flatten() {
            let dir = entry.path();
            if !dir.is_dir() {
                continue;
            }

            let proton_script = dir.join("proton");
            if !proton_script.is_file() {
                continue;
            }

            let ids = {
                let parsed = compat_tool_ids(&dir.join("compatibilitytool.vdf"));
                if parsed.is_empty() {
                    let name = dir
                        .file_name()
                        .and_then(|v| v.to_str())
                        .unwrap_or("proton")
                        .to_owned();
                    vec![(name.clone(), name)]
                } else {
                    parsed
                }
            };

            for (tool_id, display_name) in ids {
                let key = (tool_id.clone(), dir.clone());
                if seen.insert(key) {
                    out.push(ProtonTool {
                        tool_id,
                        display_name,
                        root: dir.clone(),
                        proton_script: proton_script.clone(),
                        source: source.to_owned(),
                    });
                }
            }
        }
    }

    out.sort_by_key(|t| (t.display_name.to_lowercase(), t.root.clone()));
    Ok(out)
}

pub fn compat_tool_mapping(root: &Path) -> HashMap<String, String> {
    let mut mapping = HashMap::new();

    for path in [
        root.join("config/config.vdf"),
        root.join("config/localconfig.vdf"),
    ] {
        if !path.exists() {
            continue;
        }

        let Ok(data) = parse_vdf_file(&path) else {
            continue;
        };

        let mut matches = Vec::new();
        find_objects(&data, "CompatToolMapping", &mut matches);

        for map in matches {
            for (app_id, value) in map {
                if let Kv::Object(meta) = value {
                    if let Some(name) = string_at(meta, "name") {
                        if !name.is_empty() {
                            mapping.insert(app_id.clone(), name.to_owned());
                        }
                    }
                }
            }
        }
    }

    mapping
}

/// The per-game compatdata/version file records the Proton tool used when
/// that prefix was last updated. This is read-only evidence, NOT permission to
/// guess a runtime or an indication that a game can be launched outside Steam.
fn recorded_prefix_proton(game: &GameInstall) -> Result<Option<String>> {
    let file = game.compatdata_dir.join("version");
    let meta = match fs::symlink_metadata(&file) {
        Ok(meta) => meta,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(err) => return Err(err).with_context(|| format!("checking {}", file.display())),
    };
    if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 4096 {
        return Err(anyhow!("unsafe Proton version record: {}", file.display()));
    }
    let raw = fs::read_to_string(&file)
        .with_context(|| format!("reading Proton version record {}", file.display()))?;
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.len() > 256 || trimmed.contains('\n')
        || trimmed.contains('\r') || trimmed.chars().any(|ch| ch.is_control()) {
        return Err(anyhow!("invalid Proton version record for AppID {}", game.app_id));
    }
    Ok(Some(trimmed.to_owned()))
}

/// Match the exact Steam tool name, display name, or installed folder name.
/// Multiple identities for the SAME script are harmless; separate matching
/// installations are ambiguous and must remain blocked.
fn unique_tool_matching(tools: &[ProtonTool], wanted: &str) -> Option<ProtonTool> {
    let matches = tools.iter().filter(|tool| {
        tool.tool_id.eq_ignore_ascii_case(wanted)
            || tool.display_name.eq_ignore_ascii_case(wanted)
            || tool.root.file_name().and_then(|name| name.to_str())
                .map(|name| name.eq_ignore_ascii_case(wanted)).unwrap_or(false)
    }).collect::<Vec<_>>();
    let first = *matches.first()?;
    let same_script = matches.iter().all(|tool|
        fs::canonicalize(&tool.proton_script).ok()
            == fs::canonicalize(&first.proton_script).ok());
    if same_script { Some(first.clone()) } else { None }
}

pub fn choose_proton(
    game: &GameInstall,
    root: &Path,
    tools: &[ProtonTool],
    explicit: Option<&str>,
) -> Result<(Option<ProtonTool>, String)> {
    if let Some(explicit) = explicit {
        let candidate = PathBuf::from(explicit);
        let proton_script = if candidate.file_name().and_then(|v| v.to_str()) == Some("proton") {
            candidate.clone()
        } else {
            candidate.join("proton")
        };

        if proton_script.is_file() {
            let root_dir = proton_script
                .parent()
                .map(Path::to_path_buf)
                .ok_or_else(|| anyhow!("invalid proton path"))?;
            let name = root_dir
                .file_name()
                .and_then(|v| v.to_str())
                .unwrap_or("proton")
                .to_owned();

            return Ok((
                Some(ProtonTool {
                    tool_id: name.clone(),
                    display_name: name,
                    root: root_dir,
                    proton_script,
                    source: "explicit".into(),
                }),
                "explicit path".into(),
            ));
        }

        if let Some(tool) = tools.iter().find(|tool| {
            tool.tool_id == explicit || tool.display_name.eq_ignore_ascii_case(explicit)
        }) {
            return Ok((Some(tool.clone()), "explicit id".into()));
        }

        return Ok((None, format!("explicit Proton not found: {explicit}")));
    }

    let mapping = compat_tool_mapping(root);
    let selected = mapping
        .get(&game.app_id.to_string())
        .or_else(|| mapping.get("0"));

    if let Some(selected) = selected {
        if let Some(tool) = unique_tool_matching(tools, selected) {
            return Ok((
                Some(tool),
                format!("Steam CompatToolMapping ({selected})"),
            ));
        }
        return Ok((
            None,
            format!("Steam selected {selected:?}, but no uniquely matching installed Proton script was found"),
        ));
    }

    // Steam often stores the active per-game tool under compatdata/<appid>/
    // version without creating an explicit CompatToolMapping. Only use an
    // exact, unique tool match; never choose the newest or the only Proton.
    if let Some(recorded) = recorded_prefix_proton(game)? {
        if let Some(tool) = unique_tool_matching(tools, &recorded) {
            return Ok((Some(tool), format!("Steam compatdata version ({recorded})")));
        }
        return Ok((None, format!(
            "Steam prefix records Proton {recorded:?}, but no uniquely matching installed tool was found"
        )));
    }

    Ok((None, "neither an explicit Steam CompatToolMapping nor a per-game compatdata/version record was found".into()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn proton_fixture() -> (PathBuf, GameInstall, Vec<ProtonTool>) {
        use std::sync::atomic::{AtomicU64, Ordering};
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "gameweld-proton-selection-{}-{}", std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)));
        let compat = root.join("library/steamapps/compatdata/3008130");
        let proton = root.join("compatibilitytools.d/Proton-CachyOS/proton");
        fs::create_dir_all(&compat).unwrap();
        fs::create_dir_all(proton.parent().unwrap()).unwrap();
        fs::write(&proton, b"#!/bin/sh\nexit 0\n").unwrap();
        let game = GameInstall {
            app_id: 3008130, name: "Test Game".into(),
            install_dir: root.join("library/steamapps/common/Test Game"),
            library_root: root.join("library"),
            manifest: root.join("library/steamapps/appmanifest_3008130.acf"),
            compatdata_dir: compat.clone(),
            prefix_dir: compat.join("pfx"),
        };
        let tool = ProtonTool {
            tool_id: "Proton-CachyOS".into(), display_name: "Proton-CachyOS".into(),
            root: proton.parent().unwrap().to_path_buf(),
            proton_script: proton, source: "test".into(),
        };
        (root, game, vec![tool])
    }

    #[test]
    fn chooses_exact_recorded_per_game_proton_when_mapping_absent() {
        let (root, game, tools) = proton_fixture();
        fs::write(game.compatdata_dir.join("version"), "proton-cachyos\n").unwrap();
        let (selected, source) = choose_proton(&game, &root, &tools, None).unwrap();
        assert_eq!(selected.unwrap().tool_id, "Proton-CachyOS");
        assert!(source.contains("compatdata version"));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn refuses_missing_or_ambiguous_prefix_version() {
        let (root, game, mut tools) = proton_fixture();
        assert!(choose_proton(&game, &root, &tools, None).unwrap().0.is_none());
        fs::write(game.compatdata_dir.join("version"), "Uninstalled-Proton\n").unwrap();
        assert!(choose_proton(&game, &root, &tools, None).unwrap().0.is_none());
        fs::write(game.compatdata_dir.join("version"), "Proton-CachyOS\n").unwrap();
        let mut duplicate = tools[0].clone();
        let other = root.join("other/Proton-CachyOS/proton");
        fs::create_dir_all(other.parent().unwrap()).unwrap();
        fs::write(&other, "not the same executable").unwrap();
        duplicate.root = other.parent().unwrap().to_path_buf();
        duplicate.proton_script = other;
        tools.push(duplicate);
        assert!(choose_proton(&game, &root, &tools, None).unwrap().0.is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn unsafe_version_records_are_rejected() {
        let (root, game, tools) = proton_fixture();
        let version = game.compatdata_dir.join("version");
        fs::write(&version, "Proton-CachyOS\nInjected\n").unwrap();
        assert!(choose_proton(&game, &root, &tools, None).is_err());
        fs::remove_file(&version).unwrap();
        #[cfg(unix)]
        {
            std::os::unix::fs::symlink("/etc/hosts", &version).unwrap();
            assert!(choose_proton(&game, &root, &tools, None).is_err());
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn parses_libraryfolders() {
        let data = parse_vdf_text(
            r#"
            "libraryfolders"
            {
                "0" { "path" "/home/test/.local/share/Steam" }
                "1" { "path" "/mnt/games/SteamLibrary" }
            }
            "#,
        )
        .unwrap();

        let mut found = Vec::new();
        find_objects(&data, "libraryfolders", &mut found);
        assert_eq!(found.len(), 1);
        assert_eq!(
            object_at(found[0], "1")
                .and_then(|v| string_at(v, "path")),
            Some("/mnt/games/SteamLibrary")
        );
    }

    #[test]
    fn parses_compat_mapping() {
        let data = parse_vdf_text(
            r#"
            "Steam"
            {
                "CompatToolMapping"
                {
                    "123"
                    {
                        "name" "GE-Proton10-18"
                    }
                }
            }
            "#,
        )
        .unwrap();

        let mut found = Vec::new();
        find_objects(&data, "CompatToolMapping", &mut found);
        assert_eq!(
            object_at(found[0], "123")
                .and_then(|v| string_at(v, "name")),
            Some("GE-Proton10-18")
        );
    }
}
