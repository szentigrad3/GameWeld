use adw::prelude::*;
use std::{
    cell::RefCell,
    fs,
    path::{Path, PathBuf},
    process::Command as ProcessCommand,
    rc::Rc,
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};
use uuid::Uuid;
use wand_client::WandClient;
use wand_core::{
    GameInstall, GameProfile, Preferences, ProviderDescriptor, ProtonTool,
    SessionRecord, SessionState,
};

fn nonempty(text: &str) -> Option<String> {
    let value = text.trim();
    if value.is_empty() {
        None
    } else {
        Some(value.to_owned())
    }
}

#[derive(Debug, Clone)]
struct HelperOutcome {
    success: bool,
    output: String,
}

fn helper_script(name: &str) -> Option<PathBuf> {
    if let Some(root) = std::env::var_os("WAND_NATIVE_ROOT") {
        let path = PathBuf::from(root).join("scripts").join(name);
        if path.is_file() {
            return Some(path);
        }
    }

    let data_home = std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
                .join(".local/share")
        });
    let installed = data_home.join("wand-native/scripts").join(name);
    if installed.is_file() {
        return Some(installed);
    }

    let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("scripts")
        .join(name);
    source.is_file().then_some(source)
}

fn run_helper_background(
    title: &str,
    script_name: &str,
    args: Vec<String>,
    status: &gtk::Label,
    output: &gtk::TextView,
    buttons: Vec<gtk::Button>,
) {
    let Some(script) = helper_script(script_name) else {
        status.set_text(&format!("{title}: helper is missing"));
        output
            .buffer()
            .set_text(&format!("Could not locate helper script: {script_name}"));
        return;
    };

    status.set_text(&format!("{title}: working…"));
    output.buffer().set_text(&format!(
        "Running {} {}\n",
        script.display(),
        args.join(" ")
    ));
    for button in &buttons {
        button.set_sensitive(false);
    }

    let result = Arc::new(Mutex::new(None::<HelperOutcome>));
    let worker_result = Arc::clone(&result);
    thread::spawn(move || {
        let outcome = match ProcessCommand::new(&script).args(&args).output() {
            Ok(command_output) => {
                let mut text = String::new();
                text.push_str(&String::from_utf8_lossy(&command_output.stdout));
                if !command_output.stderr.is_empty() {
                    if !text.is_empty() && !text.ends_with('\n') {
                        text.push('\n');
                    }
                    text.push_str(&String::from_utf8_lossy(&command_output.stderr));
                }
                HelperOutcome {
                    success: command_output.status.success(),
                    output: text,
                }
            }
            Err(error) => HelperOutcome {
                success: false,
                output: format!("Failed to start {}: {error}", script.display()),
            },
        };

        if let Ok(mut slot) = worker_result.lock() {
            *slot = Some(outcome);
        }
    });

    let title = title.to_string();
    let status = status.clone();
    let output = output.clone();
    gtk::glib::timeout_add_local(Duration::from_millis(200), move || {
        let outcome = result.lock().ok().and_then(|mut slot| slot.take());
        let Some(outcome) = outcome else {
            return gtk::glib::ControlFlow::Continue;
        };

        status.set_text(&format!(
            "{}: {}",
            title,
            if outcome.success { "complete" } else { "failed" }
        ));
        output.buffer().set_text(if outcome.output.trim().is_empty() {
            if outcome.success {
                "Completed successfully."
            } else {
                "The helper failed without producing output."
            }
        } else {
            &outcome.output
        });
        for button in &buttons {
            button.set_sensitive(true);
        }
        gtk::glib::ControlFlow::Break
    });
}

fn render_session(session: &SessionRecord) -> String {
    let mut text = String::new();

    for event in &session.events {
        text.push_str(&format!(
            "{}  {:<18}  {}\n",
            event.at.format("%H:%M:%S"),
            format!("{:?}", event.state),
            event.message
        ));
    }

    if let Some(error) = &session.error {
        text.push_str(&format!("\nError: {error}\n"));
    }

    text
}

fn render_logs(client: &WandClient, view: &gtk::TextView) {
    match client.logs(250) {
        Ok(records) => {
            let text = records
                .into_iter()
                .map(|record| {
                    format!(
                        "{} {:<5} {:<24} {}  {}\n",
                        record.timestamp.format("%Y-%m-%d %H:%M:%S"),
                        record.level,
                        record.event,
                        record.message,
                        record.fields
                    )
                })
                .collect::<String>();
            view.buffer().set_text(&text);
        }
        Err(error) => {
            view.buffer()
                .set_text(&format!("Could not read wandd logs: {error}"));
        }
    }
}

fn render_processes(
    client: &WandClient,
    app_id: u32,
    view: &gtk::TextView,
) {
    match client.processes(app_id) {
        Ok(probe) => {
            let mut text = format!(
                "Steam AppID: {}\nBest candidate PID: {:?}\n\n",
                probe.app_id, probe.best_candidate_pid
            );

            for process in probe.candidates {
                text.push_str(&format!(
                    "PID {:>7}  score {:>4}  {:?}\n",
                    process.pid, process.score, process.role
                ));
                text.push_str(&format!(
                    "  parent: {:?}\n  comm: {}\n  exe: {:?}\n  windows: {:?}\n  cmd: {}\n\n",
                    process.parent_pid,
                    process.comm,
                    process.exe,
                    process.windows_executable,
                    process.cmdline
                ));
            }

            view.buffer().set_text(&text);
        }
        Err(error) => {
            view.buffer()
                .set_text(&format!("Process probe failed: {error}"));
        }
    }
}

fn is_terminal(state: &SessionState) -> bool {
    matches!(state, SessionState::Stopped | SessionState::Failed)
}

fn set_dropdown_items(
    dropdown: &gtk::DropDown,
    values: impl IntoIterator<Item = String>,
    active: Option<&str>,
) {
    let mut materialized: Vec<String> = values.into_iter().collect();

    if let Some(active) = active {
        if !materialized.iter().any(|value| value == active) {
            materialized.push(active.to_owned());
        }
    }

    let selected = active
        .and_then(|active| materialized.iter().position(|value| value == active))
        .unwrap_or(0) as u32;

    let refs: Vec<&str> = materialized.iter().map(String::as_str).collect();
    let model = gtk::StringList::new(&refs);
    dropdown.set_model(Some(&model));
    dropdown.set_selected(selected);
}

fn dropdown_active_text(dropdown: &gtk::DropDown) -> Option<String> {
    let item = dropdown.selected_item()?;
    let string = item.downcast::<gtk::StringObject>().ok()?;
    Some(string.string().to_string())
}

fn prepend_history_row(history: &gtk::ListBox, session: &SessionRecord) {
    let row = gtk::ListBoxRow::new();
    let box_ = gtk::Box::new(gtk::Orientation::Vertical, 2);
    box_.set_margin_top(7);
    box_.set_margin_bottom(7);
    box_.set_margin_start(10);
    box_.set_margin_end(10);

    let title = gtk::Label::new(Some(&format!(
        "{} — {:?}",
        session.game_name, session.state
    )));
    title.set_xalign(0.0);
    box_.append(&title);

    let subtitle = gtk::Label::new(Some(&format!(
        "{} • {} • {}",
        session.id,
        session.provider_id,
        session.updated_at.format("%Y-%m-%d %H:%M:%S")
    )));
    subtitle.set_xalign(0.0);
    subtitle.add_css_class("dim-label");
    subtitle.set_ellipsize(gtk::pango::EllipsizeMode::Middle);
    box_.append(&subtitle);

    row.set_child(Some(&box_));
    history.prepend(&row);
}

fn populate_history(client: &WandClient, history: &gtk::ListBox) {
    while let Some(child) = history.first_child() {
        history.remove(&child);
    }

    if let Ok(mut sessions) = client.sessions() {
        sessions.sort_by_key(|session| session.updated_at);

        for session in sessions.into_iter().rev().take(12) {
            prepend_history_row(history, &session);
        }
    }
}

fn fill_game_details(
    client: &WandClient,
    game: &GameInstall,
    title: &gtk::Label,
    app_id: &gtk::Label,
    proton_combo: &gtk::DropDown,
    provider_combo: &gtk::DropDown,
    trainer: &gtk::Entry,
    status: &gtk::Label,
    provider_health: &gtk::Label,
    providers: &[ProviderDescriptor],
    protons: &[ProtonTool],
) {
    title.set_text(&game.name);
    app_id.set_text(&format!("App ID: {}", game.app_id));

    match client.inspect(game.app_id) {
        Ok(inspect) => {
            let profile = inspect.profile;

            let provider_value = profile
                .as_ref()
                .and_then(|profile| profile.provider_id.clone())
                .unwrap_or_else(|| "generic-exe".into());

            set_dropdown_items(
                provider_combo,
                providers.iter().map(|provider| provider.id.clone()),
                Some(&provider_value),
            );

            let proton_value = profile
                .as_ref()
                .and_then(|profile| profile.preferred_proton.clone())
                .or_else(|| {
                    inspect
                        .proton
                        .as_ref()
                        .map(|proton| proton.tool_id.clone())
                });

            set_dropdown_items(
                proton_combo,
                std::iter::once("Steam selected".to_string())
                    .chain(protons.iter().map(|proton| proton.tool_id.clone())),
                proton_value.as_deref(),
            );

            let trainer_value = profile
                .as_ref()
                .and_then(|profile| profile.trainer.clone())
                .map(|path| path.display().to_string())
                .unwrap_or_default();
            trainer.set_text(&trainer_value);

            let running = if inspect.running_processes.is_empty() {
                "not running"
            } else {
                "running"
            };

            status.set_text(&format!(
                "{} • {} • {}",
                running,
                inspect.proton_reason,
                inspect
                    .proton
                    .as_ref()
                    .map(|proton| proton.display_name.as_str())
                    .unwrap_or("Proton unresolved")
            ));

            match client.provider_health(Some(provider_value), Some(game.app_id)) {
                Ok(health) => {
                    if let Some(health) = health.first() {
                        provider_health.set_text(&format!(
                            "Provider: {} • {}",
                            health.status,
                            health.details.join(" ")
                        ));
                    }
                }
                Err(error) => {
                    provider_health.set_text(&format!(
                        "Provider health unavailable: {error}"
                    ));
                }
            }
        }
        Err(error) => {
            status.set_text(&format!("Inspect failed: {error}"));
        }
    }
}

