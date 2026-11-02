"""GTK4 graphical shell. Read-only local game discovery; trainer execution disabled."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from .core import installed_games, load_settings, save_settings, find_games


class DesktopWindow(Gtk.ApplicationWindow):
    """Stable two-column desktop layout; never creates Wine or game processes."""

    def __init__(self, app):
        super().__init__(application=app, title="GameWeld Desktop Alpha",
                         default_width=1100, default_height=720)
        self.prefs = load_settings()
        self.games = installed_games(self.prefs["steamapps"])
        self.query = ""
        self.favourites_only = False
        self.selected_appid = None
        self.set_child(self.make_ui())

    def make_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for edge in ("top", "bottom", "start", "end"):
            getattr(root, "set_margin_" + edge)(18)

        heading = Gtk.Label(label="GameWeld — Installed Games", xalign=0)
        heading.add_css_class("title-1")
        root.append(heading)

        tabs = Gtk.Stack()
        tabs.set_vexpand(True)
        root.append(Gtk.StackSwitcher(stack=tabs))
        root.append(tabs)

        library = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        library.set_vexpand(True)
        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search = Gtk.SearchEntry(placeholder_text="Search Steam games or App IDs")
        search.set_hexpand(True)
        search.connect("search-changed", self.on_search)
        tools.append(search)

        favourites = Gtk.CheckButton(label="Favourites")
        favourites.connect("toggled", self.on_favourites)
        tools.append(favourites)

        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.on_refresh)
        tools.append(refresh)
        library.append(tools)

        self.summary = Gtk.Label(label="", xalign=0)
        self.summary.add_css_class("dim-label")
        library.append(self.summary)

        # A non-expanding Gtk.Paned used to reduce this entire list to one row
        # even when Steam discovery returned over a hundred games. Use a real
        # vertically expanding scroller instead, without the Paned handle.
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        columns.set_vexpand(True)
        columns.set_hexpand(True)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_size_request(420, -1)
        self.scroller.set_min_content_height(340)
        self.scroller.set_vexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self.on_select)
        self.scroller.set_child(self.listbox)
        columns.append(self.scroller)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        details.set_hexpand(True)
        details.set_vexpand(True)
        caption = Gtk.Label(label="GAME DETAILS", xalign=0)
        caption.add_css_class("dim-label")
        details.append(caption)
        self.info = Gtk.Label(label="Choose a game for read-only details.", xalign=0)
        self.info.set_wrap(True)
        details.append(self.info)
        self.fav_button = Gtk.Button(label="Toggle favourite")
        self.fav_button.set_sensitive(False)
        self.fav_button.connect("clicked", self.on_toggle)
        details.append(self.fav_button)
        safety = Gtk.Label(
            label="Game discovery is read-only. Trainer attachment is disabled.",
            xalign=0)
        safety.set_wrap(True)
        safety.add_css_class("dim-label")
        details.append(safety)
        columns.append(details)
        library.append(columns)
        tabs.add_titled(library, "library", "Game Library")

        lab = Gtk.Label(
            label="IPC Lab is not integrated in this clean desktop alpha.\n"
                  "No trainers or game processes can be launched.")
        lab.set_wrap(True)
        tabs.add_titled(lab, "ipc", "IPC Lab")

        status = Gtk.Label(
            label="Local Steam manifests only.\n"
                  "No game memory access, Steam changes, or trainer execution.")
        status.set_wrap(True)
        tabs.add_titled(status, "status", "Status")

        self.repaint()
        return root

    def repaint(self):
        # Preserve selection after a refresh or favourite toggle; do not hide
        # the rest of the list in a non-expanding container.
        selected_id = self.selected_appid
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        visible = find_games(self.games, self.query,
                             self.prefs["favourites"], self.favourites_only)
        favourite_ids = set(self.prefs["favourites"])
        selected_row = None
        for game in visible:
            row = Gtk.ListBoxRow()
            row.set_name(str(game["appid"]))
            prefix = "★  " if game["appid"] in favourite_ids else ""
            label = Gtk.Label(label=prefix + game["title"], xalign=0)
            label.set_margin_top(9)
            label.set_margin_bottom(9)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_hexpand(True)
            row.set_child(label)
            self.listbox.append(row)
            if game["appid"] == selected_id:
                selected_row = row

        self.summary.set_text(
            f"{len(visible)} visible of {len(self.games)} Steam games discovered")
        if selected_row is not None:
            self.listbox.select_row(selected_row)
        else:
            self.selected_appid = None
            self.show_game(None)

    def show_game(self, game):
        self.fav_button.set_sensitive(game is not None)
        if game is None:
            self.info.set_text("Choose a game for read-only details.")
            return
        self.info.set_text(
            f"{game['title']}\n\n"
            f"Steam App ID: {game['appid']}\n"
            f"Build ID: {game['buildid'] or 'not listed'}\n"
            f"Favourite: {'Yes' if game['appid'] in self.prefs['favourites'] else 'No'}\n"
            "Trainer: unavailable in this alpha")

    def on_search(self, widget):
        self.query = widget.get_text()
        self.repaint()

    def on_favourites(self, widget):
        self.favourites_only = widget.get_active()
        self.repaint()

    def on_refresh(self, _):
        self.games = installed_games(self.prefs["steamapps"])
        self.repaint()

    def selected(self):
        if self.selected_appid is None:
            return None
        return next((g for g in self.games if g["appid"] == self.selected_appid), None)

    def on_select(self, _, row):
        if row is None:
            self.selected_appid = None
            self.show_game(None)
            return
        try:
            self.selected_appid = int(row.get_name())
        except (ValueError, TypeError):
            self.selected_appid = None
        self.show_game(self.selected())

    def on_toggle(self, _):
        game = self.selected()
        if game is None:
            return
        previous = list(self.prefs["favourites"])
        favourite_ids = set(previous)
        if game["appid"] in favourite_ids:
            favourite_ids.remove(game["appid"])
        else:
            favourite_ids.add(game["appid"])
        self.prefs["favourites"] = sorted(favourite_ids)
        try:
            save_settings(self.prefs)
        except (OSError, ValueError):
            self.prefs["favourites"] = previous
            self.info.set_text("Could not save favourites. Check local config permissions.")
            return
        self.repaint()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.gameweld.Desktop")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = DesktopWindow(self)
        window.present()


def launch():
    return App().run(None)
