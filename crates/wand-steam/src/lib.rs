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
        if let Some(tool) = tools.iter().find(|tool| {
            tool.tool_id == *selected
                || tool.display_name == *selected
                || tool
                    .root
                    .file_name()
                    .and_then(|v| v.to_str())
                    .map(|v| v == selected)
                    .unwrap_or(false)
        }) {
            return Ok((
                Some(tool.clone()),
                format!("Steam CompatToolMapping ({selected})"),
            ));
        }

        return Ok((
            None,
            format!(
                "Steam selected {selected:?}, but its compatibility-tool directory was not found"
            ),
        ));
    }

    Ok((None, "no explicit Steam CompatToolMapping found".into()))
}

#[cfg(test)]
mod tests {
    use super::*;

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