fn open_preferences(
    parent: &adw::ApplicationWindow,
    client: WandClient,
    providers: Rc<Vec<ProviderDescriptor>>,
    onboarding: gtk::Box,
) {
    let preferences = client.preferences().unwrap_or_default();

    let window = gtk::Window::builder()
        .title("Wand Preferences")
        .transient_for(parent)
        .modal(true)
        .default_width(520)
        .default_height(320)
        .build();

    let root = gtk::Box::new(gtk::Orientation::Vertical, 12);
    root.set_margin_top(18);
    root.set_margin_bottom(18);
    root.set_margin_start(18);
    root.set_margin_end(18);

    let heading = gtk::Label::new(Some("Wand Native setup"));
    heading.set_xalign(0.0);
    heading.add_css_class("title-2");
    root.append(&heading);

    let default_provider = gtk::DropDown::new(None::<gtk::gio::ListModel>, None::<gtk::Expression>);
    set_dropdown_items(
        &default_provider,
        providers.iter().map(|provider| provider.id.clone()),
        Some(&preferences.default_provider),
    );

    let provider_row = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    provider_row.append(&gtk::Label::new(Some("Default provider")));
    provider_row.append(&default_provider);
    root.append(&provider_row);

    let launch_game =
        gtk::CheckButton::with_label("Launch the Steam game automatically");
    launch_game.set_active(preferences.launch_game_automatically);
    root.append(&launch_game);

    let diagnostics = gtk::Entry::new();
    diagnostics.set_hexpand(true);
    diagnostics.set_placeholder_text(Some(
        "Diagnostics directory (blank = Desktop)",
    ));
    if let Some(path) = &preferences.diagnostics_directory {
        diagnostics.set_text(&path.display().to_string());
    }
    root.append(&diagnostics);

    let explanation = gtk::Label::new(Some(
        "Wand Native can start a managed one-Proton session for Wand plus the selected game without using Steam Launch Options.",
    ));
    explanation.set_xalign(0.0);
    explanation.set_wrap(true);
    root.append(&explanation);

    let actions = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let cancel = gtk::Button::with_label("Cancel");
    let save = gtk::Button::with_label("Save");
    save.add_css_class("suggested-action");
    actions.append(&cancel);
    actions.append(&save);
    root.append(&actions);

    {
        let window = window.clone();
        cancel.connect_clicked(move |_| window.close());
    }

    {
        let window = window.clone();
        let client = client.clone();
        let onboarding = onboarding.clone();

        save.connect_clicked(move |_| {
            let default_provider = dropdown_active_text(&default_provider)
                .unwrap_or_else(|| "generic-exe".into());

            let preferences = Preferences {
                onboarding_complete: true,
                default_provider,
                launch_game_automatically: launch_game.is_active(),
                diagnostics_directory: nonempty(&diagnostics.text())
                    .map(PathBuf::from),
            };

            if client.set_preferences(preferences).is_ok() {
                onboarding.set_visible(false);
                window.close();
            }
        });
    }

    window.set_child(Some(&root));
    window.present();
}

fn poll_session(
    client: WandClient,
    session_id: Uuid,
    state_label: gtk::Label,
    timeline: gtk::TextView,
    stop_button: gtk::Button,
    diagnostics_button: gtk::Button,
    history: gtk::ListBox,
    logs: gtk::TextView,
) {
    gtk::glib::timeout_add_local(Duration::from_millis(750), move || {
        match client.session(session_id) {
            Ok(session) => {
                state_label.set_text(&format!(
                    "Session: {:?}  •  {}",
                    session.state, session.id
                ));

                timeline.buffer().set_text(&render_session(&session));

                stop_button.set_sensitive(session.state == SessionState::Running);
                diagnostics_button.set_sensitive(true);

                if is_terminal(&session.state) {
                    prepend_history_row(&history, &session);
                    render_logs(&client, &logs);
                    return gtk::glib::ControlFlow::Break;
                }
            }
            Err(error) => {
                state_label.set_text(&format!(
                    "Session update failed: {error}"
                ));
                return gtk::glib::ControlFlow::Break;
            }
        }

        gtk::glib::ControlFlow::Continue
    });
}

fn install_wand_theme() {
    let provider = gtk::CssProvider::new();
    provider.load_from_data(include_str!("theme.css"));
    if let Some(display) = gtk::gdk::Display::default() {
        gtk::style_context_add_provider_for_display(
            &display,
            &provider,
            gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
        );
    }
}

fn asset_path(name: &str) -> PathBuf {
    if let Some(root) = std::env::var_os("WAND_NATIVE_ROOT") {
        let root = PathBuf::from(root);
        for candidate in [
            root.join("assets").join(name),
            root.join("crates/wand-ui/assets").join(name),
        ] {
            if candidate.is_file() {
                return candidate;
            }
        }
    }

    let data_home = std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
                .join(".local/share")
        });
    let installed = data_home.join("wand-native/assets").join(name);
    if installed.is_file() {
        return installed;
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("assets")
        .join(name)
}

fn asset_dir_path(relative: &str) -> PathBuf {
    if let Some(root) = std::env::var_os("WAND_NATIVE_ROOT") {
        let root = PathBuf::from(root);
        for candidate in [
            root.join("assets").join(relative),
            root.join("crates/wand-ui/assets").join(relative),
        ] {
            if candidate.is_dir() {
                return candidate;
            }
        }
    }

    let data_home = std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default())
                .join(".local/share")
        });
    let installed = data_home.join("wand-native/assets").join(relative);
    if installed.is_dir() {
        return installed;
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("assets")
        .join(relative)
}

#[derive(Clone, Copy)]
enum ArtworkKind {
    Hero,
    Cover,
}

fn image_file(path: &Path) -> bool {
    path.is_file()
        && path
            .extension()
            .and_then(|ext| ext.to_str())
            .map(|ext| matches!(ext.to_ascii_lowercase().as_str(), "png" | "jpg" | "jpeg" | "webp"))
            .unwrap_or(false)
}

fn first_named_art(dir: &Path, app_id: Option<u32>, kind: ArtworkKind) -> Option<PathBuf> {
    // Steam has used both a legacy flat cache and a newer hashed layout. Keep
    // exact artwork names ahead of any heuristic scan so logos/blur variants
    // never replace the real library hero by accident.
    let stems: &[&str] = match kind {
        ArtworkKind::Hero => &["library_hero", "library_header", "hero", "header"],
        ArtworkKind::Cover => &["library_600x900_2x", "library_600x900", "cover", "600x900", "portrait"],
    };
    for stem in stems {
        for ext in ["png", "jpg", "jpeg", "webp"] {
            let filename = app_id
                .map(|id| format!("{id}_{stem}.{ext}"))
                .unwrap_or_else(|| format!("{stem}.{ext}"));
            let path = dir.join(filename);
            if path.is_file() {
                return Some(path);
            }
        }
    }
    None
}

fn artwork_name_score(path: &Path, kind: ArtworkKind) -> i64 {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();

    // Never use Steam's intentionally blurred library background or a logo as
    // the full hero/cover. Those were the cause of the smeared symbol images
    // seen in UI Test 5 on several real games.
    if name.contains("blur") || name.contains("logo") || name.contains("icon") {
        return i64::MIN;
    }

    match kind {
        ArtworkKind::Hero => {
            if name.contains("library_hero") { 50 }
            else if name.contains("library_header") { 40 }
            else if name.contains("header") { 30 }
            else if name.contains("hero") { 20 }
            else { 0 }
        }
        ArtworkKind::Cover => {
            if name.contains("library_600x900_2x") { 50 }
            else if name.contains("library_600x900") { 40 }
            else if name.contains("600x900") { 30 }
            else if name.contains("portrait") || name.contains("cover") { 20 }
            else { 0 }
        }
    }
}

fn scan_steam_art_tree(
    dir: &Path,
    app_id: u32,
    kind: ArtworkKind,
    require_app_prefix: bool,
    depth: usize,
) -> Option<PathBuf> {
    let id = app_id.to_string();
    let mut best: Option<(i64, PathBuf)> = None;
    let entries = fs::read_dir(dir).ok()?;

    for entry in entries.filter_map(Result::ok) {
        let path = entry.path();
        if path.is_dir() && depth > 0 {
            if let Some(candidate) = scan_steam_art_tree(&path, app_id, kind, false, depth - 1) {
                let score = artwork_name_score(&candidate, kind);
                if score > best.as_ref().map(|(s, _)| *s).unwrap_or(i64::MIN) {
                    best = Some((score, candidate));
                }
            }
            continue;
        }
        if !image_file(&path) {
            continue;
        }
        let filename = path.file_name().and_then(|n| n.to_str()).unwrap_or_default();
        if require_app_prefix && !filename.starts_with(&id) {
            continue;
        }
        let score = artwork_name_score(&path, kind);
        if score == i64::MIN {
            continue;
        }
        if score > best.as_ref().map(|(s, _)| *s).unwrap_or(i64::MIN) {
            best = Some((score, path));
        }
    }
    best.map(|(_, path)| path)
}

fn game_artwork_path(game: &GameInstall, kind: ArtworkKind) -> Option<PathBuf> {
    let app_id = game.app_id;

    if let Some(root) = std::env::var_os("WAND_NATIVE_ARTWORK_DIR").map(PathBuf::from) {
        if let Some(path) = first_named_art(&root.join(app_id.to_string()), None, kind) {
            return Some(path);
        }
    }

    let data_home = std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/share")));
    if let Some(data_home) = data_home {
        if let Some(path) = first_named_art(
            &data_home.join("wand-native/artwork").join(app_id.to_string()),
            None,
            kind,
        ) {
            return Some(path);
        }
    }

    let curated = asset_dir_path(&format!("games/{app_id}"));
    if let Some(path) = first_named_art(&curated, None, kind) {
        return Some(path);
    }

    let mut steam_roots = Vec::new();
    if let Some(root) = std::env::var_os("STEAM_COMPAT_CLIENT_INSTALL_PATH") {
        steam_roots.push(PathBuf::from(root).join("appcache/librarycache"));
    }
    if let Some(home) = std::env::var_os("HOME").map(PathBuf::from) {
        steam_roots.push(home.join(".local/share/Steam/appcache/librarycache"));
        steam_roots.push(home.join(".steam/steam/appcache/librarycache"));
        steam_roots.push(home.join(".steam/root/appcache/librarycache"));
    }

    for root in steam_roots {
        // Legacy flat cache: <appid>_library_hero.jpg etc.
        if let Some(path) = first_named_art(&root, Some(app_id), kind) {
            return Some(path);
        }

        // Current Steam cache can be <appid>/<asset-hash>/library_hero.jpg.
        // Walk a few levels below the app id before falling back to the flat
        // heuristic scan. This keeps each selected title tied to its own art.
        let app_dir = root.join(app_id.to_string());
        if let Some(path) = first_named_art(&app_dir, None, kind)
            .or_else(|| scan_steam_art_tree(&app_dir, app_id, kind, false, 3))
            .or_else(|| scan_steam_art_tree(&root, app_id, kind, true, 0))
        {
            return Some(path);
        }
    }
    None
}

