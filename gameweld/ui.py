"""GTK4 graphical shell. No executable or trainer-launch controls."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from .core import installed_games, load_settings, save_settings, find_games

class DesktopWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="GameWeld Desktop Alpha",
                         default_width=1050, default_height=680)
        self.prefs = load_settings()
        self.games = installed_games(self.prefs["steamapps"])
        self.query = ""
        self.favourites_only = False
        self.set_child(self.make_ui())

    def make_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for key in ("top", "bottom", "start", "end"):
            getattr(root, "set_margin_" + key)(18)
        heading = Gtk.Label(label="GameWeld — Installed Games", xalign=0)
        heading.add_css_class("title-1")
        root.append(heading)
        tabs = Gtk.Stack()
        tabs.set_vexpand(True)
        switch = Gtk.StackSwitcher(stack=tabs)
        root.append(switch)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search = Gtk.SearchEntry(placeholder_text="Search Steam games or App IDs")
        search.set_hexpand(True)
        search.connect("search-changed", self.on_search)
        actions.append(search)
        only = Gtk.CheckButton(label="Favourites")
        only.connect("toggled", self.on_favourites)
        actions.append(only)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.on_refresh)
        actions.append(refresh)
        page.append(actions)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        pane_left = Gtk.ScrolledWindow()
        pane_left.set_min_content_width(350)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-selected", self.on_select)
        pane_left.set_child(self.listbox)
        panes.set_start_child(pane_left)
        pane_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        pane_right.set_margin_start(16)
        self.info = Gtk.Label(label="Choose a game for read-only details.", xalign=0)
        pane_right.append(self.info)
        self.fav_button = Gtk.Button(label="Toggle favourite")
        self.fav_button.set_sensitive(False)
        self.fav_button.connect("clicked", self.on_toggle)
        pane_right.append(self.fav_button)
        panes.set_end_child(pane_right)
        page.append(panes)
        tabs.add_titled(page, "library", "Game Library")
        lab = Gtk.Label(label="IPC Lab: unavailable in this clean alpha.\nNo trainer/game attachment is enabled.")
        tabs.add_titled(lab, "ipc", "IPC Lab")
        tabs.add_titled(Gtk.Label(label="Read-only Steam data. Game memory and trainer execution disabled."),
                       "status", "Status")
        root.append(tabs)
        self.repaint()
        return root

    def repaint(self):
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        games = find_games(self.games, self.query, self.prefs["favourites"], self.favourites_only)
        for game in games:
            row = Gtk.ListBoxRow()
            row.set_name(str(game["appid"]))
            star = "★ " if game["appid"] in self.prefs["favourites"] else ""
            label = Gtk.Label(label=star + game["title"], xalign=0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            row.set_child(label)
            self.listbox.append(row)

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
        row = self.listbox.get_selected_row()
        if row is None:
            return None
        return next((g for g in self.games if str(g["appid"]) == row.get_name()), None)

    def on_select(self, _, row):
        game = self.selected()
        self.fav_button.set_sensitive(game is not None)
        self.info.set_text(("Steam App ID: {}\n{}\nBuild ID: {}\nTrainer: disabled".format(
            game["appid"], game["title"], game["buildid"] or "not listed"))
            if game else "Choose a game for read-only details.")

    def on_toggle(self, _):
        game = self.selected()
        if not game:
            return
        favourites = set(self.prefs["favourites"])
        if game["appid"] in favourites:
            favourites.remove(game["appid"])
        else:
            favourites.add(game["appid"])
        self.prefs["favourites"] = sorted(favourites)
        save_settings(self.prefs)
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
