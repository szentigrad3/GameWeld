"""GameWeld GTK4 desktop. No third-party trainers or active game memory access."""
import json
import threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from .core import installed_games, load_settings, save_settings, find_games
from .diagnostics import game_report
from .ipc import fixture_default_path, preflight, run_probe, run_benchmark
from .history import read_report, record_summary, sanitise_benchmark, history_report
from .startup import startup_trend

CSS = '''
.gw-heading {font-size: 23px; font-weight: 700;}
.gw-caption {opacity: .75;}
.gw-section {font-weight: 700; font-size: 15px;}
.gw-safety {color: #dcae72;}
.gw-card {padding: 14px; border-radius: 10px;}
'''


def box(vertical=True, spacing=10):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                   spacing=spacing)


def label(text='', style=None):
    obj = Gtk.Label(label=text, xalign=0)
    obj.set_wrap(True)
    if style:
        obj.add_css_class(style)
    return obj


def margins(widget, n=14):
    for side in ('top','bottom','start','end'):
        getattr(widget, 'set_margin_' + side)(n)
    return widget


class DesktopWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='GameWeld — Desktop Alpha',
                         default_width=1180, default_height=760)
        self.prefs = load_settings()
        self.games = []
        self.query = ''
        self.favourites_only = False
        self.selected_appid = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.connect('close-request', self.on_close_request)
        self.set_child(self.make_ui())
        self.refresh_games()

    def make_ui(self):
        root = box(spacing=12)
        margins(root, 18)
        root.set_hexpand(True)
        root.set_vexpand(True)
        head = box(vertical=False, spacing=12)
        title = label('GameWeld', 'gw-heading')
        title.set_hexpand(True)
        head.append(title)
        refresh = Gtk.Button(label='Refresh library')
        refresh.connect('clicked', lambda *_: self.refresh_games())
        head.append(refresh)
        root.append(head)
        root.append(label('Linux desktop alpha  ·  Local library  ·  No trainer attachment', 'gw-caption'))

        self.tabs = Gtk.Stack()
        self.tabs.set_vexpand(True)
        self.tabs.set_hexpand(True)
        switcher = Gtk.StackSwitcher(stack=self.tabs)
        root.append(switcher)
        root.append(self.tabs)
        self.make_library()
        self.make_ipc()
        self.make_history()
        self.make_preferences()
        return root

    def make_library(self):
        page = box(spacing=10)
        page.set_vexpand(True)
        searchbar = box(vertical=False, spacing=9)
        search = Gtk.SearchEntry(placeholder_text='Search games or Steam App ID')
        search.set_hexpand(True)
        search.connect('search-changed', self.on_search)
        searchbar.append(search)
        favourite = Gtk.CheckButton(label='Favourites only')
        favourite.connect('toggled', self.on_favourites)
        searchbar.append(favourite)
        self.sort = Gtk.DropDown.new_from_strings(['Title', 'Steam App ID', 'Favourites first'])
        self.sort.set_selected({'title': 0, 'appid': 1, 'favourites': 2}[self.prefs['sort']])
        self.sort.connect('notify::selected', self.on_sort)
        searchbar.append(self.sort)
        page.append(searchbar)
        self.summary = label('Loading Steam library…', 'gw-caption')
        page.append(self.summary)

        columns = box(vertical=False, spacing=18)
        columns.set_vexpand(True)
        columns.set_hexpand(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(420, -1)
        scroll.set_min_content_height(360)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.rows = Gtk.ListBox()
        self.rows.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.rows.connect('row-selected', self.on_select)
        scroll.set_child(self.rows)
        columns.append(scroll)

        details = box(spacing=10)
        details.set_hexpand(True)
        details.set_vexpand(True)
        details.append(label('SELECTED GAME', 'gw-section'))
        self.game_title = label('Choose an installed game')
        self.game_title.add_css_class('title-2')
        details.append(self.game_title)
        self.game_meta = label('', 'gw-caption')
        details.append(self.game_meta)
        actions = box(vertical=False, spacing=8)
        self.fav_button = Gtk.Button(label='☆ Favourite')
        self.fav_button.set_sensitive(False)
        self.fav_button.connect('clicked', self.on_toggle_fav)
        actions.append(self.fav_button)
        self.copy_button = Gtk.Button(label='Copy App ID')
        self.copy_button.set_sensitive(False)
        self.copy_button.connect('clicked', self.on_copy)
        actions.append(self.copy_button)
        self.inspect_button = Gtk.Button(label='Inspect (read-only)')
        self.inspect_button.set_sensitive(False)
        self.inspect_button.connect('clicked', self.on_inspect)
        actions.append(self.inspect_button)
        details.append(actions)

        details.append(label('PERSONAL NOTES', 'gw-section'))
        self.note = Gtk.TextView()
        self.note.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.note.set_sensitive(False)
        self.note.set_vexpand(False)
        note_sc = Gtk.ScrolledWindow()
        note_sc.set_min_content_height(100)
        note_sc.set_child(self.note)
        details.append(note_sc)
        self.save_note_button = Gtk.Button(label='Save note')
        self.save_note_button.set_sensitive(False)
        self.save_note_button.connect('clicked', self.on_save_note)
        details.append(self.save_note_button)

        details.append(label('INSTALLATION DIAGNOSTICS', 'gw-section'))
        self.inspect_label = label('Select a game to view read-only installation evidence.', 'gw-caption')
        self.inspect_label.set_selectable(True)
        details.append(self.inspect_label)
        details.append(label('Trainer controls disabled. Game and Proton processes are never attached.', 'gw-safety'))
        columns.append(details)
        page.append(columns)
        self.tabs.add_titled(page, 'library', 'Game library')

    def make_ipc(self):
        page = margins(box(spacing=12), 8)
        page.append(label('Windows IPC Lab', 'gw-heading'))
        page.append(label('Run only the exact SHA-256-pinned original Batch77 Win64 test fixture. '
                          'This is an isolated Wine communication test, not a trainer.', 'gw-caption'))
        self.fixture_entry = Gtk.Entry()
        self.fixture_entry.set_text(str(fixture_default_path()))
        self.fixture_entry.set_hexpand(True)
        page.append(label('Fixture file (must match the pinned 4 KiB Batch77 binary):'))
        page.append(self.fixture_entry)
        check = Gtk.Button(label='Check fixture and Wine (read-only)')
        check.connect('clicked', self.on_ipc_preflight)
        page.append(check)
        run_options = box(vertical=False, spacing=9)
        run_options.append(label('Isolated sessions:'))
        self.ipc_run_count = Gtk.DropDown.new_from_strings(['1', '2', '3'])
        self.ipc_run_count.set_selected(0)
        run_options.append(self.ipc_run_count)
        page.append(run_options)
        self.ipc_consent = Gtk.CheckButton(label='I authorise the selected number of isolated Wine fixture sessions (no game/trainer access)')
        self.ipc_consent.connect('toggled', self.on_consent)
        page.append(self.ipc_consent)
        self.ipc_save_history = Gtk.CheckButton(
            label='Save a privacy-minimised benchmark summary to local history')
        self.ipc_save_history.set_active(False)
        page.append(self.ipc_save_history)
        self.run_button = Gtk.Button(label='Run IPC protocol benchmark')
        self.run_button.set_sensitive(False)
        self.run_button.connect('clicked', self.on_ipc_run)
        page.append(self.run_button)
        self.cancel_button = Gtk.Button(label='Cancel owned IPC test')
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect('clicked', self.on_ipc_cancel)
        page.append(self.cancel_button)
        page.append(label('All raw paths, process IDs and probe challenges are excluded from exported results. '
                          'Complete detached Wine helper cleanup is not guaranteed.', 'gw-safety'))
        self.ipc_status = label('No IPC test started.')
        page.append(self.ipc_status)
        output_sc = Gtk.ScrolledWindow()
        output_sc.set_vexpand(True)
        self.ipc_output = Gtk.TextView()
        self.ipc_output.set_monospace(True)
        self.ipc_output.set_editable(False)
        output_sc.set_child(self.ipc_output)
        page.append(output_sc)
        self.tabs.add_titled(page, 'lab', 'IPC Lab')

    def make_history(self):
        page = margins(box(spacing=12), 8)
        page.set_vexpand(True)
        page.append(label('IPC Benchmark History', 'gw-heading'))
        page.append(label('Only numerical timing summaries and bounded status fields are stored. '
                          'Saving is always opt-in; original Wine logs are not retained.', 'gw-caption'))
        actions = box(vertical=False, spacing=8)
        refresh = Gtk.Button(label='Refresh history')
        refresh.connect('clicked', self.on_refresh_history)
        actions.append(refresh)
        page.append(actions)
        page.append(label('Import an existing GameWeld benchmark JSON (local file):'))
        import_row = box(vertical=False, spacing=8)
        self.import_entry = Gtk.Entry()
        self.import_entry.set_placeholder_text('Path to gameweld-desktop-030-benchmark.json')
        self.import_entry.set_hexpand(True)
        import_row.append(self.import_entry)
        import_btn = Gtk.Button(label='Import validated summary')
        import_btn.connect('clicked', self.on_import_history)
        import_row.append(import_btn)
        page.append(import_row)
        self.history_status = label('History not loaded.', 'gw-caption')
        page.append(self.history_status)
        view = Gtk.ScrolledWindow()
        view.set_vexpand(True)
        self.history_text = Gtk.TextView()
        self.history_text.set_editable(False)
        self.history_text.set_cursor_visible(False)
        self.history_text.set_monospace(True)
        self.history_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_child(self.history_text)
        page.append(view)
        page.append(label('Read-only statistics do not prove compatibility with trainers, games or Steam Proton.', 'gw-safety'))
        self.tabs.add_titled(page, 'history', 'History')
        self.on_refresh_history(None)

    def on_refresh_history(self, _):
        try:
            report = history_report()
            records = report['records']
            trend = startup_trend()
            mean = trend['session_weighted_mean_ms']
            median = trend['session_median_ms']
            summary_line = (f"{trend['successful_session_count']} measured sessions"
                            + (f"  ·  mean READY {mean/1000:.2f} s" if mean is not None else '')
                            + (f"  ·  median {median/1000:.2f} s" if median is not None else ''))
            self.history_status.set_text(
                f"{report['record_count']} saved reports  ·  {report['success_count']} successful\n"
                + summary_line)
            lines = []
            for item in reversed(records[-30:]):
                value = item['startup_mean_ms']
                startup = f'{value / 1000:.2f} s' if value is not None else 'not measured'
                lines.append(f"{item['recorded_at_utc']}   {item['state']}\n"
                             f"   {item['runs_completed']} session(s)  ·  mean READY {startup}\n")
            if trend['latest_vs_earlier_ratio'] is not None:
                ratio = trend['latest_vs_earlier_ratio']
                lines.insert(0, f"Latest report / earlier sessions: {ratio:.2f}× startup time\n"
                                + ('Single-run comparison; not evidence of a cause.\n'
                                   if trend['latest_comparison_is_single_run']
                                   else 'Observational comparison; not a verified cause.\n'))
            self.history_text.get_buffer().set_text('\n'.join(lines) or 'No benchmark summaries recorded.')
        except (OSError, ValueError):
            self.history_status.set_text('Cannot load saved history. Check local file permissions/format.')
            self.history_text.get_buffer().set_text('Existing history was not modified.')

    def on_import_history(self, _):
        path = self.import_entry.get_text().strip()
        try:
            result = record_summary(read_report(path))
        except (OSError, ValueError):
            self.history_status.set_text('Import rejected: invalid or unsafe benchmark report.')
            return
        self.on_refresh_history(None)
        self.history_status.set_text('Benchmark summary imported.' if result['state']=='summary_recorded'
                                     else 'Benchmark already present in history.')

    def make_preferences(self):
        page = margins(box(spacing=12), 8)
        page.append(label('Preferences & safety', 'gw-heading'))
        page.append(label('Steam libraries are discovered from local manifests only. No network requests.'))
        page.append(label('Primary Steam steamapps directory:'))
        self.steam_entry = Gtk.Entry()
        self.steam_entry.set_text(self.prefs['steamapps'])
        page.append(self.steam_entry)
        save = Gtk.Button(label='Save Steam location and rescan')
        save.connect('clicked', self.on_save_location)
        page.append(save)
        self.preferences_status = label('Favourites and personal notes are saved locally.')
        page.append(self.preferences_status)
        page.append(label('GameWeld 0.4.0-alpha. Third-party trainers, live-game memory '
                          'access and Steam launch-option changes are unavailable.', 'gw-safety'))
        self.tabs.add_titled(page, 'settings', 'Preferences')

    def refresh_games(self):
        try:
            self.games = installed_games(self.prefs['steamapps'])
        except (OSError, ValueError) as exc:
            self.games = []
        self.repaint()

    def repaint(self):
        saved = self.selected_appid
        self.rows.unselect_all()
        while row := self.rows.get_first_child():
            self.rows.remove(row)
        games = find_games(self.games, self.query, self.prefs['favourites'],
                           self.favourites_only, self.prefs['sort'])
        select = None
        for game in games:
            row = Gtk.ListBoxRow()
            row.set_name(str(game['appid']))
            prefix = '★  ' if game['appid'] in self.prefs['favourites'] else ''
            title = label(prefix + game['title'])
            title.set_margin_top(9)
            title.set_margin_bottom(9)
            title.set_margin_start(12)
            title.set_margin_end(12)
            row.set_child(title)
            self.rows.append(row)
            if game['appid'] == saved:
                select = row
        self.summary.set_text(f'{len(games)} visible / {len(self.games)} installed  ·  '
                              f'{len(self.prefs["favourites"])} favourites')
        if select is not None:
            self.rows.select_row(select)
        else:
            self.selected_appid = None
            self.show_game(None)

    def current_game(self):
        return next((g for g in self.games if g['appid'] == self.selected_appid), None)

    def show_game(self, game):
        active = game is not None
        for button in (self.fav_button, self.copy_button, self.inspect_button,
                       self.save_note_button):
            button.set_sensitive(active)
        self.note.set_sensitive(active)
        buf = self.note.get_buffer()
        if not active:
            self.game_title.set_text('Choose an installed game')
            self.game_meta.set_text('')
            buf.set_text('')
            self.inspect_label.set_text('Select a game to inspect.')
            return
        appid = game['appid']
        self.game_title.set_text(game['title'])
        self.game_meta.set_text(f'Steam App ID: {appid}   ·   '
                                f'Build: {game["buildid"] or "unknown"}   ·   '
                                f'{game["library"].title()} Steam library')
        self.fav_button.set_label('★ Unfavourite' if appid in self.prefs['favourites'] else '☆ Favourite')
        buf.set_text(self.prefs['notes'].get(str(appid), ''))
        self.inspect_label.set_text('Press Inspect for a read-only on-disk report.')

    def on_select(self, _, row):
        self.selected_appid = int(row.get_name()) if row is not None else None
        self.show_game(self.current_game())

    def on_search(self, widget):
        self.query = widget.get_text()
        self.repaint()

    def on_favourites(self, widget):
        self.favourites_only = widget.get_active()
        self.repaint()

    def on_sort(self, widget, _):
        self.prefs['sort'] = ('title', 'appid', 'favourites')[widget.get_selected()]
        self.store_prefs()
        self.repaint()

    def store_prefs(self):
        try:
            save_settings(self.prefs)
            return True
        except (OSError, ValueError):
            self.preferences_status.set_text('Failed to write local settings; check permissions.')
            return False

    def on_toggle_fav(self, _):
        game = self.current_game()
        if not game:return
        item = game['appid']
        previous = list(self.prefs['favourites'])
        fav = set(previous)
        if item in fav:fav.remove(item)
        else:fav.add(item)
        self.prefs['favourites'] = sorted(fav)
        if not self.store_prefs():
            self.prefs['favourites'] = previous
        self.repaint()

    def on_copy(self, _):
        game = self.current_game()
        if game:self.get_clipboard().set_text(str(game['appid']))

    def on_save_note(self, _):
        game = self.current_game()
        if not game:return
        buf = self.note.get_buffer()
        note = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if len(note)>1200:
            self.inspect_label.set_text('Note too long: limit is 1200 characters.')
            return
        key = str(game['appid'])
        old = self.prefs['notes'].get(key)
        if note:self.prefs['notes'][key] = note
        else:self.prefs['notes'].pop(key, None)
        if self.store_prefs():
            self.inspect_label.set_text('Local note saved.')
        else:
            if old is None:self.prefs['notes'].pop(key, None)
            else:self.prefs['notes'][key] = old

    def on_inspect(self, _):
        game = self.current_game()
        if game is None:return
        report = game_report(game)
        # Short summary: no private paths or raw process data shown.
        self.inspect_label.set_text(
            f'Installation directory: {"found" if report["install_directory_found"] else "not verified"}\n'
            f'Compatdata directory: {"found" if report["compatdata_directory_found"] else "not verified"}\n'
            'Running game identity: not verified\nTrainer compatibility: not verified')

    def on_save_location(self, _):
        path = self.steam_entry.get_text().strip()
        if not path or len(path)>2048 or '\0' in path:
            self.preferences_status.set_text('Invalid Steam library path.')
            return
        previous = self.prefs['steamapps']
        self.prefs['steamapps'] = path
        if self.store_prefs():
            self.refresh_games()
            self.preferences_status.set_text('Local preference saved and Steam library rescanned.')
        else:self.prefs['steamapps'] = previous

    def on_consent(self, _):
        self.run_button.set_sensitive(self.ipc_consent.get_active() and not self.busy)

    def show_ipc_result(self, report):
        self.ipc_output.get_buffer().set_text(json.dumps(report, indent=2, sort_keys=True))
        label_text = 'IPC: ' + report.get('state', 'unknown')
        if isinstance(report.get('startup_mean_ms'), (int,float)):
            label_text += f"  ·  mean Wine startup: {report['startup_mean_ms']/1000:.2f} s"
        self.ipc_status.set_text(label_text)

    def on_ipc_preflight(self, _):
        self.show_ipc_result(preflight(self.fixture_entry.get_text()))

    def on_ipc_cancel(self, _):
        if self.busy:
            self.cancel_event.set()
            self.cancel_button.set_sensitive(False)
            self.ipc_status.set_text('Cancelling the owned Wine fixture; cleanup in progress…')

    def on_close_request(self, *_args):
        if self.busy:
            self.on_ipc_cancel(None)
            return True  # The owned child must be cleaned up before window close.
        return False

    def on_ipc_run(self, _):
        if self.busy or not self.ipc_consent.get_active():return
        self.busy = True
        self.run_button.set_sensitive(False)
        self.cancel_event.clear()
        self.cancel_button.set_sensitive(True)
        self.ipc_consent.set_active(False)
        count = self.ipc_run_count.get_selected() + 1
        self.ipc_status.set_text(f'Running {count} owned Wine fixture session(s) in fresh temporary prefixes…')
        fixture = self.fixture_entry.get_text()
        save_summary = self.ipc_save_history.get_active()
        def worker():
            try:result = run_benchmark(consent=True, fixture=fixture, timeout=75, runs=count,
                                     cancel_event=self.cancel_event)
            except Exception:result = {'state': 'ipc_error', 'trainer_launched':False,
                                      'game_memory_accessed':False}
            if save_summary and result.get('state') == 'isolated_ipc_benchmark_verified':
                try:
                    record_summary(sanitise_benchmark(result))
                    result['history_summary_saved'] = True
                except (OSError, ValueError):
                    result['history_summary_saved'] = False
            def deliver():
                self.busy = False
                self.cancel_button.set_sensitive(False)
                self.show_ipc_result(result)
                if save_summary:
                    self.on_refresh_history(None)
                    if result.get('history_summary_saved') is False:
                        self.ipc_status.set_text('IPC completed; failed to save local benchmark history.')
                return False
            GLib.idle_add(deliver)
        threading.Thread(target=worker, daemon=True).start()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.gameweld.Desktop')

    def do_activate(self):
        win = self.props.active_window
        if win is None:
            css = Gtk.CssProvider()
            css.load_from_data(CSS.encode('utf-8'))
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(display, css,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            win = DesktopWindow(self)
        win.present()


def launch():
    return App().run(None)