fn set_game_artwork(hero: &gtk::Picture, cover: &gtk::Picture, game: &GameInstall) {
    let hero_path = game_artwork_path(game, ArtworkKind::Hero);
    let cover_path = game_artwork_path(game, ArtworkKind::Cover);
    let hero_final = hero_path.as_ref().or(cover_path.as_ref());
    let cover_final = cover_path.as_ref().or(hero_path.as_ref());
    hero.set_filename(hero_final);
    cover.set_filename(cover_final);
}

fn icon_image(name: &str, pixel_size: i32) -> gtk::Image {
    let image = gtk::Image::from_icon_name(name);
    image.set_pixel_size(pixel_size);
    image
}

fn nav_button(icon: &str, label: &str) -> gtk::Button {
    let button = gtk::Button::new();
    button.add_css_class("wand-nav-button");

    let row = gtk::Box::new(gtk::Orientation::Horizontal, 16);
    row.set_margin_start(4);
    row.set_margin_end(4);
    row.append(&icon_image(icon, 24));

    let text = gtk::Label::new(Some(label));
    text.set_xalign(0.0);
    text.set_hexpand(true);
    text.add_css_class("wand-nav-label");
    row.append(&text);

    button.set_child(Some(&row));
    button
}

fn badge(text: &str) -> gtk::Label {
    let label = gtk::Label::new(Some(text));
    label.add_css_class("wand-badge");
    label
}

fn status_row(icon: &str, key: &str, value: &str) -> (gtk::Box, gtk::Label) {
    let row = gtk::Box::new(gtk::Orientation::Horizontal, 9);
    row.append(&icon_image(icon, 18));

    let key_label = gtk::Label::new(Some(key));
    key_label.set_width_chars(8);
    key_label.set_xalign(0.0);
    key_label.add_css_class("wand-status-key");
    row.append(&key_label);

    let value_label = gtk::Label::new(Some(value));
    value_label.set_xalign(0.0);
    value_label.set_hexpand(true);
    value_label.set_ellipsize(gtk::pango::EllipsizeMode::End);
    value_label.add_css_class("wand-status-value");
    row.append(&value_label);

    (row, value_label)
}

fn quick_action(icon: &str, label: &str) -> gtk::Button {
    let button = gtk::Button::new();
    button.add_css_class("wand-quick-action");

    let row = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    row.append(&icon_image(icon, 18));

    let text = gtk::Label::new(Some(label));
    text.set_xalign(0.0);
    text.set_hexpand(true);
    row.append(&text);

    row.append(&icon_image("go-next-symbolic", 14));
    button.set_child(Some(&row));
    button
}

fn info_card(icon: &str, title: &str, body: &str, state: &str) -> (gtk::Box, gtk::Label, gtk::Label) {
    let card = gtk::Box::new(gtk::Orientation::Vertical, 8);
    card.add_css_class("wand-info-card");
    card.set_hexpand(true);

    let head = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    head.append(&icon_image(icon, 28));

    let text_box = gtk::Box::new(gtk::Orientation::Vertical, 2);
    text_box.set_hexpand(true);
    let title_label = gtk::Label::new(Some(title));
    title_label.set_xalign(0.0);
    title_label.add_css_class("wand-card-title");
    text_box.append(&title_label);

    let body_label = gtk::Label::new(Some(body));
    body_label.set_xalign(0.0);
    body_label.set_wrap(true);
    body_label.add_css_class("wand-card-copy");
    text_box.append(&body_label);
    head.append(&text_box);
    card.append(&head);

    let state_label = badge(state);
    state_label.set_halign(gtk::Align::Center);
    card.append(&state_label);

    (card, body_label, state_label)
}

fn build_ui(app: &adw::Application) {
    install_wand_theme();
    let client = WandClient::default();

    let window = adw::ApplicationWindow::builder()
        .application(app)
        .title("Wand Native 0.1.42")
        .default_width(1536)
        .default_height(1024)
        .build();
    window.set_decorated(false);

    let games = Rc::new(client.games().unwrap_or_default());
    let providers = Rc::new(client.providers().unwrap_or_default());
    let protons = Rc::new(client.protons().unwrap_or_default());
    let preferences = client.preferences().unwrap_or_default();

    let selected_game: Rc<RefCell<Option<GameInstall>>> = Rc::new(RefCell::new(None));
    let current_session: Rc<RefCell<Option<Uuid>>> = Rc::new(RefCell::new(None));

    let root = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    root.add_css_class("wand-root");

    // ---------------------------------------------------------------------
    // Left navigation rail
    // ---------------------------------------------------------------------
    let sidebar = gtk::Box::new(gtk::Orientation::Vertical, 12);
    sidebar.add_css_class("wand-sidebar");
    sidebar.set_size_request(268, -1);

    let brand_row = gtk::Box::new(gtk::Orientation::Horizontal, 12);
    brand_row.add_css_class("wand-brand-row");
    let logo = gtk::Picture::for_filename(asset_path("wand-logo-reference.png"));
    logo.set_size_request(58, 48);
    logo.set_content_fit(gtk::ContentFit::Contain);
    brand_row.append(&logo);

    let brand_text = gtk::Box::new(gtk::Orientation::Vertical, 0);
    let brand = gtk::Label::new(Some("Wand Native"));
    brand.set_xalign(0.0);
    brand.add_css_class("wand-brand");
    brand_text.append(&brand);
    let version = gtk::Label::new(Some(&format!("v{}", env!("CARGO_PKG_VERSION"))));
    version.set_xalign(0.0);
    version.add_css_class("wand-version");
    brand_text.append(&version);
    brand_row.append(&brand_text);
    sidebar.append(&brand_row);

    let nav = gtk::Box::new(gtk::Orientation::Vertical, 6);
    nav.add_css_class("wand-nav");
    let home_nav = nav_button("go-home-symbolic", "Home");
    let library_nav = nav_button("view-grid-symbolic", "Library");
    let setup_nav = nav_button("applications-engineering-symbolic", "Setup");
    let compat_nav = nav_button("emblem-ok-symbolic", "Compatibility");
    let diagnostics_nav = nav_button("utilities-system-monitor-symbolic", "Diagnostics");
    let settings_nav = nav_button("preferences-system-symbolic", "Settings");
    let about_nav = nav_button("dialog-information-symbolic", "About");
    for button in [&home_nav, &library_nav, &setup_nav, &compat_nav, &diagnostics_nav, &settings_nav, &about_nav] {
        nav.append(button);
    }
    home_nav.add_css_class("active");
    sidebar.append(&nav);

    let sidebar_spacer = gtk::Box::new(gtk::Orientation::Vertical, 0);
    sidebar_spacer.set_vexpand(true);
    sidebar.append(&sidebar_spacer);

    let sidebar_status = gtk::Box::new(gtk::Orientation::Vertical, 8);
    sidebar_status.add_css_class("wand-sidebar-status");
    let sidebar_status_head = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    let ok = icon_image("emblem-ok-symbolic", 28);
    ok.add_css_class("wand-green-icon");
    sidebar_status_head.append(&ok);
    let sidebar_status_text = gtk::Box::new(gtk::Orientation::Vertical, 0);
    let status_name = gtk::Label::new(Some("Wand Native"));
    status_name.set_xalign(0.0);
    status_name.add_css_class("wand-card-title");
    sidebar_status_text.append(&status_name);
    let status_version = gtk::Label::new(Some(&format!("v{}", env!("CARGO_PKG_VERSION"))));
    status_version.set_xalign(0.0);
    status_version.add_css_class("wand-card-copy");
    sidebar_status_text.append(&status_version);
    sidebar_status_head.append(&sidebar_status_text);
    sidebar_status.append(&sidebar_status_head);
    let platform = gtk::Label::new(Some("Linux • Proton • Native GUI"));
    platform.set_xalign(0.0);
    platform.add_css_class("wand-subtle");
    sidebar_status.append(&platform);
    let tagline = gtk::Label::new(Some("Play More. Your Way."));
    tagline.set_xalign(0.0);
    tagline.add_css_class("wand-subtle");
    sidebar_status.append(&tagline);
    sidebar.append(&sidebar_status);
    root.append(&sidebar);

    // ---------------------------------------------------------------------
    // Right application surface and top bar
    // ---------------------------------------------------------------------
    let app_surface = gtk::Box::new(gtk::Orientation::Vertical, 0);
    app_surface.set_hexpand(true);
    app_surface.set_vexpand(true);

    let topbar = gtk::Box::new(gtk::Orientation::Horizontal, 14);
    topbar.add_css_class("wand-topbar");
    let search = gtk::SearchEntry::new();
    search.set_placeholder_text(Some("Search your games..."));
    search.set_size_request(470, -1);
    search.add_css_class("wand-search");
    topbar.append(&search);

    let top_spacer = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    top_spacer.set_hexpand(true);
    topbar.append(&top_spacer);

    let steam_top = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    steam_top.append(&icon_image("applications-games-symbolic", 28));
    let steam_top_text = gtk::Box::new(gtk::Orientation::Vertical, 0);
    let steam_title = gtk::Label::new(Some("Steam Detected"));
    steam_title.set_xalign(0.0);
    steam_title.add_css_class("wand-top-status-title");
    steam_top_text.append(&steam_title);
    let steam_online = gtk::Label::new(Some("Online"));
    steam_online.set_xalign(0.0);
    steam_online.add_css_class("wand-status-good");
    steam_top_text.append(&steam_online);
    steam_top.append(&steam_top_text);
    topbar.append(&steam_top);

    let preferences_button = gtk::Button::new();
    preferences_button.add_css_class("wand-title-button");
    preferences_button.set_child(Some(&icon_image("preferences-system-symbolic", 22)));
    preferences_button.set_tooltip_text(Some("Preferences"));
    topbar.append(&preferences_button);

    let top_separator = gtk::Separator::new(gtk::Orientation::Vertical);
    top_separator.add_css_class("wand-top-separator");
    topbar.append(&top_separator);

    let minimize = gtk::Button::with_label("—");
    minimize.add_css_class("wand-window-button");
    let maximize = gtk::Button::with_label("□");
    maximize.add_css_class("wand-window-button");
    let close = gtk::Button::with_label("×");
    close.add_css_class("wand-window-button");
    close.add_css_class("close");
    topbar.append(&minimize);
    topbar.append(&maximize);
    topbar.append(&close);
    app_surface.append(&topbar);

    {
        let window = window.clone();
        minimize.connect_clicked(move |_| window.minimize());
    }
    {
        let window = window.clone();
        maximize.connect_clicked(move |_| {
            if window.is_maximized() {
                window.unmaximize();
            } else {
                window.maximize();
            }
        });
    }
    {
        let window = window.clone();
        close.connect_clicked(move |_| window.close());
    }

    let page_stack = gtk::Stack::new();
    page_stack.set_hexpand(true);
    page_stack.set_vexpand(true);
    page_stack.set_transition_type(gtk::StackTransitionType::Crossfade);
    app_surface.append(&page_stack);
    root.append(&app_surface);

    // Kept for the existing preferences workflow without putting a first-run
    // banner over the approved home composition.
    let onboarding = gtk::Box::new(gtk::Orientation::Horizontal, 0);

    // ---------------------------------------------------------------------
    // Library page / real Steam game list
    // ---------------------------------------------------------------------
    let library_page = gtk::Box::new(gtk::Orientation::Vertical, 14);
    library_page.add_css_class("wand-page");
    let library_title = gtk::Label::new(Some("Library"));
    library_title.set_xalign(0.0);
    library_title.add_css_class("wand-page-title");
    library_page.append(&library_title);
    let library_subtitle = gtk::Label::new(Some("Steam games detected by Wand Native"));
    library_subtitle.set_xalign(0.0);
    library_subtitle.add_css_class("wand-subtle");
    library_page.append(&library_subtitle);

    let game_list = gtk::ListBox::new();
    game_list.set_selection_mode(gtk::SelectionMode::Single);
    game_list.add_css_class("wand-game-list");
    for game in games.iter() {
        let row = gtk::ListBoxRow::new();
        let row_box = gtk::Box::new(gtk::Orientation::Horizontal, 14);
        row_box.set_margin_top(12);
        row_box.set_margin_bottom(12);
        row_box.set_margin_start(14);
        row_box.set_margin_end(14);
        if let Some(art) = game_artwork_path(game, ArtworkKind::Cover)
            .or_else(|| game_artwork_path(game, ArtworkKind::Hero))
        {
            let thumb = gtk::Picture::for_filename(art);
            thumb.set_content_fit(gtk::ContentFit::Cover);
            thumb.set_size_request(64, 84);
            thumb.add_css_class("wand-library-thumb");
            row_box.append(&thumb);
        } else {
            row_box.append(&icon_image("applications-games-symbolic", 28));
        }

        let text = gtk::Box::new(gtk::Orientation::Vertical, 2);
        text.set_hexpand(true);
        let name = gtk::Label::new(Some(&game.name));
        name.set_xalign(0.0);
        name.add_css_class("wand-card-title");
        name.set_ellipsize(gtk::pango::EllipsizeMode::End);
        text.append(&name);
        let id = gtk::Label::new(Some(&format!("Steam • App ID: {}", game.app_id)));
        id.set_xalign(0.0);
        id.add_css_class("wand-card-copy");
        text.append(&id);
        row_box.append(&text);
        row_box.append(&badge("Installed"));
        row.set_child(Some(&row_box));
        game_list.append(&row);
    }
    let library_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .child(&game_list)
        .build();
    library_page.append(&library_scroll);
    page_stack.add_named(&library_page, Some("library"));

    // ---------------------------------------------------------------------
    // Home page — mirrors the approved mockup
    // ---------------------------------------------------------------------
    let home_shell = gtk::Box::new(gtk::Orientation::Horizontal, 14);
    home_shell.add_css_class("wand-home-shell");

    let home_main = gtk::Box::new(gtk::Orientation::Vertical, 10);
    home_main.set_hexpand(true);

    let hero = gtk::Picture::new();
    hero.set_content_fit(gtk::ContentFit::Cover);
    hero.set_size_request(-1, 275);
    hero.add_css_class("wand-hero-art");
    home_main.append(&hero);

    let identity = gtk::Box::new(gtk::Orientation::Vertical, 6);
    identity.add_css_class("wand-game-identity");
    let game_title = gtk::Label::new(Some("Select a Steam game"));
    game_title.set_xalign(0.0);
    game_title.set_ellipsize(gtk::pango::EllipsizeMode::End);
    game_title.add_css_class("wand-game-title");
    identity.append(&game_title);

    let meta = gtk::Box::new(gtk::Orientation::Horizontal, 9);
    meta.append(&icon_image("applications-games-symbolic", 18));
    let steam_meta = gtk::Label::new(Some("Steam"));
    steam_meta.add_css_class("wand-meta");
    meta.append(&steam_meta);
    let meta_sep = gtk::Label::new(Some("│"));
    meta_sep.add_css_class("wand-meta-separator");
    meta.append(&meta_sep);
    let game_app_id = gtk::Label::new(Some("App ID: —"));
    game_app_id.add_css_class("wand-meta");
    meta.append(&game_app_id);
    let meta_sep2 = gtk::Label::new(Some("│"));
    meta_sep2.add_css_class("wand-meta-separator");
    meta.append(&meta_sep2);
    for text in ["Action", "Adventure", "Single Player"] {
        let chip = gtk::Label::new(Some(text));
        chip.add_css_class("wand-chip");
        meta.append(&chip);
    }
    identity.append(&meta);
    home_main.append(&identity);

    let launch_card = gtk::Box::new(gtk::Orientation::Horizontal, 12);
    launch_card.add_css_class("wand-launch-card");
    let play = gtk::Button::new();
    play.add_css_class("wand-play");
    play.set_hexpand(true);
    let play_content = gtk::Box::new(gtk::Orientation::Horizontal, 18);
    play_content.set_halign(gtk::Align::Center);
    let play_icon = icon_image("media-playback-start-symbolic", 32);
    play_icon.add_css_class("wand-play-icon");
    play_content.append(&play_icon);
    let play_text = gtk::Box::new(gtk::Orientation::Vertical, 0);
    let play_title = gtk::Label::new(Some("PLAY WITH WAND"));
    play_title.add_css_class("wand-play-title");
    play_text.append(&play_title);
    let play_sub = gtk::Label::new(Some("Launch game with Wand and trainer"));
    play_sub.add_css_class("wand-play-subtitle");
    play_text.append(&play_sub);
    play_content.append(&play_text);
    play.set_child(Some(&play_content));
    launch_card.append(&play);

    let play_normal = gtk::Button::new();
    play_normal.add_css_class("wand-play-normal");
    play_normal.set_size_request(265, -1);
    let normal_content = gtk::Box::new(gtk::Orientation::Horizontal, 13);
    normal_content.set_halign(gtk::Align::Center);
    normal_content.append(&icon_image("media-playback-start-symbolic", 24));
    let normal_text = gtk::Box::new(gtk::Orientation::Vertical, 0);
    let normal_title = gtk::Label::new(Some("Play Normally"));
    normal_title.add_css_class("wand-normal-title");
    normal_text.append(&normal_title);
    let normal_sub = gtk::Label::new(Some("Launch without Wand"));
    normal_sub.add_css_class("wand-card-copy");
    normal_text.append(&normal_sub);
    normal_content.append(&normal_text);
    play_normal.set_child(Some(&normal_content));
    launch_card.append(&play_normal);
    home_main.append(&launch_card);

    let info_cards = gtk::Box::new(gtk::Orientation::Horizontal, 10);
    let (detected_card, detected_body, detected_state) = info_card(
        "applications-games-symbolic",
        "Game Detected",
        "Select a game from your Library",
        "Installed",
    );
    let (wand_card, wand_body, wand_state) = info_card(
        "emblem-system-symbolic",
        "Wand Ready",
        "Trainer and provider status",
        "Ready",
    );
    let (compat_card, compat_body, compat_state) = info_card(
        "preferences-system-symbolic",
        "Compatibility",
        "GE-Proton-Wand-SHA256",
        "Configured",
    );
    info_cards.append(&detected_card);
    info_cards.append(&wand_card);
    info_cards.append(&compat_card);
    home_main.append(&info_cards);

    let activity_card = gtk::Box::new(gtk::Orientation::Vertical, 0);
    activity_card.add_css_class("wand-activity-card");
    activity_card.set_vexpand(true);
    let activity_head = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    activity_head.add_css_class("wand-panel-header");
    activity_head.append(&icon_image("utilities-terminal-symbolic", 18));
    let activity_title = gtk::Label::new(Some("Activity Log"));
    activity_title.set_xalign(0.0);
    activity_title.set_hexpand(true);
    activity_title.add_css_class("wand-card-title");
    activity_head.append(&activity_title);
    let session_state = gtk::Label::new(Some("No managed session"));
    session_state.set_visible(false);
    activity_head.append(&session_state);
    let clear_log = gtk::Button::with_label("Clear Log");
    clear_log.add_css_class("wand-clear-button");
    activity_head.append(&clear_log);
    activity_card.append(&activity_head);

    let activity_log = gtk::TextView::new();
    activity_log.set_editable(false);
    activity_log.set_cursor_visible(false);
    activity_log.set_monospace(true);
    activity_log.set_wrap_mode(gtk::WrapMode::None);
    activity_log.add_css_class("wand-log");
    let activity_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .min_content_height(180)
        .child(&activity_log)
        .build();
    activity_card.append(&activity_scroll);
    home_main.append(&activity_card);
    home_shell.append(&home_main);

    // Right status rail.
    let status_rail = gtk::Box::new(gtk::Orientation::Vertical, 10);
    status_rail.set_size_request(352, -1);
    status_rail.add_css_class("wand-status-rail");

    let cover_card = gtk::Box::new(gtk::Orientation::Vertical, 0);
    cover_card.add_css_class("wand-cover-card");
    let cover = gtk::Picture::new();
    cover.set_content_fit(gtk::ContentFit::Cover);
    cover.set_size_request(-1, 235);
    cover_card.append(&cover);
    status_rail.append(&cover_card);

    let game_status_card = gtk::Box::new(gtk::Orientation::Vertical, 9);
    game_status_card.add_css_class("wand-status-card");
    let game_status_head = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let game_status_title = gtk::Label::new(Some("Game Status"));
    game_status_title.set_xalign(0.0);
    game_status_title.set_hexpand(true);
    game_status_title.add_css_class("wand-card-title");
    game_status_head.append(&game_status_title);
    let game_ready_badge = badge("●  Ready to Play");
    game_status_head.append(&game_ready_badge);
    game_status_card.append(&game_status_head);
    let (steam_row, steam_value) = status_row("applications-games-symbolic", "Steam:", "Online");
    let (installed_row, installed_value) = status_row("applications-games-symbolic", "Game:", "Installed");
    let (proton_row, proton_value) = status_row("preferences-system-symbolic", "Proton:", "Steam selected");
    let (prefix_row, prefix_value) = status_row("folder-symbolic", "Prefix:", "Compatible");
    game_status_card.append(&steam_row);
    game_status_card.append(&installed_row);
    game_status_card.append(&proton_row);
    game_status_card.append(&prefix_row);
    status_rail.append(&game_status_card);

    let wand_status_card = gtk::Box::new(gtk::Orientation::Vertical, 9);
    wand_status_card.add_css_class("wand-status-card");
    let wand_status_head = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let wand_status_title = gtk::Label::new(Some("Wand Status"));
    wand_status_title.set_xalign(0.0);
    wand_status_title.set_hexpand(true);
    wand_status_title.add_css_class("wand-card-title");
    wand_status_head.append(&wand_status_title);
    let wand_ready_badge = badge("●  Ready");
    wand_status_head.append(&wand_ready_badge);
    wand_status_card.append(&wand_status_head);
    let (wand_row, wand_value) = status_row("emblem-system-symbolic", "Wand:", "Installed");
    let (trainer_row, trainer_value) = status_row("emblem-ok-symbolic", "Trainer:", "Available");
    let (wand_proton_row, wand_proton_value) = status_row("preferences-system-symbolic", "Proton:", "GE-Proton-Wand-SHA256");
    let (status_row_widget, status_value) = status_row("dialog-information-symbolic", "Status:", "Ready to Launch");
    wand_status_card.append(&wand_row);
    wand_status_card.append(&trainer_row);
    wand_status_card.append(&wand_proton_row);
    wand_status_card.append(&status_row_widget);
    status_rail.append(&wand_status_card);

    let quick_card = gtk::Box::new(gtk::Orientation::Vertical, 7);
    quick_card.add_css_class("wand-status-card");
    let quick_title = gtk::Label::new(Some("Quick Actions"));
    quick_title.set_xalign(0.0);
    quick_title.add_css_class("wand-card-title");
    quick_card.append(&quick_title);
    let quick_health = quick_action("utilities-system-monitor-symbolic", "Check Trainer Health");
    let quick_repair = quick_action("applications-engineering-symbolic", "Repair Wand Setup");
    let quick_folder = quick_action("folder-symbolic", "Open Game Folder");
    let quick_steam = quick_action("applications-games-symbolic", "Open Steam Page");
    quick_card.append(&quick_health);
    quick_card.append(&quick_repair);
    quick_card.append(&quick_folder);
    quick_card.append(&quick_steam);
    status_rail.append(&quick_card);

    let rail_spacer = gtk::Box::new(gtk::Orientation::Vertical, 0);
    rail_spacer.set_vexpand(true);
    status_rail.append(&rail_spacer);
    let footer = gtk::Label::new(Some(&format!(
        "Wand Native {}  |  Open Source  |  MIT License",
        env!("CARGO_PKG_VERSION")
    )));
    footer.set_xalign(0.5);
    footer.add_css_class("wand-footer");
    status_rail.append(&footer);
    home_shell.append(&status_rail);

    let home_scroll = gtk::ScrolledWindow::new();
    home_scroll.set_policy(gtk::PolicyType::Never, gtk::PolicyType::Automatic);
    home_scroll.set_child(Some(&home_shell));
    page_stack.add_named(&home_scroll, Some("home"));

    // ---------------------------------------------------------------------
    // Setup page — keeps all advanced 0.1.41 controls out of the home view.
    // ---------------------------------------------------------------------
    let setup_page = gtk::Box::new(gtk::Orientation::Vertical, 14);
    setup_page.add_css_class("wand-page");
    let setup_title = gtk::Label::new(Some("Setup"));
    setup_title.set_xalign(0.0);
    setup_title.add_css_class("wand-page-title");
    setup_page.append(&setup_title);
    let setup_intro = gtk::Label::new(Some(
        "Configure the isolated Wand-compatible Proton runtime, provider and trainer for the selected game.",
    ));
    setup_intro.set_xalign(0.0);
    setup_intro.set_wrap(true);
    setup_intro.add_css_class("wand-subtle");
    setup_page.append(&setup_intro);

    let setup_status = gtk::Label::new(Some("Compatibility status: not checked"));
    setup_status.set_xalign(0.0);
    setup_status.add_css_class("wand-card-title");
    setup_page.append(&setup_status);

    let setup_actions = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let setup_install = gtk::Button::with_label("Install / Repair");
    setup_install.add_css_class("suggested-action");
    let setup_verify = gtk::Button::with_label("Verify");
    let setup_remove = gtk::Button::with_label("Remove Compatibility Tool");
    setup_remove.add_css_class("destructive-action");
    setup_actions.append(&setup_install);
    setup_actions.append(&setup_verify);
    setup_actions.append(&setup_remove);
    setup_page.append(&setup_actions);

    let config_card = gtk::Box::new(gtk::Orientation::Vertical, 10);
    config_card.add_css_class("wand-card");
    let config_title = gtk::Label::new(Some("Selected game profile"));
    config_title.set_xalign(0.0);
    config_title.add_css_class("wand-card-title");
    config_card.append(&config_title);

    let game_status = gtk::Label::new(Some("Select a game to inspect its Proton/session state"));
    game_status.set_xalign(0.0);
    game_status.set_wrap(true);
    config_card.append(&game_status);
    let provider_health = gtk::Label::new(Some("Provider: not inspected"));
    provider_health.set_xalign(0.0);
    provider_health.set_wrap(true);
    provider_health.add_css_class("wand-subtle");
    config_card.append(&provider_health);

    let config = gtk::Grid::new();
    config.set_column_spacing(12);
    config.set_row_spacing(10);
    config.set_hexpand(true);
    let provider_label = gtk::Label::new(Some("Provider"));
    provider_label.set_xalign(0.0);
    let provider_combo = gtk::DropDown::new(None::<gtk::gio::ListModel>, None::<gtk::Expression>);
    provider_combo.set_hexpand(true);
    set_dropdown_items(
        &provider_combo,
        providers.iter().map(|provider| provider.id.clone()),
        Some(&preferences.default_provider),
    );
    config.attach(&provider_label, 0, 0, 1, 1);
    config.attach(&provider_combo, 1, 0, 3, 1);

    let proton_label = gtk::Label::new(Some("Proton"));
    proton_label.set_xalign(0.0);
    let proton_combo = gtk::DropDown::new(None::<gtk::gio::ListModel>, None::<gtk::Expression>);
    proton_combo.set_hexpand(true);
    set_dropdown_items(
        &proton_combo,
        std::iter::once("Steam selected".to_string())
            .chain(protons.iter().map(|proton| proton.tool_id.clone())),
        Some("Steam selected"),
    );
    config.attach(&proton_label, 0, 1, 1, 1);
    config.attach(&proton_combo, 1, 1, 3, 1);

    let trainer_label = gtk::Label::new(Some("Trainer EXE"));
    trainer_label.set_xalign(0.0);
    let trainer_entry = gtk::Entry::new();
    trainer_entry.set_hexpand(true);
    trainer_entry.set_placeholder_text(Some("/home/you/Trainers/GameTrainer.exe"));
    let trainer_browse = gtk::Button::with_label("Browse…");
    let runtime_import = gtk::Button::with_label("Import Runtime…");
    runtime_import.set_sensitive(false);
    let runtime_install = gtk::Button::with_label("Install Runtime…");
    runtime_install.set_sensitive(false);
    config.attach(&trainer_label, 0, 2, 1, 1);
    config.attach(&trainer_entry, 1, 2, 1, 1);
    config.attach(&trainer_browse, 2, 2, 1, 1);
    config.attach(&runtime_import, 3, 2, 1, 1);
    config.attach(&runtime_install, 4, 2, 1, 1);
    config_card.append(&config);

    let profile_actions = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let save_profile = gtk::Button::with_label("Save Profile");
    let setup_use_for_game = gtk::Button::with_label("Use Wand Proton for Selected Game");
    let setup_trainer_health = gtk::Button::with_label("Check Trainer Health");
    profile_actions.append(&save_profile);
    profile_actions.append(&setup_use_for_game);
    profile_actions.append(&setup_trainer_health);
    config_card.append(&profile_actions);
    setup_page.append(&config_card);

    let setup_output = gtk::TextView::new();
    setup_output.set_editable(false);
    setup_output.set_cursor_visible(false);
    setup_output.set_monospace(true);
    setup_output.add_css_class("wand-log");
    setup_output.set_wrap_mode(gtk::WrapMode::WordChar);
    setup_output.buffer().set_text(
        "Use Install / Repair for first-time setup. The operation can take several minutes if the tested Proton-GE baseline needs to be downloaded.",
    );
    let setup_output_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .min_content_height(260)
        .child(&setup_output)
        .build();
    setup_page.append(&setup_output_scroll);
    page_stack.add_named(&setup_page, Some("setup"));

    // Compatibility page: a clean health-focused mirror of setup state.
    let compatibility_page = gtk::Box::new(gtk::Orientation::Vertical, 14);
    compatibility_page.add_css_class("wand-page");
    let compatibility_title = gtk::Label::new(Some("Compatibility"));
    compatibility_title.set_xalign(0.0);
    compatibility_title.add_css_class("wand-page-title");
    compatibility_page.append(&compatibility_title);
    let compatibility_copy = gtk::Label::new(Some(
        "Wand Native uses the proven isolated Proton-GE + patched crypt32 compatibility path. The runtime architecture is unchanged in 0.1.42.",
    ));
    compatibility_copy.set_xalign(0.0);
    compatibility_copy.set_wrap(true);
    compatibility_copy.add_css_class("wand-subtle");
    compatibility_page.append(&compatibility_copy);
    let compat_summary = gtk::Box::new(gtk::Orientation::Vertical, 10);
    compat_summary.add_css_class("wand-card");
    let compat_summary_title = gtk::Label::new(Some("Current compatibility tool"));
    compat_summary_title.set_xalign(0.0);
    compat_summary_title.add_css_class("wand-card-title");
    compat_summary.append(&compat_summary_title);
    let compat_tool = gtk::Label::new(Some("GE-Proton-Wand-SHA256"));
    compat_tool.set_xalign(0.0);
    compat_tool.add_css_class("wand-status-good");
    compat_summary.append(&compat_tool);
    compatibility_page.append(&compat_summary);
    page_stack.add_named(&compatibility_page, Some("compatibility"));

    // Diagnostics page.
    let diagnostics_page = gtk::Box::new(gtk::Orientation::Vertical, 12);
    diagnostics_page.add_css_class("wand-page");
    let diagnostics_title = gtk::Label::new(Some("Diagnostics"));
    diagnostics_title.set_xalign(0.0);
    diagnostics_title.add_css_class("wand-page-title");
    diagnostics_page.append(&diagnostics_title);
    let diagnostics_actions = gtk::Box::new(gtk::Orientation::Horizontal, 8);
    let process_probe = gtk::Button::with_label("Inspect Processes");
    let refresh_logs = gtk::Button::with_label("Refresh Logs");
    let stop = gtk::Button::with_label("Stop Trainer");
    stop.add_css_class("destructive-action");
    stop.set_sensitive(false);
    let diagnostics = gtk::Button::with_label("Export Diagnostics");
    diagnostics.set_sensitive(false);
    diagnostics_actions.append(&process_probe);
    diagnostics_actions.append(&refresh_logs);
    diagnostics_actions.append(&stop);
    diagnostics_actions.append(&diagnostics);
    diagnostics_page.append(&diagnostics_actions);

    let process_text = gtk::TextView::new();
    process_text.set_editable(false);
    process_text.set_cursor_visible(false);
    process_text.set_monospace(true);
    process_text.add_css_class("wand-log");
    let process_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .min_content_height(180)
        .child(&process_text)
        .build();
    diagnostics_page.append(&process_scroll);

    let logs = gtk::TextView::new();
    logs.set_editable(false);
    logs.set_cursor_visible(false);
    logs.set_monospace(true);
    logs.add_css_class("wand-log");
    let log_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .min_content_height(180)
        .child(&logs)
        .build();
    diagnostics_page.append(&log_scroll);

    let history = gtk::ListBox::new();
    history.set_selection_mode(gtk::SelectionMode::None);
    history.add_css_class("wand-game-list");
    populate_history(&client, &history);
    let history_scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hexpand(true)
        .min_content_height(160)
        .child(&history)
        .build();
    diagnostics_page.append(&history_scroll);
    page_stack.add_named(&diagnostics_page, Some("diagnostics"));
    render_logs(&client, &logs);
    render_logs(&client, &activity_log);

    // Settings page.
    let settings_page = gtk::Box::new(gtk::Orientation::Vertical, 14);
    settings_page.add_css_class("wand-page");
    let settings_title = gtk::Label::new(Some("Settings"));
    settings_title.set_xalign(0.0);
    settings_title.add_css_class("wand-page-title");
    settings_page.append(&settings_title);
    let settings_copy = gtk::Label::new(Some(
        "Provider defaults, automatic game launch and diagnostics location are managed in Wand Preferences.",
    ));
    settings_copy.set_xalign(0.0);
    settings_copy.set_wrap(true);
    settings_copy.add_css_class("wand-subtle");
    settings_page.append(&settings_copy);
    let settings_open_preferences = gtk::Button::with_label("Open Wand Preferences");
    settings_open_preferences.set_halign(gtk::Align::Start);
    settings_page.append(&settings_open_preferences);
    page_stack.add_named(&settings_page, Some("settings"));

    // About page.
    let about_page = gtk::Box::new(gtk::Orientation::Vertical, 14);
    about_page.add_css_class("wand-page");
    let about_title = gtk::Label::new(Some("Wand Native"));
    about_title.set_xalign(0.0);
    about_title.add_css_class("wand-page-title");
    about_page.append(&about_title);
    let about_version = gtk::Label::new(Some(&format!("Version {}", env!("CARGO_PKG_VERSION"))));
    about_version.set_xalign(0.0);
    about_version.add_css_class("wand-card-title");
    about_page.append(&about_version);
    let about_copy = gtk::Label::new(Some(
        "Native Linux launcher and compatibility front end for Wand. Open source under the MIT License.",
    ));
    about_copy.set_xalign(0.0);
    about_copy.set_wrap(true);
    about_copy.add_css_class("wand-subtle");
    about_page.append(&about_copy);
    page_stack.add_named(&about_page, Some("about"));

    page_stack.set_visible_child_name("home");

    // Navigation state.
    let nav_items = vec![
        (home_nav.clone(), "home".to_string()),
        (library_nav.clone(), "library".to_string()),
        (setup_nav.clone(), "setup".to_string()),
        (compat_nav.clone(), "compatibility".to_string()),
        (diagnostics_nav.clone(), "diagnostics".to_string()),
        (settings_nav.clone(), "settings".to_string()),
        (about_nav.clone(), "about".to_string()),
    ];
    for (button, name) in nav_items.clone() {
        let stack = page_stack.clone();
        let all_buttons: Vec<gtk::Button> = nav_items.iter().map(|(button, _)| button.clone()).collect();
        let active_button = button.clone();
        button.connect_clicked(move |_| {
            for candidate in &all_buttons {
                candidate.remove_css_class("active");
            }
            active_button.add_css_class("active");
            stack.set_visible_child_name(&name);
        });
    }

    // Preferences from top bar and Settings page.
    for button in [preferences_button.clone(), settings_open_preferences.clone()] {
        let parent = window.clone();
        let client = client.clone();
        let providers = providers.clone();
        let onboarding = onboarding.clone();
        button.connect_clicked(move |_| {
            open_preferences(&parent, client.clone(), providers.clone(), onboarding.clone());
        });
    }

    // Search filters the Library without changing runtime state.
    {
        let game_list = game_list.clone();
        let games = games.clone();
        search.connect_search_changed(move |entry| {
            let query = entry.text().to_string().to_lowercase();
            let mut child = game_list.first_child();
            let mut index = 0usize;
            while let Some(widget) = child {
                let next = widget.next_sibling();
                if let Ok(row) = widget.clone().downcast::<gtk::ListBoxRow>() {
                    let visible = games
                        .get(index)
                        .map(|game| {
                            query.is_empty()
                                || game.name.to_lowercase().contains(&query)
                                || game.app_id.to_string().contains(&query)
                        })
                        .unwrap_or(true);
                    row.set_visible(visible);
                }
                child = next;
                index += 1;
            }
        });
    }

    // Selected game updates every mockup-facing status element and the advanced profile controls.
    {
        let games = games.clone();
        let providers = providers.clone();
        let protons = protons.clone();
        let selected_game = selected_game.clone();
        let client = client.clone();
        let game_title = game_title.clone();
        let game_app_id = game_app_id.clone();
        let hero = hero.clone();
        let cover = cover.clone();
        let proton_combo = proton_combo.clone();
        let provider_combo = provider_combo.clone();
        let trainer_entry = trainer_entry.clone();
        let game_status = game_status.clone();
        let provider_health = provider_health.clone();
        let detected_body = detected_body.clone();
        let detected_state = detected_state.clone();
        let compat_body = compat_body.clone();
        let compat_state = compat_state.clone();
        let proton_value = proton_value.clone();
        let prefix_value = prefix_value.clone();
        let installed_value = installed_value.clone();
        let play = play.clone();
        let play_normal = play_normal.clone();

        game_list.connect_row_selected(move |_, row| {
            let Some(row) = row else {
                *selected_game.borrow_mut() = None;
                play.set_sensitive(false);
                play_normal.set_sensitive(false);
                return;
            };
            let index = row.index();
            if index < 0 {
                return;
            }
            let Some(game) = games.get(index as usize).cloned() else {
                return;
            };
            *selected_game.borrow_mut() = Some(game.clone());
            set_game_artwork(&hero, &cover, &game);

            fill_game_details(
                &client,
                &game,
                &game_title,
                &game_app_id,
                &proton_combo,
                &provider_combo,
                &trainer_entry,
                &game_status,
                &provider_health,
                &providers,
                &protons,
            );

            detected_body.set_text(&format!("{}\nApp ID: {}", game.name, game.app_id));
            detected_state.set_text("Installed");
            installed_value.set_text("Installed");
            play_normal.set_sensitive(true);

            if let Ok(inspect) = client.inspect(game.app_id) {
                let selected_proton = inspect
                    .proton
                    .as_ref()
                    .map(|p| p.display_name.as_str())
                    .unwrap_or("Steam selected");
                proton_value.set_text(selected_proton);
                compat_body.set_text(selected_proton);
                if inspect.game.prefix_dir.is_dir() {
                    prefix_value.set_text("Compatible");
                    compat_state.set_text("Configured");
                } else {
                    prefix_value.set_text("Needs Setup");
                    compat_state.set_text("Setup Needed");
                }
            }

            let provider_id = dropdown_active_text(&provider_combo)
                .unwrap_or_else(|| preferences.default_provider.clone());
            let provider_available = client
                .provider_health(Some(provider_id), Some(game.app_id))
                .ok()
                .and_then(|health| health.first().cloned())
                .map(|health| health.available)
                .unwrap_or(false);
            play.set_sensitive(provider_available);
        });
    }

    // Provider health drives the home Wand-status card as well as launch availability.
    {
        let client = client.clone();
        let provider_health = provider_health.clone();
        let selected_game = selected_game.clone();
        let providers = providers.clone();
        let trainer_entry = trainer_entry.clone();
        let trainer_browse = trainer_browse.clone();
        let runtime_import = runtime_import.clone();
        let runtime_install = runtime_install.clone();
        let proton_combo = proton_combo.clone();
        let play = play.clone();
        let wand_body = wand_body.clone();
        let wand_state = wand_state.clone();
        let trainer_value = trainer_value.clone();
        let status_value = status_value.clone();
        let wand_ready_badge = wand_ready_badge.clone();

        provider_combo.connect_selected_notify(move |combo| {
            let Some(provider_id) = dropdown_active_text(combo) else {
                return;
            };
            let requires_trainer_path = providers
                .iter()
                .find(|provider| provider.id == provider_id)
                .map(|provider| provider.requires_trainer_path)
                .unwrap_or(true);
            trainer_entry.set_sensitive(requires_trainer_path);
            trainer_browse.set_sensitive(requires_trainer_path);
            runtime_import.set_sensitive(provider_id == "wemod");
            runtime_install.set_sensitive(provider_id == "wemod");
            proton_combo.set_sensitive(true);
            if requires_trainer_path {
                trainer_entry.set_placeholder_text(Some("/home/you/Trainers/GameTrainer.exe"));
            } else {
                trainer_entry.set_placeholder_text(Some("Provider manages its own runtime"));
            }

            let app_id = selected_game.borrow().as_ref().map(|game| game.app_id);
            match client.provider_health(Some(provider_id), app_id) {
                Ok(health) => {
                    if let Some(health) = health.first() {
                        provider_health.set_text(&format!(
                            "Provider: {} • {}",
                            health.status,
                            health.details.join(" ")
                        ));
                        play.set_sensitive(health.available && app_id.is_some());
                        if health.available {
                            wand_body.set_text("Trainer installed and configured");
                            wand_state.set_text("Ready");
                            trainer_value.set_text("Available");
                            status_value.set_text("Ready to Launch");
                            wand_ready_badge.set_text("●  Ready");
                        } else {
                            wand_body.set_text("Trainer/provider needs attention");
                            wand_state.set_text("Check Setup");
                            trainer_value.set_text("Needs Setup");
                            status_value.set_text("Setup Required");
                            wand_ready_badge.set_text("●  Setup Required");
                        }
                    }
                }
                Err(error) => {
                    provider_health.set_text(&format!("Provider health unavailable: {error}"));
                    play.set_sensitive(false);
                    wand_body.set_text("Provider health unavailable");
                    wand_state.set_text("Unavailable");
                    trainer_value.set_text("Unavailable");
                    status_value.set_text("Unavailable");
                    wand_ready_badge.set_text("●  Unavailable");
                }
            }
        });
    }

    // Compatibility install / verify / remove.
    {
        let status = setup_status.clone();
        let output = setup_output.clone();
        let buttons = vec![setup_install.clone(), setup_verify.clone(), setup_remove.clone()];
        setup_install.connect_clicked(move |_| {
            run_helper_background(
                "Compatibility install",
                "wand-appimage-setup.sh",
                vec!["install".to_string()],
                &status,
                &output,
                buttons.clone(),
            );
        });
    }
    {
        let status = setup_status.clone();
        let output = setup_output.clone();
        let buttons = vec![setup_install.clone(), setup_verify.clone(), setup_remove.clone()];
        setup_verify.connect_clicked(move |_| {
            run_helper_background(
                "Compatibility verification",
                "wand-appimage-setup.sh",
                vec!["verify".to_string()],
                &status,
                &output,
                buttons.clone(),
            );
        });
    }
    {
        let status = setup_status.clone();
        let output = setup_output.clone();
        let buttons = vec![setup_install.clone(), setup_verify.clone(), setup_remove.clone()];
        setup_remove.connect_clicked(move |_| {
            run_helper_background(
                "Compatibility removal",
                "wand-appimage-setup.sh",
                vec!["remove".to_string()],
                &status,
                &output,
                buttons.clone(),
            );
        });
    }

    // Set Wand Proton for selected game.
    {
        let client = client.clone();
        let selected_game = selected_game.clone();
        let status = setup_status.clone();
        let output = setup_output.clone();
        let proton_combo = proton_combo.clone();
        let onboarding = onboarding.clone();
        let compat_body = compat_body.clone();
        let compat_state = compat_state.clone();
        let proton_value = proton_value.clone();
        setup_use_for_game.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                status.set_text("Selected game: none");
                output.buffer().set_text("Choose a Steam game from the Library first.");
                return;
            };
            let existing = client.inspect(game.app_id).ok().and_then(|inspect| inspect.profile);
            let profile = GameProfile {
                app_id: game.app_id,
                provider_id: existing.as_ref().and_then(|p| p.provider_id.clone()),
                preferred_proton: Some("GE-Proton-Wand-SHA256".to_string()),
                trainer: existing.as_ref().and_then(|p| p.trainer.clone()),
                trainer_args: existing.as_ref().map(|p| p.trainer_args.clone()).unwrap_or_default(),
                auto_launch_trainer: existing.as_ref().map(|p| p.auto_launch_trainer).unwrap_or(true),
            };
            match client.set_profile(profile) {
                Ok(_) => {
                    set_dropdown_items(
                        &proton_combo,
                        vec!["Steam selected".to_string(), "GE-Proton-Wand-SHA256".to_string()],
                        Some("GE-Proton-Wand-SHA256"),
                    );
                    let mut prefs = client.preferences().unwrap_or_default();
                    prefs.onboarding_complete = true;
                    let _ = client.set_preferences(prefs);
                    onboarding.set_visible(false);
                    status.set_text("Selected game: Wand Proton enabled");
                    output.buffer().set_text(&format!(
                        "{} (AppID {}) will use GE-Proton-Wand-SHA256 when launched from Wand Native.",
                        game.name, game.app_id
                    ));
                    compat_body.set_text("GE-Proton-Wand-SHA256");
                    compat_state.set_text("Configured");
                    proton_value.set_text("GE-Proton-Wand-SHA256");
                }
                Err(error) => {
                    status.set_text("Selected game: profile update failed");
                    output.buffer().set_text(&format!("Could not save the game profile: {error}"));
                }
            }
        });
    }

    // Trainer health from setup and home quick action.
    for health_button in [setup_trainer_health.clone(), quick_health.clone()] {
        let selected_game = selected_game.clone();
        let status = setup_status.clone();
        let output = setup_output.clone();
        let button_clone = health_button.clone();
        health_button.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                status.set_text("Trainer health: no game selected");
                output.buffer().set_text("Choose a Steam game from the Library first.");
                return;
            };
            run_helper_background(
                "Trainer health",
                "wand-trainer-health.sh",
                vec![game.app_id.to_string()],
                &status,
                &output,
                vec![button_clone.clone()],
            );
        });
    }

    // Quick repair action.
    {
        let status = setup_status.clone();
        let output = setup_output.clone();
        let repair_button = quick_repair.clone();
        quick_repair.connect_clicked(move |_| {
            run_helper_background(
                "Compatibility repair",
                "wand-appimage-setup.sh",
                vec!["install".to_string()],
                &status,
                &output,
                vec![repair_button.clone()],
            );
        });
    }

    // Quick open game folder.
    {
        let selected_game = selected_game.clone();
        quick_folder.connect_clicked(move |_| {
            if let Some(game) = selected_game.borrow().clone() {
                let _ = ProcessCommand::new("xdg-open").arg(&game.install_dir).spawn();
            }
        });
    }

    // Quick open Steam page.
    {
        let selected_game = selected_game.clone();
        quick_steam.connect_clicked(move |_| {
            if let Some(game) = selected_game.borrow().clone() {
                let uri = format!("steam://store/{}", game.app_id);
                let _ = ProcessCommand::new("xdg-open").arg(uri).spawn();
            }
        });
    }

    // Play normally via Steam, outside the Wand-managed session path.
    {
        let selected_game = selected_game.clone();
        let game_status = game_status.clone();
        play_normal.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                game_status.set_text("Select a game before launching it");
                return;
            };
            match ProcessCommand::new("steam")
                .arg("-applaunch")
                .arg(game.app_id.to_string())
                .env_remove("DESKTOP_STARTUP_ID")
                .env_remove("XDG_ACTIVATION_TOKEN")
                .env_remove("GIO_LAUNCHED_DESKTOP_FILE")
                .env_remove("GIO_LAUNCHED_DESKTOP_FILE_PID")
                .spawn()
            {
                Ok(_) => game_status.set_text("Launched normally through Steam"),
                Err(error) => game_status.set_text(&format!("Normal launch failed: {error}")),
            }
        });
    }

    // Trainer picker.
    {
        let parent = window.clone();
        let trainer_entry = trainer_entry.clone();
        trainer_browse.connect_clicked(move |_| {
            let dialog = gtk::FileDialog::builder()
                .title("Choose trainer executable")
                .modal(true)
                .build();
            let filter = gtk::FileFilter::new();
            filter.set_name(Some("Windows executables"));
            filter.add_pattern("*.exe");
            let filters = gtk::gio::ListStore::new::<gtk::FileFilter>();
            filters.append(&filter);
            dialog.set_filters(Some(&filters));
            dialog.set_default_filter(Some(&filter));
            let trainer_entry = trainer_entry.clone();
            dialog.open(Some(&parent), None::<&gtk::gio::Cancellable>, move |result| {
                if let Ok(file) = result {
                    if let Some(path) = file.path() {
                        trainer_entry.set_text(&path.display().to_string());
                    }
                }
            });
        });
    }

    // Provider runtime import.
    {
        let parent = window.clone();
        let client = client.clone();
        let selected_game = selected_game.clone();
        let provider_health = provider_health.clone();
        let play = play.clone();
        runtime_import.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                provider_health.set_text("Select a game before importing a provider runtime.");
                return;
            };
            let dialog = gtk::FileDialog::builder()
                .title("Choose existing Wine/Proton prefix")
                .modal(true)
                .build();
            let client = client.clone();
            let provider_health = provider_health.clone();
            let play = play.clone();
            dialog.select_folder(Some(&parent), None::<&gtk::gio::Cancellable>, move |result| {
                let Ok(folder) = result else { return; };
                let Some(path) = folder.path() else {
                    provider_health.set_text("Selected prefix has no local filesystem path.");
                    return;
                };
                match client.import_provider_runtime("wemod".into(), game.app_id, path, false) {
                    Ok(result) => {
                        provider_health.set_text(&format!(
                            "Provider: {} • imported from {}",
                            result.health.status,
                            result.source.display()
                        ));
                        play.set_sensitive(result.health.available);
                    }
                    Err(error) => provider_health.set_text(&format!("Runtime import failed: {error}")),
                }
            });
        });
    }

    // Provider runtime installer bootstrap.
    {
        let parent = window.clone();
        let client = client.clone();
        let selected_game = selected_game.clone();
        let proton_combo = proton_combo.clone();
        let provider_health = provider_health.clone();
        runtime_install.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                provider_health.set_text("Select a game before installing a provider runtime.");
                return;
            };
            let dialog = gtk::FileDialog::builder()
                .title("Choose official Wand/WeMod Windows installer")
                .modal(true)
                .build();
            let filter = gtk::FileFilter::new();
            filter.set_name(Some("Windows installers"));
            filter.add_pattern("*.exe");
            let filters = gtk::gio::ListStore::new::<gtk::FileFilter>();
            filters.append(&filter);
            dialog.set_filters(Some(&filters));
            dialog.set_default_filter(Some(&filter));
            let client = client.clone();
            let provider_health = provider_health.clone();
            let proton = dropdown_active_text(&proton_combo).filter(|value| value != "Steam selected");
            dialog.open(Some(&parent), None::<&gtk::gio::Cancellable>, move |result| {
                let Ok(file) = result else { return; };
                let Some(installer) = file.path() else {
                    provider_health.set_text("Selected installer has no local filesystem path.");
                    return;
                };
                match client.bootstrap_provider_runtime(
                    "wemod".into(),
                    game.app_id,
                    installer,
                    proton.clone(),
                    Vec::new(),
                ) {
                    Ok(result) => provider_health.set_text(&format!(
                        "Installer launched with {} (PID {:?}). Complete the Windows installer, then reselect this game to refresh provider health.",
                        result.proton.display_name,
                        result.launch_pid
                    )),
                    Err(error) => provider_health.set_text(&format!("Runtime installer failed to launch: {error}")),
                }
            });
        });
    }

    // Save selected profile.
    {
        let client = client.clone();
        let selected_game = selected_game.clone();
        let provider_combo = provider_combo.clone();
        let proton_combo = proton_combo.clone();
        let trainer_entry = trainer_entry.clone();
        let game_status = game_status.clone();
        save_profile.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                game_status.set_text("Select a game before saving a profile");
                return;
            };
            let provider = dropdown_active_text(&provider_combo);
            let proton = dropdown_active_text(&proton_combo).filter(|value| value != "Steam selected");
            let profile = GameProfile {
                app_id: game.app_id,
                provider_id: provider,
                preferred_proton: proton,
                trainer: nonempty(&trainer_entry.text()).map(PathBuf::from),
                trainer_args: Vec::new(),
                auto_launch_trainer: true,
            };
            match client.set_profile(profile) {
                Ok(_) => game_status.set_text("Profile saved"),
                Err(error) => game_status.set_text(&format!("Profile save failed: {error}")),
            }
        });
    }

    // Process inspection and logs.
    {
        let client = client.clone();
        let selected_game = selected_game.clone();
        let process_text = process_text.clone();
        process_probe.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                process_text.buffer().set_text("Select a game first.");
                return;
            };
            render_processes(&client, game.app_id, &process_text);
        });
    }
    {
        let client = client.clone();
        let logs = logs.clone();
        let activity_log = activity_log.clone();
        refresh_logs.connect_clicked(move |_| {
            render_logs(&client, &logs);
            render_logs(&client, &activity_log);
        });
    }
    {
        let activity_log = activity_log.clone();
        clear_log.connect_clicked(move |_| activity_log.buffer().set_text(""));
    }

    // Play with Wand — same runtime/session path as 0.1.41.
    {
        let client = client.clone();
        let selected_game = selected_game.clone();
        let current_session = current_session.clone();
        let provider_combo = provider_combo.clone();
        let providers = providers.clone();
        let proton_combo = proton_combo.clone();
        let trainer_entry = trainer_entry.clone();
        let game_status = game_status.clone();
        let session_state = session_state.clone();
        let activity_log = activity_log.clone();
        let stop = stop.clone();
        let diagnostics = diagnostics.clone();
        let history = history.clone();
        let logs = logs.clone();
        let status_value = status_value.clone();
        play.connect_clicked(move |_| {
            let Some(game) = selected_game.borrow().clone() else {
                game_status.set_text("Select a game before starting a session");
                return;
            };
            let provider = dropdown_active_text(&provider_combo);
            let requires_trainer_path = provider
                .as_ref()
                .and_then(|provider_id| providers.iter().find(|descriptor| &descriptor.id == provider_id))
                .map(|descriptor| descriptor.requires_trainer_path)
                .unwrap_or(true);
            let trainer = if requires_trainer_path {
                let Some(trainer_text) = nonempty(&trainer_entry.text()) else {
                    game_status.set_text("Choose the trainer executable first");
                    return;
                };
                PathBuf::from(trainer_text)
            } else {
                PathBuf::new()
            };
            let proton = dropdown_active_text(&proton_combo).filter(|value| value != "Steam selected");
            let launch_game = client
                .preferences()
                .map(|preferences| preferences.launch_game_automatically)
                .unwrap_or(true);
            let timeout_secs = if provider.as_deref() == Some("wemod") { 600 } else { 120 };
            match client.begin_session(
                game.app_id,
                trainer,
                provider,
                proton,
                launch_game,
                timeout_secs,
                Vec::new(),
            ) {
                Ok(session) => {
                    *current_session.borrow_mut() = Some(session.id);
                    session_state.set_text(&format!("Session: {:?}  •  {}", session.state, session.id));
                    activity_log.buffer().set_text(&render_session(&session));
                    diagnostics.set_sensitive(true);
                    status_value.set_text("Launching…");
                    poll_session(
                        client.clone(),
                        session.id,
                        session_state.clone(),
                        activity_log.clone(),
                        stop.clone(),
                        diagnostics.clone(),
                        history.clone(),
                        logs.clone(),
                    );
                }
                Err(error) => {
                    game_status.set_text(&format!("Session start failed: {error}"));
                    status_value.set_text("Launch Failed");
                    render_logs(&client, &logs);
                }
            }
        });
    }

    // Stop trainer.
    {
        let client = client.clone();
        let current_session = current_session.clone();
        let session_state = session_state.clone();
        let activity_log = activity_log.clone();
        let logs = logs.clone();
        let status_value = status_value.clone();
        stop.connect_clicked(move |_| {
            let Some(id) = *current_session.borrow() else { return; };
            match client.stop_session(id) {
                Ok(session) => {
                    session_state.set_text(&format!("Session: {:?}  •  {}", session.state, session.id));
                    activity_log.buffer().set_text(&render_session(&session));
                    render_logs(&client, &logs);
                    status_value.set_text("Ready to Launch");
                }
                Err(error) => session_state.set_text(&format!("Stop failed: {error}")),
            }
        });
    }

    // Diagnostics export.
    {
        let client = client.clone();
        let current_session = current_session.clone();
        let game_status = game_status.clone();
        diagnostics.connect_clicked(move |_| {
            let Some(id) = *current_session.borrow() else { return; };
            let preferences = client.preferences().unwrap_or_default();
            let destination = preferences
                .diagnostics_directory
                .or_else(|| std::env::var_os("HOME").map(PathBuf::from).map(|home| home.join("Desktop")))
                .unwrap_or_else(|| PathBuf::from("."));
            match client.export_diagnostics(id, destination) {
                Ok(path) => game_status.set_text(&format!("Diagnostics exported: {}", path.display())),
                Err(error) => game_status.set_text(&format!("Diagnostics export failed: {error}")),
            }
        });
    }

    // Keep the top-right Steam state live without changing launch architecture.
    {
        let client = client.clone();
        let steam_title = steam_title.clone();
        let steam_online = steam_online.clone();
        let steam_value = steam_value.clone();
        let wand_value = wand_value.clone();
        let wand_proton_value = wand_proton_value.clone();
        gtk::glib::timeout_add_local(Duration::from_secs(2), move || {
            match client.status() {
                Ok(status) => {
                    steam_title.set_text("Steam Detected");
                    steam_online.set_text("Online");
                    steam_value.set_text("Online");
                    wand_value.set_text("Installed");
                    wand_proton_value.set_text("GE-Proton-Wand-SHA256");
                    if status.game_count == 0 {
                        steam_online.set_text("No games found");
                    }
                }
                Err(_) => {
                    steam_title.set_text("Wand Service");
                    steam_online.set_text("Offline");
                    steam_value.set_text("Unavailable");
                    wand_value.set_text("Unavailable");
                }
            }
            gtk::glib::ControlFlow::Continue
        });
    }

    if games.is_empty() {
        game_title.set_text("No Steam games detected");
        game_app_id.set_text("App ID: —");
        detected_body.set_text("No installed Steam games were returned by wandd");
        detected_state.set_text("Not Found");
        installed_value.set_text("Not Found");
        game_ready_badge.set_text("●  Select a Game");
        play.set_sensitive(false);
        play_normal.set_sensitive(false);
        save_profile.set_sensitive(false);
    } else if let Some(first) = game_list.row_at_index(0) {
        game_list.select_row(Some(&first));
    }

    window.set_content(Some(&root));
    window.present();
}

fn main() {
    let application = adw::Application::builder()
        .application_id("dev.wand.WandNative")
        .build();

    application.connect_activate(build_ui);
    application.run();
}
