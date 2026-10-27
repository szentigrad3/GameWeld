#define _GNU_SOURCE
#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <pthread.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "gameweld-pc2-window-policy.h"
#include "gameweld-pc2-window-state.h"
#include "gameweld-pc2-recent-history.h"

/* Minimal GTK3 declarations. We intentionally build against the stable GTK3 ABI
 * already used by the proven 0.1.41 AppImage. This keeps the redesign independent
 * of development headers in the build container. */
typedef struct _GtkWidget GtkWidget;
typedef struct _GtkWindow GtkWindow;
typedef struct _GtkLabel GtkLabel;
typedef struct _GtkImage GtkImage;
typedef struct _GtkButton GtkButton;
typedef struct _GtkEntry GtkEntry;
typedef struct _GtkEditable GtkEditable;
typedef struct _GtkComboBox GtkComboBox;
typedef struct _GtkComboBoxText GtkComboBoxText;
typedef struct _GtkToggleButton GtkToggleButton;
typedef struct _GtkListBox GtkListBox;
typedef struct _GtkListBoxRow GtkListBoxRow;
typedef struct _GtkStack GtkStack;
typedef struct _GtkTextView GtkTextView;
typedef struct _GtkTextBuffer GtkTextBuffer;
typedef struct _GtkTreeView GtkTreeView;
typedef struct _GtkTreeSelection GtkTreeSelection;
typedef struct _GtkTreeModel GtkTreeModel;
typedef struct _GtkListStore GtkListStore;
typedef struct _GtkCellRenderer GtkCellRenderer;
typedef struct _GtkNotebook GtkNotebook;
typedef struct _GtkScrolledWindow GtkScrolledWindow;
typedef struct _GtkTreeIter { int stamp; void *user_data; void *user_data2; void *user_data3; } GtkTreeIter;
typedef struct _GtkDialog GtkDialog;
typedef struct _GtkClipboard GtkClipboard;
typedef struct _GtkFileChooser GtkFileChooser;
typedef struct _GtkStyleContext GtkStyleContext;
typedef struct _GtkCssProvider GtkCssProvider;
typedef struct _GdkScreen GdkScreen;
typedef struct _GdkRectangle { int x; int y; int width; int height; } GdkRectangle;
typedef struct _GdkPixbuf GdkPixbuf;
typedef void (*GCallback)(void);
typedef unsigned long gulong;
typedef int gboolean;
typedef unsigned int guint;
typedef long gssize;
typedef void *gpointer;
typedef char gchar;
typedef int64_t gint64;
typedef struct _GString { char *str; size_t len; size_t allocated_len; } GString;
extern char *g_strdup(const char *);
extern gchar **g_strsplit(const gchar *, const gchar *, int);
extern unsigned int g_strv_length(gchar **);
extern void g_strfreev(gchar **);
extern gboolean g_str_has_prefix(const gchar *, const gchar *);
extern gint64 g_ascii_strtoll(const gchar *, gchar **, guint);
extern GString *g_string_new(const gchar *);
extern GString *g_string_append(GString *, const gchar *);
extern GString *g_string_append_c(GString *, gchar);
extern gchar *g_string_free(GString *, gboolean);
extern int g_mkdir_with_parents(const char *, int);

extern void gtk_init(int *, char ***);
extern GtkWidget *gtk_window_new(int);
extern void gtk_window_set_title(GtkWindow *, const char *);
extern void gtk_window_set_default_size(GtkWindow *, int, int);
extern void gtk_window_resize(GtkWindow *, int, int);
extern void gtk_window_get_size(GtkWindow *, int *, int *);
extern void gtk_window_set_position(GtkWindow *, int);
extern void gtk_window_set_icon_name(GtkWindow *, const char *);
extern GtkWidget *gtk_box_new(int, int);
extern void gtk_orientable_set_orientation(void *, int);
extern void gtk_box_pack_start(void *, GtkWidget *, gboolean, gboolean, guint);
extern void gtk_box_pack_end(void *, GtkWidget *, gboolean, gboolean, guint);
extern GtkWidget *gtk_label_new(const char *);
extern void gtk_label_set_text(GtkLabel *, const char *);
extern void gtk_label_set_markup(GtkLabel *, const char *);
extern void gtk_label_set_xalign(GtkLabel *, float);
extern void gtk_label_set_yalign(GtkLabel *, float);
extern void gtk_label_set_line_wrap(GtkLabel *, gboolean);
extern void gtk_label_set_ellipsize(GtkLabel *, int);
extern GtkWidget *gtk_button_new(void);
extern GtkWidget *gtk_button_new_with_label(const char *);
extern void gtk_button_set_label(GtkButton *, const char *);
extern GtkWidget *gtk_entry_new(void);
extern void gtk_entry_set_text(GtkEntry *, const char *);
extern void gtk_entry_set_placeholder_text(GtkEntry *, const char *);
extern void gtk_entry_set_icon_from_icon_name(GtkEntry *, int, const char *);
extern const char *gtk_entry_get_text(GtkEntry *);
extern GtkWidget *gtk_combo_box_text_new(void);
extern GtkWidget *gtk_expander_new(const char *);
extern void gtk_expander_set_expanded(GtkWidget *, gboolean);
extern void gtk_combo_box_text_append_text(GtkComboBoxText *, const char *);
extern void gtk_combo_box_text_remove_all(GtkComboBoxText *);
extern int gtk_combo_box_get_active(GtkComboBox *);
extern void gtk_combo_box_set_active(GtkComboBox *, int);
extern void gtk_combo_box_text_append(GtkComboBoxText *, const char *, const char *);
extern const char *gtk_combo_box_get_active_id(GtkComboBox *);
extern gboolean gtk_combo_box_set_active_id(GtkComboBox *, const char *);
extern GtkWidget *gtk_check_button_new_with_label(const char *);
extern gboolean gtk_toggle_button_get_active(GtkToggleButton *);
extern void gtk_toggle_button_set_active(GtkToggleButton *, gboolean);
extern GtkWidget *gtk_message_dialog_new(GtkWindow *, int, int, int, const char *, ...);
extern GtkWidget *gtk_file_chooser_dialog_new(const char *, GtkWindow *, int, const char *, int, ...);
extern int gtk_dialog_run(GtkDialog *);
extern GtkWidget *gtk_dialog_get_content_area(GtkDialog *);
extern char *gtk_file_chooser_get_filename(GtkFileChooser *);
extern gboolean gtk_file_chooser_set_current_folder(GtkFileChooser *, const char *);
extern void g_free(void *);
extern gchar *g_shell_quote(const gchar *);
extern void *gdk_atom_intern_static_string(const gchar *);
extern GtkClipboard *gtk_clipboard_get(void *);
extern void gtk_clipboard_set_text(GtkClipboard *, const gchar *, int);
extern int g_mkdir_with_parents(const char *, int);
extern GtkWidget *gtk_image_new(void);
extern GtkWidget *gtk_image_new_from_pixbuf(const GdkPixbuf *);
extern GtkWidget *gtk_image_new_from_icon_name(const char *, int);
extern void gtk_image_set_pixel_size(GtkImage *, int);
extern void gtk_image_set_from_pixbuf(GtkImage *, const GdkPixbuf *);
extern GdkPixbuf *gdk_pixbuf_new_from_file_at_scale(const char *, int, int, gboolean, void **);
extern void *gdk_pixbuf_get_file_info(const char *, int *, int *);
extern void gtk_window_set_decorated(GtkWindow *, gboolean);
extern void gtk_window_set_titlebar(GtkWindow *, GtkWidget *);
extern void gtk_window_iconify(GtkWindow *);
extern void gtk_window_maximize(GtkWindow *);
extern void gtk_window_unmaximize(GtkWindow *);
extern gboolean gtk_window_is_maximized(GtkWindow *);
extern GtkWidget *gtk_scrolled_window_new(void *, void *);
extern GtkWidget *gtk_expander_new(const char *);
extern void gtk_widget_set_no_show_all(GtkWidget *, gboolean);
extern void gtk_widget_hide(GtkWidget *);
extern void gtk_scrolled_window_set_policy(void *, int, int);
extern GtkWidget *gtk_list_box_new(void);
extern GtkWidget *gtk_list_box_row_new(void);
extern void gtk_list_box_insert(GtkListBox *, GtkWidget *, int);
extern void gtk_list_box_select_row(GtkListBox *, GtkListBoxRow *);
extern int gtk_list_box_row_get_index(GtkListBoxRow *);
extern GtkWidget *gtk_stack_new(void);
extern void gtk_stack_add_named(GtkStack *, GtkWidget *, const char *);
extern void gtk_stack_set_visible_child_name(GtkStack *, const char *);
extern void gtk_stack_set_hhomogeneous(GtkStack *, gboolean);
extern void gtk_stack_set_vhomogeneous(GtkStack *, gboolean);
extern GtkWidget *gtk_separator_new(int);
extern GtkWidget *gtk_text_view_new(void);
extern GtkTextBuffer *gtk_text_view_get_buffer(GtkTextView *);
extern void gtk_text_buffer_set_text(GtkTextBuffer *, const char *, int);
extern void gtk_text_view_set_editable(GtkTextView *, gboolean);
extern void gtk_text_view_set_cursor_visible(GtkTextView *, gboolean);
extern void gtk_text_view_set_monospace(GtkTextView *, gboolean);
extern GtkListStore *gtk_list_store_new(int, ...);
extern GtkWidget *gtk_tree_view_new_with_model(GtkTreeModel *);
extern void gtk_tree_view_set_headers_visible(GtkTreeView *, gboolean);
extern GtkCellRenderer *gtk_cell_renderer_text_new(void);
extern int gtk_tree_view_insert_column_with_attributes(GtkTreeView *, int, const char *, GtkCellRenderer *, ...);
extern void gtk_tree_view_set_grid_lines(GtkTreeView *, int);
extern void *gtk_tree_view_get_column(GtkTreeView *, int);
extern void gtk_tree_view_column_set_min_width(void *, int);
extern void gtk_tree_view_column_set_expand(void *, gboolean);
extern void gtk_cell_renderer_set_padding(GtkCellRenderer *, int, int);
extern void g_object_set(void *, const char *, ...);
extern void gtk_text_view_set_wrap_mode(GtkTextView *, int);
extern GtkTreeModel *gtk_tree_view_get_model(GtkTreeView *);
extern GtkTreeSelection *gtk_tree_view_get_selection(GtkTreeView *);
extern void gtk_tree_selection_set_mode(GtkTreeSelection *, int);
extern gboolean gtk_tree_selection_get_selected(GtkTreeSelection *, GtkTreeModel **, GtkTreeIter *);
extern void gtk_tree_model_get(GtkTreeModel *, GtkTreeIter *, ...);
extern void gtk_list_store_clear(GtkListStore *);
extern void gtk_list_store_append(GtkListStore *, GtkTreeIter *);
extern void gtk_list_store_set(GtkListStore *, GtkTreeIter *, ...);
extern GtkWidget *gtk_notebook_new(void);
extern int gtk_notebook_append_page(GtkNotebook *, GtkWidget *, GtkWidget *);
extern void gtk_notebook_set_current_page(GtkNotebook *, int);
extern gulong g_type_from_name(const char *);
extern void gtk_container_add(void *, GtkWidget *);
extern void gtk_container_foreach(void *, void (*)(GtkWidget *, void *), void *);
extern void gtk_widget_destroy(GtkWidget *);
extern void gtk_widget_show_all(GtkWidget *);
extern void gtk_widget_set_visible(GtkWidget *, gboolean);
extern void gtk_widget_set_sensitive(GtkWidget *, gboolean);
extern void gtk_widget_set_size_request(GtkWidget *, int, int);
extern void gtk_widget_set_hexpand(GtkWidget *, gboolean);
extern void gtk_widget_set_vexpand(GtkWidget *, gboolean);
extern void gtk_widget_set_halign(GtkWidget *, int);
extern void gtk_widget_set_margin_start(GtkWidget *, int);
extern void gtk_widget_set_margin_end(GtkWidget *, int);
extern void gtk_widget_set_margin_top(GtkWidget *, int);
extern void gtk_widget_set_margin_bottom(GtkWidget *, int);
extern void gtk_widget_set_name(GtkWidget *, const char *);
extern GtkStyleContext *gtk_widget_get_style_context(GtkWidget *);
extern void gtk_style_context_add_class(GtkStyleContext *, const char *);
extern void gtk_style_context_remove_class(GtkStyleContext *, const char *);
extern GtkCssProvider *gtk_css_provider_new(void);
extern gboolean gtk_css_provider_load_from_data(GtkCssProvider *, const char *, gssize, void **);
extern GdkScreen *gdk_screen_get_default(void);
extern int gdk_screen_get_width(GdkScreen *);
extern int gdk_screen_get_height(GdkScreen *);
extern int gdk_screen_get_primary_monitor(GdkScreen *);
extern void gdk_screen_get_monitor_workarea(GdkScreen *, int, GdkRectangle *);
extern void gdk_screen_get_monitor_geometry(GdkScreen *, int, GdkRectangle *);
extern int gdk_screen_get_monitor_scale_factor(GdkScreen *, int);
extern void gtk_style_context_add_provider_for_screen(GdkScreen *, void *, guint);
extern void gtk_main(void);
extern void gtk_main_quit(void);
extern gulong g_signal_connect_data(void *, const char *, GCallback, void *, void *, int);
extern void g_signal_stop_emission_by_name(void *, const char *);
extern guint g_idle_add(gboolean (*)(void *), void *);
extern guint g_timeout_add(guint, gboolean (*)(void *), void *);
extern void g_object_unref(void *);

#define GTK_WINDOW_TOPLEVEL 0
#define GTK_ORIENTATION_HORIZONTAL 0
#define GTK_ORIENTATION_VERTICAL 1
#define GTK_POLICY_NEVER 2
#define GTK_POLICY_AUTOMATIC 1
#define GTK_WIN_POS_CENTER 1
#define GTK_STYLE_PROVIDER_PRIORITY_USER 800
#define GTK_ALIGN_CENTER 3
#define GTK_ICON_SIZE_BUTTON 4
#define GTK_ENTRY_ICON_PRIMARY 0
#define GTK_TREE_VIEW_GRID_LINES_HORIZONTAL 1
#define GTK_SELECTION_SINGLE 1
#define GTK_FILE_CHOOSER_ACTION_OPEN 0
#define GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER 2
#define GTK_DIALOG_MODAL 1
#define GTK_MESSAGE_QUESTION 2
#define GTK_MESSAGE_INFO 0
#define GTK_BUTTONS_OK 1
#define GTK_BUTTONS_YES_NO 4
#define GTK_RESPONSE_YES -8
#define GTK_RESPONSE_CANCEL -6
#define GTK_RESPONSE_ACCEPT -3
#define FALSE 0
#define TRUE 1

#define MAX_GAMES 1024
#define HTTP_MAX (1024 * 1024)

typedef struct {
    char appid[192];
    char launch_id[192];
    char key[320];
    char provider[32];
    char runner[48];
    char name[384];
    char install_dir[1024];
    char executable[1024];
    char prefix[1024];
    char compatdata[1024];
    char steam_root[1024];
    char launch_options[2048];
    char target_kind[64];
    char compat_tool[256];
    char compat_tool_path[1024];
    char compat_tool_source[128];
    char resolution_state[128];
    char resolution_label[384];
    char launch_uri[512];
    int shortcut_runtime_resolved;
    int shortcut_prefix_found;
    int shortcut_runtime_found;
    int shortcut_launch_supported;
    char wine_type[64];
    char wine_bin[1024];
    char wine_name[256];
    char art_path[2048];
    char heroic_root[2048];
    char selected_tool[256];
    int wand_found;
} Game;

typedef struct App App;

struct App {
    int port;
    pid_t backend_pid;
    Game games[MAX_GAMES];
    int game_count;
    int steam_game_count;
    int steam_manifest_game_count;
    int steam_shortcut_count;
    int heroic_game_count;
    int lutris_game_count;
    int selected;
    int wand_installed;
    int wand_healthy;
    int base_compatible;
    char base_proton[512];
    char wand_tool[512];
    char verify_message[1024];

    GtkWidget *window;
    GtkWidget *stack;
    GtkWidget *game_list;
    GtkWidget *game_rows[MAX_GAMES];
    GtkWidget *search;
    GtkWidget *search_scope;
    GtkWidget *hero_image;
    GtkWidget *cover_image;
    GtkWidget *hero_name;
    GtkWidget *hero_meta;
    char artwork_appid[320];
    GtkWidget *top_steam_status;
    GtkWidget *game_ready;
    GtkWidget *game_detected_detail;
    GtkWidget *wand_ready;
    GtkWidget *compat_ready;
    GtkWidget *right_game;
    GtkWidget *right_wand;
    GtkWidget *right_proton;
    GtkWidget *right_prefix;
    GtkWidget *play_button;
    GtkWidget *play_title;
    GtkWidget *play_subtitle;
    GtkWidget *overview_launch_assigned;
    GtkWidget *overview_profile_combo;
    GtkWidget *overview_profile_status;
    GtkWidget *overview_save_profile;
    GtkWidget *overview_reset_profile;
    GtkWidget *overview_launch_wemod;
    GtkWidget *overview_launch_aurora;
    GtkWidget *overview_launch_cheat_evolution;
    GtkWidget *overview_launch_cheat_table;
    GtkWidget *overview_launch_custom;
    GtkWidget *overview_launch_game_only;
    GtkWidget *overview_launch_hint;
    GtkWidget *pc2_deckcheatz_overview_play;
    GtkWidget *pc2_deckcheatz_library_play;
    GtkWidget *pc2_deckcheatz_overview_status;
    GtkWidget *pc2_deckcheatz_library_status;
    GtkWidget *wand_patcher_prefix_entry;
    GtkWidget *wand_patcher_install_entry;
    GtkWidget *wand_patcher_exe_entry;
    GtkWidget *wand_patcher_status;
    GtkWidget *local_trainer_entry;
    GtkWidget *local_trainer_status;
    GtkWidget *trainer_library_view;
    GtkWidget *trainer_library_selected;
    GtkWidget *trainer_library_pick;
    GtkWidget *trainer_library_quick_summary;
    GtkWidget *trainer_updates_context;
    GtkWidget *trainer_library_matched;
    GtkWidget *trainer_library_alternates;
    GtkWidget *trainer_library_ambiguous;
    GtkWidget *trainer_library_unmatched;
    GtkWidget *trainer_library_health;
    GtkWidget *trainer_library_attention_games;
    GtkWidget *trainer_library_tabs;
    GtkWidget *trainer_library_filter;
    GtkWidget *trainer_library_sort;
    GtkWidget *trainer_library_readiness_filter;
    GtkWidget *trainer_library_attention_toggle;
    GtkWidget *trainer_library_policy;
    GtkWidget *trainer_library_audit;
    GtkWidget *trainer_library_guidance;
    GtkWidget *trainer_library_recommended_action;
    GtkWidget *trainer_library_assign_suggested;
    GtkWidget *trainer_library_select_suggested;
    GtkWidget *trainer_library_assign_selected;
    GtkWidget *trainer_library_open_folder;
    GtkWidget *trainer_library_launch_assigned;
    GtkWidget *trainer_library_launch_manager_standalone;
    GtkWidget *trainer_updates_status;
    GtkWidget *trainer_updates_install_button;
    GtkWidget *trainer_updates_inspect_button;
    GtkWidget *trainer_updates_rollback_button;
    char trainer_updates_hash[65];
    char trainer_updates_url[1024];
    char trainer_updates_trust[56];
    GtkWidget *trainer_updates_provider;
    GtkWidget *trainer_monitor_status;
    GtkWidget *trainer_monitor_details;
    GtkWidget *trainer_dashboard_status;
    GtkWidget *trainer_dashboard_available;
    GtkWidget *trainer_dashboard_updates;
    GtkWidget *trainer_dashboard_managers;
    GtkWidget *trainer_monitor_details_expander;
    GtkWidget *trainer_monitor_toggle;
    GtkWidget *trainer_monitor_discovery;
    GtkWidget *trainer_monitor_budget;
    int trainer_monitor_enabled;
    int trainer_monitor_include_unassigned;
    int trainer_monitor_syncing;
    int trainer_monitor_busy;
    char trainer_updates_id[128];
    char trainer_updates_game[512];
    /* Exact update-review ownership.  No last-game status or staged catalog
     * record may outlive this game-key + publisher selection. */
    char trainer_updates_context_key[320];
    char trainer_updates_context_provider[64];
    /* Every game/provider transition invalidates older async results, even A→B→A. */
    unsigned long long trainer_updates_context_epoch;
    char trainer_updates_ready_key[320];
    char trainer_updates_ready_provider[64];
    int trainer_updates_busy;
    time_t trainer_updates_last_check;
    char trainer_updates_last_game[512];
    char trainer_library_pick_path[2048];
    char trainer_library_pick_game[512];
    char trainer_library_pick_key[320];
    char trainer_library_pick_state[64];
    char trainer_library_action_code[64];
    GtkWidget *cheat_engine_entry;
    GtkWidget *cheat_engine_installer_entry;
    GtkWidget *cheat_table_entry;
    GtkWidget *cheat_table_status;
    GtkWidget *native_profile_status;
    int legacy_wrapper_neutralized;
    char legacy_wrapper_backup[1024];
    int legacy_hooks_cleaned;
    int legacy_hook_files_changed;
    char legacy_hook_last_backup[2048];
    GtkWidget *steam_cleanup_status;
    GtkWidget *activity;
    GtkWidget *setup_status;
    GtkWidget *setup_detail;
    GtkWidget *health_detail;
    GtkWidget *support_bundle_status;
    GtkWidget *quick_store;
    GtkWidget *library_detail_name;
    GtkWidget *library_detail_meta;
    GtkWidget *library_detail_status;
    GtkWidget *library_detail_path;
    GtkWidget *nav_home;
    GtkWidget *nav_library;
    GtkWidget *nav_trainers;
    GtkWidget *nav_setup;
    GtkWidget *nav_diag;
    GtkWidget *nav_settings;
    GtkWidget *nav_about;
};

static App G;


typedef struct {
    char action[16];
    char runner[64];
    char appid[256];
    char title[256];
    char prefix[2048];
    char wine_type[64];
    char wine_bin[2048];
    char trainer[2048];
    char game_key[320];
    int exit_code;
} HeroicRuntimeJob;

typedef struct {
    char runner[64];
    char appid[256];
    char title[256];
    char install[2048];
    char executable[2048];
    char prefix[2048];
    char wine_type[64];
    char wine_bin[2048];
    char heroic_root[2048];
    int exit_code;
} HeroicWeModJob;

static int heroic_runtime_progress_active=0;
static char heroic_runtime_progress_runner[64];
static char heroic_runtime_progress_appid[256];
static char heroic_runtime_progress_key[320];

static const char *CSS =
"*{font-family:Sans;color:#eef2f7}"
"window{background:#0a0c10}"
"#root{background:#0c0f14}"
"#app-titlebar{background:#090b0f;border-bottom:1px solid #1a1f28;min-height:54px}"
"#title-brand{background:transparent}"
"#brand{color:#f8fafc;font-size:17px;font-weight:900}"
"#brandver{color:#697586;font-size:9px;font-weight:700}"
"#wandmark{color:#ffffff;font-size:14px;font-weight:900;background-image:linear-gradient(145deg,#8b5cf6,#6d28d9);border-radius:10px;padding:8px 10px}"
"#topbar{background:transparent}"
"#navstrip{background:#0c0f14;border-bottom:1px solid #1b212b;padding:7px 18px}"
".nav{background:transparent;color:#8793a3;border:0;border-radius:9px;padding:7px 9px;font-size:10px;font-weight:800;box-shadow:none;min-height:34px}"
".nav:hover{background:#151a22;color:#f8fafc}"
".nav-active{background:#201a35;color:#ffffff;box-shadow:inset 0 0 0 1px #4a3678}"
".nav-active .nav-icon,.nav-active .nav-label{color:#c7b7ff}"
".nav-icon{color:#7d8999}"
".nav-label{color:#9aa5b4;font-size:10px;font-weight:800}"
"entry{background:#121720;color:#f5f7fa;border:1px solid #252d38;border-radius:10px;padding:0 13px;font-size:12px;min-height:36px;box-shadow:none}"
"entry:focus{border-color:#7657d6;box-shadow:0 0 0 1px rgba(118,87,214,.26)}"
"combobox button{background:#141922;color:#e8edf3;border:1px solid #29313d;border-radius:8px;min-height:32px;padding:4px 9px}"
"combobox button:hover{background:#1a202a;border-color:#3a4554}"
"#global-search-wrap{background:#10151d;border:1px solid #252d38;border-radius:11px;padding:1px}"
"#global-search-scope button{background:transparent;border:0;border-radius:9px 0 0 9px;min-height:34px;padding:3px 9px;color:#cbd3dc}"
"#global-search-scope button:hover{background:#171d26;border:0}"
"#global-search-entry{background:transparent;border:0;border-left:1px solid #252d38;border-radius:0 9px 9px 0;min-height:34px;padding:0 11px}"
"#global-search-entry:focus{border:0;border-left:1px solid #7657d6;box-shadow:none}"
"checkbutton{color:#aeb8c5;font-size:11px}"
"#page{background:transparent}"
".surface{background:#11151c;border:1px solid #1f2631;border-radius:12px;padding:14px}"
".panel{background:#10141b;border:1px solid #1d2430;border-radius:12px;padding:16px}"
".panel-soft{background:#0f1319;border:1px solid #1a2029;border-radius:10px;padding:12px}"
".card{background:#11161e;color:#edf2f7;border:1px solid #202833;border-radius:10px;padding:13px;box-shadow:none}"
".card:hover{border-color:#303a49}"
".card-title{color:#f7f9fb;font-size:12px;font-weight:900}"
".muted{color:#8591a1;font-size:10px}"
".good{color:#52d89a;font-size:10px;font-weight:800}"
".warn{color:#f1b95c;font-size:10px;font-weight:800}"
".purple{color:#beaaff;font-weight:900}"
"#section-title{color:#ffffff;font-size:25px;font-weight:900}"
".page-kicker{color:#8b5cf6;font-size:9px;font-weight:900;letter-spacing:1.5px}"
".page-subtitle{color:#7d8999;font-size:11px}"
"#game-title{color:#ffffff;font-size:36px;font-weight:900}"
"#meta{color:#8b97a6;font-size:11px}"
".meta-chip{background:#181d26;border:1px solid #2a3340;border-radius:12px;padding:3px 9px;color:#b4beca;font-size:9px;font-weight:800}"
"#spotlight{background:#10141b;border:1px solid #212a35;border-radius:14px;padding:18px}"
"#spotlight-copy{background:#0e1218;border:1px solid #1c232d;border-radius:12px;padding:16px}"
"#hero-art{background:#090c11;border:1px solid #1d2530;border-radius:12px;padding:4px}"
"#cover-frame{background:#0b0e13;border:1px solid #252e3a;border-radius:10px;padding:4px}"
"#launch-panel{background:#0d1117;border:1px solid #1e2631;border-radius:10px;padding:7px}"
"#play{background-image:linear-gradient(135deg,#8b5cf6,#6d28d9);color:#ffffff;border:0;border-radius:9px;padding:0;box-shadow:0 7px 20px rgba(91,33,182,.25);min-height:62px}"
"#play:hover{background-image:linear-gradient(135deg,#9d78ff,#7c3aed)}"
"#play .launch-icon,#play .launch-title,#play .launch-subtitle{color:#ffffff}"
".launch-icon{font-size:20px;font-weight:900}"
".launch-title{font-size:14px;font-weight:900}"
".launch-subtitle{font-size:10px;font-weight:500;color:#eee9ff}"
"#normal{background:#171c25;color:#eef2f6;border:1px solid #2b3441;border-radius:9px;min-height:62px}"
"#normal:hover{background:#1d2430;border-color:#3c4756}"
"#normal .launch-icon,#normal .normal-title,#normal .normal-subtitle{color:#f3f6f9}"
".normal-title{font-size:12px;font-weight:900}"
".normal-subtitle{font-size:9px;color:#8793a3}"
".metric{background:#0f141b;border:1px solid #1d2530;border-radius:10px;padding:11px;min-height:70px}"
".metric-name{color:#7f8b9b;font-size:9px;font-weight:900;letter-spacing:1px}"
".metric-value{color:#f5f8fb;font-size:13px;font-weight:900}"
".info-card{min-height:78px;padding:11px}"
".info-icon{font-size:18px;font-weight:900;color:#dce4ed}"
".info-icon-wand{font-size:20px;font-weight:900;color:#c3afff}"
".action{background:#171c25;color:#dce3eb;border:1px solid #2a3340;border-radius:8px;padding:5px 10px;font-size:10px;font-weight:700;min-height:30px;box-shadow:none}"
".action:hover{background:#1f2631;border-color:#414d5d;color:#ffffff}"
".action:disabled{color:#5c6674;background:#10141a;border-color:#1b222b}"
".primary-action{background:#6d4ed6;color:#ffffff;border:0;border-radius:8px;padding:6px 12px;font-size:10px;font-weight:900;min-height:32px}"
".primary-action:hover{background:#7f61e4}"
".primary-action:disabled{background:#272238;color:#9082b6;box-shadow:none}"
".windowctl{background:transparent;color:#8793a2;border:0;box-shadow:none;padding:4px 9px;font-size:13px;border-radius:6px}"
".windowctl:hover{background:#171c24;color:#ffffff}#closectl:hover{background:#b23a4a;color:#ffffff}"
"list{background:transparent}row{background:#0f141b;color:#d9e1e9;border-radius:9px;margin:3px 0;border:1px solid #1d2530}row:hover{background:#151b24;border-color:#313b49}row:selected{background:#201a35;color:white;border-color:#5a4290}"
".library-row{padding:0}"
".game-row-title{font-size:12px;font-weight:900;color:#f5f7fa}.game-thumb{background:#090c11;border:1px solid #242d38;border-radius:7px;padding:2px}"
".recent-tile{background:#11161e;border:1px solid #26303d;border-radius:11px;padding:10px;min-width:128px;box-shadow:none}"
".recent-tile:hover{background:#19202a;border-color:#7860bb}"
".recent-tile-selected{background:#211a34;border-color:#8162d7}"
".recent-tile-name{color:#f4f6fb;font-size:11px;font-weight:800}"
".recent-tile-source{color:#96a3b5;font-size:9px}"
".recent-tile-cover{background:#0b0f16;border:1px solid #273140;border-radius:7px;padding:2px}"
"treeview.view{background:#0d1117;color:#cdd5df;border:0}"
"treeview.view header button{background:#131820;color:#8f9bab;border:0;border-bottom:1px solid #29313e;padding:7px;font-size:10px;font-weight:800}"
"treeview.view:selected{background:#312653;color:#ffffff}"
"notebook{background:transparent;border:0}notebook header{background:#0d1117;border-bottom:1px solid #202733}notebook tab{background:transparent;color:#7f8b9a;padding:8px 11px;border:0;font-size:10px;font-weight:800}notebook tab:checked{color:#ffffff;border-bottom:2px solid #8b5cf6;background:#131720}"
"textview,textview text{background:#090c11;color:#aab5c2;font-family:Monospace;font-size:9px}"
"#logframe{background:#090c11;border:1px solid #1c232c;border-radius:8px}"
"#status-pill{background:#10241d;color:#55d99b;border:1px solid #234b39;border-radius:11px;padding:3px 9px;font-size:9px;font-weight:900}"
"#footer{color:#505b69;font-size:8px;padding:4px 0}"
".quick-label{color:#dbe2e9;font-size:10px;font-weight:700}"
".quick-chevron{color:#687586;font-size:11px}"
".eyebrow{color:#9d83ff;font-size:9px;font-weight:900;letter-spacing:1.4px}"
".workspace-title{color:#ffffff;font-size:17px;font-weight:900}"
".workspace-subtitle{color:#7d8998;font-size:10px}"
".section-kicker{color:#707d8e;font-size:9px;font-weight:900;letter-spacing:1.2px}"
".detail-panel{background:#0f141b;border:1px solid #1d2530;border-radius:10px;padding:11px}"
"#library-inspector{background:#0f141b;border:1px solid #202833;border-radius:12px;padding:16px}"
"#library-name{color:#ffffff;font-size:22px;font-weight:900}"
"#library-meta{color:#8995a5;font-size:10px}"
"#command-hint{color:#657181;font-size:9px}"
"scrollbar{background:#0a0d12}scrollbar slider{background:#313947;border-radius:8px;min-width:7px;min-height:24px}scrollbar slider:hover{background:#4a5565}"
"tooltip{background:#161b23;color:#f1f4f7;border:1px solid #313b48;border-radius:7px}"
"separator{background:#1d242e;min-width:1px;min-height:1px}"
"button:focus{box-shadow:0 0 0 2px rgba(139,92,246,.48);outline-style:none}"
"row:focus{box-shadow:inset 0 0 0 2px rgba(139,92,246,.42)}"
"treeview.view:focus{box-shadow:inset 0 0 0 1px rgba(139,92,246,.35)}"
".status-ready{background:#10241d;color:#55d99b;border:1px solid #234b39;border-radius:11px;padding:3px 9px;font-size:9px;font-weight:900}"
".status-warning{background:#2a2111;color:#f1c46f;border:1px solid #5c4720;border-radius:11px;padding:3px 9px;font-size:9px;font-weight:900}"
".status-blocked{background:#2b1519;color:#ff9aa7;border:1px solid #65313a;border-radius:11px;padding:3px 9px;font-size:9px;font-weight:900}"
".empty-state{background:#0e1218;border:1px dashed #2a3340;border-radius:12px;padding:22px;color:#8793a3;font-size:11px}"
".section-divider{margin:5px 0}"
".page-shell{background:#0c0f14}"
".game-connection-summary{color:#dce6f4;font-size:13px;font-weight:600;background:#141b25;border:1px solid #293447;border-radius:8px;padding:12px}"
".trainer-quick-summary{color:#d8e1ed;font-size:12px;padding:9px 0}"
".update-evidence{color:#d3deea;font-size:12px}"
".update-context{color:#d9e3f0;font-size:12px;background:#141b25;border:1px solid #293447;border-radius:8px;padding:11px}"
"treeview.view{font-size:12px}"
"treeview.view header button{font-size:11px}"
"textview,textview text{font-size:11px}"
"notebook.trainer-workspace,notebook.trainer-workspace > stack{background:#0c0f14;color:#e3eaf3}"
"\n";

static void style(GtkWidget *w, const char *cls) {
    gtk_style_context_add_class(gtk_widget_get_style_context(w), cls);
}
static void unstyle(GtkWidget *w, const char *cls) {
    gtk_style_context_remove_class(gtk_widget_get_style_context(w), cls);
}
static void margins(GtkWidget *w, int all) {
    gtk_widget_set_margin_start(w, all); gtk_widget_set_margin_end(w, all);
    gtk_widget_set_margin_top(w, all); gtk_widget_set_margin_bottom(w, all);
}
static GtkWidget *label(const char *s, const char *cls) {
    GtkWidget *w = gtk_label_new(s); gtk_label_set_xalign((GtkLabel*)w, 0.0f);
    if (cls) style(w, cls); return w;
}
/* Defined below with the explicit opt-in game-only Steam handler. */
static int pc2_steam_launch_allowed(void);
static int bounded_child_output(pid_t pid,int fd,char *output,size_t capacity,int seconds);
static void on_pc2_wemod_verify_selected(GtkButton*,void*);
static void on_pc2_deckcheatz_detect(GtkButton*,void*);
static void on_pc2_deckcheatz_copy_steam_option(GtkButton*,void*);
static void on_pc2_deckcheatz_setup_session(GtkButton*,void*);
static void on_pc2_deckcheatz_restore_steam_option(GtkButton*,void*);
static int pc2_deckcheatz_find_launcher(char *,size_t);
static void on_pc2_deckcheatz_preview(GtkButton*,void*);
static void on_pc2_deckcheatz_install(GtkButton*,void*);
static void on_pc2_deckcheatz_check_update(GtkButton*,void*);
static void on_pc2_deckcheatz_update(GtkButton*,void*);
static void on_pc2_deckcheatz_adopt(GtkButton*,void*);
static void on_pc2_bridge_status(GtkButton*,void*);
static void on_pc2_bridge_upgrade(GtkButton*,void*);
static void on_pc2_bridge_play(GtkButton*,void*);
static void on_pc2_bridge_primary(GtkButton*,void*);
static void pc2_launch_with_steam_bridge(Game*);
static void pc2_bridge_readiness_for_game(Game*);
static void pc2_bridge_readiness_invalidate(void);
static void on_pc2_bridge_setup(GtkButton*,void*);
static void on_pc2_bridge_enable(GtkButton*,void*);
static void on_pc2_bridge_disable(GtkButton*,void*);
static void on_pc2_bridge_gpu_off(GtkButton*,void*);
static void on_pc2_bridge_gpu_on(GtkButton*,void*);
static void on_pc2_bridge_netfx_status(GtkButton*,void*);
static void on_pc2_bridge_netfx_plan(GtkButton*,void*);

/* PC2 exploration mode is compiled in, never inferred from backend availability.
 * Connections below run before downstream clicked handlers; they cannot
 * become active again when refresh_ui() changes button sensitivity. */
static int pc2_discovery_only(void) {
#ifdef GAMEWELD_PC2_DISCOVERY_ONLY
    return 1;
#else
    return 0;
#endif
}
/* Provider settings also appear in explicitly opted-in private functional builds.
 * Discovery mode's existing PC2 handlers stay available; the functional
 * runtime requires a separate opt-in rather than inheriting the UI layout.
 * Existing per-action dialogs still gate downloads, patching and Steam setup. */
static int pc2_provider_controls_allowed(void) {
    if (pc2_discovery_only()) return 1;
    const char *optin = getenv("GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST");
    return optin && !strcmp(optin,"I_UNDERSTAND_PRIVATE_TEST_ONLY");
}
static void pc2_block_action(GtkButton *b, void *unused) {
    (void)unused;
    if (!pc2_discovery_only()) return;
    g_signal_stop_emission_by_name(b, "clicked");
    fprintf(stderr, "PC2 discovery-only: action blocked. Use PC1 for launch/setup.\\n");
}
/* Prevent refresh_ui() or another legacy callback from visually re-enabling
 * a blocked widget. GTK notifies again on FALSE; unchanged setters are inert. */
static void pc2_guard_sensitivity(void *widget, void *property, void *unused) {
    (void)property; (void)unused;
    if(pc2_discovery_only())gtk_widget_set_sensitive((GtkWidget*)widget,FALSE);
}
static void pc2_guard_button(GtkWidget *w) {
    if (pc2_discovery_only()) {
        g_signal_connect_data(w, "clicked", (GCallback)pc2_block_action, NULL, NULL, 0);
        g_signal_connect_data(w, "notify::sensitive", (GCallback)pc2_guard_sensitivity, NULL, NULL, 0);
        gtk_widget_set_sensitive(w,FALSE);
    }
}
static GtkWidget *button(const char *s, const char *cls) {
    GtkWidget *w = gtk_button_new_with_label(s); if (cls) style(w, cls);
    if (!cls || strcmp(cls, "windowctl")) {
        /* Opening upstream source is safe; other legacy buttons are blocked. */
        if (strcmp(s, "Preview Steam launch (no action)") && strcmp(s, "Launch Steam game only (opt-in)") && strcmp(s, "Preview native Rust wrapper (no launch)") && strcmp(s, "Launch native Rust wrapper + WeMod (experimental)") && strcmp(s, "Check Steam session (read-only)") && strcmp(s, "WeMod Enhancer: Detect") && strcmp(s, "WeMod Enhancer: Install Helper") && strcmp(s, "WeMod Enhancer: Patch WeMod") && strcmp(s, "WeMod Enhancer: Restore Original") && strcmp(s, "WeMod Enhancer: Choose Folder") && strcmp(s, "Check Wand Patch (no game launch)") && strcmp(s, "Verify Wand Patch + Game (no launch)") && strcmp(s, "Set up one-session DeckCheatz") && strcmp(s, "Copy DeckCheatz Steam launch option") && strcmp(s, "Restore original Steam launch option") && strcmp(s, "Set up DeckCheatz for Steam") && strcmp(s, "Play via Steam + DeckCheatz") && strcmp(s, "DeckCheatz 1.x — Detect (no Steam options)") && strcmp(s, "DeckCheatz 1.x — Preview selected game (read-only)") && strcmp(s, "Play with WeMod") && strcmp(s, "Install DeckCheatz 1.x (managed)") && strcmp(s, "Check DeckCheatz updates") && strcmp(s, "Update DeckCheatz (opt-in)") && strcmp(s, "Manage existing DeckCheatz checkout") && strcmp(s, "Reset window size") && strcmp(s, "Check WeMod readiness") && strcmp(s, "Plan safe .NET test (read-only)") && strcmp(s, "Step 2 — Stage downloaded .NET prefix (isolated)") && strcmp(s, "Step 1 — Download selected prepared setup (cache only)") && strcmp(s, "Cancel cache download") && strcmp(s, "Find prepared WeMod setup") && strcmp(s, "Step 3 — Review prepared .NET prefix (read-only)") && strcmp(s, "Check game WeMod connection") && strcmp(s, "Check WeMod setup") && strcmp(s, "Open WeMod & DeckCheatz setup") && strcmp(s, "Update Steam Bridge") && strcmp(s, "Steam Bridge: Update installed launcher") && strcmp(s, "Steam Bridge: Set up selected game") && strcmp(s, "Steam Bridge: Enable WeMod next launch") && strcmp(s, "Steam Bridge: Disable WeMod next launch") && strcmp(s, "WeMod display: Try GPU off for this game") && strcmp(s, "WeMod display: Restore normal for this game") && strcmp(s, "Check Windows .NET in this game (read-only)")) pc2_guard_button(w);
    }
    return w;
}
static GtkWidget *box(int orient, int spacing) { return gtk_box_new(orient, spacing); }
static void pack(GtkWidget *b, GtkWidget *w, int expand) { gtk_box_pack_start(b, w, expand, expand, 0); }

static void log_line(const char *fmt, ...) {
    static char buf[32768];
    static size_t used = 0;
    char line[2048];
    va_list ap; va_start(ap, fmt); vsnprintf(line, sizeof line, fmt, ap); va_end(ap);
    time_t t=time(NULL); struct tm tm; localtime_r(&t,&tm); char ts[32]; strftime(ts,sizeof ts,"%H:%M:%S",&tm);
    char full[2200]; snprintf(full,sizeof full,"[%s] %s\n",ts,line);
    size_t n=strlen(full);
    if (used+n >= sizeof(buf)-1) { size_t drop=8192; memmove(buf,buf+drop,used-drop); used-=drop; }
    memcpy(buf+used,full,n); used+=n; buf[used]=0;
    if (G.activity) gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.activity), buf, -1);
}

static int http_request(const char *method, const char *path, const char *json, char **out_body, int *out_code) {
    *out_body=NULL; if(out_code)*out_code=0;
    int fd=socket(AF_INET,SOCK_STREAM,0); if(fd<0)return -1;
    struct sockaddr_in a={0}; a.sin_family=AF_INET; a.sin_port=htons((uint16_t)G.port); inet_pton(AF_INET,"127.0.0.1",&a.sin_addr);
    if(connect(fd,(struct sockaddr*)&a,sizeof a)<0){close(fd);return -1;}
    size_t jl=json?strlen(json):0;
    char hdr[4096]; int hn;
    if(json) hn=snprintf(hdr,sizeof hdr,"%s %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Type: application/json\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",method,path,G.port,jl,json);
    else hn=snprintf(hdr,sizeof hdr,"%s %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nConnection: close\r\n\r\n",method,path,G.port);
    if(write(fd,hdr,(size_t)hn)!=hn){close(fd);return -1;}
    char *resp=malloc(HTTP_MAX+1); if(!resp){close(fd);return -1;} size_t used=0;
    while(used<HTTP_MAX){ssize_t n=read(fd,resp+used,HTTP_MAX-used); if(n<=0)break; used+=(size_t)n;} close(fd); resp[used]=0;
    int code=0; sscanf(resp,"HTTP/%*s %d",&code); if(out_code)*out_code=code;
    char *body=strstr(resp,"\r\n\r\n"); body=body?body+4:resp;
    *out_body=strdup(body); free(resp); return 0;
}

static const char *find_key(const char *json, const char *key) {
    static char pat[128]; snprintf(pat,sizeof pat,"\"%s\":",key); return strstr(json,pat);
}
static int json_bool(const char *json,const char *key,int def) {
    const char *p=find_key(json,key); if(!p)return def; p=strchr(p,':'); if(!p)return def; p++; while(isspace((unsigned char)*p))p++; if(!strncmp(p,"true",4))return 1; if(!strncmp(p,"false",5))return 0; return def;
}
static void json_string(const char *json,const char *key,char *dst,size_t cap) {
    if(cap)dst[0]=0; const char *p=find_key(json,key); if(!p)return; p=strchr(p,':'); if(!p)return; p++; while(isspace((unsigned char)*p))p++; if(*p!='\"')return; p++;
    size_t j=0; while(*p && *p!='\"' && j+1<cap){ if(*p=='\\' && p[1]){p++; if(*p=='n'){dst[j++]='\n';p++;} else if(*p=='t'){dst[j++]='\t';p++;} else if(*p=='r'){dst[j++]='\r';p++;} else dst[j++]=*p++;} else dst[j++]=*p++; } dst[j]=0;
}
static const char *game_key(const Game *g){return (g&&g->key[0])?g->key:(g?g->appid:"");}
static int game_is_steam_shortcut(const Game *g){return g&&(!strcmp(g->provider,"steam-shortcut")||!strcmp(g->runner,"steam-shortcut"));}
static const char *steam_shortcut_preview_backend(const Game *g){if(!game_is_steam_shortcut(g))return "unassigned";if(g->shortcut_launch_supported)return "steam-shortcut-resolved";if(!strncmp(g->resolution_state,"native-or-script",16)||!strcmp(g->target_kind,"linux-appimage")||!strcmp(g->target_kind,"script"))return "steam-shortcut-native";return "steam-shortcut";}
static int game_is_steam(const Game *g){return !g||!g->provider[0]||!strcmp(g->provider,"steam")||game_is_steam_shortcut(g);}
static int game_is_heroic(const Game *g){return g&&!strcmp(g->provider,"heroic");}
static int game_is_lutris(const Game *g){return g&&!strcmp(g->provider,"lutris");}
static int lutris_session_ready(const Game *g){return g&&game_is_lutris(g)&&g->shortcut_launch_supported&&!strcmp(g->resolution_state,"resolved")&&g->prefix[0]&&g->executable[0]&&g->wine_bin[0]&&g->launch_uri[0]&&access(g->wine_bin,X_OK)==0;}
static int game_launch_enabled(const Game *g){return g&&(!game_is_lutris(g)||lutris_session_ready(g));}
static int lutris_test4_extended_blocked(const Game *g,const char *action){
    if(!game_is_lutris(g))return 0;
    log_line("Lutris %s is intentionally outside GameWeld 0.6.0 Test 4 for %s. Test 4 enables resolved game launch plus assigned/custom local-trainer same-session handoff only; manager, .CT, WeMod and saved-profile integration remain fail-closed.",action&&*action?action:"action",g->name[0]?g->name:"the selected game");
    return 1;
}
static const char *game_source_name(const Game *g){if(game_is_steam(g))return "Steam";if(game_is_heroic(g))return "Heroic";if(game_is_lutris(g))return "Lutris";return "Unknown";}
static int game_wemod_supported(const Game *g){if(!g||game_is_steam_shortcut(g)||game_is_lutris(g))return 0;if(game_is_steam(g))return 1;if(game_is_heroic(g))return g->prefix[0]&&g->wine_bin[0]&&access(g->wine_bin,X_OK)==0;return 0;}
static const char *game_ce_id(const Game *g){return game_is_steam(g)?g->appid:"0";}
static const char *heroic_provider_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-provider.py",a);else snprintf(p,sizeof p,"gameweld-heroic-provider.py");return p;}
static const char *wand_patcher_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-wand-patcher.py",a);else snprintf(p,sizeof p,"gameweld-wand-patcher.py");return p;}
static const char *lutris_provider_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-lutris-provider.py",a);else snprintf(p,sizeof p,"gameweld-lutris-provider.py");return p;}
static const char *lutris_session_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-lutris-session.sh",a);else snprintf(p,sizeof p,"gameweld-lutris-session.sh");return p;}
static const char *heroic_launch_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-launch.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-launch.sh");return p;}
static const char *heroic_cheat_table_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-cheat-table.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-cheat-table.sh");return p;}
static const char *heroic_local_trainer_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-local-trainer.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-local-trainer.sh");return p;}
static const char *heroic_session_control_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-session-control.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-session-control.sh");return p;}
static const char *heroic_trainer_runtime_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-trainer-runtime.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-trainer-runtime.sh");return p;}
static const char *heroic_wemod_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-wemod.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-wemod.sh");return p;}
static const char *trainer_updates_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-updates.py",a);else snprintf(p,sizeof p,"gameweld-trainer-updates.py");return p;}
static const char *trainer_library_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-library.py",a);else snprintf(p,sizeof p,"gameweld-trainer-library.py");return p;}
static const char *trainer_manager_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-manager.sh",a);else snprintf(p,sizeof p,"gameweld-trainer-manager.sh");return p;}
static const char *trainer_manager_game_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-manager-game.sh",a);else snprintf(p,sizeof p,"gameweld-trainer-manager-game.sh");return p;}
static const char *support_bundle_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-support-bundle.py",a);else snprintf(p,sizeof p,"gameweld-support-bundle.py");return p;}
static const char *steam_shortcuts_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-steam-shortcuts.py",a);else snprintf(p,sizeof p,"gameweld-steam-shortcuts.py");return p;}
static const char *steam_shortcut_live_launch_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-steam-shortcut-live-launch.sh",a);else snprintf(p,sizeof p,"gameweld-steam-shortcut-live-launch.sh");return p;}

/* Shell-free helper: paths and metadata are passed as exact argv tokens.
 * Do not use popen/system with untrusted game IDs, APPDIR, or XDG paths. */
static FILE *pc2_read_argv(const char *program,const char *arg1,
                          const char *arg2,const char *arg3,pid_t *child){
    if(child)*child=-1;
    if(!program||!*program||!child)return NULL;
    int fds[2];if(pipe(fds)!=0)return NULL;
    pid_t pid=fork();
    if(pid<0){close(fds[0]);close(fds[1]);return NULL;}
    if(pid==0){
        close(fds[0]);
        if(dup2(fds[1],STDOUT_FILENO)<0)_exit(127);
        close(fds[1]);
        int dn=open("/dev/null",O_WRONLY);
        if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}
        execlp(program,program,arg1,arg2,arg3,(char*)NULL);
        _exit(127);
    }
    close(fds[1]);
    FILE *stream=fdopen(fds[0],"r");
    if(!stream){
        close(fds[0]);int st=0;
        while(waitpid(pid,&st,0)<0&&errno==EINTR){}
        return NULL;
    }
    *child=pid;return stream;
}
static int pc2_close_read_argv(FILE *stream,pid_t child){
    if(!stream||child<=0)return 0;
    fclose(stream);int status=0;pid_t done;
    do{done=waitpid(child,&status,0);}while(done<0&&errno==EINTR);
    return done==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0;
}

static void state_safe_id(const char *in,char *out,size_t cap){size_t j=0;if(!cap)return;for(size_t i=0;in&&in[i]&&j+1<cap;i++){unsigned char c=(unsigned char)in[i];out[j++]=(isalnum(c)||c=='_'||c=='.'||c=='-')?(char)c:'_';}out[j]=0;}
static int heroic_runtime_repair_active_ui(const Game*g){
    if(!g||!game_is_heroic(g))return 0;
    char rr[128],aa[256],path[2048],progress[2048];state_safe_id(g->runner,rr,sizeof rr);state_safe_id(g->appid,aa,sizeof aa);
    const char*x=getenv("XDG_STATE_HOME"),*h=getenv("HOME");
    if(x&&*x)snprintf(path,sizeof path,"%s/gameweld/heroic-trainer-runtime-%s-%s.repairing",x,rr,aa);
    else snprintf(path,sizeof path,"%s/.local/state/gameweld/heroic-trainer-runtime-%s-%s.repairing",h?h:".",rr,aa);
    FILE*f=fopen(path,"r");if(!f)return 0;long pid=0;if(fscanf(f,"%ld",&pid)!=1)pid=0;fclose(f);
    if(pid>1&&kill((pid_t)pid,0)==0)return 1;
    unlink(path);snprintf(progress,sizeof progress,"%.*s.progress",(int)(strlen(path)-strlen(".repairing")),path);unlink(progress);return 0;
}

static int heroic_managed_session_state(const Game*g,long*game_pid,long*trainer_pid,char*launch,size_t launch_cap){
    if(game_pid)*game_pid=0;if(trainer_pid)*trainer_pid=0;if(launch&&launch_cap)launch[0]=0;
    if(!g||!game_is_heroic(g))return 0;
    char rr[128],aa[256],path[2048],line[4096],state[64]={0};long gp=0,tp=0;
    state_safe_id(g->runner,rr,sizeof rr);state_safe_id(g->appid,aa,sizeof aa);
    const char*x=getenv("XDG_STATE_HOME"),*h=getenv("HOME");
    if(x&&*x)snprintf(path,sizeof path,"%s/gameweld/heroic-managed-session-%s-%s.state",x,rr,aa);
    else snprintf(path,sizeof path,"%s/.local/state/gameweld/heroic-managed-session-%s-%s.state",h?h:".",rr,aa);
    FILE*f=fopen(path,"r");if(!f)return 0;
    while(fgets(line,sizeof line,f)){
        line[strcspn(line,"\r\n")]=0;
        if(!strncmp(line,"state=",6))snprintf(state,sizeof state,"%.*s",(int)sizeof(state)-1,line+6);
        else if(!strncmp(line,"game_pid=",9))gp=strtol(line+9,NULL,10);
        else if(!strncmp(line,"trainer_pid=",12))tp=strtol(line+12,NULL,10);
        else if(launch&&launch_cap&&!strncmp(line,"launch_path=",12))snprintf(launch,launch_cap,"%.*s",(int)(launch_cap?launch_cap-1:0),line+12);
    }
    fclose(f);
    int game_live=(gp>1&&kill((pid_t)gp,0)==0),trainer_live=(tp>1&&kill((pid_t)tp,0)==0);
    if(game_pid)*game_pid=game_live?gp:0;if(trainer_pid)*trainer_pid=trainer_live?tp:0;
    if(!strcmp(state,"running")&&game_live)return 1;
    if((!strcmp(state,"trainer-only")||!game_live)&&trainer_live)return 2;
    return 0;
}

static int parse_games(const char *json) {
    const char *p=find_key(json,"games"); if(!p)return 0; p=strchr(p,'['); if(!p)return 0; p++;
    int count=0; while(*p && *p!=']' && count<MAX_GAMES){ while(*p && *p!='{' && *p!=']')p++; if(*p!='{')break; const char *start=p; int depth=0; int inq=0; do{ if(*p=='\"' && (p==start||p[-1]!='\\'))inq=!inq; if(!inq){if(*p=='{')depth++;else if(*p=='}')depth--;} p++; }while(*p && depth>0); size_t n=(size_t)(p-start); char *obj=malloc(n+1); memcpy(obj,start,n); obj[n]=0;
        Game *g=&G.games[count]; memset(g,0,sizeof *g); json_string(obj,"appid",g->appid,sizeof g->appid); json_string(obj,"name",g->name,sizeof g->name); json_string(obj,"install_dir",g->install_dir,sizeof g->install_dir); json_string(obj,"selected_tool",g->selected_tool,sizeof g->selected_tool); g->wand_found=json_bool(obj,"wand_found",0); snprintf(g->provider,sizeof g->provider,"steam");snprintf(g->runner,sizeof g->runner,"steam");snprintf(g->key,sizeof g->key,"%s",g->appid); free(obj); if(g->appid[0])count++;
    } return count;
}

static int append_steam_shortcut_games(int start){
    if(start>=MAX_GAMES)return start;pid_t read_pid=-1;FILE*f=pc2_read_argv("python3",steam_shortcuts_tool(),"list",NULL,&read_pid);if(!f)return start;char line[16384];int count=start;
    while(count<MAX_GAMES&&fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(!line[0]||line[0]!='{')continue;Game*g=&G.games[count];memset(g,0,sizeof *g);json_string(line,"appid",g->appid,sizeof g->appid);json_string(line,"gameid",g->launch_id,sizeof g->launch_id);json_string(line,"key",g->key,sizeof g->key);json_string(line,"provider",g->provider,sizeof g->provider);json_string(line,"runner",g->runner,sizeof g->runner);json_string(line,"name",g->name,sizeof g->name);json_string(line,"install_dir",g->install_dir,sizeof g->install_dir);json_string(line,"executable",g->executable,sizeof g->executable);json_string(line,"prefix",g->prefix,sizeof g->prefix);json_string(line,"compatdata",g->compatdata,sizeof g->compatdata);json_string(line,"steam_root",g->steam_root,sizeof g->steam_root);json_string(line,"launch_options",g->launch_options,sizeof g->launch_options);json_string(line,"target_kind",g->target_kind,sizeof g->target_kind);json_string(line,"compat_tool",g->compat_tool,sizeof g->compat_tool);json_string(line,"compat_tool_path",g->compat_tool_path,sizeof g->compat_tool_path);json_string(line,"compat_tool_source",g->compat_tool_source,sizeof g->compat_tool_source);json_string(line,"resolution_state",g->resolution_state,sizeof g->resolution_state);json_string(line,"resolution_label",g->resolution_label,sizeof g->resolution_label);json_string(line,"launch_uri",g->launch_uri,sizeof g->launch_uri);g->shortcut_runtime_resolved=json_bool(line,"runtime_resolved",0);g->shortcut_prefix_found=json_bool(line,"prefix_found",0);g->shortcut_runtime_found=json_bool(line,"runtime_found",0);g->shortcut_launch_supported=json_bool(line,"launch_supported",0);if(g->appid[0]&&g->name[0]&&g->key[0])count++;}
    pc2_close_read_argv(f,read_pid);return count;
}

static int append_heroic_games(int start){
    if(start>=MAX_GAMES)return start;pid_t read_pid=-1;FILE*f=pc2_read_argv("python3",heroic_provider_tool(),"list",NULL,&read_pid);if(!f)return start;char line[16384];int count=start;
    while(count<MAX_GAMES&&fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(!line[0]||line[0]!='{')continue;Game*g=&G.games[count];memset(g,0,sizeof *g);json_string(line,"appid",g->appid,sizeof g->appid);json_string(line,"key",g->key,sizeof g->key);json_string(line,"provider",g->provider,sizeof g->provider);json_string(line,"runner",g->runner,sizeof g->runner);json_string(line,"name",g->name,sizeof g->name);json_string(line,"install_dir",g->install_dir,sizeof g->install_dir);json_string(line,"executable",g->executable,sizeof g->executable);json_string(line,"prefix",g->prefix,sizeof g->prefix);json_string(line,"wine_type",g->wine_type,sizeof g->wine_type);json_string(line,"wine_bin",g->wine_bin,sizeof g->wine_bin);json_string(line,"wine_name",g->wine_name,sizeof g->wine_name);json_string(line,"art_path",g->art_path,sizeof g->art_path);json_string(line,"heroic_root",g->heroic_root,sizeof g->heroic_root);if(g->appid[0]&&g->name[0])count++;}
    pc2_close_read_argv(f,read_pid);return count;
}

static int append_lutris_games(int start){
    if(start>=MAX_GAMES)return start;pid_t read_pid=-1;FILE*f=pc2_read_argv("python3",lutris_provider_tool(),"list",NULL,&read_pid);if(!f)return start;char line[16384];int count=start;
    while(count<MAX_GAMES&&fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(!line[0]||line[0]!='{')continue;Game*g=&G.games[count];memset(g,0,sizeof *g);json_string(line,"appid",g->appid,sizeof g->appid);json_string(line,"key",g->key,sizeof g->key);json_string(line,"provider",g->provider,sizeof g->provider);json_string(line,"runner",g->runner,sizeof g->runner);json_string(line,"name",g->name,sizeof g->name);json_string(line,"install_dir",g->install_dir,sizeof g->install_dir);json_string(line,"executable",g->executable,sizeof g->executable);json_string(line,"prefix",g->prefix,sizeof g->prefix);json_string(line,"wine_type",g->wine_type,sizeof g->wine_type);json_string(line,"wine_bin",g->wine_bin,sizeof g->wine_bin);json_string(line,"wine_name",g->wine_name,sizeof g->wine_name);json_string(line,"art_path",g->art_path,sizeof g->art_path);json_string(line,"launch_uri",g->launch_uri,sizeof g->launch_uri);json_string(line,"compat_tool",g->compat_tool,sizeof g->compat_tool);json_string(line,"compat_tool_path",g->compat_tool_path,sizeof g->compat_tool_path);json_string(line,"compat_tool_source",g->compat_tool_source,sizeof g->compat_tool_source);json_string(line,"resolution_state",g->resolution_state,sizeof g->resolution_state);json_string(line,"resolution_label",g->resolution_label,sizeof g->resolution_label);json_string(line,"target_kind",g->target_kind,sizeof g->target_kind);g->shortcut_prefix_found=json_bool(line,"prefix_found",0);g->shortcut_runtime_found=json_bool(line,"runtime_found",0);g->shortcut_launch_supported=json_bool(line,"launch_supported",0);if(g->appid[0]&&g->name[0]&&!strcmp(g->provider,"lutris"))count++;}
    pc2_close_read_argv(f,read_pid);return count;
}

static int refresh_model(char **err) {
    char *body=NULL; int code=0; if(http_request("GET","/api/status",NULL,&body,&code)<0){*err=strdup("Could not contact GameWeld backend.");return 0;}
    if(code!=200){*err=body;return 0;}
    G.wand_installed=json_bool(body,"wand_installed",0); G.wand_healthy=json_bool(body,"wand_healthy",0); G.base_compatible=json_bool(body,"base_compatible",0);
    json_string(body,"base_proton",G.base_proton,sizeof G.base_proton); json_string(body,"wand_tool",G.wand_tool,sizeof G.wand_tool); json_string(body,"verify_message",G.verify_message,sizeof G.verify_message);
    char old_selection[2048]={0};
    if(G.selected>=0&&G.selected<G.game_count)snprintf(old_selection,sizeof old_selection,"%s",game_key(&G.games[G.selected]));
    G.steam_manifest_game_count=parse_games(body); int steam_after_shortcuts=append_steam_shortcut_games(G.steam_manifest_game_count); G.steam_shortcut_count=steam_after_shortcuts-G.steam_manifest_game_count; G.steam_game_count=steam_after_shortcuts; int heroic_after=append_heroic_games(G.steam_game_count); G.heroic_game_count=heroic_after-G.steam_game_count; G.game_count=append_lutris_games(heroic_after); G.lutris_game_count=G.game_count-heroic_after;
    if(old_selection[0]){
        G.selected=-1;
        for(int i=0;i<G.game_count;i++)if(!strcmp(game_key(&G.games[i]),old_selection)){G.selected=i;break;}
    }else if(G.selected>=G.game_count)G.selected=G.game_count?0:-1;
    free(body); return 1;
}

static const char *proton_gate_repair(void){
    static char p[2048]; const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/wand-proton-launcher-repair.sh",appdir);
    else snprintf(p,sizeof p,"wand-proton-launcher-repair.sh");
    return p;
}
static int ensure_proton_gate(void){
    pid_t p=fork();
    if(p==0){execl(proton_gate_repair(),proton_gate_repair(),"--quiet",(char*)NULL);_exit(127);}
    if(p<0)return 0;
    int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}
    return WIFEXITED(st)&&WEXITSTATUS(st)==0;
}
static int arm_wand_launch(const char *appid){
    if(!appid||!*appid)return 0;
    /* The current explicit Proton gate consumes one-shot markers from
     * $XDG_RUNTIME_DIR/wand-native.  Test 9 still wrote them under gameweld,
     * so the repaired gate could miss the request entirely. */
    const char *runtime=getenv("XDG_RUNTIME_DIR"); char dir[2048],path[2200];
    if(runtime&&*runtime)snprintf(dir,sizeof dir,"%s/wand-native",runtime);
    else snprintf(dir,sizeof dir,"/tmp/wand-native-%ld",(long)getuid());
    if(mkdir(dir,0700)!=0&&errno!=EEXIST)return 0;
    chmod(dir,0700);
    snprintf(path,sizeof path,"%s/arm-%s",dir,appid);
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);if(fd<0)return 0;
    dprintf(fd,"appid=%s\npid=%ld\n",appid,(long)getpid());close(fd);return 1;
}

static void clear_desktop_activation_env(void) {
    unsetenv("DESKTOP_STARTUP_ID");
    unsetenv("XDG_ACTIVATION_TOKEN");
    unsetenv("GIO_LAUNCHED_DESKTOP_FILE");
    unsetenv("GIO_LAUNCHED_DESKTOP_FILE_PID");
}

static int start_backend(void) {
    const char *path=getenv("WAND_NATIVE_BACKEND"); char fallback[2048];
    if(!path||!*path){const char *appdir=getenv("APPDIR"); if(appdir){snprintf(fallback,sizeof fallback,"%s/usr/libexec/wand-native-backend",appdir);path=fallback;} else path="wand-native-backend";}
    int fds[2]; if(pipe(fds)<0)return 0; pid_t p=fork(); if(p<0)return 0;
    if(p==0){close(fds[0]); dup2(fds[1],STDOUT_FILENO); dup2(fds[1],STDERR_FILENO); close(fds[1]); clear_desktop_activation_env(); execl(path,path,(char*)NULL); _exit(127);} close(fds[1]); G.backend_pid=p;
    char line[1024]={0}; size_t n=0; for(int tries=0;tries<100 && n+1<sizeof line;tries++){char c; ssize_t r=read(fds[0],&c,1); if(r==1){line[n++]=c; if(c=='\n')break;} else {usleep(50000);} } close(fds[0]);
    char *q=strstr(line,"127.0.0.1:"); if(!q)return 0; G.port=atoi(q+10); return G.port>0;
}


static void config_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/local-trainers.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/local-trainers.tsv",home?home:".");
}
static void config_dir(char *out,size_t cap){char p[2048];config_path(p,sizeof p);snprintf(out,cap,"%s",p);char *slash=strrchr(out,'/');if(slash)*slash=0;}
static int load_local_trainer(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0; if(!appid||!*appid)return 0; char p[2048];config_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char *tab=strchr(line,'\t');if(!tab)continue;*tab=0;char *v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,appid)&&*v){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_local_trainer(const char *appid,const char *trainer){
    if(!appid||!*appid)return 0;char path[2048],dir[2048];config_path(path,sizeof path);config_dir(dir,sizeof dir);
    if(g_mkdir_with_parents(dir,0700)!=0)return 0;
    char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char *tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(trainer&&*trainer)fprintf(out,"%s\t%s\n",appid,trainer);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}

static void launch_profile_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/launch-profiles.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/launch-profiles.tsv",home?home:".");
}
static int launch_profile_mode_valid(const char *mode){
    return mode&&(!strcmp(mode,"assigned")||!strcmp(mode,"game-only")||!strcmp(mode,"wemod")||!strcmp(mode,"aurora")||!strcmp(mode,"cheat-evolution")||!strcmp(mode,"cheat-table"));
}
static const char *launch_profile_label(const char *mode){
    if(!mode||!*mode||!strcmp(mode,"assigned"))return "Assigned / detected trainer";
    if(!strcmp(mode,"game-only"))return "Game only";
    if(!strcmp(mode,"wemod"))return "WeMod";
    if(!strcmp(mode,"aurora"))return "Cheat Happens Aurora";
    if(!strcmp(mode,"cheat-evolution"))return "Cheat Evolution";
    if(!strcmp(mode,"cheat-table"))return "Cheat Engine Table (.CT)";
    return "Assigned / detected trainer";
}
static int load_launch_profile(const char *key,char *out,size_t cap){
    if(out&&cap)snprintf(out,cap,"assigned");if(!key||!*key)return 0;char p[2048];launch_profile_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char*tab=strchr(line,'\t');if(!tab)continue;*tab=0;char*v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,key)&&launch_profile_mode_valid(v)){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_launch_profile(const char *key,const char *mode){
    if(!key||!*key||!launch_profile_mode_valid(mode))return 0;char path[2048],dir[2048];launch_profile_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;
    if(g_mkdir_with_parents(dir,0700)!=0)return 0;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*outf=fopen(tmp,"w");if(!outf){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char*tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,key))continue;}fputs(line,outf);}fclose(in);}fprintf(outf,"%s\t%s\n",key,mode);fclose(outf);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}
static int delete_launch_profile(const char *key){
    if(!key||!*key)return 0;char path[2048];launch_profile_path(path,sizeof path);FILE*in=fopen(path,"r");if(!in)return 1;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*outf=fopen(tmp,"w");if(!outf){fclose(in);return 0;}char line[4096];
    while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char*tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,key))continue;}fputs(line,outf);}fclose(in);fclose(outf);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}

static int readable_file(const char *path);
static int windows_pe_executable(const char *path);
static void set_label(GtkWidget *w,const char *s);
static void refresh_ui(void);

enum { TL_GAME=0, TL_CONF, TL_VERSION, TL_HEALTH, TL_PROFILE, TL_POLICY, TL_LAUNCH, TL_REASON, TL_TRAINER, TL_FOLDER, TL_PATH, TL_KEY, TL_STATE, TL_ARCH, TL_RUNTIME, TL_ELEVATION, TL_PCONF, TL_SIGNALS, TL_RECOMMENDATION, TL_COLS };

/* RC9.1: keep the list readable. All scanner data remains in its model;
 * secondary compatibility/launch columns are available in the inspector. */
static GtkWidget *trainer_tree_new(void){
    GtkListStore *store=gtk_list_store_new(TL_COLS,g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"));
    GtkWidget *view=gtk_tree_view_new_with_model((GtkTreeModel*)store);
    g_object_unref(store);
    gtk_tree_view_set_headers_visible((GtkTreeView*)view,TRUE);
    const char *heads[]={"Game","Status","Version","Health","Trainer"};
    int columns[]={TL_GAME,TL_STATE,TL_VERSION,TL_HEALTH,TL_TRAINER};
    for(int i=0;i<5;i++){
        GtkCellRenderer *r=gtk_cell_renderer_text_new();
        gtk_cell_renderer_set_padding(r,9,8);
        /* Full game names are more useful than the default 3-character truncation.
         * Let the trainer filename yield space first, while retaining a
         * readable minimum for the game column. */
        if(i==4)g_object_set(r,"ellipsize",3,NULL);
        gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,heads[i],r,"text",columns[i],NULL);
        void *c=gtk_tree_view_get_column((GtkTreeView*)view,i);
        if(c){
            if(i==0){gtk_tree_view_column_set_min_width(c,255);gtk_tree_view_column_set_expand(c,TRUE);}
            else if(i==4){gtk_tree_view_column_set_min_width(c,190);gtk_tree_view_column_set_expand(c,TRUE);}
            else gtk_tree_view_column_set_min_width(c,i==2?112:80);
        }
    }
    gtk_tree_view_set_grid_lines((GtkTreeView*)view,GTK_TREE_VIEW_GRID_LINES_HORIZONTAL);
    return view;
}

enum { TG_STATE=0, TG_GAME, TG_CONF, TG_ISSUE, TG_KEY, TG_COLS };

static GtkWidget *trainer_attention_tree_new(void){
    GtkListStore *store=gtk_list_store_new(TG_COLS,g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"));
    GtkWidget *view=gtk_tree_view_new_with_model((GtkTreeModel*)store);g_object_unref(store);gtk_tree_view_set_headers_visible((GtkTreeView*)view,TRUE);
    GtkCellRenderer*r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Status",r,"text",TG_STATE,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Game",r,"text",TG_GAME,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Confidence",r,"text",TG_CONF,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Issue",r,"text",TG_ISSUE,NULL);
    gtk_tree_view_set_grid_lines((GtkTreeView*)view,GTK_TREE_VIEW_GRID_LINES_HORIZONTAL);
    return view;
}

static const char *trainer_library_query(void){return G.trainer_library_filter?gtk_entry_get_text((GtkEntry*)G.trainer_library_filter):"";}
static const char *trainer_library_sort_id(void){const char*id=G.trainer_library_sort?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_library_sort):NULL;return(id&&*id)?id:"status";}
static const char *trainer_library_readiness_id(void){const char*id=G.trainer_library_readiness_filter?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_library_readiness_filter):NULL;return(id&&*id)?id:"all";}
static int trainer_library_attention_only(void){return G.trainer_library_attention_toggle&&gtk_toggle_button_get_active((GtkToggleButton*)G.trainer_library_attention_toggle);}

static int trainer_game_index_by_key(const char *key){
    if(!key||!*key)return -1;
    for(int i=0;i<G.game_count;i++)if(!strcmp(game_key(&G.games[i]),key))return i;
    return -1;
}

/* Trainer rows and the game list must share one exact game identity.
 * Unmatched/manager rows cannot select a game by fuzzy title. */
static void trainer_update_context_refresh(void);
static void trainer_select_exact_game_key(const char *key){
    int idx=trainer_game_index_by_key(key);
    if(idx<0)return;
    G.selected=idx;
    if(G.game_list&&G.game_rows[idx])
        gtk_list_box_select_row((GtkListBox*)G.game_list,(GtkListBoxRow*)G.game_rows[idx]);
    refresh_ui();
    trainer_update_context_refresh();
}

static int trainer_pick_is_strong_target(void){
    return !strcmp(G.trainer_library_pick_state,"Matched")||!strcmp(G.trainer_library_pick_state,"Assigned")||!strcmp(G.trainer_library_pick_state,"Alternative");
}

typedef struct {
    char id[128];
    char label[256];
    char status[64];
    char session_kind[32];
    char runtime[2048];
    char prefix[2048];
    char pid[64];
    char log[2048];
    char game_key[320];
    char game[384];
    char reason[1024];
} TrainerManagerGamePlan;

static int trainer_manager_game_plan_for(const char*path,const Game*g,TrainerManagerGamePlan*out){
    if(!out)return 0;memset(out,0,sizeof *out);if(!path||!*path||!g)return 0;
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){
        close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}
        execl(trainer_manager_game_tool(),trainer_manager_game_tool(),"plan",path,g->provider,g->runner,g->appid,game_key(g),g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,g->compatdata,g->launch_id,(char*)NULL);_exit(127);
    }
    close(fd[1]);char buf[12288];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0||!used)return 0;buf[used]=0;buf[strcspn(buf,"\r\n")]=0;
    char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*id=strtok_r(NULL,"\t",&save);char*labelv=strtok_r(NULL,"\t",&save);char*status=strtok_r(NULL,"\t",&save);char*sk=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*prefix=strtok_r(NULL,"\t",&save);char*pidv=strtok_r(NULL,"\t",&save);char*log=strtok_r(NULL,"\t",&save);char*gkey=strtok_r(NULL,"\t",&save);char*gname=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);
    if(!kind||strcmp(kind,"MANAGER_GAME_PLAN")||!id||!labelv||!status||!sk||!runtime||!prefix||!pidv||!log||!gkey||!gname)return 0;
    snprintf(out->id,sizeof out->id,"%s",id);snprintf(out->label,sizeof out->label,"%s",labelv);snprintf(out->status,sizeof out->status,"%s",status);snprintf(out->session_kind,sizeof out->session_kind,"%s",sk);snprintf(out->runtime,sizeof out->runtime,"%s",runtime);snprintf(out->prefix,sizeof out->prefix,"%s",prefix);snprintf(out->pid,sizeof out->pid,"%s",pidv);snprintf(out->log,sizeof out->log,"%s",log);snprintf(out->game_key,sizeof out->game_key,"%s",gkey);snprintf(out->game,sizeof out->game,"%s",gname);snprintf(out->reason,sizeof out->reason,"%s",reason?reason:"");return 1;
}


static void update_trainer_library_actions(void){
    int have_pick=G.trainer_library_pick_path[0]&&readable_file(G.trainer_library_pick_path);
    int is_manager=!strcmp(G.trainer_library_pick_state,"Manager");
    int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);
    int selected_ok=G.selected>=0&&G.selected<G.game_count;
    int selected_matches=suggested>=0&&selected_ok&&!strcmp(game_key(&G.games[G.selected]),G.trainer_library_pick_key);
    int launchable=0;
    if(have_pick&&suggested>=0){
        char assigned[2048]={0};
        if(load_local_trainer(game_key(&G.games[suggested]),assigned,sizeof assigned)&&readable_file(assigned)&&!strcmp(assigned,G.trainer_library_pick_path)&&(!game_is_lutris(&G.games[suggested])||lutris_session_ready(&G.games[suggested]))&&(!game_is_steam_shortcut(&G.games[suggested])||G.games[suggested].shortcut_launch_supported))launchable=1;
    }
    if(G.trainer_library_assign_suggested)gtk_widget_set_sensitive(G.trainer_library_assign_suggested,have_pick&&!is_manager&&suggested>=0);
    if(G.trainer_library_select_suggested)gtk_widget_set_sensitive(G.trainer_library_select_suggested,suggested>=0);
    if(G.trainer_library_assign_selected){
        int safe=have_pick&&selected_ok&&!is_manager;
        if(safe&&trainer_pick_is_strong_target()&&suggested>=0&&!selected_matches)safe=0;
        gtk_widget_set_sensitive(G.trainer_library_assign_selected,safe);
    }
    if(G.trainer_library_open_folder)gtk_widget_set_sensitive(G.trainer_library_open_folder,have_pick);
    if(G.trainer_library_launch_manager_standalone){gtk_widget_set_visible(G.trainer_library_launch_manager_standalone,is_manager);gtk_widget_set_sensitive(G.trainer_library_launch_manager_standalone,is_manager&&have_pick);}
    if(G.trainer_library_launch_assigned){
        if(is_manager){
            if(selected_ok){
                TrainerManagerGamePlan gp={0};int ok=have_pick&&trainer_manager_game_plan_for(G.trainer_library_pick_path,&G.games[G.selected],&gp);
                if(ok&&!strcmp(gp.status,"running"))gtk_button_set_label((GtkButton*)G.trainer_library_launch_assigned,"Close manager for selected game");
                else gtk_button_set_label((GtkButton*)G.trainer_library_launch_assigned,"Launch manager for selected game");
                gtk_widget_set_sensitive(G.trainer_library_launch_assigned,ok&&(!strcmp(gp.status,"ready")||!strcmp(gp.status,"running")));
            }else{
                gtk_button_set_label((GtkButton*)G.trainer_library_launch_assigned,"Launch manager standalone");
                gtk_widget_set_sensitive(G.trainer_library_launch_assigned,have_pick);
            }
        }else{
            gtk_button_set_label((GtkButton*)G.trainer_library_launch_assigned,"Launch assigned trainer");gtk_widget_set_sensitive(G.trainer_library_launch_assigned,launchable);
        }
    }
}

static int trainer_profile_policy_label_for_path(const char*path,char*out,size_t cap){if(!out||!cap)return 0;out[0]=0;if(!path||!*path)return 0;int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"profile-policy",path,(char*)NULL);_exit(127);}close(fd[1]);char buf[1024]={0};ssize_t n=read(fd[0],buf,sizeof buf-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(n<=0||!WIFEXITED(st)||WEXITSTATUS(st)!=0)return 0;buf[n]=0;buf[strcspn(buf,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*mode=strtok_r(NULL,"\t",&save);char*label=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"PROFILE_POLICY")||!mode)return 0;snprintf(out,cap,"%s",(label&&*label)?label:mode);return 1;}


typedef struct {
    char revision[64];
    char recipe_id[96];
    char validation[64];
    char session[512];
    char automation[512];
    char elevation[512];
    char runtime[512];
    char dlls[512];
    char risk[512];
    char rationale[1024];
} TrainerCompatRecipe;

static int trainer_compat_recipe_for_path(const char*path,TrainerCompatRecipe*out){
    if(!out)return 0;memset(out,0,sizeof *out);if(!path||!*path)return 0;
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"profile-recipe",path,(char*)NULL);_exit(127);}
    close(fd[1]);char buf[12288];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0||!used)return 0;buf[used]=0;buf[strcspn(buf,"\r\n")]=0;
    char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*revision=strtok_r(NULL,"\t",&save);char*profile=strtok_r(NULL,"\t",&save);char*confidence=strtok_r(NULL,"\t",&save);char*recipe=strtok_r(NULL,"\t",&save);char*validation=strtok_r(NULL,"\t",&save);char*session=strtok_r(NULL,"\t",&save);char*automation=strtok_r(NULL,"\t",&save);char*elevation=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*dlls=strtok_r(NULL,"\t",&save);char*risk=strtok_r(NULL,"\t",&save);char*rationale=strtok_r(NULL,"\t",&save);
    (void)profile;(void)confidence;if(!kind||strcmp(kind,"COMPAT_RECIPE")||!revision||!recipe||!validation)return 0;
    snprintf(out->revision,sizeof out->revision,"%s",revision);snprintf(out->recipe_id,sizeof out->recipe_id,"%s",recipe);snprintf(out->validation,sizeof out->validation,"%s",validation);snprintf(out->session,sizeof out->session,"%s",session?session:"");snprintf(out->automation,sizeof out->automation,"%s",automation?automation:"");snprintf(out->elevation,sizeof out->elevation,"%s",elevation?elevation:"");snprintf(out->runtime,sizeof out->runtime,"%s",runtime?runtime:"");snprintf(out->dlls,sizeof out->dlls,"%s",dlls?dlls:"");snprintf(out->risk,sizeof out->risk,"%s",risk?risk:"");snprintf(out->rationale,sizeof out->rationale,"%s",rationale?rationale:"");return 1;
}

typedef struct {
    char action[64];
    char label[256];
    char runtime[256];
    char elevation[256];
    char policy_mode[64];
    char profile[128];
    char confidence[32];
    char reason[1024];
} TrainerLaunchPreview;

typedef struct {
    char id[128];
    char label[256];
    char runtime_kind[32];
    char runtime[2048];
    char prefix[2048];
    char log[2048];
    char status[64];
    char reason[1024];
} TrainerManagerPlan;

static int trainer_manager_plan_for_path(const char*path,TrainerManagerPlan*out){
    if(!out)return 0;memset(out,0,sizeof *out);if(!path||!*path)return 0;
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execl(trainer_manager_tool(),trainer_manager_tool(),"plan",path,(char*)NULL);_exit(127);}
    close(fd[1]);char buf[8192];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0||!used)return 0;buf[used]=0;buf[strcspn(buf,"\r\n")]=0;
    char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*id=strtok_r(NULL,"\t",&save);char*labelv=strtok_r(NULL,"\t",&save);char*rkind=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*prefix=strtok_r(NULL,"\t",&save);char*log=strtok_r(NULL,"\t",&save);char*status=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);
    if(!kind||strcmp(kind,"MANAGER_PLAN")||!id||!labelv||!rkind||!runtime||!prefix||!log||!status)return 0;
    snprintf(out->id,sizeof out->id,"%s",id);snprintf(out->label,sizeof out->label,"%s",labelv);snprintf(out->runtime_kind,sizeof out->runtime_kind,"%s",rkind);snprintf(out->runtime,sizeof out->runtime,"%s",runtime);snprintf(out->prefix,sizeof out->prefix,"%s",prefix);snprintf(out->log,sizeof out->log,"%s",log);snprintf(out->status,sizeof out->status,"%s",status);snprintf(out->reason,sizeof out->reason,"%s",reason?reason:"");return 1;
}


static int trainer_launch_preview_for_path(const char*path,const char*backend,TrainerLaunchPreview*out){
    if(!out)return 0;memset(out,0,sizeof *out);if(!path||!*path)return 0;if(!backend||!*backend)backend="unassigned";
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"launch-plan",path,backend,(char*)NULL);_exit(127);}
    close(fd[1]);char buf[8192];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0||!used)return 0;buf[used]=0;buf[strcspn(buf,"\r\n")]=0;
    char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*action=strtok_r(NULL,"\t",&save);char*labelv=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*elevation=strtok_r(NULL,"\t",&save);char*mode=strtok_r(NULL,"\t",&save);char*profile=strtok_r(NULL,"\t",&save);char*confidence=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);
    if(!kind||strcmp(kind,"LAUNCH_PLAN")||!action||!labelv||!runtime||!elevation||!mode||!profile||!confidence)return 0;
    snprintf(out->action,sizeof out->action,"%s",action);snprintf(out->label,sizeof out->label,"%s",labelv);snprintf(out->runtime,sizeof out->runtime,"%s",runtime);snprintf(out->elevation,sizeof out->elevation,"%s",elevation);snprintf(out->policy_mode,sizeof out->policy_mode,"%s",mode);snprintf(out->profile,sizeof out->profile,"%s",profile);snprintf(out->confidence,sizeof out->confidence,"%s",confidence);snprintf(out->reason,sizeof out->reason,"%s",reason?reason:"");return 1;
}

static void set_trainer_library_guidance(const char*state,const char*health,const char*profile,const char*pconf,const char*reason,int suggested,int ready_launch,const char*launch_code){
    G.trainer_library_action_code[0]=0;
    if(!G.trainer_library_guidance||!G.trainer_library_recommended_action)return;
    char msg[3072];const char*button="No direct action";int enable=0;
    const char*st=(state&&*state)?state:"Unmatched";const char*he=(health&&*health)?health:"—";
    int low=(pconf&&(!strcmp(pconf,"Low")))||(profile&&(!strcmp(profile,"Unknown Windows trainer")||!strcmp(profile,"Possible FLiNG trainer")||!strcmp(profile,"Conflicting trainer signatures")));
    if(!strcmp(st,"Missing")||!strcmp(he,"Missing")){
        snprintf(msg,sizeof msg,"Attention: assigned trainer file is missing.\nWhy: %s\nRecommended: rescan the suggested game first so GameWeld can recover an exact moved filename. If it cannot be recovered, use Remove Missing Mappings or Clear Selected Game Assignment; trainer EXE files are never deleted.",(reason&&*reason)?reason:"The stored assignment path is no longer readable.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"rescan-suggested");button="Rescan Suggested Game";enable=1;}else button="Use Remove Missing Mappings";
    }else if(!strcmp(st,"Ambiguous")){
        snprintf(msg,sizeof msg,"Attention: multiple plausible trainers matched this game.\nWhy: %s\nRecommended: inspect the selected candidate, then explicitly assign it to the suggested game only if it is the intended trainer. GameWeld will not choose an ambiguous candidate automatically.",(reason&&*reason)?reason:"The scan found more than one strong candidate.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-suggested");button="Assign This Candidate";enable=1;}
    }else if(!strcmp(st,"Manager")){
        if(G.selected>=0&&G.selected<G.game_count&&G.trainer_library_pick_path[0]){
            TrainerManagerGamePlan gp={0};int gpok=trainer_manager_game_plan_for(G.trainer_library_pick_path,&G.games[G.selected],&gp);
            if(gpok&&!strcmp(gp.status,"ready")){
                snprintf(msg,sizeof msg,"Manager/game integration ready for %s.\nWhy: %s\nRecommended: launch this manager inside the selected game's live %s compatibility session. This joins the exact game prefix/wineserver so the Windows manager can see the Windows game process. The manager remains unassigned and the standalone manager prefix is not reused.",G.games[G.selected].name,gp.reason,gp.session_kind);
                snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"launch-manager-game");button="Launch Manager for Selected Game";enable=1;
            }else if(gpok&&!strcmp(gp.status,"running")){
                snprintf(msg,sizeof msg,"Manager/game integration is already active for %s.\nWhy: %s\nNo duplicate manager instance will be started.",G.games[G.selected].name,gp.reason);button="Manager Already Active";enable=0;
            }else{
                snprintf(msg,sizeof msg,"Recognized trainer manager application.\nSelected game: %s\nGame-session status: %s\nWhy: %s\nRecommended: start the selected game first, then use Launch Manager for Selected Game. Standalone launch remains available separately for login/setup and never creates a per-game trainer assignment.",G.games[G.selected].name,(gpok&&gp.status[0])?gp.status:"unavailable",(gpok&&gp.reason[0])?gp.reason:((reason&&*reason)?reason:"No compatible live session is currently available."));
                button="Start Game First";enable=0;
            }
        }else{
            snprintf(msg,sizeof msg,"Recognized trainer manager application.\nWhy: %s\nRecommended: select a game to inspect live-session compatibility, or launch the manager standalone in its dedicated persistent GameWeld prefix for login/setup. Manager applications are never auto-assigned to games.",(reason&&*reason)?reason:"This executable belongs to a validated multi-game trainer-manager package.");
            if(G.trainer_library_pick_path[0]){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"launch-manager");button="Launch Manager Standalone";enable=1;}
        }
    }else if(!strcmp(st,"Unmatched")){
        snprintf(msg,sizeof msg,"Attention: this trainer has no conservative game match.\nWhy: %s\nRecommended: select the intended game in Library and use Assign to Selected Game. If this EXE is not a trainer you want GameWeld to manage, use Ignore Selected Trainer.",(reason&&*reason)?reason:"No installed game reached the automatic-match threshold.");
        if(G.selected>=0&&G.selected<G.game_count){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-selected");button="Assign to Selected Game";enable=1;}else if(G.trainer_library_pick_path[0]){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"open-folder");button="Open Trainer Folder";enable=1;}
    }else if(!strcmp(st,"Alternative")){
        snprintf(msg,sizeof msg,"Review: this is an alternate trainer version for the suggested game.\nRecommended: assign it only if you intentionally want to switch the game's current trainer version. The current assignment remains unchanged until you click the action.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-suggested");button="Use This Trainer Version";enable=1;}
    }else if(!ready_launch){
        snprintf(msg,sizeof msg,"Action needed: this trainer is not the exact trainer currently assigned to a launch target.\nRecommended: assign it explicitly before direct launch. This prevents Trainer Library from silently changing a game's active trainer.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-suggested");button="Assign to Suggested Game";enable=1;}
        else if(G.selected>=0&&G.selected<G.game_count){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-selected");button="Assign to Selected Game";enable=1;}
    }else if(launch_code&&!strcmp(launch_code,"steam-shortcut-resolved")){
        snprintf(msg,sizeof msg,"Ready: this trainer is matched to a Steam non-Steam shortcut whose Steam Play runtime and compatdata/prefix have been identified.\nGameWeld validates the live shortcut session, waits for the actual configured Windows game EXE and visible game readiness, then launches the trainer through that exact Proton prefix with runinprefix.\nRecommended: Launch Assigned Trainer.");
        button="Live handoff ready";enable=0;
    }else if(launch_code&&!strcmp(launch_code,"steam-shortcut-native")){
        snprintf(msg,sizeof msg,"Review: this trainer is matched to a Steam non-Steam shortcut with no resolved Proton/compatdata session.\nA native Linux/script shortcut cannot receive a Windows trainer through Proton unless Steam Play is actually configured and produces a prefix.\nRecommended: verify the shortcut's Steam compatibility setting before attempting trainer launch.");
        button="No Proton session resolved";enable=0;
    }else if(launch_code&&!strcmp(launch_code,"steam-shortcut-pending")){
        snprintf(msg,sizeof msg,"Resolution incomplete: this trainer is matched to a Steam non-Steam shortcut, but GameWeld could not resolve both a concrete Steam Play runtime and compatdata prefix.\nRecommended: launch the shortcut once from Steam with the intended compatibility tool, then refresh Game Sources so GameWeld can inspect the created compatdata safely.");
        button="Runtime/prefix unresolved";enable=0;
    }else if(low){
        snprintf(msg,sizeof msg,"Review recommended: the trainer compatibility profile is advisory or low confidence.\nRecommended: keep Auto Detect unless you have validated a manual policy for this trainer. The profile buttons above remain explicit user choices; GameWeld will not promote this advisory profile into a new automatic compatibility path.");
        if(G.trainer_library_pick_path[0]){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"open-folder");button="Open Trainer Folder";enable=1;}
    }else{
        snprintf(msg,sizeof msg,"Ready: assignment, health and launch targeting are valid.\nNext launch: %s\nRecommended: launch the exact assigned trainer through the already-validated Steam/Heroic path.",(launch_code&&*launch_code)?launch_code:"resolved by current backend policy");
        snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"launch");button="Launch Assigned Trainer";enable=1;
    }
    set_label(G.trainer_library_guidance,msg);
    gtk_button_set_label((GtkButton*)G.trainer_library_recommended_action,button);
    gtk_widget_set_sensitive(G.trainer_library_recommended_action,enable);
    /* The main Trainer Actions panel owns the one Launch button. */
    gtk_widget_set_visible(G.trainer_library_recommended_action,
        strcmp(G.trainer_library_action_code,"launch") &&
        strcmp(G.trainer_library_action_code,"launch-manager") &&
        strcmp(G.trainer_library_action_code,"launch-manager-game"));
}

static void trainer_pick_changed(GtkTreeSelection *sel,void*d){
    (void)d;GtkTreeModel*m=NULL;GtkTreeIter it;
    if(!gtk_tree_selection_get_selected(sel,&m,&it))return;
    char *game=NULL,*conf=NULL,*version=NULL,*health=NULL,*profile=NULL,*reason=NULL,*path=NULL,*key=NULL,*state=NULL,*folder=NULL,*arch=NULL,*runtime=NULL,*elevation=NULL,*pconf=NULL,*signals=NULL,*recommendation=NULL;
    gtk_tree_model_get(m,&it,TL_GAME,&game,TL_CONF,&conf,TL_VERSION,&version,TL_HEALTH,&health,TL_PROFILE,&profile,TL_REASON,&reason,TL_PATH,&path,TL_KEY,&key,TL_STATE,&state,TL_FOLDER,&folder,TL_ARCH,&arch,TL_RUNTIME,&runtime,TL_ELEVATION,&elevation,TL_PCONF,&pconf,TL_SIGNALS,&signals,TL_RECOMMENDATION,&recommendation,-1);
    /* Update active context *before* computing launch guidance.  In RC9.1
     * a clicked CONTROL Resonant row could leave 7 Days to Die active. */
    trainer_select_exact_game_key(key);
    if(G.trainer_updates_provider&&key&&*key){
        const char *source=NULL;
        if(path&&(strstr(path,"/HexTrainer/")||strstr(path,"/hextrainer/")))source="hextrainer";
        else if(path&&(strstr(path,"/CheatEvolution/")||strstr(path,"/Cheat Evolution/")))source="cheatevolution";
        else if(path&&(strstr(path,"/Aurora/")||strstr(path,"/CheatHappens/")))source="aurora";
        else if(path&&(strstr(path,"/Wand/")||strstr(path,"/WeMod/")))source="wand";
        else if((path&&strstr(path,"FLiNG"))||(profile&&strstr(profile,"FLiNG")))source="fling";
        if(source)gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_updates_provider,source);
    }
    if(G.trainer_library_quick_summary){
        char quick[2048];
        const char *nm=(game&&*game)?game:"Unmatched trainer";
        const char *v=(version&&*version&&strcmp(version,"—"))?version:"Not identified";
        snprintf(quick,sizeof quick,"%s\nStatus: %s  ·  Health: %s\nVersion label: %s  ·  Runtime: %s\nCompatibility: %s",
            nm,(state&&*state)?state:"Unmatched",(health&&*health)?health:"Unknown",v,
            (runtime&&*runtime)?runtime:"Not identified",(profile&&*profile)?profile:"Unknown");
        set_label(G.trainer_library_quick_summary,quick);
    }
    if(path&&*path){
        snprintf(G.trainer_library_pick_path,sizeof G.trainer_library_pick_path,"%s",path);
        snprintf(G.trainer_library_pick_game,sizeof G.trainer_library_pick_game,"%s",game?game:"");
        snprintf(G.trainer_library_pick_key,sizeof G.trainer_library_pick_key,"%s",key?key:"");
        snprintf(G.trainer_library_pick_state,sizeof G.trainer_library_pick_state,"%s",state?state:"");
        if(G.trainer_library_pick){
            char msg[6144];int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);
            snprintf(msg,sizeof msg,"Selected trainer: %s\nStatus: %s • Health: %s • Suggested game: %s%s%s%s%s\nCompatibility profile: %s%s%s\nArchitecture: %s • Runtime: %s\nElevation: %s",path,(state&&*state)?state:"UNMATCHED",(health&&*health)?health:"—",(game&&*game)?game:"unmatched",(conf&&*conf)?" • confidence ":"",(conf&&*conf)?conf:"",(version&&*version)?" • version ":"",(version&&*version)?version:"",(profile&&*profile)?profile:"Unknown",(pconf&&*pconf&&strcmp(pconf,"—"))?" • detection confidence ":"",(pconf&&*pconf&&strcmp(pconf,"—"))?pconf:"",(arch&&*arch)?arch:"Unknown",(runtime&&*runtime)?runtime:"Unknown",(elevation&&*elevation)?elevation:"Not declared");
            if(signals&&*signals&&strcmp(signals,"—")){strncat(msg,"\nSignals: ",sizeof msg-strlen(msg)-1);strncat(msg,signals,sizeof msg-strlen(msg)-1);}strncat(msg,"\nDetector: 0.5.0-test5-r1 • Scanner: 0.5.0-test4-r1 • Manager Launcher: 0.5.0-test7-r1 • Manager/Game Bridge: 0.5.0-test17-r1 • real manager-package fingerprints are sample-backed; conflicts remain manual-review only",sizeof msg-strlen(msg)-1);
            if(recommendation&&*recommendation&&strcmp(recommendation,"—")){strncat(msg,"\nSuggested GameWeld profile: ",sizeof msg-strlen(msg)-1);strncat(msg,recommendation,sizeof msg-strlen(msg)-1);}
            TrainerCompatRecipe recipe={0};if(trainer_compat_recipe_for_path(path,&recipe)){strncat(msg,"\nCompatibility Engine v2: ",sizeof msg-strlen(msg)-1);strncat(msg,recipe.recipe_id,sizeof msg-strlen(msg)-1);strncat(msg," • ",sizeof msg-strlen(msg)-1);strncat(msg,recipe.validation,sizeof msg-strlen(msg)-1);if(recipe.automation[0]){strncat(msg,"\nAutomation: ",sizeof msg-strlen(msg)-1);strncat(msg,recipe.automation,sizeof msg-strlen(msg)-1);}if(recipe.session[0]){strncat(msg,"\nSession recipe: ",sizeof msg-strlen(msg)-1);strncat(msg,recipe.session,sizeof msg-strlen(msg)-1);}if(recipe.risk[0]){strncat(msg,"\nRecipe risk: ",sizeof msg-strlen(msg)-1);strncat(msg,recipe.risk,sizeof msg-strlen(msg)-1);}}
            char policy_label[512];if(trainer_profile_policy_label_for_path(path,policy_label,sizeof policy_label)){strncat(msg,"\nLaunch policy: ",sizeof msg-strlen(msg)-1);strncat(msg,policy_label,sizeof msg-strlen(msg)-1);}
            TrainerLaunchPreview preview={0};int ready_launch=0;
            if(state&&(!strcmp(state,"Manager")||!strcmp(state,"MANAGER"))){
                TrainerManagerPlan mp={0};
                if(trainer_manager_plan_for_path(path,&mp)){
                    strncat(msg,"\nStandalone manager status: ",sizeof msg-strlen(msg)-1);strncat(msg,mp.status,sizeof msg-strlen(msg)-1);
                    strncat(msg,"\nStandalone runtime: ",sizeof msg-strlen(msg)-1);strncat(msg,mp.runtime_kind,sizeof msg-strlen(msg)-1);strncat(msg," • ",sizeof msg-strlen(msg)-1);strncat(msg,mp.runtime,sizeof msg-strlen(msg)-1);
                    strncat(msg,"\nDedicated manager prefix: ",sizeof msg-strlen(msg)-1);strncat(msg,mp.prefix,sizeof msg-strlen(msg)-1);
                    strncat(msg,"\nStandalone log: ",sizeof msg-strlen(msg)-1);strncat(msg,mp.log,sizeof msg-strlen(msg)-1);
                    if(mp.reason[0]){strncat(msg,"\nStandalone plan: ",sizeof msg-strlen(msg)-1);strncat(msg,mp.reason,sizeof msg-strlen(msg)-1);}
                }else strncat(msg,"\nStandalone launch plan: unavailable — package validation or runtime resolution failed.",sizeof msg-strlen(msg)-1);
                if(G.selected>=0&&G.selected<G.game_count){
                    TrainerManagerGamePlan gp={0};Game*cg=&G.games[G.selected];
                    strncat(msg,"\nSelected game context: ",sizeof msg-strlen(msg)-1);strncat(msg,cg->name,sizeof msg-strlen(msg)-1);strncat(msg," • ",sizeof msg-strlen(msg)-1);strncat(msg,cg->provider,sizeof msg-strlen(msg)-1);
                    if(trainer_manager_game_plan_for(path,cg,&gp)){
                        strncat(msg,"\nGame-session manager status: ",sizeof msg-strlen(msg)-1);strncat(msg,gp.status,sizeof msg-strlen(msg)-1);
                        if(gp.pid[0]&&strcmp(gp.pid,"—")){strncat(msg," • game/session PID ",sizeof msg-strlen(msg)-1);strncat(msg,gp.pid,sizeof msg-strlen(msg)-1);}
                        strncat(msg,"\nGame-session runtime: ",sizeof msg-strlen(msg)-1);strncat(msg,gp.session_kind,sizeof msg-strlen(msg)-1);strncat(msg," • ",sizeof msg-strlen(msg)-1);strncat(msg,gp.runtime,sizeof msg-strlen(msg)-1);
                        strncat(msg,"\nGame-session prefix: ",sizeof msg-strlen(msg)-1);strncat(msg,gp.prefix,sizeof msg-strlen(msg)-1);
                        strncat(msg,"\nGame-session log: ",sizeof msg-strlen(msg)-1);strncat(msg,gp.log,sizeof msg-strlen(msg)-1);
                        if(gp.reason[0]){strncat(msg,"\nIntegration plan: ",sizeof msg-strlen(msg)-1);strncat(msg,gp.reason,sizeof msg-strlen(msg)-1);}
                    }else strncat(msg,"\nGame-session plan: unavailable for the selected game.",sizeof msg-strlen(msg)-1);
                }else strncat(msg,"\nSelected game context: none — choose a game to inspect same-session manager compatibility.",sizeof msg-strlen(msg)-1);
                strncat(msg,"\nTrainer Library rule: manager applications are never assigned to an individual game. Standalone launch is for login/setup; game-attached launch joins only an already-running compatible Windows game session.",sizeof msg-strlen(msg)-1);
            }else{
                const char*preview_backend="unassigned";if(suggested>=0)preview_backend=game_is_lutris(&G.games[suggested])?"unassigned":(game_is_steam_shortcut(&G.games[suggested])?steam_shortcut_preview_backend(&G.games[suggested]):(game_is_steam(&G.games[suggested])?"steam":"heroic"));
                if(trainer_launch_preview_for_path(path,preview_backend,&preview)){strncat(msg,"\nEffective next launch: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.label,sizeof msg-strlen(msg)-1);if(preview.runtime[0]&&strcmp(preview.runtime,"—")){strncat(msg,"\nRuntime: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.runtime,sizeof msg-strlen(msg)-1);}if(preview.elevation[0]&&strcmp(preview.elevation,"—")){strncat(msg,"\nLaunch elevation: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.elevation,sizeof msg-strlen(msg)-1);}if(preview.reason[0]){strncat(msg,"\nLaunch-plan reason: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.reason,sizeof msg-strlen(msg)-1);}}
                char current_assignment[2048]={0};ready_launch=suggested>=0&&load_local_trainer(game_key(&G.games[suggested]),current_assignment,sizeof current_assignment)&&readable_file(current_assignment)&&!strcmp(current_assignment,path);strncat(msg,ready_launch?"\nTrainer Library launch: Ready — this is the trainer currently assigned to the suggested game.":"\nTrainer Library launch: Assign this trainer to its game before launching it directly from Trainer Library.",sizeof msg-strlen(msg)-1);
            }
            set_trainer_library_guidance((state&&*state)?state:"Unmatched",(health&&*health)?health:"—",(profile&&*profile)?profile:"Unknown",(pconf&&*pconf)?pconf:"—",reason,suggested,ready_launch,preview.action);
            if(suggested>=0&&game_is_steam_shortcut(&G.games[suggested])){Game*sg=&G.games[suggested];strncat(msg,"\nSteam shortcut handoff: ",sizeof msg-strlen(msg)-1);strncat(msg,sg->resolution_label[0]?sg->resolution_label:"Resolution incomplete",sizeof msg-strlen(msg)-1);if(sg->compat_tool[0]){strncat(msg,"\nSteam Play tool: ",sizeof msg-strlen(msg)-1);strncat(msg,sg->compat_tool,sizeof msg-strlen(msg)-1);}if(sg->compatdata[0]){strncat(msg,"\nCompatdata: ",sizeof msg-strlen(msg)-1);strncat(msg,sg->compatdata,sizeof msg-strlen(msg)-1);}strncat(msg,"\nDirect shortcut trainer launch is enabled only when runtime + compatdata resolution is complete; the launcher validates the live session before runinprefix handoff.",sizeof msg-strlen(msg)-1);}
            if(reason&&*reason){strncat(msg,"\nWhy matched: ",sizeof msg-strlen(msg)-1);strncat(msg,reason,sizeof msg-strlen(msg)-1);}
            if(folder&&*folder){strncat(msg,"\nSource folder: ",sizeof msg-strlen(msg)-1);strncat(msg,folder,sizeof msg-strlen(msg)-1);}
            if(G.selected>=0&&G.selected<G.game_count&&suggested>=0&&strcmp(game_key(&G.games[G.selected]),G.trainer_library_pick_key)){
                strncat(msg,"\nSafety: the currently selected Library game is different. Use Assign to Suggested Game, or choose the intended game first.",sizeof msg-strlen(msg)-1);
            }
            set_label(G.trainer_library_pick,msg);
        }
    }
    update_trainer_library_actions();
    g_free(game);g_free(conf);g_free(version);g_free(health);g_free(profile);g_free(reason);g_free(path);g_free(key);g_free(state);g_free(folder);g_free(arch);g_free(runtime);g_free(elevation);g_free(pconf);g_free(signals);g_free(recommendation);
}

static void trainer_attention_game_changed(GtkTreeSelection*sel,void*d){
    (void)d;GtkTreeModel*m=NULL;GtkTreeIter it;if(!gtk_tree_selection_get_selected(sel,&m,&it))return;char*key=NULL,*game=NULL,*state=NULL,*issue=NULL;gtk_tree_model_get(m,&it,TG_KEY,&key,TG_GAME,&game,TG_STATE,&state,TG_ISSUE,&issue,-1);int idx=trainer_game_index_by_key(key);if(idx>=0){G.selected=idx;refresh_ui();if(G.trainer_library_selected){char lt[2048]={0},msg[4096];int mapped=load_local_trainer(game_key(&G.games[idx]),lt,sizeof lt);if(mapped&&readable_file(lt))snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Valid",G.games[idx].name,lt);else if(mapped)snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Missing",G.games[idx].name,lt);else snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: none",G.games[idx].name);set_label(G.trainer_library_selected,msg);}G.trainer_library_pick_path[0]=0;snprintf(G.trainer_library_pick_key,sizeof G.trainer_library_pick_key,"%s",key?key:"");snprintf(G.trainer_library_pick_game,sizeof G.trainer_library_pick_game,"%s",game?game:"");snprintf(G.trainer_library_pick_state,sizeof G.trainer_library_pick_state,"%s",state?state:"");snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"rescan-selected");if(G.trainer_library_guidance){char guidance[3072];snprintf(guidance,sizeof guidance,"Game needs attention: %s\nWhy: %s\nRecommended: rescan this selected game first. GameWeld keeps existing readable assignments and only recovers a missing mapping when the exact trainer filename is found uniquely.",(state&&*state)?state:"Needs attention",(issue&&*issue)?issue:"The last scan could not resolve a healthy trainer assignment.");set_label(G.trainer_library_guidance,guidance);}if(G.trainer_library_recommended_action){gtk_button_set_label((GtkButton*)G.trainer_library_recommended_action,"Rescan Selected Game");gtk_widget_set_sensitive(G.trainer_library_recommended_action,TRUE);}update_trainer_library_actions();}g_free(key);g_free(game);g_free(state);g_free(issue);
}

static void trainer_store_add(GtkWidget *view,const char *state,const char *game,const char *score,const char *reason,const char *path,const char *source,const char *key,const char *version,const char *health,const char *profile,const char *arch,const char *runtime,const char *elevation,const char *pconf,const char *signals,const char *recommendation,const char *policy,const char *launch){
    if(!view||!path||!*path)return;GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)view);if(!m)return;GtkListStore*st=(GtkListStore*)m;GtkTreeIter it;const char*base=strrchr(path,'/');base=base?base+1:path;char conf[64];if(score&&atoi(score)>0)snprintf(conf,sizeof conf,"%s%%",score);else snprintf(conf,sizeof conf,"—");const char *shown_state=!strcmp(state?state:"","ASSIGNED")?"Assigned":(!strcmp(state?state:"","MATCH")?"Matched":(!strcmp(state?state:"","ALTERNATE")?"Alternative":(!strcmp(state?state:"","AMBIG")?"Ambiguous":(!strcmp(state?state:"","MISSING")?"Missing":(!strcmp(state?state:"","MANAGER")?"Manager":"Unmatched")))));char prof[512];snprintf(prof,sizeof prof,"%s%s%s%s%s",(profile&&*profile)?profile:"Unknown",(pconf&&*pconf&&strcmp(pconf,"—"))?" (":"",(pconf&&*pconf&&strcmp(pconf,"—"))?pconf:"",(pconf&&*pconf&&strcmp(pconf,"—"))?")":"",(arch&&*arch&&strcmp(arch,"—"))?"":"");if(arch&&*arch&&strcmp(arch,"—")){strncat(prof," • ",sizeof prof-strlen(prof)-1);strncat(prof,arch,sizeof prof-strlen(prof)-1);}gtk_list_store_append(st,&it);gtk_list_store_set(st,&it,TL_GAME,(game&&*game)?game:"—",TL_CONF,conf,TL_VERSION,(version&&*version)?version:"—",TL_HEALTH,(health&&*health)?health:"—",TL_PROFILE,prof,TL_POLICY,(policy&&*policy)?policy:"Automatic",TL_LAUNCH,(launch&&*launch)?launch:"No launch target assigned",TL_REASON,reason?reason:"",TL_TRAINER,base,TL_FOLDER,source?source:"",TL_PATH,path,TL_KEY,key?key:"",TL_STATE,shown_state,TL_ARCH,arch?arch:"",TL_RUNTIME,runtime?runtime:"",TL_ELEVATION,elevation?elevation:"",TL_PCONF,pconf?pconf:"",TL_SIGNALS,signals?signals:"",TL_RECOMMENDATION,recommendation?recommendation:"",-1);
}

static void refresh_trainer_library_audit(void){
    if(!G.trainer_library_audit)return;
    int fd[2];if(pipe(fd)!=0){set_label(G.trainer_library_audit,"Compatibility readiness unavailable.");return;}
    pid_t p=fork();
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"audit",(char*)NULL);_exit(127);}
    close(fd[1]);char buf[1024]={0};ssize_t n=read(fd[0],buf,sizeof buf-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}
    if(n<=0||!WIFEXITED(st)||WEXITSTATUS(st)!=0){set_label(G.trainer_library_audit,"Compatibility readiness unavailable.");return;}
    buf[n]=0;buf[strcspn(buf,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*total=strtok_r(NULL,"\t",&save);char*managed=strtok_r(NULL,"\t",&save);char*steam=strtok_r(NULL,"\t",&save);char*inherit=strtok_r(NULL,"\t",&save);char*explicitv=strtok_r(NULL,"\t",&save);char*unassigned=strtok_r(NULL,"\t",&save);char*manual=strtok_r(NULL,"\t",&save);char*advisory=strtok_r(NULL,"\t",&save);char*attention=strtok_r(NULL,"\t",&save);
    if(!kind||strcmp(kind,"AUDIT")||!total||!managed||!steam||!inherit||!explicitv||!unassigned||!manual||!advisory||!attention){set_label(G.trainer_library_audit,"Compatibility readiness unavailable.");return;}
    char msg[2304];snprintf(msg,sizeof msg,"%s trainer%s profiled • %s Heroic managed FLiNG • %s Steam live-session • %s Heroic existing-session • %s explicit compatibility override • %s no launch target\n%s manual launch-policy override%s • %s advisory/low-confidence profile%s • %s assignment/health issue%s\nUse the Readiness filter above to drill into any bucket instantly; filtering uses the cached scan and never changes launch settings.",total,atoi(total)==1?"":"s",managed,steam,inherit,explicitv,unassigned,manual,atoi(manual)==1?"":"s",advisory,atoi(advisory)==1?"":"s",attention,atoi(attention)==1?"":"s");
    set_label(G.trainer_library_audit,msg);
}

static void refresh_trainer_library_rows(void){
    GtkWidget*views[5]={G.trainer_library_matched,G.trainer_library_alternates,G.trainer_library_ambiguous,G.trainer_library_unmatched,G.trainer_library_health};for(int i=0;i<5;i++)if(views[i]){GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)views[i]);if(m)gtk_list_store_clear((GtkListStore*)m);}
    if(G.trainer_library_attention_games){GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)G.trainer_library_attention_games);if(m)gtk_list_store_clear((GtkListStore*)m);}
    if(!G.trainer_library_matched&&!G.trainer_library_alternates&&!G.trainer_library_ambiguous&&!G.trainer_library_unmatched&&!G.trainer_library_health&&!G.trainer_library_attention_games)return;
    const char*q=trainer_library_query();const char*sort=trainer_library_sort_id();const char*readiness=trainer_library_readiness_id();int attention=trainer_library_attention_only();
    int fd[2];if(pipe(fd)!=0)return;pid_t p=fork();
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}if(attention)execlp("python3","python3",trainer_library_tool(),"rows","--query",q?q:"","--sort",sort,"--readiness",readiness,"--attention",(char*)NULL);else execlp("python3","python3",trainer_library_tool(),"rows","--query",q?q:"","--sort",sort,"--readiness",readiness,(char*)NULL);_exit(127);}
    close(fd[1]);FILE*f=fdopen(fd[0],"r");char line[8192];int found_pick=0;
    if(f){while(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(line,"\t",&save);char*state=strtok_r(NULL,"\t",&save);char*key=strtok_r(NULL,"\t",&save);char*game=strtok_r(NULL,"\t",&save);char*score=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);char*path=strtok_r(NULL,"\t",&save);char*source=strtok_r(NULL,"\t",&save);char*version=strtok_r(NULL,"\t",&save);char*health=strtok_r(NULL,"\t",&save);char*profile=strtok_r(NULL,"\t",&save);char*arch=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*elevation=strtok_r(NULL,"\t",&save);char*pconf=strtok_r(NULL,"\t",&save);char*signals=strtok_r(NULL,"\t",&save);char*recommendation=strtok_r(NULL,"\t",&save);char*policy=strtok_r(NULL,"\t",&save);char*launch=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"ROW")||!state||!path)continue;GtkWidget*v=(!strcmp(state,"MATCH")||!strcmp(state,"ASSIGNED"))?G.trainer_library_matched:(!strcmp(state,"ALTERNATE")?G.trainer_library_alternates:(!strcmp(state,"AMBIG")?G.trainer_library_ambiguous:(!strcmp(state,"MISSING")?G.trainer_library_health:G.trainer_library_unmatched)));trainer_store_add(v,state,game,score,reason,path,source,key,version,health,profile,arch,runtime,elevation,pconf,signals,recommendation,policy,launch);if(G.trainer_library_pick_path[0]&&!strcmp(G.trainer_library_pick_path,path))found_pick=1;}fclose(f);}else close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}
    if(G.trainer_library_attention_games){int gd[2];if(pipe(gd)==0){pid_t gp=fork();if(gp==0){close(gd[0]);dup2(gd[1],STDOUT_FILENO);close(gd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}const char*gsort=!strcmp(sort,"confidence")?"confidence":"game";execlp("python3","python3",trainer_library_tool(),"game-rows","--query",q?q:"","--sort",gsort,(char*)NULL);_exit(127);}close(gd[1]);FILE*gf=fdopen(gd[0],"r");if(gf){while(fgets(line,sizeof line,gf)){line[strcspn(line,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(line,"\t",&save);char*state=strtok_r(NULL,"\t",&save);char*key=strtok_r(NULL,"\t",&save);char*game=strtok_r(NULL,"\t",&save);char*score=strtok_r(NULL,"\t",&save);char*issue=strtok_r(NULL,"\t",&save);char*detail=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"GAME")||!state||!key||!game)continue;GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)G.trainer_library_attention_games);GtkListStore*ls=(GtkListStore*)m;GtkTreeIter it;char conf[64];if(score&&atoi(score)>0)snprintf(conf,sizeof conf,"%s%%",score);else snprintf(conf,sizeof conf,"—");const char*shown=!strcmp(state,"MISSING")?"Missing":(!strcmp(state,"AMBIG")?"Ambiguous":"No trainer");char why[2048];snprintf(why,sizeof why,"%s%s%s",issue?issue:"",(detail&&*detail&&strcmp(detail,"—"))?" — ":"",(detail&&*detail&&strcmp(detail,"—"))?detail:"");gtk_list_store_append(ls,&it);gtk_list_store_set(ls,&it,TG_STATE,shown,TG_GAME,game,TG_CONF,conf,TG_ISSUE,why,TG_KEY,key,-1);}fclose(gf);}else close(gd[0]);int gst=0;if(gp>0)while(waitpid(gp,&gst,0)<0&&errno==EINTR){}}}
    if(G.trainer_library_pick_path[0]&&!found_pick&&!attention){G.trainer_library_pick_path[0]=0;G.trainer_library_pick_game[0]=0;G.trainer_library_pick_key[0]=0;G.trainer_library_pick_state[0]=0;G.trainer_library_action_code[0]=0;if(G.trainer_library_pick)set_label(G.trainer_library_pick,"Select a trainer row to review its compatibility profile, suggested game/version, assign it safely, reassign an ambiguous/unmatched trainer, or ignore it.");if(G.trainer_library_guidance)set_label(G.trainer_library_guidance,"Select a trainer or game-attention row to see why it needs action and which existing GameWeld operation is appropriate.");if(G.trainer_library_recommended_action){gtk_button_set_label((GtkButton*)G.trainer_library_recommended_action,"No action selected");gtk_widget_set_sensitive(G.trainer_library_recommended_action,FALSE);}}
    update_trainer_library_actions();
    refresh_trainer_library_audit();
}

static void refresh_trainer_library_view(void){
    if(G.trainer_library_selected){
        char msg[4096]={0},lt[2048]={0};
        if(G.selected>=0&&G.selected<G.game_count){Game*g=&G.games[G.selected];int mapped=load_local_trainer(game_key(g),lt,sizeof lt);if(mapped&&readable_file(lt))snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Valid",g->name,lt);else if(mapped)snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Missing — rescan may recover it if the exact filename moved within known folders.",g->name,lt);else snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: none",g->name);}else snprintf(msg,sizeof msg,"Select a game in Library to assign or clear its trainer.");set_label(G.trainer_library_selected,msg);
    }
    if(G.trainer_library_policy){
        int fd[2];if(pipe(fd)==0){pid_t p=fork();if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);execlp("python3","python3",trainer_library_tool(),"policy",(char*)NULL);_exit(127);}close(fd[1]);char pol[128]={0};ssize_t n=read(fd[0],pol,sizeof pol-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(n>0){pol[n]=0;pol[strcspn(pol,"\r\n")]=0;char line[256];snprintf(line,sizeof line,"Duplicate-version policy: %s%s",pol,!strcmp(pol,"ask")?" (safe default)":"");set_label(G.trainer_library_policy,line);}}
    }
    if(G.trainer_library_view){
        int fd[2];if(pipe(fd)!=0){gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.trainer_library_view),"Could not open Trainer Library report.",-1);}else{
            pid_t p=fork();if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"report",(char*)NULL);_exit(127);}close(fd[1]);char *buf=calloc(1,262145);size_t used=0;if(buf){ssize_t n;while(used<262144&&(n=read(fd[0],buf+used,262144-used))>0)used+=(size_t)n;buf[used]=0;}close(fd[0]);int st=0;if(p>0){while(waitpid(p,&st,0)<0&&errno==EINTR){}}if(!buf||!used){if(buf)free(buf);buf=strdup("No Trainer Library scan has completed yet.\n\nPress Scan / Auto-Match Trainers to create the first report.");}gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.trainer_library_view),buf?buf:"Trainer Library report unavailable.",-1);free(buf);
        }
    }
    refresh_trainer_library_rows();
}
static int neutralize_legacy_wrapper(void){
    const char *home=getenv("HOME");if(!home||!*home)return 0;char p[2048];snprintf(p,sizeof p,"%s/.local/bin/wand-steam-wrap",home);struct stat st;if(stat(p,&st)!=0||!S_ISREG(st.st_mode))return 0;
    FILE*f=fopen(p,"r");if(!f)return 0;char buf[8192];size_t n=fread(buf,1,sizeof buf-1,f);fclose(f);buf[n]=0;if(strstr(buf,"wand-native-pass-through 0.1.43"))return 0;
    char backup[2048];time_t now=time(NULL);snprintf(backup,sizeof backup,"%s.disabled-by-0.1.43-%ld",p,(long)now);if(rename(p,backup)!=0)return 0;
    f=fopen(p,"w");if(!f){rename(backup,p);return 0;}fputs("#!/usr/bin/env bash\n# wand-native-pass-through 0.1.43\n# Legacy Steam launch option compatibility: do not auto-start Wand.\nexec \"$@\"\n",f);fclose(f);chmod(p,0755);snprintf(G.legacy_wrapper_backup,sizeof G.legacy_wrapper_backup,"%s",backup);return 1;
}

static int cleanup_localconfig_file(const char *path,char *last_backup,size_t cap){
    FILE*f=fopen(path,"r");if(!f)return 0;
    char **lines=NULL;size_t count=0,alloc=0;char *line=NULL;size_t n=0;ssize_t got;int changed=0;
    while((got=getline(&line,&n,f))>=0){
        if(count==alloc){size_t na=alloc?alloc*2:256;char **nl=realloc(lines,na*sizeof(*nl));if(!nl){free(line);fclose(f);for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}lines=nl;alloc=na;}
        lines[count]=strdup(line);if(!lines[count]){free(line);fclose(f);for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
        if(strstr(line,"\"LaunchOptions\"")&&strstr(line,"wand-steam-wrap"))changed=1;
        count++;
    }
    free(line);fclose(f);if(!changed){for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
    char backup[4096];time_t now=time(NULL);if(snprintf(backup,sizeof backup,"%s.wand-native-backup-%ld",path,(long)now)<0||strlen(path)+48>=sizeof backup){for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
    FILE*src=fopen(path,"rb"),*dst=fopen(backup,"wb");if(!src||!dst){if(src)fclose(src);if(dst)fclose(dst);for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
    char buf[16384];size_t r;while((r=fread(buf,1,sizeof buf,src))>0)fwrite(buf,1,r,dst);fclose(src);fclose(dst);
    char tmp[4096];if(snprintf(tmp,sizeof tmp,"%s.wand-native-tmp-%ld",path,(long)getpid())<0||strlen(path)+48>=sizeof tmp){for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}FILE*out=fopen(tmp,"w");if(!out){for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
    for(size_t i=0;i<count;i++){
        char *cur=lines[i];
        if(strstr(cur,"\"LaunchOptions\"")&&strstr(cur,"wand-steam-wrap")){
            size_t indent=0;while(cur[indent]==' '||cur[indent]=='\t')indent++;
            fwrite(cur,1,indent,out);fputs("\"LaunchOptions\"\t\t\"\"\n",out);
        }else fputs(cur,out);
        free(cur);
    }
    free(lines);fclose(out);
    if(rename(tmp,path)!=0){unlink(tmp);return 0;}
    if(last_backup&&cap)snprintf(last_backup,cap,"%s",backup);
    return 1;
}

static int steam_root_seen(char roots[][4096],int count,const char *root){
    if(!root||!*root)return 1;
    char canon[4096];if(!realpath(root,canon))snprintf(canon,sizeof canon,"%s",root);
    for(int i=0;i<count;i++)if(!strcmp(roots[i],canon))return 1;
    return 0;
}
static void add_steam_root(char roots[][4096],int *count,int max,const char *root){
    if(!root||!*root||*count>=max)return;char canon[4096];if(!realpath(root,canon))snprintf(canon,sizeof canon,"%s",root);
    char user[4096];if(strlen(canon)>sizeof user-sizeof "/userdata")return;if(snprintf(user,sizeof user,"%s/userdata",canon)<0)return;struct stat st;if(stat(user,&st)!=0||!S_ISDIR(st.st_mode))return;
    if(steam_root_seen(roots,*count,canon))return;snprintf(roots[*count],4096,"%s",canon);(*count)++;
}
static void discover_running_steam_roots(char roots[][4096],int *count,int max){
    DIR*d=opendir("/proc");if(!d)return;struct dirent*de;
    while((de=readdir(d))){if(!isdigit((unsigned char)de->d_name[0]))continue;char cp[256];if(strlen(de->d_name)>sizeof cp-sizeof "/proc//cmdline")continue;snprintf(cp,sizeof cp,"/proc/%s/cmdline",de->d_name);FILE*f=fopen(cp,"rb");if(!f)continue;char buf[16384];size_t n=fread(buf,1,sizeof buf-1,f);fclose(f);if(!n)continue;buf[n]=0;
        for(size_t i=0;i<n;i++)if(buf[i]==0)buf[i]='\n';
        const char *tags[]={"-clientui=","-cachedir=","-steampath="};
        for(size_t ti=0;ti<3;ti++){char *m=strstr(buf,tags[ti]);if(!m)continue;m+=strlen(tags[ti]);char *e=strchr(m,'\n');size_t l=e?(size_t)(e-m):strlen(m);if(!l||l>=4096)continue;char v[4096];memcpy(v,m,l);v[l]=0;
            if(ti==0){char *slash=strrchr(v,'/');if(slash&&slash!=v)*slash=0;add_steam_root(roots,count,max,v);}
            else if(ti==1){char *q=strstr(v,"/config/htmlcache");if(q)*q=0;add_steam_root(roots,count,max,v);}
            else {char *q=strstr(v,"/steamrt64/steam");if(q)*q=0;else {q=strstr(v,"/ubuntu12_32/steam");if(q)*q=0;}add_steam_root(roots,count,max,v);}
        }
    }closedir(d);
}
static void discover_mount_steam_roots(char roots[][4096],int *count,int max){
    const char *bases[]={"/mnt","/media","/run/media"};const char *user=getenv("USER");
    for(size_t bi=0;bi<3;bi++){char base[4096];snprintf(base,sizeof base,"%s",bases[bi]);if(bi==2&&user&&*user)snprintf(base,sizeof base,"/run/media/%s",user);DIR*d=opendir(base);if(!d)continue;struct dirent*de;
        while((de=readdir(d))){if(de->d_name[0]=='.')continue;char p1[4096];if(strlen(base)+strlen(de->d_name)+2>sizeof p1)continue;memcpy(p1,base,strlen(base));p1[strlen(base)]='/';strcpy(p1+strlen(base)+1,de->d_name);add_steam_root(roots,count,max,p1);DIR*d2=opendir(p1);if(!d2)continue;struct dirent*de2;while((de2=readdir(d2))){if(de2->d_name[0]=='.')continue;char p2[4096];if(strlen(p1)+strlen(de2->d_name)+2>sizeof p2)continue;memcpy(p2,p1,strlen(p1));p2[strlen(p1)]='/';strcpy(p2+strlen(p1)+1,de2->d_name);add_steam_root(roots,count,max,p2);}closedir(d2);
        }closedir(d);
    }
}
static int cleanup_legacy_steam_hooks(char *last_backup,size_t cap,int *files_changed){
    const char *home=getenv("HOME");if(!home||!*home)return 0;
    char roots[24][4096];int root_count=0;const char *roots_rel[]={".local/share/Steam",".steam/steam",".steam/root",".var/app/com.valvesoftware.Steam/.local/share/Steam"};
    for(size_t ri=0;ri<sizeof roots_rel/sizeof roots_rel[0];ri++){char r[4096];snprintf(r,sizeof r,"%s/%s",home,roots_rel[ri]);add_steam_root(roots,&root_count,24,r);}
    const char *envroot=getenv("STEAM_COMPAT_CLIENT_INSTALL_PATH");if(envroot&&*envroot)add_steam_root(roots,&root_count,24,envroot);
    discover_running_steam_roots(roots,&root_count,24);discover_mount_steam_roots(roots,&root_count,24);
    int cleaned=0,files=0;
    for(int ri=0;ri<root_count;ri++){char userroot[4096];if(strlen(roots[ri])+sizeof "/userdata">sizeof userroot)continue;snprintf(userroot,sizeof userroot,"%s/userdata",roots[ri]);DIR*d=opendir(userroot);if(!d)continue;
        struct dirent*de;while((de=readdir(d))){if(de->d_name[0]=='.')continue;int numeric=1;for(const char*q=de->d_name;*q;q++)if(!isdigit((unsigned char)*q)){numeric=0;break;}if(!numeric)continue;
            char cfg[4096];if(strlen(userroot)+strlen(de->d_name)+sizeof "//config/localconfig.vdf">sizeof cfg)continue;memcpy(cfg,userroot,strlen(userroot));cfg[strlen(userroot)]='/';strcpy(cfg+strlen(userroot)+1,de->d_name);strcat(cfg,"/config/localconfig.vdf");struct stat st;if(stat(cfg,&st)!=0||!S_ISREG(st.st_mode))continue;
            char b[4096]={0};if(cleanup_localconfig_file(cfg,b,sizeof b)){cleaned++;files++;if(last_backup&&cap&&b[0])snprintf(last_backup,cap,"%s",b);}
        }closedir(d);
    }
    if(files_changed)*files_changed=files;
    return cleaned;
}

static void on_clean_legacy_hooks(GtkButton*b,void*d){
    (void)b;(void)d;char backup[2048]={0};int files=0;int n=cleanup_legacy_steam_hooks(backup,sizeof backup,&files);
    G.legacy_hooks_cleaned+=n;G.legacy_hook_files_changed+=files;if(backup[0])snprintf(G.legacy_hook_last_backup,sizeof G.legacy_hook_last_backup,"%s",backup);
    if(n>0){
        log_line("Removed legacy wand-steam-wrap Launch Options from %d Steam config file(s).",files);
        log_line("Steam config backup: %s",backup);
        log_line("Restart Steam once before testing direct Play so its in-memory launch options refresh.");
        if(G.steam_cleanup_status)gtk_label_set_text((GtkLabel*)G.steam_cleanup_status,"Legacy Steam launch hooks removed. Restart Steam once, then direct Play will be normal.");
    }else{
        log_line("No legacy wand-steam-wrap Launch Options were found in Steam localconfig.vdf files.");
        if(G.steam_cleanup_status)gtk_label_set_text((GtkLabel*)G.steam_cleanup_status,"No legacy wand-steam-wrap Launch Options found.");
    }
}

typedef struct {
    char action[64];
    char profile[128];
    char confidence[32];
    char runtime[96];
    char elevation[128];
    char reason[768];
} TrainerLaunchPolicy;

static int trainer_launch_policy(const char *trainer,TrainerLaunchPolicy*out){
    if(!out)return 0;memset(out,0,sizeof *out);if(!trainer||!*trainer)return 0;
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){
        close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}
        execlp("python3","python3",trainer_library_tool(),"launch-policy",trainer,(char*)NULL);_exit(127);
    }
    close(fd[1]);char buf[4096];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);
    int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0||!used)return 0;buf[used]=0;buf[strcspn(buf,"\r\n")]=0;
    char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*action=strtok_r(NULL,"\t",&save);char*profile=strtok_r(NULL,"\t",&save);char*confidence=strtok_r(NULL,"\t",&save);char*runtime=strtok_r(NULL,"\t",&save);char*elevation=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);
    if(!kind||strcmp(kind,"POLICY")||!action||!profile||!confidence||!runtime||!elevation)return 0;
    snprintf(out->action,sizeof out->action,"%s",action);snprintf(out->profile,sizeof out->profile,"%s",profile);snprintf(out->confidence,sizeof out->confidence,"%s",confidence);snprintf(out->runtime,sizeof out->runtime,"%s",runtime);snprintf(out->elevation,sizeof out->elevation,"%s",elevation);snprintf(out->reason,sizeof out->reason,"%s",reason?reason:"");return 1;
}

static int env_value_is_auto(const char*v){return !v||!*v||!strcasecmp(v,"auto");}
static int trainer_profile_auto_enabled(void){
    const char*v=getenv("GAMEWELD_AUTO_TRAINER_PROFILE");
    return !(v&&*v&&(!strcasecmp(v,"off")||!strcasecmp(v,"never")||!strcmp(v,"0")||!strcasecmp(v,"false")));
}
static int trainer_profile_has_compat_override(void){
    const char*v=getenv("GAMEWELD_LOCAL_TRAINER_COMPAT_SESSION");if(!env_value_is_auto(v))return 1;
    v=getenv("GAMEWELD_FLING_COMPAT_SESSION");return !env_value_is_auto(v);
}
static int trainer_profile_has_elevation_override(void){return !env_value_is_auto(getenv("GAMEWELD_TRAINER_ELEVATION"));}
static int trainer_launch_policy_is_manual(const TrainerLaunchPolicy *pol){return pol&&strstr(pol->reason,"Manual per-trainer override")!=NULL;}

static const char *local_trainer_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-local-trainer.sh",appdir);else snprintf(p,sizeof p,"gameweld-local-trainer.sh");return p;}
static const char *steam_shortcut_trainer_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-steam-shortcut-trainer.sh",appdir);else snprintf(p,sizeof p,"gameweld-steam-shortcut-trainer.sh");return p;}
static void spawn_steam_shortcut_trainer(const Game *g,const char *trainer){
    if(!g||!trainer||!*trainer)return;
    if(!g->shortcut_launch_supported||!g->compatdata[0]||!g->compat_tool_path[0]||!g->launch_id[0]){log_line("Steam non-Steam shortcut trainer launch blocked for %s: runtime/prefix/rungameid resolution is incomplete.",g->name);return;}
    TrainerLaunchPolicy pol;int have=trainer_launch_policy(trainer,&pol);
    if(have)log_line("Steam shortcut trainer profile: %s (%s). Runtime remains the shortcut's exact live Steam Proton session.",pol.profile,pol.confidence);
    pid_t p=fork();if(p==0){if(have){setenv("GAMEWELD_DETECTED_TRAINER_PROFILE",pol.profile,1);setenv("GAMEWELD_DETECTED_TRAINER_CONFIDENCE",pol.confidence,1);}execl(steam_shortcut_trainer_launcher(),steam_shortcut_trainer_launcher(),g->appid,g->launch_id,g->compatdata,g->compat_tool_path,g->executable,trainer,(char*)NULL);_exit(127);}
}
static void spawn_steam_shortcut_table(const Game *g,const char *windows_ce,const char *table){
    if(!g||!windows_ce||!*windows_ce||!table||!*table)return;
    if(!g->shortcut_launch_supported||!g->compatdata[0]||!g->compat_tool_path[0]||!g->launch_id[0]){log_line("Steam non-Steam shortcut .CT launch blocked for %s: runtime/prefix/rungameid resolution is incomplete.",g->name);return;}
    if(!windows_pe_executable(windows_ce)){log_line("Steam shortcut .CT launch needs the Windows Cheat Engine companion, but this is not a Windows PE executable: %s",windows_ce);return;}
    log_line("Launching %s + Cheat Engine table through the shortcut's exact live Proton session: %s",g->name,table);
    pid_t p=fork();if(p==0){setenv("GAMEWELD_CHEAT_TABLE_SESSION","steam-shortcut",1);execl(steam_shortcut_trainer_launcher(),steam_shortcut_trainer_launcher(),g->appid,g->launch_id,g->compatdata,g->compat_tool_path,g->executable,windows_ce,table,(char*)NULL);_exit(127);}
}
static void spawn_steam_shortcut_normal(const Game *g){
    if(!g||!g->launch_uri[0])return;pid_t p=fork();if(p==0){execlp("steam","steam",g->launch_uri,(char*)NULL);_exit(127);}
}
static void spawn_local_trainer(const char *appid,const char *trainer){
    TrainerLaunchPolicy pol;int have=trainer_launch_policy(trainer,&pol);
    if(have&&!strcmp(pol.action,"heroic-fling-managed"))log_line("Trainer launch policy resolved to managed FLiNG for Steam: %s (%s). Steam keeps the proven live Proton-session handoff; Heroic-only profile overrides do not replace the Steam runtime.",pol.profile,pol.confidence);
    pid_t p=fork();if(p==0){if(have){setenv("GAMEWELD_DETECTED_TRAINER_PROFILE",pol.profile,1);setenv("GAMEWELD_DETECTED_TRAINER_CONFIDENCE",pol.confidence,1);}execl(local_trainer_launcher(),local_trainer_launcher(),appid,trainer,(char*)NULL);_exit(127);}
}
static void cheat_tables_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/cheat-tables.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/cheat-tables.tsv",home?home:".");
}
static void cheat_engine_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/cheat-engine-exe.txt",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/cheat-engine-exe.txt",home?home:".");
}
static void cheat_engine_installer_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/cheat-engine-installer.txt",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/cheat-engine-installer.txt",home?home:".");
}
static int load_cheat_engine_installer(char *out,size_t cap){
    if(out&&cap)out[0]=0;char p[2048];cheat_engine_installer_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;char line[4096];if(!fgets(line,sizeof line,f)){fclose(f);return 0;}fclose(f);line[strcspn(line,"\r\n")]=0;if(!*line)return 0;snprintf(out,cap,"%.*s",(int)(cap?cap-1:0),line);return 1;
}
static int save_cheat_engine_installer(const char *exe){
    char path[2048],dir[2048];cheat_engine_installer_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;if(g_mkdir_with_parents(dir,0700)!=0)return 0;
    if(!exe||!*exe){unlink(path);return 1;}FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%s\n",exe);fclose(f);return 1;
}
static int readable_file(const char *path);
static const char *cheat_engine_manager(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-cheat-engine-manager.sh",appdir);else snprintf(p,sizeof p,"gameweld-cheat-engine-manager.sh");return p;}
static int detect_managed_cheat_engine(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;pid_t read_pid=-1;FILE*f=pc2_read_argv(cheat_engine_manager(),"detect",appid,NULL,&read_pid);if(!f)return 0;char line[4096];int ok=0;if(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(*line&&readable_file(line)){snprintf(out,cap,"%.*s",(int)(cap?cap-1:0),line);ok=1;}}pc2_close_read_argv(f,read_pid);return ok;
}
static int detect_managed_windows_ce(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;pid_t read_pid=-1;FILE*f=pc2_read_argv(cheat_engine_manager(),"windows-detect",appid,NULL,&read_pid);if(!f)return 0;char line[4096];int ok=0;if(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(*line&&readable_file(line)){if(out&&cap&&strlen(line)<cap){memcpy(out,line,strlen(line)+1);ok=1;}}}pc2_close_read_argv(f,read_pid);return ok;
}
static pid_t spawn_managed_ce_install(const char *appid,const char *installer){pid_t p=fork();if(p==0){execl(cheat_engine_manager(),cheat_engine_manager(),"install",appid,installer,(char*)NULL);_exit(127);}return p;}
static pid_t spawn_managed_ce_download_install(const char *appid){pid_t p=fork();if(p==0){execl(cheat_engine_manager(),cheat_engine_manager(),"download-install",appid,(char*)NULL);_exit(127);}return p;}
/* Async install supervision: completion is not success until a real executable
 * is detected. No auto-download or file modification happens outside clicks. */
typedef struct {pid_t pid;char appid[128];int exited_ok,attempt;} CeInstallJob;
static gboolean ce_install_poll(void *vp){
    CeInstallJob*j=vp;char linuxce[2048]={0},windowsce[2048]={0};
    int native=detect_managed_cheat_engine(j->appid,linuxce,sizeof linuxce);
    int companion=detect_managed_windows_ce(j->appid,windowsce,sizeof windowsce);
    if(native||companion){
        log_line("Cheat Engine auto-refresh: verified %s%s%s",native?"native CE":"",native&&companion?" + ":"",companion?"Windows companion":"");
        if(G.cheat_table_status)set_label(G.cheat_table_status,"Cheat Engine installation completed; installed executable verified automatically.");
        refresh_ui();free(j);return FALSE;
    }
    if(++j->attempt<10)return TRUE;
    if(G.cheat_table_status)set_label(G.cheat_table_status,"Installer exited, but no usable Cheat Engine executable was detected yet. Inspect installation log or refresh manually.");
    log_line("Cheat Engine: installation exited but no executable detected for %s.",j->appid);
    free(j);return FALSE;
}
static gboolean ce_install_completed(void *vp){
    CeInstallJob*j=vp;
    if(!j->exited_ok){
        log_line("Cheat Engine installer failed (or was interrupted) for %s; no installation assumed.",j->appid);
        if(G.cheat_table_status)set_label(G.cheat_table_status,"Cheat Engine installer failed; no installation was assumed.");
        free(j);return FALSE;
    }
    if(G.cheat_table_status)set_label(G.cheat_table_status,"Installer finished; checking for a real Cheat Engine executable…");
    g_timeout_add(1500,ce_install_poll,j);return FALSE;
}
static void *ce_install_wait_worker(void *vp){
    CeInstallJob*j=vp;int status=0;
    while(waitpid(j->pid,&status,0)<0&&errno==EINTR){}
    j->exited_ok=WIFEXITED(status)&&WEXITSTATUS(status)==0;
    g_idle_add(ce_install_completed,j);return NULL;
}
static void ce_install_watch(pid_t pid,const char *appid){
    if(pid<=0){log_line("Could not start Cheat Engine installer.");return;}
    CeInstallJob*j=calloc(1,sizeof *j);if(!j)return;
    j->pid=pid;snprintf(j->appid,sizeof j->appid,"%s",appid);
    pthread_t thread;if(pthread_create(&thread,NULL,ce_install_wait_worker,j)==0)pthread_detach(thread);
    else{free(j);log_line("Installer started but completion watcher failed. Refresh CE manually.");}
}

static int load_cheat_table(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char p[2048];cheat_tables_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char *tab=strchr(line,'\t');if(!tab)continue;*tab=0;char *v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,appid)&&*v){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_cheat_table(const char *appid,const char *table){
    if(!appid||!*appid)return 0;char path[2048],dir[2048];cheat_tables_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;
    if(g_mkdir_with_parents(dir,0700)!=0)return 0;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char *tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(table&&*table)fprintf(out,"%s\t%s\n",appid,table);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}
static int load_cheat_engine(char *out,size_t cap){
    if(out&&cap)out[0]=0;char p[2048];cheat_engine_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;char line[4096];if(!fgets(line,sizeof line,f)){fclose(f);return 0;}fclose(f);line[strcspn(line,"\r\n")]=0;if(!*line)return 0;if(!out||!cap||strlen(line)>=cap)return 0;memcpy(out,line,strlen(line)+1);return 1;
}
static int save_cheat_engine(const char *exe){
    char path[2048],dir[2048];cheat_engine_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;if(g_mkdir_with_parents(dir,0700)!=0)return 0;
    if(!exe||!*exe){unlink(path);return 1;}FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%s\n",exe);fclose(f);return 1;
}
static const char *cheat_table_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-cheat-table.sh",appdir);else snprintf(p,sizeof p,"gameweld-cheat-table.sh");return p;}
static void spawn_cheat_table(const char *appid,const char *ce,const char *table){pid_t p=fork();if(p==0){execl(cheat_table_launcher(),cheat_table_launcher(),appid,ce,table,(char*)NULL);_exit(127);}}

static void native_profiles_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/native-profiles.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/native-profiles.tsv",home?home:".");
}
static const char *available_native_profile(const char *appid){(void)appid;return NULL; /* third-party native profile excluded from distribution candidate */}
static int load_native_profile(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char p[2048];native_profiles_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char*tab=strchr(line,'\t');if(!tab)continue;*tab=0;char*v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,appid)&&*v){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_native_profile(const char *appid,const char *profile){
    if(!appid||!*appid)return 0;char path[2048],dir[2048];native_profiles_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;if(g_mkdir_with_parents(dir,0700)!=0)return 0;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char*tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(profile&&*profile)fprintf(out,"%s\t%s\n",appid,profile);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}
static const char *native_profile_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-native-profile.sh",appdir);else snprintf(p,sizeof p,"gameweld-native-profile.sh");return p;}
static void spawn_native_profile(const char *appid,const char *profile){pid_t p=fork();if(p==0){execl(native_profile_launcher(),native_profile_launcher(),appid,profile,(char*)NULL);_exit(127);}}

static void refresh_ui(void);
static gboolean heroic_session_status_tick(void *unused);

static gboolean job_done(void *vp);

typedef enum { JOB_SETUP, JOB_VERIFY, JOB_HEALTH, JOB_PLAY, JOB_WEMOD, JOB_REFRESH } JobType;
typedef struct { JobType type; char appid[32]; char *message; int success; int provider_retry; } Job;
static int universal_wemod_job_active=0;

static int backend_job_running(void){
    char *body=NULL;int code=0,running=0;
    if(http_request("GET","/api/job",NULL,&body,&code)>=0&&code>=200&&code<300&&body)running=json_bool(body,"running",0);
    free(body);return running;
}
static int wait_backend_idle(int max_ms){
    int waited=0;while(waited<max_ms){if(!backend_job_running())return 1;usleep(250000);waited+=250;}return !backend_job_running();
}
static int remove_stale_wemod_stage(void){
    if(!G.wand_tool[0])return 0;
    const char *needle="/compatibilitytools.d/GE-Proton-Wand-SHA256";
    if(!strstr(G.wand_tool,needle))return 0;
    char stage[1200];snprintf(stage,sizeof stage,"%s.rc4-new",G.wand_tool);
    struct stat st;if(lstat(stage,&st)!=0)return errno==ENOENT;
    pid_t p=fork();if(p==0){execlp("rm","rm","-rf","--",stage,(char*)NULL);_exit(127);}if(p<0)return 0;
    int ws=0;while(waitpid(p,&ws,0)<0&&errno==EINTR){}return WIFEXITED(ws)&&WEXITSTATUS(ws)==0;
}
static int response_is_rsync_stage_failure(const char *body){
    return body&&strstr(body,"rsync failed")&&(strstr(body,".rc4-new")||strstr(body,"exit status 23"));
}
static void launch_wemod_steam_after_set_game(Job *j,char **body){
    if(!ensure_proton_gate()){j->success=0;free(*body);*body=strdup("Could not verify/repair the explicit GE Proton Wand launch gate. The game was not started.");return;}
    if(!arm_wand_launch(j->appid)){j->success=0;free(*body);*body=strdup("Could not arm the one-shot WeMod/Wand launch marker. The game was not started.");return;}
    pid_t p=fork();if(p==0){clear_desktop_activation_env();execlp("steam","steam","-applaunch",j->appid,(char*)NULL);_exit(127);}
    if(p<0){j->success=0;free(*body);*body=strdup("Could not start Steam for the selected WeMod launch.");}
}

static void *job_worker(void *vp) {
    Job *j=vp; char *body=NULL; int code=0; char path[256],data[128];
    if(j->type==JOB_SETUP){ http_request("POST","/api/install","{}",&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_VERIFY){ http_request("GET","/api/verify",NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_HEALTH){ snprintf(path,sizeof path,"/api/health?appid=%s",j->appid); http_request("GET",path,NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_PLAY||j->type==JOB_WEMOD){
        snprintf(data,sizeof data,"{\"appid\":\"%s\"}",j->appid);
        if(j->type==JOB_WEMOD)wait_backend_idle(15000);
        http_request("POST","/api/set-game",data,&body,&code);j->success=(code>=200&&code<300);
        if(j->type==JOB_WEMOD&&!j->success&&response_is_rsync_stage_failure(body)){
            free(body);body=NULL;code=0;j->provider_retry=1;
            wait_backend_idle(15000);remove_stale_wemod_stage();usleep(350000);
            http_request("POST","/api/set-game",data,&body,&code);j->success=(code>=200&&code<300);
        }
        if(j->success)launch_wemod_steam_after_set_game(j,&body);
        else if(j->type==JOB_WEMOD&&j->provider_retry&&response_is_rsync_stage_failure(body)){
            free(body);body=strdup("WeMod compatibility-provider refresh hit the Proton staging rsync failure twice. GameWeld left Steam/game state unchanged. Open Setup and repair the Steam provider before retrying.");
        }
    }
    else { j->success=1; body=strdup("Provider refresh queued on the GTK main thread."); }
    if(body){ char msg[1800]={0}; json_string(body,"message",msg,sizeof msg); if(!msg[0])json_string(body,"error",msg,sizeof msg); if(!msg[0])json_string(body,"data",msg,sizeof msg); if(!msg[0])snprintf(msg,sizeof msg,"%s",body); j->message=strdup(msg); free(body);} else j->message=strdup(j->success?"Completed successfully.":"Operation failed.");
    g_idle_add(job_done,j); return NULL;
}
static void start_job(JobType type,const char *appid,const char *doing) {
    if(type==JOB_WEMOD&&universal_wemod_job_active){log_line("Universal launch: a WeMod provider launch is already being prepared. Wait for it to finish before starting another provider action.");return;}
    Job *j=calloc(1,sizeof *j); j->type=type; if(appid)snprintf(j->appid,sizeof j->appid,"%s",appid);
    if(type==JOB_WEMOD)universal_wemod_job_active=1;
    log_line("%s",doing); if(G.play_button)gtk_widget_set_sensitive(G.play_button,FALSE); pthread_t t; if(pthread_create(&t,NULL,job_worker,j)==0)pthread_detach(t);else{if(type==JOB_WEMOD)universal_wemod_job_active=0;free(j);log_line("Could not start background launch worker.");}
}

static gboolean job_done(void *vp) {
    Job *j=vp; log_line("%s: %s",j->success?"OK":"FAILED",j->message?j->message:""); if(j->type==JOB_WEMOD&&j->provider_retry)log_line(j->success?"Universal launch: WeMod provider staging recovered automatically on the serialized retry.":"Universal launch: WeMod provider staging retry did not recover; no additional launch was started."); char *e=NULL; refresh_model(&e); free(e); refresh_ui();
    if(j->type==JOB_WEMOD)universal_wemod_job_active=0;
    if(G.play_button)gtk_widget_set_sensitive(G.play_button,TRUE);
    if(j->type==JOB_HEALTH && G.health_detail)gtk_label_set_text((GtkLabel*)G.health_detail,j->message?j->message:"");
    if((j->type==JOB_SETUP||j->type==JOB_VERIFY) && G.setup_detail)gtk_label_set_text((GtkLabel*)G.setup_detail,j->message?j->message:"");
    free(j->message); free(j); return FALSE;
}


static int readable_file(const char *path){struct stat st;return path&&*path&&stat(path,&st)==0&&S_ISREG(st.st_mode)&&access(path,R_OK)==0;}
static int windows_pe_executable(const char *path){if(!readable_file(path))return 0;FILE*f=fopen(path,"rb");if(!f)return 0;unsigned char mz[2]={0};size_t n=fread(mz,1,2,f);fclose(f);return n==2&&mz[0]=='M'&&mz[1]=='Z';}

typedef struct AutoMatch {char *key,*path;struct AutoMatch *next;} AutoMatch;
typedef struct { char manifest[2048]; int matched,assigned,ambiguous,missing,health_issues,candidates,roots,failed,merge_report,selected_only; AutoMatch *matches; } TrainerScanJob;
static int trainer_scan_active=0;

/* Commit a full successful automatic scan as one atomic mapping transaction.
 * Manual edits performed while the scanner runs are respected at commit time. */
static int trainer_commit_matches(TrainerScanJob *j){
    if(!j->matches)return 1;
    char path[2048],dir[2048];config_path(path,sizeof path);config_dir(dir,sizeof dir);
    if(g_mkdir_with_parents(dir,0700)!=0)return 0;
    char temp[2140];snprintf(temp,sizeof temp,"%s.scan-XXXXXX",path);
    int fd=mkstemp(temp);if(fd<0)return 0;
    fchmod(fd,0600);FILE*out=fdopen(fd,"w");if(!out){close(fd);unlink(temp);return 0;}
    FILE*in=fopen(path,"r");char line[8192];int ok=1,added=0;
    if(in){while(fgets(line,sizeof line,in)){
        if(!strchr(line,'\n')&&!feof(in)){ok=0;break;}
        char key[4096]={0},current[4096]={0};char*tab=strchr(line,'\t');
        if(tab){size_t n=(size_t)(tab-line);if(n>=sizeof key){ok=0;break;}memcpy(key,line,n);snprintf(current,sizeof current,"%s",tab+1);current[strcspn(current,"\r\n")]=0;}
        int replace=0;
        for(AutoMatch*m=j->matches;m;m=m->next){if(!strcmp(m->key,key)&&!readable_file(current)){replace=1;break;}}
        if(!replace&&fputs(line,out)==EOF){ok=0;break;}
    }if(ferror(in))ok=0;fclose(in);}
    for(AutoMatch*m=j->matches;ok&&m;m=m->next){
        char cur[2048]={0};
        if(load_local_trainer(m->key,cur,sizeof cur)&&readable_file(cur)){j->assigned++;continue;}
        if(!readable_file(m->path)||strpbrk(m->key,"\t\r\n")||strpbrk(m->path,"\t\r\n")){ok=0;break;}
        /* Reject duplicate keys from malformed helper output. */
        int duplicate=0;for(AutoMatch*x=j->matches;x!=m;x=x->next)if(!strcmp(x->key,m->key))duplicate=1;
        if(duplicate){ok=0;break;}
        if(fprintf(out,"%s\t%s\n",m->key,m->path)<0){ok=0;break;}
        added++;
    }
    if(fflush(out)!=0||fsync(fd)!=0)ok=0;
    if(fclose(out)!=0)ok=0;
    if(ok&&added>0&&rename(temp,path)==0){j->matched=added;return 1;}
    unlink(temp);return ok&&added==0;
}
static void trainer_free_matches(AutoMatch *match){while(match){AutoMatch*next=match->next;free(match->key);free(match->path);free(match);match=next;}}

static void tsv_field(FILE *f,const char *s){for(const unsigned char*p=(const unsigned char*)(s?s:"");*p;p++)fputc((*p=='\t'||*p=='\r'||*p=='\n')?' ':*p,f);}
static gboolean trainer_scan_done(void *vp){TrainerScanJob*j=vp;trainer_scan_active=0;if(!j->failed&&!trainer_commit_matches(j))j->failed=1;if(j->failed)log_line("Trainer Library scan failed; existing trainer assignments were left unchanged.");else if(j->selected_only)log_line("Selected-game trainer rescan complete: %d trainer EXE(s) discovered • %d healthy/recovered assignment(s) • %d newly assigned • %d ambiguous • %d missing assignment(s) • %d not found.",j->candidates,j->assigned,j->matched,j->ambiguous,j->health_issues,j->missing);else log_line("Trainer Library scan complete: %d trainer EXE(s) discovered • %d healthy/recovered assignment(s) • %d auto-matched • %d ambiguous • %d missing assignment(s) • %d unassigned games not found.",j->candidates,j->assigned,j->matched,j->ambiguous,j->health_issues,j->missing);refresh_ui();refresh_trainer_library_view();trainer_free_matches(j->matches);free(j);return FALSE;}
static void *trainer_scan_worker(void *vp){
    TrainerScanJob*j=vp;int fd[2];if(pipe(fd)!=0){j->failed=1;unlink(j->manifest);g_idle_add(trainer_scan_done,j);return NULL;}pid_t p=fork();
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}if(j->merge_report)execlp("python3","python3",trainer_library_tool(),"auto-match","--manifest",j->manifest,"--merge-report",(char*)NULL);else execlp("python3","python3",trainer_library_tool(),"auto-match","--manifest",j->manifest,(char*)NULL);_exit(127);}
    close(fd[1]);FILE*f=fdopen(fd[0],"r");char line[8192];if(!f){close(fd[0]);j->failed=1;}else while(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;char*kind=strtok(line,"\t");char*key=strtok(NULL,"\t");char*score=strtok(NULL,"\t");char*path=strtok(NULL,"\t");if(!kind)continue;if(!strcmp(kind,"STATS")){j->candidates=key?atoi(key):0;j->roots=score?atoi(score):0;continue;}if(!key)continue;if(!strcmp(kind,"ASSIGNED")){j->assigned++;}else if(!strcmp(kind,"MATCH")&&path&&readable_file(path)){
        if(strlen(key)>2047||strlen(path)>2047||strpbrk(key,"\t\r\n")||strpbrk(path,"\t\r\n")){j->failed=1;continue;}
        AutoMatch*m=calloc(1,sizeof *m);if(!m){j->failed=1;continue;}
        m->key=strdup(key);m->path=strdup(path);if(!m->key||!m->path){free(m->key);free(m->path);free(m);j->failed=1;continue;}
        m->next=j->matches;j->matches=m;
    }else if(!strcmp(kind,"AMBIG"))j->ambiguous++;else if(!strcmp(kind,"MISSING"))j->health_issues++;else if(!strcmp(kind,"NONE"))j->missing++;}
    if(f)fclose(f);int st=0;if(p>0){while(waitpid(p,&st,0)<0&&errno==EINTR){}if(!WIFEXITED(st)||WEXITSTATUS(st)!=0)j->failed=1;}else j->failed=1;unlink(j->manifest);g_idle_add(trainer_scan_done,j);return NULL;
}
static void start_trainer_library_scan_mode(int selected_only){
    if(trainer_scan_active){log_line("Trainer Library scan is already running.");return;}if(selected_only&&(G.selected<0||G.selected>=G.game_count)){log_line("Choose a game in Library before rescanning a single game.");return;}
    char templ[]="/tmp/gameweld-trainer-scan-XXXXXX";int fd=mkstemp(templ);if(fd<0){log_line("Could not create Trainer Library scan manifest.");return;}FILE*f=fdopen(fd,"w");if(!f){close(fd);unlink(templ);return;}int pending=0;
    for(int i=0;i<G.game_count;i++){if(selected_only&&i!=G.selected)continue;Game*g=&G.games[i];char cur[2048]={0};int has_mapping=load_local_trainer(game_key(g),cur,sizeof cur);tsv_field(f,game_key(g));fputc('\t',f);tsv_field(f,g->name);fputc('\t',f);tsv_field(f,g->install_dir);fputc('\t',f);tsv_field(f,g->provider);fputc('\t',f);tsv_field(f,has_mapping?cur:"");fputc('\n',f);pending++;}
    fclose(f);if(!pending){unlink(templ);log_line("Trainer Library: no games are available to scan.");return;}TrainerScanJob*j=calloc(1,sizeof *j);snprintf(j->manifest,sizeof j->manifest,"%s",templ);j->merge_report=selected_only;j->selected_only=selected_only;trainer_scan_active=1;if(selected_only)log_line("Trainer Library rescanning %s only. Existing readable assignment will be shown in the report and will not be overwritten.",G.games[G.selected].name);else log_line("Trainer Library scanning %d games, including existing assignments for report accuracy. Each game folder and its immediate library parent get independent scan budgets so one large drive cannot starve another…",pending);pthread_t t;if(pthread_create(&t,NULL,trainer_scan_worker,j)==0)pthread_detach(t);else{trainer_scan_active=0;unlink(templ);free(j);log_line("Could not start Trainer Library scan worker.");}
}
static void start_trainer_library_scan(void){start_trainer_library_scan_mode(0);}
static void start_selected_trainer_scan(void){start_trainer_library_scan_mode(1);}
static int image_name(const char *name){
    if(!name)return 0; const char *d=strrchr(name,'.'); if(!d)return 0;
    return !strcasecmp(d,".png")||!strcasecmp(d,".jpg")||!strcasecmp(d,".jpeg")||!strcasecmp(d,".webp");
}
static int try_named_art(const char *dir,const char *appid,int cover,char *out,size_t cap){
    static const char *hero_stems[]={"library_hero","library_header","hero","header",NULL};
    static const char *cover_stems[]={"library_600x900_2x","library_600x900","cover","600x900","portrait",NULL};
    static const char *exts[]={"png","jpg","jpeg","webp",NULL};
    const char **stems=cover?cover_stems:hero_stems; char p[2048];
    for(int i=0;stems[i];i++)for(int j=0;exts[j];j++){
        if(appid&&*appid)snprintf(p,sizeof p,"%s/%s_%s.%s",dir,appid,stems[i],exts[j]);
        else snprintf(p,sizeof p,"%s/%s.%s",dir,stems[i],exts[j]);
        if(readable_file(p)){snprintf(out,cap,"%s",p);return 1;}
    }
    return 0;
}
static long long art_score(const char *path,int cover){
    int w=0,h=0; if(!gdk_pixbuf_get_file_info(path,&w,&h)||w<=0||h<=0)return -1;
    long long area=(long long)w*(long long)h; double r=(double)w/(double)h; long long score=area;
    const char *n=strrchr(path,'/');n=n?n+1:path;
    /* Never promote Steam's blurred background, logo or icon into a full-size
     * hero. UI Test 5 exposed exactly that failure on real library entries. */
    if(strstr(n,"blur")||strstr(n,"logo")||strstr(n,"icon"))return -1;
    if(cover){
        if(h>w)score+=1000000000000LL;
        if(r<=0.85)score+=1000000000000LL;
        if(strstr(n,"library_600x900_2x"))score+=6000000000000LL;
        else if(strstr(n,"library_600x900"))score+=5000000000000LL;
        else if(strstr(n,"600x900")||strstr(n,"portrait")||strstr(n,"cover"))score+=3000000000000LL;
    } else {
        if(w>h)score+=1000000000000LL;
        if(r>=1.45)score+=1000000000000LL;
        if(strstr(n,"library_hero"))score+=6000000000000LL;
        else if(strstr(n,"library_header"))score+=5000000000000LL;
        else if(strstr(n,"header"))score+=4000000000000LL;
        else if(strstr(n,"hero"))score+=3000000000000LL;
    }
    return score;
}
static void scan_art_dir(const char *dir,const char *appid,int require_prefix,int cover,char *best,size_t cap,long long *best_score){
    DIR*d=opendir(dir);if(!d)return;struct dirent*e;char p[2048];size_t alen=appid?strlen(appid):0;
    while((e=readdir(d))){if(e->d_name[0]=='.'||!image_name(e->d_name))continue;if(require_prefix&&appid&&strncmp(e->d_name,appid,alen)!=0)continue;if(strlen(dir)+strlen(e->d_name)+2>sizeof p)continue;memcpy(p,dir,strlen(dir));p[strlen(dir)]='/';strcpy(p+strlen(dir)+1,e->d_name);long long sc=art_score(p,cover);if(sc>*best_score){*best_score=sc;snprintf(best,cap,"%s",p);}}
    closedir(d);
}
static void scan_art_tree(const char *dir,const char *appid,int require_prefix,int cover,int depth,char *best,size_t cap,long long *best_score){
    DIR*d=opendir(dir);if(!d)return;struct dirent*e;char p[2048];size_t alen=appid?strlen(appid):0;
    while((e=readdir(d))){
        if(e->d_name[0]=='.')continue;
        snprintf(p,sizeof p,"%s/%s",dir,e->d_name);
        struct stat st;if(stat(p,&st)!=0)continue;
        if(S_ISDIR(st.st_mode)&&depth>0){scan_art_tree(p,appid,0,cover,depth-1,best,cap,best_score);continue;}
        if(!S_ISREG(st.st_mode)||!image_name(e->d_name))continue;
        if(require_prefix&&appid&&strncmp(e->d_name,appid,alen)!=0)continue;
        long long sc=art_score(p,cover);if(sc>*best_score){*best_score=sc;snprintf(best,cap,"%s",p);}
    }
    closedir(d);
}
static int resolve_game_art(const Game *g,int cover,char *out,size_t cap){
    if(!g||!g->appid[0])return 0; char p[2048]; if(g->art_path[0]&&readable_file(g->art_path)){snprintf(out,cap,"%s",g->art_path);return 1;} const char *home=getenv("HOME"),*xdg=getenv("XDG_DATA_HOME"),*appdir=getenv("APPDIR"),*override=getenv("WAND_NATIVE_ARTWORK_DIR");
    /* User overrides win, then curated AppImage artwork. Layout: <root>/<appid>/{hero,cover}.png */
    if(override&&*override){snprintf(p,sizeof p,"%s/%s",override,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(xdg&&*xdg){snprintf(p,sizeof p,"%s/gameweld/artwork/%s",xdg,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(home&&*home){snprintf(p,sizeof p,"%s/.local/share/gameweld/artwork/%s",home,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(appdir&&*appdir){snprintf(p,sizeof p,"%s/usr/share/gameweld/assets/games/%s",appdir,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(!game_is_steam(g))return 0;

    /* Steam uses both a legacy flat cache and, on newer clients, hashed folders
     * below appcache/librarycache/<appid>/. Resolve exact art inside that tree
     * before any broad scan so stale blur/logo files cannot win. */
    char roots[5][2048];int nr=0;const char *steam=getenv("STEAM_COMPAT_CLIENT_INSTALL_PATH");
    if(steam&&*steam)snprintf(roots[nr++],sizeof roots[0],"%s/appcache/librarycache",steam);
    if(home&&*home){snprintf(roots[nr++],sizeof roots[0],"%s/.local/share/Steam/appcache/librarycache",home);snprintf(roots[nr++],sizeof roots[0],"%s/.steam/steam/appcache/librarycache",home);snprintf(roots[nr++],sizeof roots[0],"%s/.steam/root/appcache/librarycache",home);}
    long long best_score=-1; char best[2048]={0};
    for(int i=0;i<nr;i++){
        if(try_named_art(roots[i],g->appid,cover,out,cap))return 1;
        if(strlen(roots[i])+strlen(g->appid)+2>sizeof p)continue;memcpy(p,roots[i],strlen(roots[i]));p[strlen(roots[i])]='/';strcpy(p+strlen(roots[i])+1,g->appid);
        if(try_named_art(p,NULL,cover,out,cap))return 1;
        scan_art_tree(p,NULL,0,cover,3,best,sizeof best,&best_score);
        if(best[0]){snprintf(out,cap,"%s",best);return 1;}
        scan_art_dir(roots[i],g->appid,1,cover,best,sizeof best,&best_score);
    }
    if(best[0]){snprintf(out,cap,"%s",best);return 1;}
    return 0;
}

static void set_image_path(GtkWidget *image,const char *path,int w,int h){
    if(!image)return;GdkPixbuf*pix=NULL;if(path&&*path)pix=gdk_pixbuf_new_from_file_at_scale(path,w,h,FALSE,NULL);gtk_image_set_from_pixbuf((GtkImage*)image,pix);if(pix)g_object_unref(pix);gtk_widget_set_size_request(image,w,h);
}
static GtkWidget *asset_image(const char *name,int w,int h){
    const char*a=getenv("APPDIR");char p[2048];if(a&&*a&&name&&*name)snprintf(p,sizeof p,"%s/usr/share/gameweld/assets/%s",a,name);else if(name&&*name)snprintf(p,sizeof p,"usr/share/gameweld/assets/%s",name);else if(a&&*a)snprintf(p,sizeof p,"%s/.DirIcon",a);else snprintf(p,sizeof p,".DirIcon");
    GdkPixbuf*pix=gdk_pixbuf_new_from_file_at_scale(p,w,h,FALSE,NULL);if(!pix&&a&&*a){snprintf(p,sizeof p,"%s/.DirIcon",a);pix=gdk_pixbuf_new_from_file_at_scale(p,w,h,FALSE,NULL);}if(!pix)return NULL;GtkWidget*i=gtk_image_new_from_pixbuf(pix);g_object_unref(pix);return i;
}
static void refresh_artwork(Game *g){
    char hero[2048]={0},cover[2048]={0};int hh=resolve_game_art(g,0,hero,sizeof hero);int hc=resolve_game_art(g,1,cover,sizeof cover);
    if(!hh&&hc){snprintf(hero,sizeof hero,"%s",cover);hh=1;}if(!hc&&hh){snprintf(cover,sizeof cover,"%s",hero);hc=1;}
    set_image_path(G.hero_image,hh?hero:NULL,520,300);set_image_path(G.cover_image,hc?cover:NULL,155,220);
    if(g&&strcmp(G.artwork_appid,game_key(g))){snprintf(G.artwork_appid,sizeof G.artwork_appid,"%s",game_key(g));if(hh||hc)log_line("Artwork loaded for %s%s%s",g->name,hh?" • hero":"",hc?" • cover":"");else log_line("No cached artwork found yet for %s (%s %s).",g->name,game_source_name(g),g->appid);}
}

/* Monitor workareas are reported in GTK logical pixels. KWin/Wayland and
 * HiDPI displays may expose 3840x2160 as 1920x1080 logical at 2x scaling.
 * Use the full monitor geometry (not its panel-reduced workarea) multiplied
 * by the integer GTK monitor scale to recognize a physical UHD display.
 * No hardcoded user screen dimensions or monitor count are assumed. */
static void pc2_primary_monitor_pixels(int *physical_w,int *physical_h){
    int w=0,h=0;
    GdkScreen *screen=gdk_screen_get_default();
    if(screen){
        int monitor=gdk_screen_get_primary_monitor(screen);
        GdkRectangle geometry={0,0,0,0};
        gdk_screen_get_monitor_geometry(screen,monitor,&geometry);
        int scale=gdk_screen_get_monitor_scale_factor(screen,monitor);
        if(scale<1)scale=1;
        if(scale>8)scale=8;
        w=geometry.width>0?geometry.width*scale:0;
        h=geometry.height>0?geometry.height*scale:0;
    }
    if(physical_w)*physical_w=w;
    if(physical_h)*physical_h=h;
}
/* PC2 saves ONLY last normal-window dimensions. This is independent of
 * Steam, Wine, DeckCheatz, and the rest of GameWeld's user configuration.
 * The state is deliberately not a requested maximize/fullscreen mode. */
static int pc2_window_state_path(char *out,size_t cap,int create_dir){
    const char *xdg=getenv("XDG_CONFIG_HOME");
    const char *home=getenv("HOME");
    char dir[4096]={0};
    int written=-1;
    if(xdg&&xdg[0]=='/')
        written=snprintf(dir,sizeof dir,"%s/gameweld",xdg);
    else if(home&&home[0]=='/')
        written=snprintf(dir,sizeof dir,"%s/.config/gameweld",home);
    if(written<=0||written>=(int)sizeof dir)return 0;
    if(create_dir&&g_mkdir_with_parents(dir,0700)!=0)return 0;
    written=snprintf(out,cap,"%s/pc2-window-size.txt",dir);
    return written>0 && (size_t)written<cap;
}
static int pc2_load_window_size(int *out_w,int *out_h,int max_w,int max_h){
    char path[4096]={0};
    if(!pc2_window_state_path(path,sizeof path,0))return 0;
    return gameweld_pc2_state_read(path,out_w,out_h,max_w,max_h);
}
/* Record the LAST live normal-window size when GTK configures the window.
 * Reading geometry inside the "destroy" signal is too late on KWin/GTK3:
 * the window may already be unmapped and GTK may return its original size.
 * A short coalesced save captures a completed manual resize before quit. */
static int pc2_window_last_w=0,pc2_window_last_h=0;
static int pc2_window_observation_ready=0;
static int pc2_window_save_queued=0;

static int pc2_save_window_size(void){
    if(!pc2_discovery_only())return 0;
    int w=pc2_window_last_w,h=pc2_window_last_h;
    if(w<640||h<480||w>8192||h>8192)return 0;
    char path[4096]={0};
    if(!pc2_window_state_path(path,sizeof path,1))return 0;
    return gameweld_pc2_state_write(path,w,h);
}
static gboolean pc2_window_save_after_resize(void *unused){
    (void)unused;
    pc2_window_save_queued=0;
    if(pc2_save_window_size())
        log_line("PC2 saved live window size: %dx%d normal window.",pc2_window_last_w,pc2_window_last_h);
    else
        log_line("PC2 window size save failed; check write access to the user config directory.");
    return FALSE;
}
static gboolean pc2_window_configure(GtkWidget *window,void *event,void *unused){
    (void)event;(void)unused;
    if(!pc2_discovery_only()||!pc2_window_observation_ready||!window||
       gtk_window_is_maximized((GtkWindow*)window))return FALSE;
    int w=0,h=0;
    gtk_window_get_size((GtkWindow*)window,&w,&h);
    if(w<640||h<480||w>8192||h>8192)return FALSE;
    if(w==pc2_window_last_w && h==pc2_window_last_h)return FALSE;
    pc2_window_last_w=w;
    pc2_window_last_h=h;
    if(!pc2_window_save_queued){
        pc2_window_save_queued=1;
        g_timeout_add(750,pc2_window_save_after_resize,NULL);
    }
    return FALSE;
}

static void recommended_window_geometry(int *out_w,int *out_h){
    /* Size GameWeld from the primary monitor work area instead of pinning the
     * UI to the old 1480x900 mock-up.  The goal is to use the extra vertical
     * room on 1440p/4K displays so Overview can show the launch controls and
     * session panels without needless scrolling, while still fitting 1080p
     * and smaller desktops safely. */
    GdkScreen*screen=gdk_screen_get_default();
    int sw=screen?gdk_screen_get_width(screen):1480;
    int sh=screen?gdk_screen_get_height(screen):900;
    if(screen){
        GdkRectangle work={0,0,0,0};
        int monitor=gdk_screen_get_primary_monitor(screen);
        gdk_screen_get_monitor_workarea(screen,monitor,&work);
        if(work.width>0&&work.height>0){sw=work.width;sh=work.height;}
    }
    if(pc2_discovery_only()){
        int physical_w=0,physical_h=0;
        pc2_primary_monitor_pixels(&physical_w,&physical_h);
        GameWeldPC2WindowPolicy size=gameweld_pc2_window_policy(
            sw,sh,physical_w,physical_h);
        int ww=size.width,hh=size.height;
        /* Prefer the user's last manually chosen normal-window size when
         * possible, but always clamp it to the current monitor workarea. */
        int maxw=sw>40?sw-24:sw;
        int maxh=sh>60?sh-32:sh;
        pc2_load_window_size(&ww,&hh,maxw,maxh);
        if(out_w)*out_w=ww;
        if(out_h)*out_h=hh;
        return;
    }
    /* Preserve the former PC1 window sizing, including its max bounds. */
    int maxw=sw-32; if(maxw<900)maxw=sw;
    int maxh=sh-96; if(maxh<560)maxh=sh-48;
    int ww=(sw*82)/100;
    int wh=(sh*94)/100;
    if(ww>2200)ww=2200;
    if(wh>1400)wh=1400;
    if(ww<1180)ww=1180;
    if(wh<680)wh=680;
    if(ww>maxw)ww=maxw;
    if(wh>maxh)wh=maxh;
    if(out_w)*out_w=ww;
    if(out_h)*out_h=wh;
}

static gboolean force_mockup_geometry(void *unused){
    (void)unused;
    /* KWin may restore an old development size after GTK's default-size hint,
     * so re-apply the monitor-aware size once during startup. */
    int ww=1480,wh=900;
    recommended_window_geometry(&ww,&wh);
    gtk_window_resize((GtkWindow*)G.window,ww,wh);
    gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    return FALSE;
}
/* Correct inherited, tiny development-window geometry once after mapping.
 * KWin can apply old saved geometry after GTK's default-size hint. Never
 * maximize automatically and never repeatedly override manual resizing. */
static gboolean pc2_startup_fit_window(void *unused){
    (void)unused;
    if(pc2_discovery_only()&&G.window){
        int ww=1280,hh=760;
        recommended_window_geometry(&ww,&hh);
        if(gtk_window_is_maximized((GtkWindow*)G.window))
            gtk_window_unmaximize((GtkWindow*)G.window);
        gtk_window_resize((GtkWindow*)G.window,ww,hh);
        gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
        /* Programmatic startup adjustment happens before tracking real user
         * resizing, so a stale KWin initial allocation is never persisted. */
        pc2_window_last_w=ww;pc2_window_last_h=hh;
        pc2_window_observation_ready=1;
        log_line("PC2 active window size: %dx%d; future manual resizes will be remembered.",ww,hh);
    }
    return FALSE;
}
/* A settings action to recover a preferred default size after resizing or
 * changing monitors. It deletes only PC2's small width/height preferences. */
static void on_pc2_window_size_reset(GtkButton *button,void *unused){
    (void)button;(void)unused;
    if(!pc2_discovery_only()||!G.window)return;
    char path[4096]={0};
    if(pc2_window_state_path(path,sizeof path,0))unlink(path);
    int ww=1280,hh=760;
    recommended_window_geometry(&ww,&hh);
    if(gtk_window_is_maximized((GtkWindow*)G.window))
        gtk_window_unmaximize((GtkWindow*)G.window);
    gtk_window_resize((GtkWindow*)G.window,ww,hh);
    gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    pc2_window_last_w=ww;pc2_window_last_h=hh;
    pc2_window_observation_ready=1;
    pc2_save_window_size();
    log_line("PC2 window reset: %dx%d normal window; next launch uses reset dimensions.",ww,hh);
}
static void spawn_detached(const char *a,const char *b,const char *c){pid_t p=fork();if(p==0){clear_desktop_activation_env();if(c)execlp(a,a,b,c,(char*)NULL);else if(b)execlp(a,a,b,(char*)NULL);else execlp(a,a,(char*)NULL);_exit(127);}}
static void set_label(GtkWidget *w,const char *s){ if(w)gtk_label_set_text((GtkLabel*)w,s?s:""); }
/* Recent Games is a local recently-SELECTED history. It is not Steam
 * playtime, launch history or trainer availability evidence. All tiles only
 * change the active game; the Play with WeMod button handles launch consent. */
static GameWeldPC2RecentHistory pc2_recents={0};
static GtkWidget *pc2_recent_tiles=NULL;
static int pc2_recent_render_queued=0;
static void pc2_recent_render(void);
static gboolean pc2_recent_render_idle(void *unused){
    (void)unused;
    pc2_recent_render_queued=0;
    pc2_recent_render();
    return FALSE;
}
static void pc2_schedule_recent_render(void){
    if(pc2_recent_render_queued)return;
    pc2_recent_render_queued=1;
    g_idle_add(pc2_recent_render_idle,NULL);
}

static int pc2_recent_path(char *out,size_t cap,int create_dir){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    char dir[4096]={0};
    int n=0;
    if(xdg&&xdg[0]=='/')n=snprintf(dir,sizeof dir,"%s/gameweld",xdg);
    else if(home&&home[0]=='/')n=snprintf(dir,sizeof dir,"%s/.config/gameweld",home);
    if(n<=0||(size_t)n>=sizeof dir)return 0;
    if(create_dir&&g_mkdir_with_parents(dir,0700)!=0)return 0;
    n=snprintf(out,cap,"%s/pc2-recent-games.txt",dir);
    return n>0&&(size_t)n<cap;
}
static void pc2_recent_load(void){
    memset(&pc2_recents,0,sizeof pc2_recents);
    if(!pc2_discovery_only())return;
    char path[4096];
    if(!pc2_recent_path(path,sizeof path,0))return;
    struct stat st;
    if(lstat(path,&st)!=0||!S_ISREG(st.st_mode)||st.st_size>16384)return;
    FILE *file=fopen(path,"r");
    if(!file)return;
    char line[GAMEWELD_PC2_RECENT_KEY_SIZE+4];
    char saved[GAMEWELD_PC2_RECENT_COUNT][GAMEWELD_PC2_RECENT_KEY_SIZE]={{0}};
    int n=0;
    while(n<GAMEWELD_PC2_RECENT_COUNT&&fgets(line,sizeof line,file)){
        if(!strchr(line,'\n')&&!feof(file)){n=0;break;}
        line[strcspn(line,"\r\n")]=0;
        if(gameweld_pc2_recent_key_ok(line))
            snprintf(saved[n++],sizeof saved[0],"%s",line);
    }
    fclose(file);
    /* Stored order is newest-first. Replay oldest-first through the same
     * checked LRU operation so it remains deterministic and deduplicated. */
    for(int i=n-1;i>=0;i--)gameweld_pc2_recent_push(&pc2_recents,saved[i]);
}
static void pc2_recent_save(void){
    if(!pc2_discovery_only())return;
    char path[4096];
    if(!pc2_recent_path(path,sizeof path,1))return;
    char temporary[4200];
    int n=snprintf(temporary,sizeof temporary,"%s.tmp-XXXXXX",path);
    if(n<=0||(size_t)n>=sizeof temporary)return;
    int fd=mkstemp(temporary);
    if(fd<0)return;
    fchmod(fd,0600);
    FILE *file=fdopen(fd,"w");
    if(!file){close(fd);unlink(temporary);return;}
    int ok=1;
    for(int i=0;i<pc2_recents.count;i++)
        if(fprintf(file,"%s\n",pc2_recents.keys[i])<0){ok=0;break;}
    if(fflush(file)!=0)ok=0;
    if(ok&&fsync(fd)!=0)ok=0;
    if(fclose(file)!=0)ok=0;
    if(!ok||rename(temporary,path)!=0)unlink(temporary);
}
static void pc2_recent_record(int index){
    if(!pc2_discovery_only()||index<0||index>=G.game_count)return;
    if(gameweld_pc2_recent_push(&pc2_recents,game_key(&G.games[index])))
        pc2_recent_save();
}
static int pc2_recent_index_of(const char *key){
    if(!key||!*key)return -1;
    for(int i=0;i<G.game_count;i++)
        if(!strcmp(game_key(&G.games[i]),key))return i;
    return -1;
}
static void pc2_recent_select(GtkButton *button,void *userdata){
    (void)button;
    int index=(int)(intptr_t)userdata-1;
    if(index<0||index>=G.game_count)return;
    if(G.selected==index){
        pc2_recent_record(index);
        pc2_schedule_recent_render();
        return;
    }
    if(G.game_list&&G.game_rows[index]){
        gtk_list_box_select_row((GtkListBox*)G.game_list,
                                (GtkListBoxRow*)G.game_rows[index]);
    }else{
        G.selected=index;
        pc2_recent_record(index);
        refresh_ui();
        pc2_schedule_recent_render();
    }
}
static void pc2_recent_clear_child(GtkWidget *child,void *unused){
    (void)unused;gtk_widget_destroy(child);
}
static void pc2_recent_render(void){
    if(!pc2_discovery_only()||!pc2_recent_tiles)return;
    gtk_container_foreach(pc2_recent_tiles,pc2_recent_clear_child,NULL);
    int ids[GAMEWELD_PC2_RECENT_COUNT],is_recent[GAMEWELD_PC2_RECENT_COUNT];
    int count=0;
    for(int i=0;i<pc2_recents.count&&count<GAMEWELD_PC2_RECENT_COUNT;i++){
        int idx=pc2_recent_index_of(pc2_recents.keys[i]);
        if(idx>=0){ids[count]=idx;is_recent[count++]=1;}
    }
    /* Fill unused slots from the installed Library without implying those
     * games were played or selected in the past. */
    for(int idx=0;idx<G.game_count&&count<GAMEWELD_PC2_RECENT_COUNT;idx++){
        int duplicate=0;
        for(int j=0;j<count;j++)if(ids[j]==idx){duplicate=1;break;}
        if(!duplicate){ids[count]=idx;is_recent[count++]=0;}
    }
    for(int i=0;i<count;i++){
        int idx=ids[i];
        Game *game=&G.games[idx];
        GtkWidget *tile=gtk_button_new();
        style(tile,"recent-tile");
        if(idx==G.selected)style(tile,"recent-tile-selected");
        GtkWidget *content=box(GTK_ORIENTATION_VERTICAL,6);
        GtkWidget *cover=gtk_image_new();
        style(cover,"recent-tile-cover");
        char art[2048]={0};
        if(!resolve_game_art(game,1,art,sizeof art))
            resolve_game_art(game,0,art,sizeof art);
        set_image_path(cover,art[0]?art:NULL,105,125);
        pack(content,cover,0);
        GtkWidget *name=label(game->name,"recent-tile-name");
        gtk_label_set_ellipsize((GtkLabel*)name,3);
        gtk_widget_set_size_request(name,130,-1);
        pack(content,name,0);
        const char *provider=game_is_steam(game)?"Steam":
                             game_is_lutris(game)?"Lutris":"Heroic";
        char source[64];
        snprintf(source,sizeof source,"%s • %s",is_recent[i]?"Recently selected":"Library",provider);
        GtkWidget *hint=label(source,"recent-tile-source");
        pack(content,hint,0);
        gtk_container_add(tile,content);
        g_signal_connect_data(tile,"clicked",(GCallback)pc2_recent_select,
                              (void *)(intptr_t)(idx+1),NULL,0);
        pack(pc2_recent_tiles,tile,0);
    }
    gtk_widget_show_all(pc2_recent_tiles);
}
static void selected_changed(GtkListBox *list,GtkListBoxRow *row,void *data){
    (void)list;(void)data;
    if(!row)return;
    int idx=gtk_list_box_row_get_index(row);
    if(idx>=0&&idx<G.game_count){
        G.selected=idx;
        pc2_recent_record(idx);
        refresh_ui();
        pc2_schedule_recent_render();
        trainer_update_context_refresh();
    }
}

static void refresh_ui(void) {
    char b[4096]; Game *g=(G.selected>=0&&G.selected<G.game_count)?&G.games[G.selected]:NULL;
    long managed_game_pid=0,managed_trainer_pid=0;char managed_launch[128]={0};
    int managed_state=g?heroic_managed_session_state(g,&managed_game_pid,&managed_trainer_pid,managed_launch,sizeof managed_launch):0;
    if(G.quick_store)gtk_widget_set_visible(G.quick_store,g&&game_is_steam(g)&&!game_is_steam_shortcut(g));
    if(G.top_steam_status){
        snprintf(b,sizeof b,"<span foreground=\"#f4f6fa\" weight=\"bold\">Game Sources</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Steam %d • Heroic %d • Lutris %d</span>\n<span foreground=\"#aeb9c7\">%d installed manifests • %d Steam shortcuts • Lutris prefix-validation</span>",G.steam_game_count,G.heroic_game_count,G.lutris_game_count,G.steam_manifest_game_count,G.steam_shortcut_count);
        gtk_label_set_markup((GtkLabel*)G.top_steam_status,b);
    }
    if(pc2_discovery_only()){
        int allowed=g&&game_is_steam(g)&&!game_is_steam_shortcut(g)
                    &&g->install_dir[0]&&g->appid[0];
        if(G.pc2_deckcheatz_overview_play)
            gtk_widget_set_sensitive(G.pc2_deckcheatz_overview_play,FALSE);
        if(G.pc2_deckcheatz_library_play)
            gtk_widget_set_sensitive(G.pc2_deckcheatz_library_play,FALSE);
        if(!allowed){
            pc2_bridge_readiness_invalidate();
            if(G.pc2_deckcheatz_overview_status)
                set_label(G.pc2_deckcheatz_overview_status,
                    "Steam Bridge supports installed Steam Windows games.");
            if(G.pc2_deckcheatz_library_status)
                set_label(G.pc2_deckcheatz_library_status,
                    "Steam Bridge supports installed Steam Windows games.");
        }else{
            pc2_bridge_readiness_for_game(g);
        }
    }
    if(!pc2_discovery_only()&&pc2_provider_controls_allowed()){
        if(g&&game_is_steam(g)&&!game_is_steam_shortcut(g)&&
           g->install_dir[0]&&g->appid[0])
            pc2_bridge_readiness_for_game(g);
        else pc2_bridge_readiness_invalidate();
    }
    if(g){
        const char *src=game_source_name(g);
        refresh_artwork(g);set_label(G.hero_name,g->name);
        if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"Steam • Non-Steam Shortcut • App ID: %s",g->appid);
        else if(game_is_steam(g))snprintf(b,sizeof b,"Steam • App ID: %s",g->appid);
        else if(game_is_lutris(g))snprintf(b,sizeof b,"Lutris • %s • ID: %s",g->runner[0]?g->runner:"wine",g->appid);
        else snprintf(b,sizeof b,"Heroic • %s • ID: %s",g->runner,g->appid);
        set_label(G.hero_meta,b);
        if(G.library_detail_name)set_label(G.library_detail_name,g->name);
        if(G.library_detail_meta)set_label(G.library_detail_meta,b);
        if(G.library_detail_status){if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"%s\n%s",g->shortcut_launch_supported?"Restart-free Steam shortcut manager handoff ready":"Shortcut discovered; runtime handoff still needs resolution",g->resolution_label[0]?g->resolution_label:"Resolution pending");else if(game_is_steam(g))snprintf(b,sizeof b,"Steam launch path ready • trainer handoff uses the live game-selected Proton session");else if(game_is_lutris(g))snprintf(b,sizeof b,"Lutris Test 4 live-session readiness • %s\nResolved entries can launch through Lutris; assigned/custom local trainers are handed into the verified same-prefix live session.",g->resolution_label[0]?g->resolution_label:"Resolution pending");else snprintf(b,sizeof b,"Heroic launch path ready • %s runner • %s",g->runner,g->wine_name[0]?g->wine_name:"launcher-managed runtime");set_label(G.library_detail_status,b);}
        if(G.library_detail_path){snprintf(b,sizeof b,"Install path: %s",g->install_dir[0]?g->install_dir:"Not reported");set_label(G.library_detail_path,b);}
        if(G.overview_launch_assigned)gtk_widget_set_sensitive(G.overview_launch_assigned,game_launch_enabled(g));
        if(G.overview_launch_game_only)gtk_widget_set_sensitive(G.overview_launch_game_only,game_launch_enabled(g));
        if(G.overview_launch_custom)gtk_widget_set_sensitive(G.overview_launch_custom,game_launch_enabled(g));
        if(G.overview_launch_aurora)gtk_widget_set_sensitive(G.overview_launch_aurora,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_launch_cheat_evolution)gtk_widget_set_sensitive(G.overview_launch_cheat_evolution,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_launch_cheat_table)gtk_widget_set_sensitive(G.overview_launch_cheat_table,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_launch_wemod)gtk_widget_set_sensitive(G.overview_launch_wemod,game_wemod_supported(g));
        if(G.overview_save_profile)gtk_widget_set_sensitive(G.overview_save_profile,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_reset_profile)gtk_widget_set_sensitive(G.overview_reset_profile,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_profile_combo)gtk_widget_set_sensitive(G.overview_profile_combo,game_launch_enabled(g)&&!game_is_lutris(g));
        if(G.overview_launch_hint){
            if(game_is_steam(g)&&!game_is_steam_shortcut(g))snprintf(b,sizeof b,"%s selected • Assigned trainer, Cheat Engine .CT, WeMod, Aurora, Cheat Evolution, custom trainer, or game only. Save one as the one-click default.",g->name);
            else if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"%s selected • Assigned trainer, Cheat Engine .CT, Aurora, Cheat Evolution, custom trainer, or game only. Save one as the one-click default. WeMod is not yet validated for Steam shortcuts.",g->name);
            else if(game_is_lutris(g))snprintf(b,sizeof b,"%s selected • GameWeld 0.6.0 Test 4 can launch fully resolved Lutris entries and hand an assigned/custom local trainer into the verified live same-prefix runtime. Advanced manager/.CT/WeMod paths remain disabled.",g->name);
            else snprintf(b,sizeof b,"%s selected • Assigned trainer, Cheat Engine .CT, WeMod (Heroic field validation), Aurora, Cheat Evolution, custom trainer, or game only. Save one as the one-click default.",g->name);
            set_label(G.overview_launch_hint,b);
        }
        {
            char profile[64]="assigned";int saved=load_launch_profile(game_key(g),profile,sizeof profile);
            if(G.overview_profile_combo)gtk_combo_box_set_active_id((GtkComboBox*)G.overview_profile_combo,profile);
            if(G.overview_profile_status){if(game_is_lutris(g))set_label(G.overview_profile_status,"Lutris Test 4 uses Assigned / detected trainer as the one-click path. Saving advanced launch profiles remains disabled while live-session ownership is field-validated.");else{snprintf(b,sizeof b,"%sDefault: %s",saved?"Saved • ":"Not saved • using ",launch_profile_label(profile));set_label(G.overview_profile_status,b);}}
            /* The primary Play card is updated after trainer/session readiness is
             * resolved below.  Test 15 updated it here, then the legacy readiness
             * block overwrote it with PLAY WITH LOCAL TRAINER. */
        }
        if(G.game_detected_detail){if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"%.380s\nSteam • Non-Steam Shortcut • App ID %.190s\nRungameid: %.190s\nTarget: %.2040s\nResolution: %.100s",g->name,g->appid,g->launch_id[0]?g->launch_id:"—",g->executable[0]?g->executable:"—",g->resolution_label[0]?g->resolution_label:"Pending");else if(game_is_lutris(g))snprintf(b,sizeof b,"%.380s\nLutris • %.100s • ID %.190s\nTarget: %.2040s\nPrefix: %.2040s\nWine: %.200s\nResolution: %.100s",g->name,g->runner[0]?g->runner:"wine",g->appid,g->executable[0]?g->executable:"Not resolved",g->prefix[0]?g->prefix:"Not resolved",g->wine_name[0]?g->wine_name:(g->wine_bin[0]?g->wine_bin:"Not resolved"),g->resolution_label[0]?g->resolution_label:"Pending");else snprintf(b,sizeof b,"%.360s\n%.100s • %.190s",g->name,src,game_is_steam(g)?g->appid:g->runner);set_label(G.game_detected_detail,b);}
        if(game_is_steam_shortcut(g)){
            if(g->shortcut_launch_supported)gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Non-Steam shortcut detected</span>\n<span foreground=\"#aeb9c7\">🎮   Target:      </span><span foreground=\"#28e57b\" weight=\"bold\">Shortcut identity resolved</span>\n<span foreground=\"#aeb9c7\">⚙   Handoff:     </span><span foreground=\"#28e57b\" weight=\"bold\">Runtime/prefix resolved • restart-free manager handoff enabled</span>");
            else gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Non-Steam shortcut detected</span>\n<span foreground=\"#aeb9c7\">🎮   Target:      </span><span foreground=\"#28e57b\" weight=\"bold\">Library-visible</span>\n<span foreground=\"#aeb9c7\">⚙   Handoff:     </span><span foreground=\"#efb85b\" weight=\"bold\">Resolution incomplete</span>");
            if(g->prefix[0])snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix);else snprintf(b,sizeof b,"▰   Prefix:      Not created/resolved");set_label(G.right_prefix,b);
        }else if(game_is_steam(g)){
            gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Detected</span>\n<span foreground=\"#aeb9c7\">🎮   Game:        </span><span foreground=\"#28e57b\" weight=\"bold\">Installed</span>\n<span foreground=\"#aeb9c7\">⚙   Runner:      Steam Play</span>");
            set_label(G.right_prefix,g->wand_found?"▰   Prefix:      Compatible":"▰   Prefix:      Detected");
        }else if(game_is_lutris(g)){
            snprintf(b,sizeof b,"Lutris: Detected\nRunner: %s\nGame: %s\nResolution: %s",g->runner[0]?g->runner:"wine",g->executable[0]?"Installed target resolved":"Discovered",g->resolution_label[0]?g->resolution_label:"Pending");set_label(G.right_game,b);
            snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix[0]?g->prefix:"Not resolved");set_label(G.right_prefix,b);
        }else{
            if(managed_state==1)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Running (GameWeld managed)\nPID: %ld",g->runner,managed_game_pid);else if(managed_state==2)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Closed • trainer still running\nTrainer PID: %ld",g->runner,managed_trainer_pid);else snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Installed",g->runner);set_label(G.right_game,b);
            snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix[0]?g->prefix:"Heroic managed");set_label(G.right_prefix,b);
        }
    } else {
        if(G.game_detected_detail)set_label(G.game_detected_detail,"No game selected");set_image_path(G.hero_image,NULL,520,180);set_image_path(G.cover_image,NULL,155,220);G.artwork_appid[0]=0;set_label(G.hero_name,"Select a game");set_label(G.hero_meta,"Steam / Heroic / Lutris");gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">Game source:     Not selected\n🎮   Game:        Not detected\n⚙   Runner:      —</span>");set_label(G.right_prefix,"▰   Prefix:      —");
        if(G.overview_launch_assigned)gtk_widget_set_sensitive(G.overview_launch_assigned,FALSE);if(G.overview_launch_game_only)gtk_widget_set_sensitive(G.overview_launch_game_only,FALSE);if(G.overview_launch_custom)gtk_widget_set_sensitive(G.overview_launch_custom,FALSE);if(G.overview_launch_aurora)gtk_widget_set_sensitive(G.overview_launch_aurora,FALSE);if(G.overview_launch_cheat_evolution)gtk_widget_set_sensitive(G.overview_launch_cheat_evolution,FALSE);if(G.overview_launch_cheat_table)gtk_widget_set_sensitive(G.overview_launch_cheat_table,FALSE);if(G.overview_launch_wemod)gtk_widget_set_sensitive(G.overview_launch_wemod,FALSE);if(G.overview_save_profile)gtk_widget_set_sensitive(G.overview_save_profile,FALSE);if(G.overview_reset_profile)gtk_widget_set_sensitive(G.overview_reset_profile,FALSE);if(G.overview_profile_combo)gtk_widget_set_sensitive(G.overview_profile_combo,FALSE);if(G.overview_profile_status)set_label(G.overview_profile_status,"Select a game to choose its one-click default.");if(G.overview_launch_hint)set_label(G.overview_launch_hint,"Select a game in Library. Its launch options stay here on Overview.");
    }
    if(g&&game_is_lutris(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Lutris live session</span>\n<span foreground=\"#aeb9c7\">✣   Trainers:    </span><span foreground=\"#28e57b\" weight=\"bold\">Assigned/custom local handoff</span>");
        snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Wine:        </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s • %s</span>",g->wine_name[0]?g->wine_name:(g->wine_bin[0]?g->wine_bin:"Not resolved"),g->resolution_label[0]?g->resolution_label:"Resolution pending",lutris_session_ready(g)?"same-session local trainer handoff ready":"launch blocked until fully resolved");gtk_label_set_markup((GtkLabel*)G.right_proton,b);
    } else if(g&&game_is_heroic(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Heroic\n✣   Trainers:    Local / Cheat Engine</span>");
        if(managed_state==1)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#28e57b\" weight=\"bold\">GameWeld managed</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Actual game process running</span>");else if(managed_state==2)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#efb85b\" weight=\"bold\">Trainer remains</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Game process exited</span>");else snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Heroic:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Direct live-prefix ready</span>",g->wine_name[0]?g->wine_name:(g->wine_type[0]?g->wine_type:"Launcher-managed"));gtk_label_set_markup((GtkLabel*)G.right_proton,b);
    } else if(g&&game_is_steam_shortcut(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Steam non-Steam shortcut</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     Discovery + assignment ready</span>");
        if(g->shortcut_launch_supported){snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Runtime + compatdata resolved • restart-free manager handoff enabled</span>",g->compat_tool[0]?g->compat_tool:"Resolved Steam Play tool");gtk_label_set_markup((GtkLabel*)G.right_proton,b);}else{snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">%s</span>",g->compat_tool[0]?g->compat_tool:"Not resolved",g->resolution_label[0]?g->resolution_label:"Refresh after Steam creates the shortcut prefix");gtk_label_set_markup((GtkLabel*)G.right_proton,b);}
    } else {
        if(G.wand_installed)gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Steam compatibility</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     </span><span foreground=\"#28e57b\" weight=\"bold\">Available</span>");else gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Steam compatibility not installed\n✣   Trainer:     Unavailable</span>");
        if(G.wand_healthy)gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">GE-Proton-Wand-SHA256</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Ready to Launch</span>");else gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">Needs setup</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Setup required</span>");
    }
    set_label(G.game_ready,g?(game_is_lutris(g)?(lutris_session_ready(g)?"Live handoff ready":"Discovered"):(managed_state==1?"Running":(managed_state==2?"Trainer active":(game_is_steam_shortcut(g)?"Shortcut detected":"Installed")))):"Not detected");set_label(G.wand_ready,(g&&game_is_lutris(g))?(lutris_session_ready(g)?"Lutris session":"Lutris discovery"):((g&&game_is_heroic(g))?"Heroic":(g&&game_is_steam_shortcut(g)?"Discovery ready":(G.wand_installed?"Ready":"Needs setup"))));set_label(G.compat_ready,(g&&game_is_lutris(g))?(g->resolution_label[0]?g->resolution_label:"Resolution pending"):((g&&game_is_heroic(g))?(managed_state?"Managed session":"Launcher-managed"):(g&&game_is_steam_shortcut(g)?(g->shortcut_launch_supported?"Restart-free attach • field validated":"Resolution pending"):(G.wand_healthy?"Configured":"Needs repair"))));
    char lt[2048]={0},ct[2048]={0},ce[2048]={0},managed_ce[2048]={0},windows_ce[2048]={0},ce_installer[2048]={0},np[128]={0};
    int has_local_mapping=g&&load_local_trainer(game_key(g),lt,sizeof lt);
    int has_local=has_local_mapping&&readable_file(lt);
    int has_ct=g&&load_cheat_table(game_key(g),ct,sizeof ct)&&readable_file(ct);
    int has_managed_ce=g&&detect_managed_cheat_engine(game_ce_id(g),managed_ce,sizeof managed_ce);
    int has_windows_ce=g&&detect_managed_windows_ce(game_ce_id(g),windows_ce,sizeof windows_ce);
    int has_custom_ce=load_cheat_engine(ce,sizeof ce)&&readable_file(ce);
    if(!has_custom_ce&&has_managed_ce)snprintf(ce,sizeof ce,"%s",managed_ce);
    int has_ce=has_managed_ce||has_custom_ce;
    int has_ce_installer=load_cheat_engine_installer(ce_installer,sizeof ce_installer)&&readable_file(ce_installer);
    int use_ct=has_ct&&has_ce;
    const char *native_available=(g&&game_is_steam(g)&&!game_is_steam_shortcut(g))?available_native_profile(g->appid):NULL;
    int has_native=g&&native_available&&load_native_profile(game_key(g),np,sizeof np)&&!strcmp(np,native_available);
    /* Keep the primary Play card visually bound to the saved one-click profile.
     * Runtime/session state still takes precedence; the legacy trainer wording is
     * only used when Assigned / detected trainer is the effective default. */
    char primary_mode[64]="assigned";
    if(g)load_launch_profile(game_key(g),primary_mode,sizeof primary_mode);
    if(G.play_title){
        if(g&&game_is_lutris(g))set_label(G.play_title,has_local?"PLAY WITH LUTRIS TRAINER":"PLAY THROUGH LUTRIS");
        else if(managed_state==1)set_label(G.play_title,"GAME RUNNING");
        else if(managed_state==2)set_label(G.play_title,"TRAINER STILL RUNNING");
        else if(g&&!strcmp(primary_mode,"wemod"))set_label(G.play_title,"PLAY WITH WEMOD");
        else if(g&&!strcmp(primary_mode,"aurora"))set_label(G.play_title,"PLAY WITH AURORA");
        else if(g&&!strcmp(primary_mode,"cheat-evolution"))set_label(G.play_title,"PLAY WITH CHEAT EVOLUTION");
        else if(g&&!strcmp(primary_mode,"cheat-table"))set_label(G.play_title,"PLAY WITH CHEAT TABLE");
        else if(g&&!strcmp(primary_mode,"game-only"))set_label(G.play_title,"PLAY GAME ONLY");
        else set_label(G.play_title,has_native?"PLAY WITH NATIVE TRAINER":(use_ct?"PLAY WITH CHEAT TABLE":(has_local?"PLAY WITH LOCAL TRAINER":((g&&game_is_steam_shortcut(g))?"LAUNCH STEAM SHORTCUT":((g&&!game_is_steam(g))?"PLAY THROUGH HEROIC":(g?"PLAY WITH STEAM TRAINER":"PLAY WITH TRAINER"))))));
    }
    if(G.play_subtitle){
        if(g&&game_is_lutris(g))set_label(G.play_subtitle,"0.6.0 Test 4 launches through Lutris, proves the exact live prefix/runtime owner, then hands an assigned local trainer into that same session. No isolated Wine/UMU fallback.");
        else if(managed_state==1)set_label(G.play_subtitle,"GameWeld is tracking the actual Heroic game process • trainer shares the managed UMU session");
        else if(managed_state==2)set_label(G.play_subtitle,"The game has exited but the trainer is still active • close it or use Stop Stuck Trainer");
        else if(g&&strcmp(primary_mode,"assigned")){snprintf(b,sizeof b,"One-click default: %s",launch_profile_label(primary_mode));set_label(G.play_subtitle,b);}
        else set_label(G.play_subtitle,has_native?"Built-in Resonance trainer • no Cheat Engine • unlimited local profile":(use_ct?"Launch game + Cheat Engine table (local / unlimited)":(has_local?"Launch game + your local trainer (local / unlimited)":((g&&game_is_steam_shortcut(g))?"Launch through the shortcut’s Steam rungameid; assigned trainers use the validated live Proton session":((g&&!game_is_steam(g))?"Launch with Heroic using its configured Wine/Proton runner":(g?"Launch through Steam with the configured trainer provider":"Select a game to see its configured launch path"))))));
    }
    if(G.play_button)gtk_widget_set_sensitive(G.play_button,managed_state==0&&game_launch_enabled(g));
    if(pc2_discovery_only()){
        set_label(G.wand_ready,"Unverified");
        set_label(G.compat_ready,"Not verified");
        set_label(G.play_title,"TRAINER LAUNCH DISABLED");
        set_label(G.play_subtitle,"PC2 test build: legacy trainer and Play Normally actions are blocked. Use the separate Steam game-only opt-in button.");
        if(G.overview_launch_hint)set_label(G.overview_launch_hint,
            pc2_steam_launch_allowed()?
            "PC2 SOURCE TEST • Trainer/manager buttons disabled. For a standard Steam game, use the separate Steam game-only opt-in button and confirm Yes.":
            "PC2 SOURCE TEST • Trainer/manager buttons disabled. Restart with --enable-steam-game-launch to test a game-only Steam handoff.");
        if(G.right_proton)set_label(G.right_proton,"Proton health: not verified in PC2\nNo repair indicated by missing optional metadata.");
    }
    if(G.native_profile_status){
        if(!g)set_label(G.native_profile_status,"Select a game first.");
        else if(!game_is_steam(g))set_label(G.native_profile_status,"Native converted-table profiles are currently available for selected Steam titles only.");
        else if(has_native)set_label(G.native_profile_status,"Enabled: Resonance v1.1 native profile. God Mode, Invisible, Resonance Points, FOV and Console run without Cheat Engine.");
        else if(native_available)set_label(G.native_profile_status,"Native profile available for this game. Enable it to run the converted Resonance table features without Cheat Engine.");
        else set_label(G.native_profile_status,"No built-in native table profile is available for this game yet.");
    }
    if(G.trainer_library_quick_summary&&!G.trainer_library_pick_path[0]){
        char qs[2048];
        const char *base=has_local_mapping?strrchr(lt,'/'):NULL;
        base=base?base+1:(has_local_mapping?lt:"Not assigned");
        if(g)snprintf(qs,sizeof qs,"%s\nTrainer: %s\nStatus: %s\nSelect a trainer row for version and compatibility details.",
            g->name,base,has_local?"Ready":(has_local_mapping?"File missing":"No assigned trainer"));
        else snprintf(qs,sizeof qs,"Select a game and trainer row to view its version, health and compatibility.");
        set_label(G.trainer_library_quick_summary,qs);
    }
    if(G.local_trainer_entry)gtk_entry_set_text((GtkEntry*)G.local_trainer_entry,has_local_mapping?lt:"");
    if(G.local_trainer_status){if(g&&game_is_lutris(g)){snprintf(b,sizeof b,"Lutris Test 4: %s • prefix %s • Runtime %s. Resolved entries can launch now; assigned/custom local trainers require verified same-session ownership and fail closed if it cannot be proven.",g->resolution_label[0]?g->resolution_label:"resolution pending",g->prefix[0]?g->prefix:"not resolved",g->wine_name[0]?g->wine_name:(g->wine_bin[0]?g->wine_bin:"not resolved"));set_label(G.local_trainer_status,b);}else if(managed_state==1){snprintf(b,sizeof b,"Managed Heroic session active: game PID %ld%s. Running state comes from the actual process, not Heroic’s PLAY/PLAYING badge.",managed_game_pid,managed_trainer_pid?" • trainer active":"");set_label(G.local_trainer_status,b);}else if(managed_state==2){snprintf(b,sizeof b,"Game process has exited; trainer PID %ld is still active. Close it normally or use Stop Stuck Trainer.",managed_trainer_pid);set_label(G.local_trainer_status,b);}else if(has_local){snprintf(b,sizeof b,"Local trainer configured for %s.%s",g->name,has_native?" Native profile currently takes priority for PLAY.":(use_ct?" Cheat Table currently takes priority for PLAY.":" PLAY uses this trainer."));set_label(G.local_trainer_status,b);}else if(has_local_mapping){snprintf(b,sizeof b,"Trainer mapping exists for %s, but the EXE is missing: %s. Use Trainer Library rescan to recover it or clear the stale mapping.",g->name,lt);set_label(G.local_trainer_status,b);}else set_label(G.local_trainer_status,g?"No local trainer configured for this game.":"Select a game first.");}
    if(G.cheat_engine_entry)gtk_entry_set_text((GtkEntry*)G.cheat_engine_entry,has_ce?ce:"");
    if(G.cheat_engine_installer_entry)gtk_entry_set_text((GtkEntry*)G.cheat_engine_installer_entry,has_ce_installer?ce_installer:"");
    if(G.cheat_table_entry)gtk_entry_set_text((GtkEntry*)G.cheat_table_entry,has_ct?ct:"");
    if(G.cheat_table_status){
        if(!g)set_label(G.cheat_table_status,"Select a game first.");
        else if(game_is_lutris(g))set_label(G.cheat_table_status,"Lutris Test 4 enables game launch plus assigned/custom local-trainer same-session handoff. Cheat Engine .CT integration remains intentionally disabled in this test.");
        else if(has_native)set_label(G.cheat_table_status,"Native profile is taking priority. Cheat Engine is not required for the converted Resonance v1.1 features.");
        else if(use_ct&&has_managed_ce&&has_windows_ce){snprintf(b,sizeof b,"Selected game: %s (%s). Managed Linux CE + Windows CE companion + table are ready. PLAY WITH CHEAT TABLE will join the verified live %s prefix directly and auto-attach the gameplay process.",g->name,game_is_steam(g)?g->appid:g->runner,game_is_steam(g)?"Steam":"Heroic");set_label(G.cheat_table_status,b);}
        else if(use_ct&&has_managed_ce){snprintf(b,sizeof b,"Selected game: %s. Managed Linux CE + table are ready, but the Windows CE companion is still missing. Install the selected Windows CE package once, then Detect / Refresh CE.",g->name);set_label(G.cheat_table_status,b);}
        else if(use_ct){snprintf(b,sizeof b,"External Cheat Engine + table ready for %s. PLAY uses this provider first.",g->name);set_label(G.cheat_table_status,b);}
        else if(has_ct&&!has_ce)set_label(G.cheat_table_status,"Table configured. Install the official native Linux Cheat Engine 7.7.1 package, or choose an existing CE executable.");
        else if(!has_ct&&has_managed_ce){snprintf(b,sizeof b,"Managed Cheat Engine detected. Choose a .CT table for %s.",g->name);set_label(G.cheat_table_status,b);}
        else if(!has_ct&&has_ce){snprintf(b,sizeof b,"Cheat Engine configured. Choose a .CT table for %s.",g->name);set_label(G.cheat_table_status,b);}
        else set_label(G.cheat_table_status,has_ce_installer?"Official Cheat Engine package saved. Install it, then choose a .CT table.":"Use Download + Install Linux CE for the official native 7.7.1 build, then choose a .CT table. Cheat Engine is not redistributed inside GameWeld.");
    }
    if(G.trainer_library_selected){
        if(g){const char*base=strrchr(lt,'/');base=base?base+1:lt;
            if(has_local)snprintf(b,sizeof b,"Game: %s\nAssigned trainer: %s\nHealth: Valid",g->name,base);
            else if(has_local_mapping)snprintf(b,sizeof b,"Game: %s\nAssigned trainer: %s\nHealth: Missing",g->name,base);
            else snprintf(b,sizeof b,"Game: %s\nAssigned trainer: none",g->name);
            set_label(G.trainer_library_selected,b);}
        else set_label(G.trainer_library_selected,"Select a game in Library to assign or clear its trainer.");
    }
    update_trainer_library_actions();
    /* Also cover game selection from the main Library and launcher navigation. */
    trainer_update_context_refresh();
    if(G.setup_status)set_label(G.setup_status,G.wand_healthy?"✓ Steam compatibility ready":"Steam compatibility setup required");
    if(G.setup_detail){snprintf(b,sizeof b,"%s\nBase Proton: %s\nGameWeld tool: %s",G.verify_message[0]?G.verify_message:"Not checked",G.base_proton[0]?G.base_proton:"Not detected",G.wand_tool[0]?G.wand_tool:"Not installed");set_label(G.setup_detail,b);}
}

static void spawn_lutris_normal(const Game*g){
    if(!lutris_session_ready(g)){log_line("Lutris launch blocked for %s: Test 4 requires a fully resolved prefix, target and configured runtime.",g&&g->name[0]?g->name:"the selected game");return;}
    pid_t p=fork();if(p==0){clear_desktop_activation_env();execl(lutris_session_tool(),lutris_session_tool(),"launch",g->appid,g->name,g->launch_uri,g->prefix,g->wine_type,g->wine_bin,g->compat_tool_path,g->executable,g->install_dir,"",g->wine_name,(char*)NULL);_exit(127);}
}
static void spawn_lutris_trainer(const Game*g,const char*trainer){
    if(!lutris_session_ready(g)){log_line("Lutris trainer handoff blocked for %s: Test 4 requires a fully resolved prefix, target and configured runtime.",g&&g->name[0]?g->name:"the selected game");return;}
    if(!trainer||!readable_file(trainer)){log_line("Lutris trainer handoff blocked for %s: assigned trainer is not readable.",g->name);return;}
    pid_t p=fork();if(p==0){clear_desktop_activation_env();execl(lutris_session_tool(),lutris_session_tool(),"trainer",g->appid,g->name,g->launch_uri,g->prefix,g->wine_type,g->wine_bin,g->compat_tool_path,g->executable,g->install_dir,trainer,g->wine_name,(char*)NULL);_exit(127);}
}
static void spawn_heroic_normal(const Game*g){pid_t p=fork();if(p==0){execl(heroic_launch_tool(),heroic_launch_tool(),g->runner,g->appid,(char*)NULL);_exit(127);}}
static void spawn_heroic_table(const Game*g,const char*ce,const char*table){pid_t p=fork();if(p==0){execl(heroic_cheat_table_tool(),heroic_cheat_table_tool(),g->runner,g->appid,g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,ce,table,(char*)NULL);_exit(127);}}
static void spawn_heroic_trainer(const Game*g,const char*trainer){
    TrainerLaunchPolicy pol;int have=trainer_launch_policy(trainer,&pol);int apply_managed=0,auto_elevate=0;
    if(have&&!strcmp(pol.action,"heroic-fling-managed")){
        int manual=trainer_launch_policy_is_manual(&pol);
        if(!trainer_profile_has_compat_override()&&(manual||trainer_profile_auto_enabled())){
            apply_managed=1;auto_elevate=!trainer_profile_has_elevation_override();
            if(manual)log_line("Applying per-trainer launch policy for %s: Force Managed FLiNG -> Heroic GE-Proton10-34 + Wine-Wayland%s.",g->name,auto_elevate?" + Windows-token elevation":"; elevation kept at explicit user setting");
            else log_line("Auto-applying trainer profile for %s: %s (%s) -> Heroic GE-Proton10-34 + Wine-Wayland%s.",g->name,pol.profile,pol.confidence,auto_elevate?" + Windows-token elevation":"; elevation kept at explicit user setting");
        }
        else if(!manual&&!trainer_profile_auto_enabled())log_line("Trainer profile detected for %s: %s (%s), but automatic profile application is disabled by GAMEWELD_AUTO_TRAINER_PROFILE.",g->name,pol.profile,pol.confidence);
        else log_line("Trainer launch policy for %s requested managed FLiNG, but an explicit GAMEWELD_* compatibility override remains authoritative.",g->name);
    }else if(have&&trainer_launch_policy_is_manual(&pol)&&!strcmp(pol.action,"inherit")){
        log_line("Applying per-trainer launch policy for %s: Force Inherit Session. Automatic compatibility switching is disabled for this trainer.",g->name);
    }
    pid_t p=fork();if(p==0){
        if(have){setenv("GAMEWELD_DETECTED_TRAINER_PROFILE",pol.profile,1);setenv("GAMEWELD_DETECTED_TRAINER_CONFIDENCE",pol.confidence,1);}
        if(apply_managed){setenv("GAMEWELD_LOCAL_TRAINER_COMPAT_SESSION","force",1);if(auto_elevate)setenv("GAMEWELD_TRAINER_ELEVATION","admin",1);}
        execl(heroic_local_trainer_tool(),heroic_local_trainer_tool(),g->runner,g->appid,g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,trainer,g->heroic_root,(char*)NULL);_exit(127);
    }
}
static void spawn_heroic_session_control(const Game*g,const char*action,const char*trainer){pid_t p=fork();if(p==0){execl(heroic_session_control_tool(),heroic_session_control_tool(),action,g->runner,g->appid,g->name,g->prefix,g->wine_type,g->wine_bin,trainer?trainer:"",g->install_dir,(char*)NULL);_exit(127);}}
static void heroic_runtime_sidecar_path(const char *runner,const char *appid,const char *suffix,char *out,size_t cap){
    char rr[128],aa[256];state_safe_id(runner,rr,sizeof rr);state_safe_id(appid,aa,sizeof aa);
    const char*x=getenv("XDG_STATE_HOME"),*h=getenv("HOME");
    if(x&&*x)snprintf(out,cap,"%s/gameweld/heroic-trainer-runtime-%s-%s.%s",x,rr,aa,suffix);
    else snprintf(out,cap,"%s/.local/state/gameweld/heroic-trainer-runtime-%s-%s.%s",h?h:".",rr,aa,suffix);
}
static int read_small_text(const char *path,char *out,size_t cap){
    if(!out||cap<2)return 0;out[0]=0;FILE*f=fopen(path,"r");if(!f)return 0;size_t n=fread(out,1,cap-1,f);out[n]=0;fclose(f);return n>0;
}
static void kv_value(const char *text,const char *key,char *out,size_t cap){
    if(!out||!cap)return;out[0]=0;if(!text||!key)return;char pat[128];snprintf(pat,sizeof pat,"%s=",key);const char*p=text;
    while((p=strstr(p,pat))){if(p==text||p[-1]=='\n'){p+=strlen(pat);size_t n=strcspn(p,"\r\n");if(n>=cap)n=cap-1;memcpy(out,p,n);out[n]=0;return;}p+=strlen(pat);} }
static void heroic_runtime_result_text(const char *runner,const char *appid,char *out,size_t cap){
    char path[2048],txt[8192],state[64],summary[1024],wi[64],d48[64],d8[64];
    heroic_runtime_sidecar_path(runner,appid,"result",path,sizeof path);out[0]=0;
    if(!read_small_text(path,txt,sizeof txt))return;
    kv_value(txt,"state",state,sizeof state);kv_value(txt,"summary",summary,sizeof summary);kv_value(txt,"wininet",wi,sizeof wi);kv_value(txt,"dotnet48",d48,sizeof d48);kv_value(txt,"dotnet8",d8,sizeof d8);
    if((!strcmp(state,"ready")||!strcmp(state,"missing"))&&(wi[0]||d48[0]||d8[0])){
        snprintf(out,cap,"%s  wininet: %s • .NET 4.8: %s • .NET 8: %s",summary[0]?summary:(state[0]?state:"Runtime check complete."),wi[0]?wi:"unknown",d48[0]?d48:"unknown",d8[0]?d8:"unknown");
    }else snprintf(out,cap,"%s",summary[0]?summary:(state[0]?state:"Runtime operation complete."));
}
static gboolean heroic_runtime_progress_tick(void *unused){
    (void)unused;if(!heroic_runtime_progress_active)return FALSE;
    if(G.selected<0||G.selected>=G.game_count)return TRUE;Game*g=&G.games[G.selected];
    if(strcmp(game_key(g),heroic_runtime_progress_key))return TRUE;
    char path[2048],progress[512]={0};heroic_runtime_sidecar_path(heroic_runtime_progress_runner,heroic_runtime_progress_appid,"progress",path,sizeof path);
    if(read_small_text(path,progress,sizeof progress)){progress[strcspn(progress,"\r\n")]=0;char msg[768];snprintf(msg,sizeof msg,"Trainer compatibility operation... %s",progress);if(G.local_trainer_status)set_label(G.local_trainer_status,msg);}
    return TRUE;
}
static gboolean heroic_runtime_job_done(void *vp){
    HeroicRuntimeJob*j=vp;char msg[1800]={0};heroic_runtime_result_text(j->runner,j->appid,msg,sizeof msg);
    if(!msg[0])snprintf(msg,sizeof msg,"FLiNG runtime %s finished with status %d. See the trainer-runtime log for details.",j->action,j->exit_code);
    log_line("FLiNG runtime %s for %s: %s",j->action,j->title,msg);
    if(!strcmp(j->action,"repair")||!strcmp(j->action,"download-helper")||!strcmp(j->action,"cancel"))heroic_runtime_progress_active=0;
    if(G.selected>=0&&G.selected<G.game_count&&!strcmp(game_key(&G.games[G.selected]),j->game_key)&&G.local_trainer_status)set_label(G.local_trainer_status,msg);
    free(j);return FALSE;
}
static void *heroic_runtime_worker(void *vp){
    HeroicRuntimeJob*j=vp;pid_t p=fork();
    if(p==0){execl(heroic_trainer_runtime_tool(),heroic_trainer_runtime_tool(),j->action,j->runner,j->appid,j->title,j->prefix,j->wine_type,j->wine_bin,j->trainer,(char*)NULL);_exit(127);}
    if(p<0)j->exit_code=127;else{int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(WIFEXITED(st))j->exit_code=WEXITSTATUS(st);else if(WIFSIGNALED(st))j->exit_code=128+WTERMSIG(st);else j->exit_code=1;}
    g_idle_add(heroic_runtime_job_done,j);return NULL;
}
static void start_heroic_runtime_job(const Game*g,const char*action,const char*trainer){
    HeroicRuntimeJob*j=calloc(1,sizeof *j);snprintf(j->action,sizeof j->action,"%s",action?action:"");snprintf(j->runner,sizeof j->runner,"%s",g->runner);snprintf(j->appid,sizeof j->appid,"%s",g->appid);snprintf(j->title,sizeof j->title,"%s",g->name);snprintf(j->prefix,sizeof j->prefix,"%s",g->prefix);snprintf(j->wine_type,sizeof j->wine_type,"%s",g->wine_type);snprintf(j->wine_bin,sizeof j->wine_bin,"%s",g->wine_bin);snprintf(j->trainer,sizeof j->trainer,"%s",trainer?trainer:"");snprintf(j->game_key,sizeof j->game_key,"%s",game_key(g));
    if(!strcmp(action,"repair")||!strcmp(action,"download-helper")){heroic_runtime_progress_active=1;snprintf(heroic_runtime_progress_runner,sizeof heroic_runtime_progress_runner,"%s",g->runner);snprintf(heroic_runtime_progress_appid,sizeof heroic_runtime_progress_appid,"%s",g->appid);snprintf(heroic_runtime_progress_key,sizeof heroic_runtime_progress_key,"%s",game_key(g));g_timeout_add(500,heroic_runtime_progress_tick,NULL);}
    pthread_t t;if(pthread_create(&t,NULL,heroic_runtime_worker,j)==0)pthread_detach(t);else{log_line("Could not start FLiNG runtime worker.");free(j);heroic_runtime_progress_active=0;}
}
static void heroic_wemod_sidecar_path(const char *runner,const char *appid,const char *suffix,char *out,size_t cap){
    char rr[128],aa[256];state_safe_id(runner,rr,sizeof rr);state_safe_id(appid,aa,sizeof aa);const char*x=getenv("XDG_STATE_HOME"),*h=getenv("HOME");
    if(x&&*x)snprintf(out,cap,"%s/gameweld/heroic-wemod-%s-%s.%s",x,rr,aa,suffix);else snprintf(out,cap,"%s/.local/state/gameweld/heroic-wemod-%s-%s.%s",h?h:".",rr,aa,suffix);
}
static gboolean heroic_wemod_job_done(void *vp){
    HeroicWeModJob*j=vp;char path[2048],txt[8192]={0},state[128]={0},summary[1400]={0};heroic_wemod_sidecar_path(j->runner,j->appid,"result",path,sizeof path);
    if(read_small_text(path,txt,sizeof txt)){kv_value(txt,"state",state,sizeof state);kv_value(txt,"summary",summary,sizeof summary);}
    if(summary[0])log_line("Heroic WeMod for %s: %s%s%s%s",j->title,summary,state[0]?" [":"",state[0]?state:"",state[0]?"]":"");
    else log_line("Heroic WeMod for %s %s (status %d). Diagnostics: %s",j->title,j->exit_code==0?"completed its launch handoff":"failed",j->exit_code,path);
    universal_wemod_job_active=0;refresh_ui();free(j);return FALSE;
}
static void *heroic_wemod_worker(void *vp){
    HeroicWeModJob*j=vp;pid_t p=fork();if(p==0){execl(heroic_wemod_tool(),heroic_wemod_tool(),j->runner,j->appid,j->title,j->install,j->executable,j->prefix,j->wine_type,j->wine_bin,j->heroic_root,(char*)NULL);_exit(127);}
    if(p<0)j->exit_code=127;else{int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}if(WIFEXITED(st))j->exit_code=WEXITSTATUS(st);else if(WIFSIGNALED(st))j->exit_code=128+WTERMSIG(st);else j->exit_code=1;}g_idle_add(heroic_wemod_job_done,j);return NULL;
}
static void start_heroic_wemod_job(const Game*g){
    if(universal_wemod_job_active){log_line("Universal launch: a WeMod provider launch is already being prepared. Wait for it to finish before starting another provider action.");return;}
    HeroicWeModJob*j=calloc(1,sizeof *j);snprintf(j->runner,sizeof j->runner,"%s",g->runner);snprintf(j->appid,sizeof j->appid,"%s",g->appid);snprintf(j->title,sizeof j->title,"%s",g->name);snprintf(j->install,sizeof j->install,"%s",g->install_dir);snprintf(j->executable,sizeof j->executable,"%s",g->executable);snprintf(j->prefix,sizeof j->prefix,"%s",g->prefix);snprintf(j->wine_type,sizeof j->wine_type,"%s",g->wine_type);snprintf(j->wine_bin,sizeof j->wine_bin,"%s",g->wine_bin);snprintf(j->heroic_root,sizeof j->heroic_root,"%s",g->heroic_root);
    universal_wemod_job_active=1;log_line("Universal launch: preparing one Proton session for %s + WeMod/Wand so both Windows processes share the exact same compatibility context.",g->name);pthread_t t;if(pthread_create(&t,NULL,heroic_wemod_worker,j)==0)pthread_detach(t);else{universal_wemod_job_active=0;free(j);log_line("Could not start Heroic WeMod worker.");}
}
static void on_play(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}char lt[2048]={0},ct[2048]={0},ce[2048]={0},np[128]={0};Game*g=&G.games[G.selected];if(game_is_lutris(g)){if(!lutris_session_ready(g)){log_line("Lutris launch blocked for %s: prefix, Windows target or configured runtime is not fully resolved. Refresh Game Sources after fixing Lutris configuration.",g->name);return;}const char*k=game_key(g);if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through Lutris, then handing the assigned trainer into the verified live same-prefix session: %s",g->name,lt);spawn_lutris_trainer(g,lt);}else{log_line("No local trainer is assigned to %s; launching normally through Lutris with Test 4 session ownership validation.",g->name);spawn_lutris_normal(g);}return;}if(game_is_steam_shortcut(g)){if(!g->shortcut_launch_supported){log_line("Steam non-Steam shortcut %s cannot use trainer handoff because its Steam Play runtime/prefix is unresolved. Launch it once from Steam with compatibility enabled, then Refresh Game Sources.",g->name);return;}const char*k=game_key(g);if(load_cheat_table(k,ct,sizeof ct)&&readable_file(ct)){if(detect_managed_windows_ce(game_ce_id(g),ce,sizeof ce)&&windows_pe_executable(ce)){log_line("Launching %s through its validated live Steam shortcut session + Cheat Engine table: %s",g->name,ct);spawn_steam_shortcut_table(g,ce,ct);return;}char custom_ce[2048]={0};if(load_cheat_engine(custom_ce,sizeof custom_ce)&&windows_pe_executable(custom_ce)){log_line("Launching %s through its validated live Steam shortcut session + external Windows Cheat Engine table: %s",g->name,ct);spawn_steam_shortcut_table(g,custom_ce,ct);return;}log_line("A .CT table is assigned to %s, but the Windows Cheat Engine companion is not ready. Open Settings → Managed Cheat Engine Provider (.CT), install/detect Windows CE once, then retry.",g->name);return;}if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through its validated live Steam non-Steam shortcut Proton session + local trainer: %s",g->name,lt);spawn_steam_shortcut_trainer(g,lt);return;}log_line("No local trainer or Cheat Engine table is assigned to %s; launching the Steam non-Steam shortcut normally through rungameid %s.",g->name,g->launch_id);spawn_steam_shortcut_normal(g);return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Game launch is blocked until it finishes or you press Cancel Runtime Repair in Settings.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Trainer runtime repair is still active. Wait for completion or cancel it before launching the game.");return;}const char*k=game_key(g);const char*native_available=game_is_steam(g)?available_native_profile(g->appid):NULL;if(native_available&&load_native_profile(k,np,sizeof np)&&!strcmp(np,native_available)){log_line("Launching %s through Steam + native trainer profile: %s",g->name,np);spawn_native_profile(g->appid,np);return;}if(load_cheat_table(k,ct,sizeof ct)&&readable_file(ct)){if((load_cheat_engine(ce,sizeof ce)&&readable_file(ce))||detect_managed_cheat_engine(game_ce_id(g),ce,sizeof ce)){log_line("Launching %s through %s + Cheat Engine table: %s",g->name,game_is_steam(g)?"Steam":"Heroic",ct);if(game_is_steam(g))spawn_cheat_table(g->appid,ce,ct);else spawn_heroic_table(g,ce,ct);return;}}if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through %s + local trainer: %s",g->name,game_is_steam(g)?"Steam":"Heroic",lt);if(game_is_steam(g))spawn_local_trainer(g->appid,lt);else spawn_heroic_trainer(g,lt);return;}if(game_is_steam(g))start_job(JOB_PLAY,g->appid,"Preparing game and launching with the Steam compatibility provider…");else{log_line("No trainer/table configured for %s; launching normally through Heroic.",g->name);spawn_heroic_normal(g);}}
static void on_play_normal(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(game_is_lutris(g)){if(!lutris_session_ready(g)){log_line("Normal Lutris launch blocked for %s: Test 4 requires a fully resolved prefix, target and runtime.",g->name);return;}spawn_lutris_normal(g);log_line("Launching %s normally through Lutris; GameWeld will validate the exact live prefix/runtime session without starting a trainer.",g->name);return;}if(game_is_steam_shortcut(g)){if(!g->launch_uri[0]){log_line("Steam non-Steam shortcut %s has no rungameid launch URI.",g->name);return;}spawn_steam_shortcut_normal(g);log_line("Launching Steam non-Steam shortcut %s normally through rungameid %s…",g->name,g->launch_id);return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Normal Heroic launch is blocked until repair completes or is cancelled.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"FLiNG runtime repair is active; normal Heroic launch is temporarily blocked to protect the prefix.");return;}if(game_is_steam(g)){spawn_detached("steam","-applaunch",g->appid);log_line("Launching normally through Steam…");}else{spawn_heroic_normal(g);log_line("Launching normally through Heroic (%s)…",g->runner);}}


/* Test 9 universal launch surface -------------------------------------------------
 * The UI exposes provider choices in one place while reusing the already-validated
 * provider/session helpers.  Manager applications are still never assigned to a
 * game.  When a manager is requested before a compatible live session exists,
 * GameWeld starts the game normally and waits for the exact live session before
 * attaching the manager. */
static char universal_pending_manager_path[2048];
static int universal_pending_game=-1;
static int universal_pending_ticks=0;
static int universal_pending_ready_ticks=0;

static void universal_pending_reset(void){
    universal_pending_game=-1;
    universal_pending_manager_path[0]=0;
    universal_pending_ticks=0;
    universal_pending_ready_ticks=0;
}

static int universal_manager_settle_ticks(void){
    const char*e=getenv("GAMEWELD_MANAGER_ATTACH_SETTLE_SECONDS");
    if(e&&*e){char*end=NULL;long v=strtol(e,&end,10);if(end&&!*end&&v>=0&&v<=30)return (int)v;}
    return 5;
}

static int find_manager_path_by_id(const char *wanted,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!wanted||!*wanted)return 0;
    int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"rows","--sort","status",(char*)NULL);_exit(127);}
    close(fd[1]);FILE*f=fdopen(fd[0],"r");char line[8192];int found=0;
    if(f){while(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;char copy[8192];snprintf(copy,sizeof copy,"%s",line);char*save=NULL;char*tok=strtok_r(copy,"\t",&save);if(!tok||strcmp(tok,"ROW"))continue;char*state=strtok_r(NULL,"\t",&save);if(!state||strcmp(state,"MANAGER"))continue;char*key=strtok_r(NULL,"\t",&save);char*game=strtok_r(NULL,"\t",&save);char*score=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);char*path=strtok_r(NULL,"\t",&save);(void)key;(void)game;(void)score;(void)reason;if(!path||!*path||!readable_file(path))continue;TrainerManagerPlan mp={0};if(trainer_manager_plan_for_path(path,&mp)&&!strcmp(mp.id,wanted)){snprintf(out,cap,"%s",path);found=1;break;}}fclose(f);}else close(fd[0]);
    int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}return found;
}

static gboolean universal_manager_refresh_once(void*d){(void)d;refresh_ui();refresh_trainer_library_view();return FALSE;}
static void stop_manager_path_for_game(const char*path,Game*g){
    if(!path||!*path||!readable_file(path)||!g){log_line("Universal launch: trainer manager executable is unavailable for close.");return;}
    TrainerManagerGamePlan gp={0};if(!trainer_manager_game_plan_for(path,g,&gp)){log_line("Universal launch: manager/game close plan could not be resolved for %s.",g->name);return;}
    if(strcmp(gp.status,"running")){log_line("%s is not currently active for %s.",gp.label[0]?gp.label:"Trainer manager",g->name);return;}
    pid_t p=fork();if(p==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_game_tool(),trainer_manager_game_tool(),"stop",path,g->provider,g->runner,g->appid,game_key(g),g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,g->compatdata,g->launch_id,(char*)NULL);_exit(127);}if(p<0){log_line("Universal launch: could not stop %s for %s.",gp.label,g->name);return;}
    log_line("Closing %s for %s without stopping the game session…",gp.label,g->name);g_timeout_add(1200,universal_manager_refresh_once,NULL);
}

static void launch_manager_path_for_game(const char*path,Game*g){
    if(lutris_test4_extended_blocked(g,"trainer-manager attach"))return;
    if(!path||!*path||!readable_file(path)||!g){log_line("Universal launch: trainer manager executable is unavailable.");return;}
    TrainerManagerGamePlan gp={0};if(!trainer_manager_game_plan_for(path,g,&gp)){log_line("Universal launch: manager/game plan could not be resolved for %s.",g->name);return;}
    if(!strcmp(gp.status,"running")){stop_manager_path_for_game(path,g);return;}
    if(strcmp(gp.status,"ready")){log_line("Universal launch: %s is not ready to attach to %s yet: %s (%s)",gp.label,g->name,gp.reason[0]?gp.reason:"No compatible live session is available.",gp.status);return;}
    pid_t p=fork();if(p==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_game_tool(),trainer_manager_game_tool(),"launch",path,g->provider,g->runner,g->appid,game_key(g),g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,g->compatdata,g->launch_id,(char*)NULL);_exit(127);}if(p<0){log_line("Universal launch: could not start %s for %s.",gp.label,g->name);return;}
    log_line("Universal launch started %s for %s; waiting for the real manager UI process. %s runtime %s • prefix %s • diagnostics %s",gp.label,g->name,gp.session_kind,gp.runtime,gp.prefix,gp.log);
}

static void ensure_manager_path_for_game(const char*path,Game*g){
    if(lutris_test4_extended_blocked(g,"trainer-manager attach"))return;
    if(!path||!*path||!readable_file(path)||!g){log_line("One-click profile: trainer manager executable is unavailable.");return;}
    TrainerManagerGamePlan gp={0};if(!trainer_manager_game_plan_for(path,g,&gp)){log_line("One-click profile: manager/game plan could not be resolved for %s.",g->name);return;}
    if(!strcmp(gp.status,"running")){log_line("One-click profile: %s is already active for %s; leaving the running manager and game session untouched.",gp.label,g->name);refresh_ui();return;}
    if(strcmp(gp.status,"ready")){log_line("One-click profile: %s is not ready to attach to %s yet: %s (%s)",gp.label,g->name,gp.reason[0]?gp.reason:"No compatible live session is available.",gp.status);return;}
    pid_t p=fork();if(p==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_game_tool(),trainer_manager_game_tool(),"launch",path,g->provider,g->runner,g->appid,game_key(g),g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,g->compatdata,g->launch_id,(char*)NULL);_exit(127);}if(p<0){log_line("One-click profile: could not start %s for %s.",gp.label,g->name);return;}
    log_line("One-click profile started %s for %s; waiting for the real manager UI process. %s runtime %s • prefix %s • diagnostics %s",gp.label,g->name,gp.session_kind,gp.runtime,gp.prefix,gp.log);
}

static int steam_shortcut_has_proton_launcher_service(const Game*g){
    if(!g||!g->launch_options[0])return 0;
    char low[sizeof g->launch_options];size_t i=0;for(;g->launch_options[i]&&i+1<sizeof low;i++)low[i]=(char)tolower((unsigned char)g->launch_options[i]);low[i]=0;
    return strstr(low,"steam_compat_launcher_service=proton")!=NULL;
}
static int launch_steam_shortcut_restart_free(Game*g,const char*context){
    if(!g||!game_is_steam_shortcut(g)||!g->shortcut_launch_supported||!g->compatdata[0]||!g->compat_tool_path[0]||!g->executable[0])return 0;
    int fd[2];if(pipe(fd)!=0){log_line("%s: could not start restart-free Steam runtime launch for %s.",context?context:"Universal launch",g->name);return 0;}
    pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);log_line("%s: could not fork restart-free Steam runtime launch for %s.",context?context:"Universal launch",g->name);return 0;}
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);clear_desktop_activation_env();execl(steam_shortcut_live_launch_tool(),steam_shortcut_live_launch_tool(),g->appid,g->launch_id,g->compatdata,g->compat_tool_path,g->executable,g->install_dir,g->steam_root,g->launch_options,(char*)NULL);_exit(127);}
    close(fd[1]);char buf[8192];size_t used=0;ssize_t n;while(used+1<sizeof buf&&(n=read(fd[0],buf+used,sizeof buf-used-1))>0)used+=(size_t)n;close(fd[0]);int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){}buf[used]=0;
    char *line=strstr(buf,"STATUS\t");if(!line)line=buf;char code[96]={0},msg[4096]={0},detail[2048]={0};if(sscanf(line,"STATUS\t%95[^\t]\t%4095[^\t\n]\t%2047[^\n]",code,msg,detail)<1){snprintf(code,sizeof code,"error");snprintf(msg,sizeof msg,"%.*s",(int)sizeof(msg)-1,buf);}
    int ok=WIFEXITED(st)&&WEXITSTATUS(st)==0&&!strcmp(code,"started");
    if(ok){log_line("%s: restart-free Steam shortcut session started for %s. Steam stayed running; no shortcut database mutation or client restart was used.%s%s",context?context:"Universal launch",g->name,detail[0]?" Log: ":"",detail[0]?detail:"");return 1;}
    log_line("%s: restart-free Steam shortcut session failed for %s (%s). %s",context?context:"Universal launch",g->name,code[0]?code:"unknown",msg);
    return 0;
}

static int universal_start_game_for_manager(Game*g,const char*id,const char*context){
    if(!g||!id||!*id)return 0;
    if(lutris_test4_extended_blocked(g,"trainer-manager launch"))return 0;
    if(game_is_steam_shortcut(g)&&!strcmp(id,"cheat-evolution")){
        if(steam_shortcut_has_proton_launcher_service(g)){
            log_line("%s: %s already carries the Proton launcher-service option; using Steam rungameid without restarting Steam.",context?context:"Universal launch",g->name);
            on_play_normal(NULL,NULL);
            return 1;
        }
        if(!launch_steam_shortcut_restart_free(g,context))return 0;
        log_line("%s: restart-free live attach path armed for %s. Steam remains open, shortcuts.vdf is untouched, and Cheat Evolution will attach only after GameWeld validates the exact Windows session.",context?context:"Universal launch",g->name);
        return 1;
    }
    on_play_normal(NULL,NULL);
    return 1;
}

static gboolean universal_pending_manager_tick(void*d){
    (void)d;
    if(universal_pending_game<0||universal_pending_game>=G.game_count||!universal_pending_manager_path[0]){universal_pending_reset();return FALSE;}
    Game*g=&G.games[universal_pending_game];TrainerManagerGamePlan gp={0};int ok=trainer_manager_game_plan_for(universal_pending_manager_path,g,&gp);
    if(ok&&!strcmp(gp.status,"running")){
        ensure_manager_path_for_game(universal_pending_manager_path,g);
        universal_pending_reset();
        return FALSE;
    }
    if(ok&&!strcmp(gp.status,"ready")){
        int settle=universal_manager_settle_ticks();
        universal_pending_ready_ticks++;
        if(universal_pending_ready_ticks==1){
            if(settle>0)log_line("Universal launch: exact live Windows session validated for %s. Holding %d second%s for window/runtime settle before trainer-manager attach…",g->name,settle,settle==1?"":"s");
            else log_line("Universal launch: exact live Windows session validated for %s; attaching trainer manager now.",g->name);
        }
        if(universal_pending_ready_ticks<settle)return TRUE;
        ensure_manager_path_for_game(universal_pending_manager_path,g);
        universal_pending_reset();
        return FALSE;
    }
    universal_pending_ready_ticks=0;
    universal_pending_ticks++;
    if(universal_pending_ticks==15)log_line("Universal launch: still waiting for the exact %s Windows process/session. Steam remains running; no unrelated Steam title will be used as a fallback.",g->name);
    if(universal_pending_ticks>=180){
        log_line("Universal launch timed out waiting for %s to expose its exact Windows process and compatible live session. Steam was not restarted and no alternate Steam game was accepted; retry once the selected game reaches its menu.",g->name);
        universal_pending_reset();
        return FALSE;
    }
    return TRUE;
}

static void universal_launch_manager(const char*id,const char*labelv){
    if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}
    if(universal_wemod_job_active){log_line("Universal launch: WeMod provider preparation is still active. Wait for it to finish before attaching another manager.");return;}
    char path[2048]={0};if(!find_manager_path_by_id(id,path,sizeof path)){log_line("%s was not found in Trainer Library. Run Scan all trainers after extracting/installing the manager.",labelv);return;}
    Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"trainer-manager launch"))return;TrainerManagerGamePlan gp={0};if(trainer_manager_game_plan_for(path,g,&gp)&&(!strcmp(gp.status,"ready")||!strcmp(gp.status,"running"))){launch_manager_path_for_game(path,g);return;}
    if(universal_pending_manager_path[0]){log_line("Another universal manager launch is already waiting for a game session.");return;}
    snprintf(universal_pending_manager_path,sizeof universal_pending_manager_path,"%s",path);universal_pending_game=G.selected;universal_pending_ticks=0;universal_pending_ready_ticks=0;
    log_line("Universal launch: starting %s first. %s will attach only after GameWeld validates that exact Windows game session and completes the readiness settle period.",g->name,labelv);
    if(!universal_start_game_for_manager(g,id,"Universal launch")){universal_pending_reset();return;}
    g_timeout_add(1000,universal_pending_manager_tick,NULL);
}

static void universal_ensure_manager(const char*id,const char*labelv){
    if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}
    if(universal_wemod_job_active){log_line("One-click profile: WeMod provider preparation is still active. Wait for it to finish before attaching another manager.");return;}
    char path[2048]={0};if(!find_manager_path_by_id(id,path,sizeof path)){log_line("One-click profile unavailable: %s was not found in Trainer Library. Run Scan all trainers after extracting/installing the manager.",labelv);return;}
    Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"trainer-manager launch"))return;TrainerManagerGamePlan gp={0};if(trainer_manager_game_plan_for(path,g,&gp)){if(!strcmp(gp.status,"running")){log_line("One-click profile: %s is already active for %s; leaving the running manager and game session untouched.",gp.label[0]?gp.label:labelv,g->name);refresh_ui();return;}if(!strcmp(gp.status,"ready")){ensure_manager_path_for_game(path,g);return;}}
    if(universal_pending_manager_path[0]){log_line("Another universal manager launch is already waiting for a game session.");return;}
    snprintf(universal_pending_manager_path,sizeof universal_pending_manager_path,"%s",path);universal_pending_game=G.selected;universal_pending_ticks=0;universal_pending_ready_ticks=0;
    log_line("One-click profile: starting %s first. %s will attach only to that exact Windows session after the readiness settle period.",g->name,labelv);
    if(!universal_start_game_for_manager(g,id,"One-click profile")){universal_pending_reset();return;}
    g_timeout_add(1000,universal_pending_manager_tick,NULL);
}

static int resolve_windows_ce_for_game(const Game*g,char*out,size_t cap){
    if(out&&cap)out[0]=0;if(!g)return 0;
    if(detect_managed_windows_ce(game_ce_id(g),out,cap)&&windows_pe_executable(out))return 1;
    char custom[2048]={0};if(load_cheat_engine(custom,sizeof custom)&&windows_pe_executable(custom)){snprintf(out,cap,"%s",custom);return 1;}
    return 0;
}
static int choose_table_for_game(Game*g,char*out,size_t cap){
    if(out&&cap)out[0]=0;if(!g)return 0;
    if(load_cheat_table(game_key(g),out,cap)&&readable_file(out))return 1;
    GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Cheat Engine .CT table",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Table",GTK_RESPONSE_ACCEPT,NULL);
    int r=gtk_dialog_run((GtkDialog*)dlg);int ok=0;
    if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){const char*dot=strrchr(fn,'.');if(!dot||strcasecmp(dot,".ct"))log_line("Warning: selected file does not use the .CT extension: %s",fn);if(save_cheat_table(game_key(g),fn)){snprintf(out,cap,"%s",fn);ok=1;log_line("Cheat table configured for %s: %s",g->name,fn);}else log_line("Could not save Cheat Table configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();return ok;
}
static void on_launch_with_cheat_table(GtkButton*b,void*d){
    (void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"Cheat Engine table launch"))return;char table[2048]={0},ce[2048]={0};
    if(!choose_table_for_game(g,table,sizeof table)){log_line("Cheat Engine table launch cancelled for %s.",g->name);return;}
    if(game_is_steam_shortcut(g)){
        if(!g->shortcut_launch_supported){log_line("Cheat Engine table launch blocked for Steam shortcut %s: launch it once from Steam with compatibility enabled, then Refresh Game Sources.",g->name);return;}
        if(!resolve_windows_ce_for_game(g,ce,sizeof ce)){log_line("Cheat Engine table is assigned to %s, but the Windows CE companion is not ready. Open Settings → Managed Cheat Engine Provider (.CT), install/detect Windows CE once, then retry.",g->name);return;}
        spawn_steam_shortcut_table(g,ce,table);return;
    }
    if(game_is_steam(g)){
        if((load_cheat_engine(ce,sizeof ce)&&readable_file(ce))||detect_managed_cheat_engine(game_ce_id(g),ce,sizeof ce)){log_line("Launching %s through Steam + Cheat Engine table: %s",g->name,table);spawn_cheat_table(g->appid,ce,table);return;}
    }else{
        if((load_cheat_engine(ce,sizeof ce)&&readable_file(ce))||detect_managed_cheat_engine(game_ce_id(g),ce,sizeof ce)){log_line("Launching %s through Heroic + Cheat Engine table: %s",g->name,table);spawn_heroic_table(g,ce,table);return;}
    }
    log_line("Cheat Engine table is assigned to %s, but Cheat Engine is not ready. Open Settings → Managed Cheat Engine Provider (.CT), install or choose CE, then retry.",g->name);
}

static void on_launch_with_wemod(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"WeMod launch"))return;if(!game_wemod_supported(g)){if(game_is_steam_shortcut(g))log_line("WeMod is not yet validated for Steam non-Steam shortcuts. Use Assigned Trainer, Aurora, Cheat Evolution, or a custom trainer for this shortcut.");else log_line("WeMod cannot launch for %s because the exact Heroic Wine/Proton runner or prefix is unresolved. Refresh Game Sources after launching the game once through Heroic.",g->name);return;}if(universal_pending_manager_path[0]){log_line("Universal launch: a trainer manager is already waiting for this game session. Let that launch finish before starting WeMod.");return;}if(game_is_steam(g)){pc2_launch_with_steam_bridge(g);return;}start_heroic_wemod_job(g);}
static void on_launch_with_aurora(GtkButton*b,void*d){(void)b;(void)d;universal_launch_manager("cheat-happens-aurora","Cheat Happens Aurora");}
static void on_launch_with_cheat_evolution(GtkButton*b,void*d){(void)b;(void)d;universal_launch_manager("cheat-evolution","Cheat Evolution");}
static void on_launch_custom_trainer(GtkButton*b,void*d){
    (void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Windows trainer EXE",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",-6,"Use Trainer",-3,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==-3){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&readable_file(fn)){Game*g=&G.games[G.selected];if(save_local_trainer(game_key(g),fn)){log_line("Universal launch: assigned custom trainer to %s: %s",g->name,fn);refresh_ui();refresh_trainer_library_view();gtk_widget_destroy(dlg);g_free(fn);on_play(NULL,NULL);return;}log_line("Could not save custom trainer assignment for %s.",g->name);}if(fn)g_free(fn);}gtk_widget_destroy(dlg);
}
static void on_save_launch_profile(GtkButton*b,void*d){
    (void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}const char*mode=G.overview_profile_combo?gtk_combo_box_get_active_id((GtkComboBox*)G.overview_profile_combo):NULL;if(!launch_profile_mode_valid(mode)){log_line("Choose a valid default launch option first.");return;}Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"launch-profile configuration"))return;if(!strcmp(mode,"wemod")&&!game_wemod_supported(g)){log_line("WeMod cannot be saved as the default for %s because its current game source does not expose a validated/resolved compatibility session for WeMod yet.",g->name);return;}if(!strcmp(mode,"cheat-table")){char ctcheck[2048]={0};if(!(load_cheat_table(game_key(g),ctcheck,sizeof ctcheck)&&readable_file(ctcheck))){log_line("Cheat Engine Table cannot be saved as the default for %s until a .CT table is assigned.",g->name);return;}}if(!strcmp(mode,"aurora")||!strcmp(mode,"cheat-evolution")){char path[2048]={0};const char*id=!strcmp(mode,"aurora")?"cheat-happens-aurora":"cheat-evolution";if(!find_manager_path_by_id(id,path,sizeof path)){log_line("%s cannot be saved as the one-click default because that manager is not currently present in Trainer Library.",launch_profile_label(mode));return;}}if(save_launch_profile(game_key(g),mode)){log_line("Saved one-click launch profile for %s: %s",g->name,launch_profile_label(mode));refresh_ui();}else log_line("Could not save the launch profile for %s.",g->name);
}
static void on_reset_launch_profile(GtkButton*b,void*d){
    (void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(delete_launch_profile(game_key(g))){log_line("Reset one-click launch profile for %s. Assigned / detected trainer is the default again.",g->name);if(G.overview_profile_combo)gtk_combo_box_set_active_id((GtkComboBox*)G.overview_profile_combo,"assigned");refresh_ui();}else log_line("Could not reset the launch profile for %s.",g->name);
}
static void on_play_default(GtkButton*b,void*d){
    (void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(game_is_lutris(g)){log_line("One-click Lutris launch for %s uses the Test 4 assigned/local-trainer path; advanced saved profiles remain disabled.",g->name);on_play(NULL,NULL);return;}char mode[64]="assigned";load_launch_profile(game_key(g),mode,sizeof mode);log_line("One-click launch for %s: %s",g->name,launch_profile_label(mode));if(!strcmp(mode,"game-only")){on_play_normal(NULL,NULL);return;}if(!strcmp(mode,"wemod")){on_launch_with_wemod(NULL,NULL);return;}if(!strcmp(mode,"aurora")){universal_ensure_manager("cheat-happens-aurora","Cheat Happens Aurora");return;}if(!strcmp(mode,"cheat-evolution")){universal_ensure_manager("cheat-evolution","Cheat Evolution");return;}if(!strcmp(mode,"cheat-table")){on_launch_with_cheat_table(NULL,NULL);return;}on_play(NULL,NULL);
}
static void on_steam_launch_preview(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.selected<0||G.selected>=G.game_count){log_line("Select a Steam game to preview its launch URI.");return;}
    Game*g=&G.games[G.selected];
    if(!game_is_steam(g)||game_is_steam_shortcut(g)){
        log_line("Steam launch preview is currently limited to installed Steam games, not Heroic, Lutris or Steam shortcuts.");
        if(G.library_detail_status)set_label(G.library_detail_status,"Steam preview: select a standard Steam game.");
        return;
    }
    const char*id=g->appid;
    if(!*id||strlen(id)>10){log_line("Invalid Steam app ID for preview.");return;}
    for(const char*p=id;*p;p++)if(!isdigit((unsigned char)*p)){log_line("Invalid Steam app ID for preview.");return;}
    char path[160];snprintf(path,sizeof path,"/api/launch-preview?appid=%s",id);
    char*body=NULL;int code=0;
    if(http_request("GET",path,NULL,&body,&code)<0||code!=200||!body){
        log_line("No read-only Steam launch preview available for %s (HTTP %d).",g->name,code);
        if(G.library_detail_status)set_label(G.library_detail_status,"Steam launch preview unavailable; no game launched.");
        free(body);return;
    }
    char uri[256]={0},mode[64]={0};
    json_string(body,"uri",uri,sizeof uri);
    json_string(body,"mode",mode,sizeof mode);
    int enabled=json_bool(body,"launch_enabled",1);
    if(strcmp(mode,"preview_only")||strncmp(uri,"steam://rungameid/",18)||enabled){
        log_line("Unsafe or unexpected launch-preview response; ignoring it.");
        free(body);return;
    }
    log_line("PC2 Steam launch preview for %s: %s (no launch performed)",g->name,uri);
    if(G.library_detail_status)set_label(G.library_detail_status,"Steam launch URI preview complete. See Activity; launch remains disabled.");
    free(body);
}
/* Test 10: source-only Steam game launch. The legacy UI remains locked, and
 * this callback alone gets a game-only opt-in path. Never start a trainer,
 * rewrite Steam LaunchOptions, change Proton selection or call legacy play.
 * Launch requires a startup flag AND an explicit in-app Yes. */
static int pc2_steam_launch_allowed(void){
    const char*flag=getenv("GAMEWELD_PC2_ENABLE_STEAM_LAUNCH");
    return pc2_discovery_only()&&flag&&!strcmp(flag,"1");
}
/* Native Rust wrapper is a SEPARATE, explicitly opted-in private test path.
 * It never uses the saved Steam Launch Options or legacy Bridge. */
static int pc2_native_wrapper_allowed(void){
    const char*flag=getenv("GAMEWELD_PC2_ENABLE_NATIVE_WRAPPER");
    return pc2_discovery_only()&&flag&&!strcmp(flag,"1");
}
/* Prefer Steam's own Proton, Steam Runtime and game launch supervisor.
 * WeMod is a separate, consented client-only handoff after game detection. */
static int pc2_steam_wemod_allowed(void){
    const char*flag=getenv("GAMEWELD_PC2_ENABLE_STEAM_WEMOD");
    return pc2_discovery_only()&&flag&&!strcmp(flag,"1")&&pc2_steam_launch_allowed();
}
static void pc2_steam_wemod_attach_selected(int live);
/* A game-only Steam request must not be logged as successful until we can
 * inspect the Steam command's result and same-user process association.
 * This worker is opt-in and never starts any trainer or changes settings. */
typedef struct {
    char appid[32],game_name[256],output[4096];
    int confirmed;
    int expect_deckcheatz;
    int session_mode;
    int steam_managed_wemod;
    char deckcheatz_launcher[4096];
} PC2SteamLaunchJob;
static int pc2_steam_launch_busy=0;
static gboolean pc2_steam_launch_done(gpointer data){
    PC2SteamLaunchJob*j=(PC2SteamLaunchJob*)data;
    pc2_steam_launch_busy=0;
    const char *state=strstr(j->output,"Launch result: FAILED")?"FAILED":
        strstr(j->output,"Launch result: STEAM_ASSOCIATION_OBSERVED")?"ASSOCIATED PROCESS OBSERVED":
        "UNCONFIRMED";
    log_line("PC2 Steam %s [%s] %s (app %s): %.3000s",
             j->expect_deckcheatz?"DeckCheatz wrapper route":"game-only launch",
             state,j->game_name,j->appid,
             j->output[0]?j->output:"No launch-helper result.");
    if(j->session_mode)
        log_line("One-shot DeckCheatz token was consumed by Steam shim or will expire automatically. "
                 "Original game execution is the default for subsequent launches; Steam's one-time shim remains configured.");
    else if(j->expect_deckcheatz)
        log_line("Steam may execute saved Launch Options; DeckCheatz window, trainer attachment and effect remain UNVERIFIED.");
    if(G.selected>=0&&G.selected<G.game_count&&
       !strcmp(G.games[G.selected].appid,j->appid)&&G.library_detail_status){
        set_label(G.library_detail_status,!strcmp(state,"FAILED")?
            "Steam launch FAILED. Check Activity for the command error.":
            !strcmp(state,"UNCONFIRMED")?
            "Steam launch UNCONFIRMED. Check Steam's Downloads/game status and Activity.":
            j->expect_deckcheatz?
            "Steam process detected; existing Launch Options may have run. WeMod not verified.":
            "Steam process association observed; game window and trainer still unverified.");
    }
    /* Only after Steam association was observed, preview the separate WeMod
     * handoff. Do not launch a client or modify the prefix without consent. */
    if(j->steam_managed_wemod && !strcmp(state,"ASSOCIATED PROCESS OBSERVED") &&
       G.selected>=0 && G.selected<G.game_count &&
       !strcmp(G.games[G.selected].appid,j->appid)){
        pc2_steam_wemod_attach_selected(0);
    }else if(j->steam_managed_wemod){
        GtkWidget*notice=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_INFO,GTK_BUTTONS_OK,
            "Steam launch not verified for %.140s.\n\n%.2100s\n\n"
            "WeMod was NOT started. Use the separate WeMod button once the game is running.",
            j->game_name,j->output);
        gtk_dialog_run((GtkDialog*)notice);gtk_widget_destroy(notice);
    }
    free(j);return FALSE;
}
static int pc2_deckcheatz_session_helper(const char *action,const char *appid,
                                        const char *launcher,char *output,size_t cap){
    if(!action||!appid||!output||cap<64)return 0;
    int pipes[2];if(pipe(pipes)!=0)return 0;
    pid_t pid=fork();
    if(pid==0){
        close(pipes[0]);setsid();
        dup2(pipes[1],STDOUT_FILENO);dup2(pipes[1],STDERR_FILENO);close(pipes[1]);
        clear_desktop_activation_env();
        const char*appdir=getenv("APPDIR");char helper[4096]={0};
        if(appdir&&*appdir)
            snprintf(helper,sizeof helper,"%s/usr/libexec/gameweld-deckcheatz-session.py",appdir);
        else snprintf(helper,sizeof helper,"gameweld-deckcheatz-session.py");
        if(launcher&&*launcher)
            execlp("python3","python3",helper,action,"--appid",appid,
                   "--launcher",launcher,(char*)NULL);
        else
            execlp("python3","python3",helper,action,"--appid",appid,(char*)NULL);
        _exit(127);
    }
    close(pipes[1]);
    if(pid<0){close(pipes[0]);return 0;}
    return bounded_child_output(pid,pipes[0],output,cap,12);
}
static int pc2_session_configured_for_game(const char *appid){
    char result[4096]={0};
    if(!pc2_deckcheatz_session_helper("verify",appid,NULL,result,sizeof result)){
        return 0;
    }
    return strstr(result,"\"session_wrapper_installed_in_saved_options\": true")!=NULL;
}
static void *pc2_steam_launch_worker(void *data){
    PC2SteamLaunchJob*j=(PC2SteamLaunchJob*)data;
    if(j->session_mode){
        char armed[4096]={0};
        int ok=pc2_deckcheatz_session_helper("arm",j->appid,
                        j->deckcheatz_launcher,armed,sizeof armed);
        if(!ok || !strstr(armed,"\"SINGLE_SESSION_ARMED\"")){
            snprintf(j->output,sizeof j->output,
                     "Launch result: FAILED (one-shot DeckCheatz was not armed): %.2700s",
                     armed[0]?armed:"Session helper unavailable");
            g_idle_add(pc2_steam_launch_done,j);return NULL;
        }
    }
    int pipes[2];if(pipe(pipes)<0){
        if(j->session_mode){char ignored[2048]={0};
            pc2_deckcheatz_session_helper("disarm",j->appid,NULL,
                                          ignored,sizeof ignored);}
        snprintf(j->output,sizeof j->output,"Launch result: FAILED (could not create result pipe)");
        g_idle_add(pc2_steam_launch_done,j);return NULL;
    }
    pid_t pid=fork();
    if(pid==0){
        setpgid(0,0);
        close(pipes[0]);dup2(pipes[1],STDOUT_FILENO);
        dup2(pipes[1],STDERR_FILENO);close(pipes[1]);
        clear_desktop_activation_env();
        char helper[2048];
        const char*appdir=getenv("APPDIR");
        if(appdir&&*appdir)
            snprintf(helper,sizeof helper,"%s/usr/libexec/gameweld-steam-handoff.py",appdir);
        else snprintf(helper,sizeof helper,"gameweld-steam-handoff.py");
        if(j->expect_deckcheatz)
            execlp("python3","python3",helper,"launch","--appid",j->appid,
                   "--confirm","--require-idle-before-launch",(char*)NULL);
        else
            execlp("python3","python3",helper,"launch","--appid",j->appid,
                   "--confirm",(char*)NULL);
        _exit(127);
    }
    close(pipes[1]);
    if(pid<0){
        close(pipes[0]);
        snprintf(j->output,sizeof j->output,"Launch result: FAILED (could not start helper)");
    } else {
        j->confirmed=bounded_child_output(pid,pipes[0],j->output,sizeof j->output,28);
        if(!j->output[0])snprintf(j->output,sizeof j->output,
            "Launch result: FAILED (helper exited without reporting a status)");
    }
    if(j->session_mode &&
       !strstr(j->output,"Launch result: STEAM_ASSOCIATION_OBSERVED")){
        /* Don't leave a pending DeckCheatz token available to an unrelated
         * manual Steam launch after a failed or unconfirmed Play request.
         * If Steam already consumed it, this explicit disarm is harmless. */
        char ignored[2048]={0};
        pc2_deckcheatz_session_helper("disarm",j->appid,NULL,ignored,sizeof ignored);
    }
    g_idle_add(pc2_steam_launch_done,j);
    return NULL;
}
static void pc2_steam_launch_selected(int expect_deckcheatz){
    if(!pc2_steam_launch_allowed()){
        if(expect_deckcheatz){
            log_line("DeckCheatz Steam setup only. Use --enable-steam-game-launch to opt into launches.");
            on_pc2_deckcheatz_setup_session(NULL,NULL);
        }else log_line("PC2 Steam game-only launch is disabled. Start with --enable-steam-game-launch to opt in.");
        return;
    }
    if(G.selected<0||G.selected>=G.game_count){log_line("Select a Steam game first.");return;}
    Game*g=&G.games[G.selected];
    if(!game_is_steam(g)||game_is_steam_shortcut(g)){
        log_line("PC2 game-only launch currently supports standard installed Steam games, not shortcuts, Heroic or Lutris.");
        return;
    }
    char launcher[4096]={0};
    if(expect_deckcheatz && !pc2_deckcheatz_find_launcher(launcher,sizeof launcher)){
        log_line("Cannot launch through Steam wrapper: installed DeckCheatz wemod launcher not found.");
        on_pc2_deckcheatz_copy_steam_option(NULL,NULL);
        return;
    }
    const char*id=g->appid;
    if(!id[0]||id[0]=='0'||strlen(id)>10){log_line("Invalid Steam ID; launch blocked.");return;}
    for(const char*q=id;*q;q++)if(!isdigit((unsigned char)*q)){log_line("Invalid Steam ID; launch blocked.");return;}
    char request_path[160],expected_uri[160];
    snprintf(request_path,sizeof request_path,"/api/launch-preview?appid=%s",id);
    snprintf(expected_uri,sizeof expected_uri,"steam://rungameid/%s",id);
    char*body=NULL;int code=0;
    if(http_request("GET",request_path,NULL,&body,&code)<0||code!=200||!body){
        log_line("PC2 backend did not approve a safe preview for %s (HTTP %d). Nothing launched.",g->name,code);
        free(body);return;
    }
    char mode[64]={0},provider[64]={0},reply_id[64]={0},uri[256]={0};
    json_string(body,"mode",mode,sizeof mode);
    json_string(body,"provider",provider,sizeof provider);
    json_string(body,"appid",reply_id,sizeof reply_id);
    json_string(body,"uri",uri,sizeof uri);
    int launch_enabled=json_bool(body,"launch_enabled",1);
    free(body);
    if(strcmp(mode,"preview_only")||strcmp(provider,"steam")||strcmp(reply_id,id)||
       strcmp(uri,expected_uri)||launch_enabled){
        log_line("PC2 backend preview mismatch. Launch blocked without side effects.");
        return;
    }
    int session_mode=expect_deckcheatz && pc2_session_configured_for_game(id);
    GtkWidget*confirm=gtk_message_dialog_new(
        (GtkWindow*)G.window,GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        session_mode?
        "Use DeckCheatz for JUST THIS Steam play session?\n\n"
        "%.140s (Steam App ID %s)\n\n"
        "GameWeld verified its one-shot session shim in the saved Steam "
        "Launch Options. It will arm DeckCheatz for the NEXT launch only, "
        "then automatically revert to normal game execution on future launches. "
        "The shim stays in Steam until you manually restore the original text. "
        "The game must be closed. Continue?":
        expect_deckcheatz?
        "Launch using your EXISTING Steam DeckCheatz option?\n\n"
        "%.140s (Steam App ID %s)\n\n"
        "Confirm you already added the DeckCheatz wemod wrapper and "
        "%%command%% to THIS game in Steam Properties > Launch Options. "
        "GameWeld cannot verify these Steam settings. Game and WeMod must "
        "be closed before launch. No Steam setting will be changed. Continue?":
        "Launch Steam game only?\n\n%.140s (Steam App ID %s)\n\n"
        "This will request Steam to launch ONLY the game. No trainer, WeMod, "
        "Cheat Engine, Proton setup or GameWeld configuration changes will be requested.\n\n"
        "Steam itself may update a game or runtime normally. Continue?",
        g->name,id);
    int accepted=gtk_dialog_run((GtkDialog*)confirm);
    gtk_widget_destroy(confirm);
    if(accepted!=GTK_RESPONSE_YES){log_line("PC2 Steam game-only launch cancelled.");return;}
    if(!pc2_steam_launch_allowed()){
        log_line("PC2 launch opt-in was revoked; nothing launched.");return;
    }
    if(pc2_steam_launch_busy){
        log_line("PC2 Steam launch already in progress; no duplicate request sent.");
        return;
    }
    PC2SteamLaunchJob*j=(PC2SteamLaunchJob*)calloc(1,sizeof *j);
    if(!j){log_line("PC2 Steam launch FAILED: could not allocate helper state.");return;}
    snprintf(j->appid,sizeof j->appid,"%s",id);
    snprintf(j->game_name,sizeof j->game_name,"%.240s",g->name);
    j->expect_deckcheatz=expect_deckcheatz;
    j->steam_managed_wemod=pc2_steam_wemod_allowed()&&!expect_deckcheatz;
    j->session_mode=session_mode;
    if(session_mode)snprintf(j->deckcheatz_launcher,
                             sizeof j->deckcheatz_launcher,"%s",launcher);
    pthread_t thread;
    pc2_steam_launch_busy=1;
    if(pthread_create(&thread,NULL,pc2_steam_launch_worker,j)==0){
        pthread_detach(thread);
        log_line("PC2 Steam %s launch check for %.140s (app %s); Steam manages saved launch options.",
                 expect_deckcheatz?"DeckCheatz-wrapper":"game-only",g->name,id);
        if(G.library_detail_status)set_label(G.library_detail_status,
            "Checking Steam launch response; a command request is not game startup confirmation.");
    }else{
        pc2_steam_launch_busy=0;free(j);
        log_line("PC2 Steam launch FAILED: could not start launch-check worker.");
    }
}
static void on_pc2_steam_game_only(GtkButton*b,void*d){
    (void)b;(void)d;
    pc2_steam_launch_selected(0);
}

/* Isolated Rust wrapper preview and opt-in launch. Never edits Steam options,
 * enables a legacy Play callback, or silently falls back to the Steam Bridge.
 * A spawned child PID is NOT proof that WeMod or the game is working. */
typedef struct {
    char appid[32], game[256], wrapper[4096], cli[4096], output[4096];
    int live, ok;
} PC2NativeWrapperJob;
static int pc2_native_wrapper_busy=0;
static gboolean pc2_native_wrapper_done(gpointer data){
    PC2NativeWrapperJob*j=(PC2NativeWrapperJob*)data;
    pc2_native_wrapper_busy=0;
    log_line("Native Rust wrapper %s for %s (AppID %s): %s",
        j->live?"EXPERIMENTAL LAUNCH":"read-only preview",
        j->game,j->appid,j->output[0]?j->output:"No helper output.");
    if(G.selected>=0&&G.selected<G.game_count&&
       !strcmp(G.games[G.selected].appid,j->appid)&&G.library_detail_status)
        set_label(G.library_detail_status,j->ok?
            (j->live?
                "Native wrapper process spawned. Game and WeMod attachment NOT VERIFIED; see Activity.":
                "Rust native wrapper PREVIEW PASSED. No game launched; see Activity.") :
            "Rust native wrapper BLOCKED or failed. Check Activity for the exact reason.");
    GtkWidget*notice=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,j->ok?GTK_MESSAGE_INFO:GTK_MESSAGE_QUESTION,
        GTK_BUTTONS_OK,"Native Rust wrapper %s\n\n%.2900s",
        j->ok?"response":"blocked",j->output[0]?j->output:"No helper output.");
    gtk_dialog_run((GtkDialog*)notice);
    gtk_widget_destroy(notice);
    free(j);
    return FALSE;
}
static void *pc2_native_wrapper_worker(void *data){
    PC2NativeWrapperJob*j=(PC2NativeWrapperJob*)data;
    int fd[2];if(pipe(fd)!=0){
        snprintf(j->output,sizeof j->output,"Cannot create native wrapper output pipe.");
        g_idle_add(pc2_native_wrapper_done,j);return NULL;
    }
    pid_t pid=fork();
    if(pid==0){
        setpgid(0,0);
        close(fd[0]);
        if(dup2(fd[1],STDOUT_FILENO)<0)_exit(127);
        if(dup2(fd[1],STDERR_FILENO)<0)_exit(127);
        close(fd[1]);
        clear_desktop_activation_env();
        const char*proton=getenv("GAMEWELD_NATIVE_PROTON");
        if(j->live){
            if(proton&&*proton)
                execl(j->cli,j->cli,"--appid",j->appid,"--wrapper",j->wrapper,
                    "--proton",proton,"--launch","--approve-experimental",
                    "--acknowledge-game-closed",(char*)NULL);
            else
                execl(j->cli,j->cli,"--appid",j->appid,"--wrapper",j->wrapper,
                    "--launch","--approve-experimental",
                    "--acknowledge-game-closed",(char*)NULL);
        }else{
            if(proton&&*proton)
                execl(j->cli,j->cli,"--appid",j->appid,"--wrapper",j->wrapper,
                    "--proton",proton,"--preview",(char*)NULL);
            else
                execl(j->cli,j->cli,"--appid",j->appid,"--wrapper",j->wrapper,
                    "--preview",(char*)NULL);
        }
        _exit(127);
    }
    close(fd[1]);
    if(pid<0){
        close(fd[0]);
        snprintf(j->output,sizeof j->output,"Cannot start native Rust wrapper helper.");
    }else{
        j->ok=bounded_child_output(pid,fd[0],j->output,sizeof j->output,22);
        if(!j->output[0])snprintf(j->output,sizeof j->output,
            "Native Rust wrapper returned no output (possible failed execution).");
    }
    g_idle_add(pc2_native_wrapper_done,j);
    return NULL;
}
static void pc2_native_wrapper_action(int live){
    if(!pc2_native_wrapper_allowed())return;
    if(G.selected<0||G.selected>=G.game_count){
        log_line("Select a Steam game before using the native Rust wrapper.");return;
    }
    Game*g=&G.games[G.selected];
    if(!game_is_steam(g)||game_is_steam_shortcut(g)){
        log_line("Rust native wrapper currently requires an installed standard Steam game.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "Native Rust wrapper is Steam-game-only; select an installed Steam game.");
        return;
    }
    if(pc2_native_wrapper_busy){
        log_line("Rust native wrapper check already running.");return;
    }
    char wrapper[4096]={0};
    if(!pc2_deckcheatz_find_launcher(wrapper,sizeof wrapper)){
        GtkWidget*notice=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_INFO,GTK_BUTTONS_OK,
            "Native Rust wrapper cannot run: DeckCheatz launcher not found.\n\n"
            "Use Settings to detect your installed DeckCheatz checkout first.");
        gtk_dialog_run((GtkDialog*)notice);gtk_widget_destroy(notice);
        log_line("Native wrapper BLOCKED: existing DeckCheatz launcher not found. Detect the checkout in Settings.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz launcher not found. Detect or inspect your existing DeckCheatz checkout first.");
        return;
    }
    const char*cli=getenv("GAMEWELD_NATIVE_WRAPPER_CLI");
    if(!cli||cli[0]!='/'||access(cli,X_OK)!=0){
        log_line("Native Rust wrapper CLI unavailable. Restart via --enable-native-wrapper-test.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "Native Rust wrapper binary unavailable; restart with --enable-native-wrapper-test.");
        return;
    }
    if(live){
        GtkWidget*confirm=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
            "Experimental native DeckCheatz + Proton launch\n\n"
            "%.140s (AppID %s)\n\n"
            "This bypasses Steam's launch supervisor and may not work with "
            "SteamAPI, DRM, runtime or overlay. It can modify your existing "
            "game Proton prefix through upstream software.\n\n"
            "Close the game and WeMod first. Do not continue without a separate "
            "backup of that prefix. No Steam Launch Options are changed.\n\n"
            "Confirm you accept this private test?",g->name,g->appid);
        int response=gtk_dialog_run((GtkDialog*)confirm);
        gtk_widget_destroy(confirm);
        if(response!=GTK_RESPONSE_YES)return;
    }
    PC2NativeWrapperJob*j=calloc(1,sizeof *j);
    if(!j){log_line("Could not allocate native wrapper check.");return;}
    snprintf(j->appid,sizeof j->appid,"%s",g->appid);
    snprintf(j->game,sizeof j->game,"%.240s",g->name);
    snprintf(j->wrapper,sizeof j->wrapper,"%s",wrapper);
    snprintf(j->cli,sizeof j->cli,"%s",cli);
    j->live=live;
    pc2_native_wrapper_busy=1;
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_native_wrapper_worker,j)==0){
        pthread_detach(thread);
        if(G.library_detail_status)set_label(G.library_detail_status,
            live?"Attempting opt-in native launch; outcome pending and attachment unverified.":
                 "Checking native wrapper launch plan without starting a game…");
    }else{
        pc2_native_wrapper_busy=0;free(j);
        log_line("Could not start native wrapper worker.");
    }
}
static void on_pc2_native_wrapper_preview(GtkButton*b,void*d){
    (void)b;(void)d;pc2_native_wrapper_action(0);
}
static void on_pc2_native_wrapper_launch(GtkButton*b,void*d){
    (void)b;(void)d;pc2_native_wrapper_action(1);
}
static void on_pc2_steam_session_check(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!pc2_provider_controls_allowed())return;
    if(G.selected<0||G.selected>=G.game_count){
        log_line("Choose an installed Steam game for session observation.");return;
    }
    Game*g=&G.games[G.selected];
    if(!game_is_steam(g)||game_is_steam_shortcut(g)){
        log_line("PC2 Steam session observation currently supports standard installed Steam games only.");return;
    }
    const char*id=g->appid;
    if(!id[0]||id[0]=='0'||strlen(id)>10){
        log_line("Cannot observe session for invalid Steam app ID.");return;
    }
    for(const char*q=id;*q;q++)if(!isdigit((unsigned char)*q)){
        log_line("Cannot observe session for invalid Steam app ID.");return;
    }
    char endpoint[160];
    snprintf(endpoint,sizeof endpoint,"/api/steam-session?appid=%s",id);
    char*body=NULL;int code=0;
    if(http_request("GET",endpoint,NULL,&body,&code)<0||code!=200||!body){
        log_line("Read-only Steam session observation unavailable for %s (HTTP %d).",g->name,code);
        free(body);return;
    }
    char mode[64]={0},state[100]={0},reply_id[64]={0};
    json_string(body,"mode",mode,sizeof mode);
    json_string(body,"state",state,sizeof state);
    json_string(body,"appid",reply_id,sizeof reply_id);
    int confirmed=json_bool(body,"game_running_confirmed",1);
    free(body);
    if(strcmp(mode,"read_only")||strcmp(reply_id,id)||confirmed){
        log_line("Unexpected Steam session API response; no claim about game state.");return;
    }
    if(!strcmp(state,"associated_processes_observed")){
        log_line("Steam app-ID %s: associated process environment observed; executable/session ownership is NOT verified.",id);
        if(G.library_detail_status)set_label(G.library_detail_status,
            "Steam-associated process observed, but game executable/ownership is not verified.");
    }else if(!strcmp(state,"no_process_evidence")){
        log_line("Steam app-ID %s: no exact same-user process association detected; game may still be running.",id);
        if(G.library_detail_status)set_label(G.library_detail_status,
            "No exact Steam process evidence detected; this is not proof the game has stopped.");
    }else{
        log_line("Steam session observation is unavailable or unsupported; game state unknown.");
    }
}
static void on_steam_page(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Non-Steam shortcuts do not have a Steam store page.");return;}if(game_is_steam(g)){char u[256];snprintf(u,sizeof u,"steam://store/%s",g->appid);spawn_detached("xdg-open",u,NULL);}else if(game_is_lutris(g))log_line("Store-page shortcut is not wired for Lutris entries in 0.6.0 Test 4.");else log_line("Store-page shortcut is not wired for Heroic %s games yet.",g->runner);}
static void on_game_folder(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;if(G.games[G.selected].install_dir[0])spawn_detached("xdg-open",G.games[G.selected].install_dir,NULL);}
static void on_open_selected_trainer_folder(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]){log_line("Select a trainer row first.");return;}char dir[2048];snprintf(dir,sizeof dir,"%s",G.trainer_library_pick_path);char *slash=strrchr(dir,'/');if(slash&&slash!=dir)*slash=0;else if(slash==dir)slash[1]=0;else snprintf(dir,sizeof dir,".");spawn_detached("xdg-open",dir,NULL);log_line("Opened trainer folder: %s",dir);}
static void on_minimize(GtkButton*b,void*d){(void)b;(void)d;gtk_window_iconify((GtkWindow*)G.window);}
static void on_maximize(GtkButton*b,void*d){
    (void)b;(void)d;
    /* Do not infer maximization from button click count. KWin can maximize
     * our window at startup, or by dragging/double-clicking the titlebar. */
    if(gtk_window_is_maximized((GtkWindow*)G.window))
        gtk_window_unmaximize((GtkWindow*)G.window);
    else
        gtk_window_maximize((GtkWindow*)G.window);
}
static void on_close_btn(GtkButton*b,void*d){(void)b;(void)d;gtk_widget_destroy(G.window);}
static gboolean heroic_session_status_tick(void *unused){
    (void)unused;
    static int last_state=-1;static long last_gp=-1,last_tp=-1;static char last_key[320]={0};
    Game*g=(G.selected>=0&&G.selected<G.game_count)?&G.games[G.selected]:NULL;
    long gp=0,tp=0;char launch[128]={0};int state=g?heroic_managed_session_state(g,&gp,&tp,launch,sizeof launch):0;
    const char*k=g?game_key(g):"";
    if(strcmp(last_key,k)||state!=last_state||gp!=last_gp||tp!=last_tp){snprintf(last_key,sizeof last_key,"%s",k);last_state=state;last_gp=gp;last_tp=tp;refresh_ui();}
    return TRUE;
}

static void on_setup(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_SETUP,NULL,"Installing / repairing Steam compatibility layer…");}
static void on_verify(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_VERIFY,NULL,"Verifying Steam compatibility layer…");}
static void on_export_support_bundle(GtkButton *b,void *d){
    (void)b;(void)d;
    if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first before exporting a support bundle.");if(G.support_bundle_status)set_label(G.support_bundle_status,"Choose a game in Library or Home first.");return;}
    Game*g=&G.games[G.selected];char trainer[2048]={0};load_local_trainer(game_key(g),trainer,sizeof trainer);
    int fd[2];if(pipe(fd)!=0){log_line("Could not start support-bundle export.");return;}
    pid_t p=fork();
    if(p==0){
        close(fd[0]);dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);
        execlp("python3","python3",support_bundle_tool(),"create",
            "--version","0.7.0","--name",g->name,"--key",game_key(g),"--provider",g->provider,"--appid",g->appid,"--launch-id",g->launch_id,"--runner",g->runner,
            "--target-kind",g->target_kind,"--executable",g->executable,"--install-dir",g->install_dir,"--prefix",g->prefix,"--compatdata",g->compatdata,
            "--compat-tool",g->compat_tool,"--compat-tool-path",g->compat_tool_path,"--compat-tool-source",g->compat_tool_source,"--resolution-state",g->resolution_state,"--resolution",g->resolution_label,
            "--trainer",trainer,(char*)NULL);_exit(127);
    }
    close(fd[1]);char out[4096]={0};ssize_t n=read(fd[0],out,sizeof out-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}
    if(n>0){out[n]=0;while(n>0&&(out[n-1]=='\n'||out[n-1]=='\r'))out[--n]=0;}
    if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0&&out[0]){log_line("Support bundle exported for %s: %s",g->name,out);if(G.support_bundle_status){char msg[4600];snprintf(msg,sizeof msg,"Selected-game support bundle created:\n%s\n\nContains only this game's launch metadata, Trainer Library diagnostics and matching GameWeld logs. Trainer EXE bytes and unrelated game logs are not included.",out);set_label(G.support_bundle_status,msg);}}
    else{log_line("Support bundle export failed for %s: %s",g->name,out[0]?out:"unknown error");if(G.support_bundle_status)set_label(G.support_bundle_status,"Support bundle export failed. See Activity Log for details.");}
}

static void on_health(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Steam non-Steam shortcut resolution for %s: %s | target=%s | tool=%s | compatdata=%s | live-session validation ready.",g->name,g->resolution_label[0]?g->resolution_label:"unresolved",g->target_kind[0]?g->target_kind:"unknown",g->compat_tool[0]?g->compat_tool:"unresolved",g->compatdata[0]?g->compatdata:"not found");return;}if(game_is_lutris(g)){log_line("Lutris Test 4 readiness for %s: %s | runner=%s | target=%s | prefix=%s | runtime=%s | runtime-path=%s | resolved=%s. Assigned trainers use fail-closed live-session ownership.",g->name,g->resolution_label[0]?g->resolution_label:"unresolved",g->runner[0]?g->runner:"wine",g->executable[0]?g->executable:"not resolved",g->prefix[0]?g->prefix:"not resolved",g->wine_name[0]?g->wine_name:(g->wine_bin[0]?g->wine_bin:"not resolved"),g->wine_bin[0]?g->wine_bin:"not resolved",lutris_session_ready(g)?"yes":"no");return;}if(game_is_heroic(g)){log_line("Heroic launch diagnostics are recorded in ~/.local/state/gameweld/heroic-*.log.");return;}start_job(JOB_HEALTH,g->appid,"Checking trainer health…");}
static void on_refresh(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_REFRESH,NULL,"Refreshing Steam, Heroic, Lutris and GameWeld status…");}

static void nav_activate(GtkWidget *active,const char *page){GtkWidget *all[]={G.nav_home,G.nav_library,G.nav_trainers,G.nav_setup,G.nav_diag,G.nav_settings,G.nav_about};for(int i=0;i<7;i++)if(all[i])unstyle(all[i],"nav-active");style(active,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,page);}
static void nav_home(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_home,"home");}
static void nav_library(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_library,"library");}
static void on_check_trainer_updates(GtkButton*,void*);
static void nav_trainers(GtkButton*b,void*d){(void)b;(void)d;refresh_trainer_library_view();nav_activate(G.nav_trainers,"trainers");
    if(G.selected>=0&&G.selected<G.game_count&&!G.trainer_updates_busy){
        const char *name=G.games[G.selected].name;time_t now=time(NULL);
        if(strcmp(name,G.trainer_updates_last_game)||now-G.trainer_updates_last_check>=86400){
            snprintf(G.trainer_updates_last_game,sizeof G.trainer_updates_last_game,"%s",name);
            G.trainer_updates_last_check=now;
            on_check_trainer_updates(NULL,NULL);
        }
    }
}
static void nav_setup(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_setup,"setup");}
static void nav_diag(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_diag,"diag");}
static void nav_settings(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_settings,"settings");}
static void nav_about(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_about,"about");}

static const char *global_search_scope_id(void){const char*id=G.search_scope?gtk_combo_box_get_active_id((GtkComboBox*)G.search_scope):NULL;return(id&&*id)?id:"all";}
static int game_matches_global_scope(Game*g,const char*scope){
    if(!scope||!strcmp(scope,"all"))return 1;
    if(!strcmp(scope,"steam"))return game_is_steam(g)&&!game_is_steam_shortcut(g);
    if(!strcmp(scope,"shortcut"))return game_is_steam_shortcut(g);
    if(!strcmp(scope,"heroic"))return game_is_heroic(g);
    if(!strcmp(scope,"lutris"))return game_is_lutris(g);
    return 1;
}
static void apply_global_game_search(const char*q,const char*scope){
    for(int i=0;i<G.game_count;i++){
        int vis=game_matches_global_scope(&G.games[i],scope);
        if(vis&&q&&*q){char a[512],b[512];snprintf(a,sizeof a,"%s",G.games[i].name);snprintf(b,sizeof b,"%s",q);for(char*p=a;*p;p++)*p=(char)tolower((unsigned char)*p);for(char*p=b;*p;p++)*p=(char)tolower((unsigned char)*p);vis=strstr(a,b)!=NULL;}
        gtk_widget_set_visible(G.game_rows[i],vis);
    }
}
static void on_search(GtkEntry *entry,void*d){
    (void)d;const char*q=gtk_entry_get_text(entry);const char*scope=global_search_scope_id();
    if(!strcmp(scope,"trainers")){
        for(int i=0;i<G.game_count;i++)gtk_widget_set_visible(G.game_rows[i],TRUE);
        if(G.trainer_library_filter)gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,q?q:"");
        refresh_trainer_library_rows();
        if(q&&*q){refresh_trainer_library_view();nav_activate(G.nav_trainers,"trainers");}
        return;
    }
    if(G.trainer_library_filter&&gtk_entry_get_text((GtkEntry*)G.trainer_library_filter)[0]){gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,"");refresh_trainer_library_rows();}
    apply_global_game_search(q,scope);
    if(q&&*q)nav_activate(G.nav_library,"library");
}
static void on_search_scope_changed(GtkComboBox*w,void*d){
    (void)w;(void)d;const char*scope=global_search_scope_id();
    const char*ph="Search all games…";
    if(!strcmp(scope,"steam"))ph="Search Steam games…";
    else if(!strcmp(scope,"shortcut"))ph="Search Steam shortcuts…";
    else if(!strcmp(scope,"heroic"))ph="Search Heroic games…";
    else if(!strcmp(scope,"lutris"))ph="Search Lutris games…";
    else if(!strcmp(scope,"trainers"))ph="Search trainers…";
    if(G.search)gtk_entry_set_placeholder_text((GtkEntry*)G.search,ph);
    const char*q=G.search?gtk_entry_get_text((GtkEntry*)G.search):"";
    if(!strcmp(scope,"trainers")){
        for(int i=0;i<G.game_count;i++)gtk_widget_set_visible(G.game_rows[i],TRUE);
        if(G.trainer_library_filter)gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,q?q:"");
        refresh_trainer_library_rows();nav_activate(G.nav_trainers,"trainers");
    }else{
        if(G.trainer_library_filter&&gtk_entry_get_text((GtkEntry*)G.trainer_library_filter)[0]){gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,"");refresh_trainer_library_rows();}
        apply_global_game_search(q,scope);nav_activate(G.nav_library,"library");
    }
}
static void on_destroy(GtkWidget*w,void*d){(void)w;(void)d;pc2_save_window_size();if(G.backend_pid>0)kill(G.backend_pid,SIGTERM);gtk_main_quit();}

static GtkWidget *card(const char *title,const char *detail,GtkWidget **detail_out){GtkWidget *c=box(GTK_ORIENTATION_VERTICAL,6);style(c,"card");margins(c,4);GtkWidget*t=label(title,"card-title");pack(c,t,0);GtkWidget*x=label(detail,"muted");gtk_label_set_line_wrap((GtkLabel*)x,TRUE);pack(c,x,0);if(detail_out)*detail_out=x;return c;}

static GtkWidget *icon_named(const char *name,int px){GtkWidget*i=gtk_image_new_from_icon_name(name,GTK_ICON_SIZE_BUTTON);if(i)gtk_image_set_pixel_size((GtkImage*)i,px);return i;}
static GtkWidget *make_nav(const char *icon,const char *txt,GCallback cb){GtkWidget*b=gtk_button_new();style(b,"nav");GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,7);GtkWidget*i=icon_named(icon,16);if(i){style(i,"nav-icon");pack(r,i,0);}GtkWidget*l=label(txt,"nav-label");pack(r,l,0);gtk_container_add(b,r);g_signal_connect_data(b,"clicked",cb,NULL,NULL,0);return b;}
static GtkWidget *quick_button(const char *icon,const char *txt){GtkWidget*b=gtk_button_new();pc2_guard_button(b);style(b,"action");GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*i=icon_named(icon,18);if(i)pack(r,i,0);GtkWidget*l=label(txt,"quick-label");pack(r,l,1);GtkWidget*ch=label("›","quick-chevron");pack(r,ch,0);gtk_container_add(b,r);return b;}

static GtkWidget *status_card(const char *icon,const char *title,const char *detail,GtkWidget **out,const char *pill){
    GtkWidget*c=box(GTK_ORIENTATION_VERTICAL,8);style(c,"card");style(c,"info-card");
    GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,13);
    GtkWidget*ic=label(icon,NULL);style(ic,!strcmp(icon,"W")?"info-icon-wand":"info-icon");gtk_widget_set_halign(ic,GTK_ALIGN_CENTER);pack(r,ic,0);
    GtkWidget*txt=box(GTK_ORIENTATION_VERTICAL,3);pack(txt,label(title,"card-title"),0);GtkWidget*d=label(detail,"muted");gtk_label_set_line_wrap((GtkLabel*)d,TRUE);pack(txt,d,0);pack(r,txt,1);pack(c,r,1);
    GtkWidget*p=label(pill,"good");gtk_widget_set_name(p,"status-pill");gtk_widget_set_halign(p,GTK_ALIGN_CENTER);pack(c,p,0);if(out)*out=p;return c;
}
static GtkWidget *meta_chip(const char *text){GtkWidget*w=label(text,NULL);style(w,"meta-chip");return w;}
static void on_trainer_library_filter_changed(GtkEditable*w,void*d){(void)w;(void)d;refresh_trainer_library_rows();}
static void on_trainer_library_sort_changed(GtkComboBox*w,void*d){(void)w;(void)d;refresh_trainer_library_rows();}
static void on_trainer_library_readiness_changed(GtkComboBox*w,void*d){(void)w;(void)d;refresh_trainer_library_rows();}
static void on_trainer_library_attention_toggled(GtkToggleButton*w,void*d){(void)d;if(G.trainer_library_tabs&&gtk_toggle_button_get_active(w))gtk_notebook_set_current_page((GtkNotebook*)G.trainer_library_tabs,5);refresh_trainer_library_rows();}
static void on_trainer_library_clear_filter(GtkButton*b,void*d){(void)b;(void)d;if(G.trainer_library_filter)gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,"");if(G.trainer_library_readiness_filter)gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_readiness_filter,"all");if(G.trainer_library_attention_toggle)gtk_toggle_button_set_active((GtkToggleButton*)G.trainer_library_attention_toggle,FALSE);if(G.trainer_library_sort)gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_sort,"status");refresh_trainer_library_rows();}

static void on_choose_local_trainer(GtkButton*,void*);
static void on_clear_local_trainer(GtkButton*,void*);
static void on_scan_trainer_library(GtkButton*,void*);
static void on_rescan_selected_trainer(GtkButton*,void*);
static void on_add_trainer_folder(GtkButton*,void*);
static void on_assign_library_pick(GtkButton*,void*);
static void on_ignore_library_pick(GtkButton*,void*);
static void on_clear_ignored_trainers(GtkButton*,void*);
static GtkWidget *launch_button(int primary){
    GtkWidget*b=gtk_button_new();pc2_guard_button(b);gtk_widget_set_name(b,primary?"play":"normal");
    GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,14);margins(r,12);
    GtkWidget*ic=label("▶","launch-icon");gtk_widget_set_halign(ic,GTK_ALIGN_CENTER);pack(r,ic,0);
    GtkWidget*t=box(GTK_ORIENTATION_VERTICAL,1);
    GtkWidget*title=label(primary?"PLAY WITH TRAINER":"Play Normally",primary?"launch-title":"normal-title");
    GtkWidget*sub=label(primary?"Launch the selected game with its configured trainer":"Launch without trainer",primary?"launch-subtitle":"normal-subtitle");
    if(primary){G.play_title=title;G.play_subtitle=sub;}
    pack(t,title,0);pack(t,sub,0);pack(r,t,1);gtk_container_add(b,r);return b;
}

static GtkWidget *build_home(void){
    GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");
    GtkWidget*page=box(GTK_ORIENTATION_VERTICAL,14);gtk_widget_set_name(page,"page");margins(page,20);gtk_container_add(outer,page);

    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("OVERVIEW","page-kicker"),0);pack(ht,label("Your game, runtime and trainer in one place","workspace-title"),0);pack(ht,label(pc2_discovery_only()?"Use Steam\x27s saved DeckCheatz %command% wrapper for WeMod. Set it up once, then launch through Steam with consent.":"GameWeld keeps launcher-native sessions intact and gives every game one Launch With surface for trainers and manager providers.","page-subtitle"),0);pack(head,ht,1);GtkWidget*online=label(pc2_discovery_only()?"●  Library discovery active":"●  Services ready","good");gtk_widget_set_name(online,"status-pill");pack(head,online,0);pack(page,head,0);

    GtkWidget*spot=box(GTK_ORIENTATION_HORIZONTAL,16);gtk_widget_set_name(spot,"spotlight");
    GtkWidget*copy=box(GTK_ORIENTATION_VERTICAL,12);gtk_widget_set_name(copy,"spotlight-copy");gtk_widget_set_size_request(copy,390,-1);
    pack(copy,label("CURRENT GAME","eyebrow"),0);
    GtkWidget*idrow=box(GTK_ORIENTATION_HORIZONTAL,13);GtkWidget*cover=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(cover,"cover-frame");G.cover_image=gtk_image_new();gtk_widget_set_size_request(G.cover_image,155,220);pack(cover,G.cover_image,0);pack(idrow,cover,0);
    GtkWidget*ids=box(GTK_ORIENTATION_VERTICAL,7);G.hero_name=label("Select a game",NULL);gtk_widget_set_name(G.hero_name,"game-title");gtk_label_set_line_wrap((GtkLabel*)G.hero_name,TRUE);pack(ids,G.hero_name,0);G.hero_meta=label("Steam / Heroic • App ID —",NULL);gtk_widget_set_name(G.hero_meta,"meta");gtk_label_set_line_wrap((GtkLabel*)G.hero_meta,TRUE);pack(ids,G.hero_meta,0);pack(ids,meta_chip("LOCAL / SINGLE PLAYER"),0);G.game_detected_detail=label("Choose a game from Library to review its trainer, runtime and exact launch path before starting the session.","muted");gtk_label_set_line_wrap((GtkLabel*)G.game_detected_detail,TRUE);pack(ids,G.game_detected_detail,1);pack(idrow,ids,1);pack(copy,idrow,1);
    if(pc2_discovery_only()){
        GtkWidget*direct=button(pc2_steam_wemod_allowed()?
            "Play via Steam + WeMod (private test)":pc2_native_wrapper_allowed()?
            "Launch native Rust wrapper + WeMod (experimental)":pc2_steam_launch_allowed()?
            "Play via Steam + DeckCheatz":"Set up one-session DeckCheatz","primary-action");
        G.pc2_deckcheatz_overview_play=direct;
        g_signal_connect_data(direct,"clicked",(GCallback)on_pc2_bridge_primary,NULL,NULL,0);
        pack(copy,direct,0);
        G.pc2_deckcheatz_overview_status=label("Select an installed Steam game to use WeMod.","muted");
        gtk_label_set_line_wrap((GtkLabel*)G.pc2_deckcheatz_overview_status,TRUE);
        pack(copy,G.pc2_deckcheatz_overview_status,0);
    }
    GtkWidget*plays=box(GTK_ORIENTATION_HORIZONTAL,8);gtk_widget_set_name(plays,"launch-panel");G.play_button=launch_button(1);g_signal_connect_data(G.play_button,"clicked",(GCallback)on_play_default,NULL,NULL,0);pack(plays,G.play_button,1);GtkWidget*normal=launch_button(0);G.overview_launch_game_only=normal;gtk_widget_set_size_request(normal,170,62);g_signal_connect_data(normal,"clicked",(GCallback)on_play_normal,NULL,NULL,0);pack(plays,normal,0);pack(copy,plays,0);if(pc2_discovery_only()){gtk_widget_set_no_show_all(plays,TRUE);gtk_widget_hide(plays);}
    /* PC2 Overview is a game-first landing page. Keep Steam/session, Wand
     * and DeckCheatz diagnostics in Settings/Support instead of displaying
     * the legacy experimental launch toolbox under Play with WeMod. */
    pack(spot,copy,0);
    GtkWidget*art=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(art,"hero-art");G.hero_image=gtk_image_new();gtk_widget_set_size_request(G.hero_image,520,300);pack(art,G.hero_image,1);pack(spot,art,1);pack(page,spot,0);
    if(pc2_discovery_only()){
        GtkWidget *recent=box(GTK_ORIENTATION_VERTICAL,11);style(recent,"panel");
        GtkWidget *row=box(GTK_ORIENTATION_HORIZONTAL,10);
        pack(row,label("RECENT GAMES","section-kicker"),0);
        GtkWidget *description=label(
            "Recently selected first, then other installed games. Click a cover to select; Play with WeMod launches separately.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)description,TRUE);
        pack(row,description,1);
        pack(recent,row,0);
        GtkWidget *scroll=gtk_scrolled_window_new(NULL,NULL);
        gtk_scrolled_window_set_policy((GtkScrolledWindow*)scroll,
                                       GTK_POLICY_AUTOMATIC,GTK_POLICY_NEVER);
        pc2_recent_tiles=box(GTK_ORIENTATION_HORIZONTAL,11);
        gtk_container_add(scroll,pc2_recent_tiles);
        pack(recent,scroll,0);
        pack(page,recent,0);
    }

    GtkWidget*launchwith=box(GTK_ORIENTATION_VERTICAL,10);style(launchwith,"panel");
    GtkWidget*lwh=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*lwt=box(GTK_ORIENTATION_VERTICAL,2);pack(lwt,label("LAUNCH WITH","section-kicker"),0);pack(lwt,label("Choose how to start the selected game","card-title"),0);pack(lwh,lwt,1);G.overview_launch_hint=label("Select a game in Library. Its launch options stay here on Overview.","muted");gtk_label_set_line_wrap((GtkLabel*)G.overview_launch_hint,TRUE);pack(lwh,G.overview_launch_hint,1);pack(launchwith,lwh,0);
    GtkWidget*prof=box(GTK_ORIENTATION_HORIZONTAL,8);G.overview_profile_combo=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"assigned","Assigned / detected trainer");gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"game-only","Game only");gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"wemod","WeMod");gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"aurora","Cheat Happens Aurora");gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"cheat-evolution","Cheat Evolution");gtk_combo_box_text_append((GtkComboBoxText*)G.overview_profile_combo,"cheat-table","Cheat Engine Table (.CT)");gtk_combo_box_set_active_id((GtkComboBox*)G.overview_profile_combo,"assigned");G.overview_save_profile=button("Save as one-click default","action");G.overview_reset_profile=button("Reset default","action");pack(prof,label("DEFAULT","section-kicker"),0);pack(prof,G.overview_profile_combo,1);pack(prof,G.overview_save_profile,0);pack(prof,G.overview_reset_profile,0);pack(launchwith,prof,0);G.overview_profile_status=label("Select a game to choose its one-click default.","good");pack(launchwith,G.overview_profile_status,0);
    GtkWidget*lwr0=box(GTK_ORIENTATION_HORIZONTAL,8);G.overview_launch_assigned=button("Assigned / detected trainer","primary-action");pack(lwr0,G.overview_launch_assigned,1);pack(launchwith,lwr0,0);
    GtkWidget*lwr1=box(GTK_ORIENTATION_HORIZONTAL,8);G.overview_launch_wemod=button("WeMod","action");G.overview_launch_aurora=button("Aurora — Launch / Close","action");G.overview_launch_cheat_evolution=button("Cheat Evolution — Launch / Close","action");pack(lwr1,G.overview_launch_wemod,1);pack(lwr1,G.overview_launch_aurora,1);pack(lwr1,G.overview_launch_cheat_evolution,1);pack(launchwith,lwr1,0);
    GtkWidget*lwr2=box(GTK_ORIENTATION_HORIZONTAL,8);G.overview_launch_cheat_table=button("Cheat Engine Table (.CT) — Choose / Launch","action");G.overview_launch_custom=button("Choose custom trainer EXE…","action");GtkWidget*olf=button("Open game folder","action");pack(lwr2,G.overview_launch_cheat_table,1);pack(lwr2,G.overview_launch_custom,1);pack(lwr2,olf,1);pack(launchwith,lwr2,0);
    g_signal_connect_data(G.overview_save_profile,"clicked",(GCallback)on_save_launch_profile,NULL,NULL,0);g_signal_connect_data(G.overview_reset_profile,"clicked",(GCallback)on_reset_launch_profile,NULL,NULL,0);g_signal_connect_data(G.overview_launch_assigned,"clicked",(GCallback)on_play,NULL,NULL,0);g_signal_connect_data(G.overview_launch_wemod,"clicked",(GCallback)on_launch_with_wemod,NULL,NULL,0);g_signal_connect_data(G.overview_launch_aurora,"clicked",(GCallback)on_launch_with_aurora,NULL,NULL,0);g_signal_connect_data(G.overview_launch_cheat_evolution,"clicked",(GCallback)on_launch_with_cheat_evolution,NULL,NULL,0);g_signal_connect_data(G.overview_launch_cheat_table,"clicked",(GCallback)on_launch_with_cheat_table,NULL,NULL,0);g_signal_connect_data(G.overview_launch_custom,"clicked",(GCallback)on_launch_custom_trainer,NULL,NULL,0);g_signal_connect_data(olf,"clicked",(GCallback)on_game_folder,NULL,NULL,0);pack(page,launchwith,0);
    if(pc2_discovery_only()){gtk_widget_set_no_show_all(launchwith,TRUE);gtk_widget_hide(launchwith);}

    GtkWidget*lower=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*readiness=box(GTK_ORIENTATION_VERTICAL,9);style(readiness,"panel");gtk_widget_set_size_request(readiness,300,-1);pack(readiness,label("SESSION READINESS","section-kicker"),0);
    GtkWidget*m1=box(GTK_ORIENTATION_HORIZONTAL,10);style(m1,"metric");GtkWidget*m1t=box(GTK_ORIENTATION_VERTICAL,2);pack(m1t,label("GAME","metric-name"),0);G.game_ready=label("Waiting","metric-value");pack(m1t,G.game_ready,0);pack(m1,m1t,1);GtkWidget*m1i=icon_named("applications-games-symbolic",18);if(m1i)pack(m1,m1i,0);pack(readiness,m1,0);
    GtkWidget*m2=box(GTK_ORIENTATION_HORIZONTAL,10);style(m2,"metric");GtkWidget*m2t=box(GTK_ORIENTATION_VERTICAL,2);pack(m2t,label("TRAINER","metric-name"),0);G.wand_ready=label("Waiting","metric-value");pack(m2t,G.wand_ready,0);pack(m2,m2t,1);GtkWidget*m2i=icon_named("applications-engineering-symbolic",18);if(m2i)pack(m2,m2i,0);pack(readiness,m2,0);
    GtkWidget*m3=box(GTK_ORIENTATION_HORIZONTAL,10);style(m3,"metric");GtkWidget*m3t=box(GTK_ORIENTATION_VERTICAL,2);pack(m3t,label("RUNTIME","metric-name"),0);G.compat_ready=label("Waiting","metric-value");pack(m3t,G.compat_ready,0);pack(m3,m3t,1);GtkWidget*m3i=icon_named("emblem-system-symbolic",18);if(m3i)pack(m3,m3i,0);pack(readiness,m3,0);pack(lower,readiness,0);

    GtkWidget*activity=box(GTK_ORIENTATION_VERTICAL,8);style(activity,"panel");GtkWidget*ah=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*aht=box(GTK_ORIENTATION_VERTICAL,1);pack(aht,label("ACTIVITY","section-kicker"),0);pack(aht,label("Current session events","card-title"),0);pack(ah,aht,1);GtkWidget*clear=button("Clear","action");pack(ah,clear,0);pack(activity,ah,0);G.activity=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.activity,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.activity,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.activity,TRUE);gtk_widget_set_name(G.activity,"logframe");GtkWidget*asc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(asc,-1,220);gtk_container_add(asc,G.activity);pack(activity,asc,1);pack(lower,activity,1);

    GtkWidget*context=box(GTK_ORIENTATION_VERTICAL,9);style(context,"panel");gtk_widget_set_size_request(context,275,-1);pack(context,label("SESSION CONTEXT","section-kicker"),0);G.right_game=label("Game source: Not selected\nGame: —\nRuntime: —","muted");gtk_label_set_line_wrap((GtkLabel*)G.right_game,TRUE);pack(context,G.right_game,0);G.right_prefix=label("Prefix: —","good");gtk_label_set_line_wrap((GtkLabel*)G.right_prefix,TRUE);pack(context,G.right_prefix,0);pack(context,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);G.right_wand=label("Provider: —\nTrainer: —","muted");gtk_label_set_line_wrap((GtkLabel*)G.right_wand,TRUE);pack(context,G.right_wand,0);G.right_proton=label("Runtime: —\nStatus: —","good");gtk_label_set_line_wrap((GtkLabel*)G.right_proton,TRUE);pack(context,G.right_proton,0);pack(context,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(context,label("QUICK ACTIONS","section-kicker"),0);GtkWidget*h=quick_button("utilities-system-monitor-symbolic","Check trainer health");GtkWidget*rp=quick_button("applications-engineering-symbolic","Repair compatibility");GtkWidget*gf=quick_button("folder-open-symbolic","Open game folder");GtkWidget*sp=quick_button("external-link-symbolic","Open store page");G.quick_store=sp;g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);g_signal_connect_data(rp,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(gf,"clicked",(GCallback)on_game_folder,NULL,NULL,0);g_signal_connect_data(sp,"clicked",(GCallback)on_steam_page,NULL,NULL,0);pack(context,h,0);pack(context,rp,0);pack(context,gf,0);pack(context,sp,0);pack(lower,context,0);pack(page,lower,1);
    if(pc2_discovery_only()){
        /* Keep the old readiness/log/context widgets allocated for existing
         * refresh and log callbacks, but remove all three diagnostic panels
         * from the PC2 Overview. no-show-all prevents show_all from
         * resurrecting the panel on subsequent navigation. */
        gtk_widget_set_no_show_all(lower,TRUE);
        gtk_widget_hide(lower);
    }
    return outer;
}

/* PC2 Library width adapts to KWin resized windows.
 * Keep the game list readable rather than compressing it to cover thumbnails.
 * GTK emits size-allocate during reflow; only switch orientation across a
 * threshold to avoid redundant size requests / allocation cycles. */
typedef struct {
    GtkWidget *list_sc;
    GtkWidget *inspector;
    int stacked;
} PC2LibraryAdaptive;

static void pc2_library_adaptive_free(void *data,void *closure){
    (void)closure;
    free(data);
}

static void pc2_library_size_allocate(GtkWidget *body,const void *allocation,void *userdata){
    PC2LibraryAdaptive *layout=(PC2LibraryAdaptive*)userdata;
    if(!pc2_discovery_only()||!body||!allocation||!layout)return;
    /* GtkAllocation is four consecutive gint values: x,y,width,height. */
    const int *bounds=(const int*)allocation;
    int available=bounds[2];
    if(available<=0)return;
    /* Small hysteresis avoids repeated flips when window width is close
     * to the layout breakpoint while GTK is recalculating requests. */
    int stacked=(layout->stacked==1)?(available<1070):(available<990);
    if(stacked==layout->stacked)return;
    layout->stacked=stacked;
    gtk_orientable_set_orientation(body,stacked?GTK_ORIENTATION_VERTICAL:GTK_ORIENTATION_HORIZONTAL);
    gtk_widget_set_size_request(layout->list_sc,-1,stacked?300:-1);
    gtk_widget_set_vexpand(layout->list_sc,stacked?FALSE:TRUE);
    gtk_widget_set_size_request(layout->inspector,stacked?-1:350,-1);
}

static GtkWidget *build_library(void){
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,22);
    /* Only PC2 uses this extra scroll viewport for the stacked layout.
     * Legacy PC1 keeps its original Library widget hierarchy. */
    GtkWidget *pc2_outer=NULL;
    if(pc2_discovery_only()){
        pc2_outer=gtk_scrolled_window_new(NULL,NULL);
        gtk_scrolled_window_set_policy((GtkScrolledWindow*)pc2_outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
        gtk_container_add(pc2_outer,p);
    }
    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("LIBRARY","page-kicker"),0);pack(ht,label("All detected games","workspace-title"),0);pack(ht,label("Steam, Steam shortcuts, Heroic and Lutris titles in one working set. Fully resolved Lutris entries support Test 4 launch + same-session local-trainer handoff.","page-subtitle"),0);pack(head,ht,1);char count[64];snprintf(count,sizeof count,"%d games",G.game_count);GtkWidget*ct=label(count,"good");gtk_widget_set_name(ct,"status-pill");pack(head,ct,0);pack(p,head,0);
    GtkWidget*body=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*listpanel=box(GTK_ORIENTATION_VERTICAL,8);style(listpanel,"panel");pack(listpanel,label("GAMES","section-kicker"),0);GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_vexpand(sc,TRUE);G.game_list=gtk_list_box_new();g_signal_connect_data(G.game_list,"row-selected",(GCallback)selected_changed,NULL,NULL,0);
    for(int i=0;i<G.game_count;i++){GtkWidget*r=gtk_list_box_row_new();style(r,"library-row");G.game_rows[i]=r;GtkWidget*rb=box(GTK_ORIENTATION_HORIZONTAL,11);margins(rb,7);GtkWidget*thumb=gtk_image_new();style(thumb,"game-thumb");char art[2048]={0};if(!resolve_game_art(&G.games[i],1,art,sizeof art))resolve_game_art(&G.games[i],0,art,sizeof art);set_image_path(thumb,art[0]?art:NULL,52,70);pack(rb,thumb,0);GtkWidget*txt=box(GTK_ORIENTATION_VERTICAL,3);pack(txt,label(G.games[i].name,"game-row-title"),0);char x[384];if(game_is_steam_shortcut(&G.games[i]))snprintf(x,sizeof x,"Steam shortcut • %s",G.games[i].appid);else if(game_is_steam(&G.games[i]))snprintf(x,sizeof x,"Steam • %s",G.games[i].appid);else if(game_is_lutris(&G.games[i]))snprintf(x,sizeof x,"Lutris • %s",G.games[i].runner[0]?G.games[i].runner:"wine");else snprintf(x,sizeof x,"Heroic • %s",G.games[i].runner);pack(txt,label(x,"muted"),0);pack(rb,txt,1);GtkWidget*installed=label(game_is_lutris(&G.games[i])?"Discovery":"Ready",game_is_lutris(&G.games[i])?"muted":"good");gtk_widget_set_name(installed,"status-pill");pack(rb,installed,0);gtk_container_add(r,rb);gtk_list_box_insert((GtkListBox*)G.game_list,r,-1);}gtk_container_add(sc,G.game_list);pack(listpanel,sc,1);pack(body,listpanel,1);
    GtkWidget*inspect=box(GTK_ORIENTATION_VERTICAL,11);gtk_widget_set_name(inspect,"library-inspector");gtk_widget_set_size_request(inspect,pc2_discovery_only()?350:410,-1);pack(inspect,label("SELECTED GAME","section-kicker"),0);G.library_detail_name=label("Select a game",NULL);gtk_widget_set_name(G.library_detail_name,"library-name");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_name,TRUE);pack(inspect,G.library_detail_name,0);G.library_detail_meta=label("Steam / Heroic / Lutris","library-meta");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_meta,TRUE);pack(inspect,G.library_detail_meta,0);pack(inspect,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(inspect,label("LAUNCH READINESS","section-kicker"),0);G.library_detail_status=label("Choose a game to inspect its runtime and trainer handoff.","muted");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_status,TRUE);pack(inspect,G.library_detail_status,0);G.library_detail_path=label("Install path: —","good");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_path,TRUE);pack(inspect,G.library_detail_path,0);pack(inspect,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(inspect,label("LAUNCH WITH","section-kicker"),0);GtkWidget*lb1=button("Assigned / detected trainer","primary-action");GtkWidget*lbct=button("Cheat Engine Table (.CT) — Choose / Launch","action");GtkWidget*lbw=button("WeMod","action");GtkWidget*lba=button("Cheat Happens Aurora","action");GtkWidget*lbc=button("Cheat Evolution","action");GtkWidget*lbx=button("Choose custom trainer EXE…","action");GtkWidget*lb2=button("Game only","action");GtkWidget*lb3=button("Open game folder","action");GtkWidget*preview=button("Preview Steam launch (no action)","action");GtkWidget*steam_only=button("Launch Steam game only (opt-in)","action");gtk_widget_set_sensitive(steam_only,pc2_steam_launch_allowed());GtkWidget*session_check=button("Check Steam session (read-only)","action");GtkWidget*deckcheatz_detect=button("DeckCheatz 1.x — Detect (no Steam options)","action");g_signal_connect_data(deckcheatz_detect,"clicked",(GCallback)on_pc2_deckcheatz_detect,NULL,NULL,0);GtkWidget*deckcheatz_install=button("Install DeckCheatz 1.x (managed)","action");g_signal_connect_data(deckcheatz_install,"clicked",(GCallback)on_pc2_deckcheatz_install,NULL,NULL,0);GtkWidget*deckcheatz_preview=button("DeckCheatz 1.x — Preview selected game (read-only)","action");g_signal_connect_data(deckcheatz_preview,"clicked",(GCallback)on_pc2_deckcheatz_preview,NULL,NULL,0);GtkWidget*deckcheatz_test=button(pc2_steam_wemod_allowed()?
            "Play via Steam + WeMod (private test)":pc2_native_wrapper_allowed()?
            "Launch native Rust wrapper + WeMod (experimental)":pc2_steam_launch_allowed()?
            "Play via Steam + DeckCheatz":"Set up one-session DeckCheatz","primary-action");G.pc2_deckcheatz_library_play=deckcheatz_test;g_signal_connect_data(deckcheatz_test,"clicked",(GCallback)on_pc2_bridge_primary,NULL,NULL,0);g_signal_connect_data(lb1,"clicked",(GCallback)on_play,NULL,NULL,0);g_signal_connect_data(lbct,"clicked",(GCallback)on_launch_with_cheat_table,NULL,NULL,0);g_signal_connect_data(lbw,"clicked",(GCallback)on_launch_with_wemod,NULL,NULL,0);g_signal_connect_data(lba,"clicked",(GCallback)on_launch_with_aurora,NULL,NULL,0);g_signal_connect_data(lbc,"clicked",(GCallback)on_launch_with_cheat_evolution,NULL,NULL,0);g_signal_connect_data(lbx,"clicked",(GCallback)on_launch_custom_trainer,NULL,NULL,0);g_signal_connect_data(lb2,"clicked",(GCallback)on_play_normal,NULL,NULL,0);g_signal_connect_data(lb3,"clicked",(GCallback)on_game_folder,NULL,NULL,0);g_signal_connect_data(preview,"clicked",(GCallback)on_steam_launch_preview,NULL,NULL,0);g_signal_connect_data(steam_only,"clicked",(GCallback)on_pc2_steam_game_only,NULL,NULL,0);g_signal_connect_data(session_check,"clicked",(GCallback)on_pc2_steam_session_check,NULL,NULL,0);if(pc2_discovery_only()){
        pack(inspect,deckcheatz_test,0);
        G.pc2_deckcheatz_library_status=label("Select an installed Steam game to use WeMod.","muted");
        gtk_label_set_line_wrap((GtkLabel*)G.pc2_deckcheatz_library_status,TRUE);
        pack(inspect,G.pc2_deckcheatz_library_status,0);
        if(pc2_native_wrapper_allowed()){
            GtkWidget*npreview=button("Preview native Rust wrapper (no launch)","action");
            GtkWidget*nlaunch=button("Launch native Rust wrapper + WeMod (experimental)","primary-action");
            g_signal_connect_data(npreview,"clicked",(GCallback)on_pc2_native_wrapper_preview,NULL,NULL,0);
            g_signal_connect_data(nlaunch,"clicked",(GCallback)on_pc2_native_wrapper_launch,NULL,NULL,0);
            pack(inspect,npreview,0);pack(inspect,nlaunch,0);
        }
        GtkWidget*advanced=gtk_expander_new("Advanced trainer / launch diagnostics");
        GtkWidget*tools=box(GTK_ORIENTATION_VERTICAL,8);
        gtk_container_add(advanced,tools);
        pack(tools,deckcheatz_detect,0);
        pack(tools,deckcheatz_install,0);
        pack(tools,deckcheatz_preview,0);
        pack(tools,steam_only,0);
        pack(tools,session_check,0);
        pack(tools,preview,0);
        pack(inspect,advanced,0);
    }else{
        pack(inspect,lb1,0);pack(inspect,lbct,0);pack(inspect,lbw,0);
        pack(inspect,lba,0);pack(inspect,lbc,0);pack(inspect,lbx,0);
        pack(inspect,lb2,0);pack(inspect,lb3,0);pack(inspect,preview,0);
        pack(inspect,steam_only,0);pack(inspect,session_check,0);
    }pack(inspect,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(inspect,label("TIP","section-kicker"),0);GtkWidget*tip=label("Use the search dropdown above to choose All games, Steam, Steam shortcuts, Heroic, Lutris, or Trainers. Lutris launch integration is intentionally disabled in Test 1; trainer searches jump directly to Trainer Library.","muted");gtk_label_set_line_wrap((GtkLabel*)tip,TRUE);pack(inspect,tip,0);pack(body,inspect,0);
    if(pc2_discovery_only()){
        PC2LibraryAdaptive *adaptive=calloc(1,sizeof *adaptive);
        if(adaptive){
            adaptive->list_sc=sc;
            adaptive->inspector=inspect;
            adaptive->stacked=-1;
            g_signal_connect_data(body,"size-allocate",(GCallback)pc2_library_size_allocate,
                adaptive,pc2_library_adaptive_free,0);
        }
    }
    pack(p,body,1);return pc2_outer?pc2_outer:p;
}


static void on_enable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Native converted-table profiles are not enabled for Steam non-Steam shortcuts.");return;}if(!game_is_steam(g)){log_line("Native converted-table profiles are currently Steam-only.");return;}const char*p=available_native_profile(g->appid);if(!p){log_line("No native trainer profile is available for %s yet.",g->name);return;}if(save_native_profile(game_key(g),p))log_line("Native trainer profile enabled for %s: %s",g->name,p);else log_line("Could not save native profile configuration.");refresh_ui();}
static void on_disable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(save_native_profile(game_key(g),NULL))log_line("Native trainer profile disabled for %s.",g->name);refresh_ui();}

/* RC10: optional read-only upgrade preflight. Only an explicit Export action
 * writes a private report. Never modify assignments, caches, game sessions,
 * or trainer executables while checking upgrade readiness. */
static int bounded_child_output(pid_t,int,char*,size_t,int);
static GtkWidget *stability_preflight_status=NULL;
static int stability_preflight_busy=0;
typedef struct {char result[1500];int ok;} StabilityPreflightJob;
static gboolean stability_preflight_done(void *data){
    StabilityPreflightJob*j=data;
    stability_preflight_busy=0;
    if(stability_preflight_status)
        set_label(stability_preflight_status,j->ok?j->result:"Stability preflight did not complete. No settings or trainers were modified; inspect the local report destination before retrying.");
    free(j);return FALSE;
}
static void *stability_preflight_worker(void *data){
    StabilityPreflightJob*j=data;
    int fds[2];if(pipe(fds)!=0){g_idle_add(stability_preflight_done,j);return NULL;}
    pid_t pid=fork();
    if(pid==0){
        setpgid(0,0);close(fds[0]);dup2(fds[1],STDOUT_FILENO);close(fds[1]);
        const char*appdir=getenv("APPDIR");char tool[2200];
        if(appdir&&*appdir)snprintf(tool,sizeof tool,"%s/usr/libexec/gameweld-stability-preflight.py",appdir);
        else snprintf(tool,sizeof tool,"gameweld-stability-preflight.py");
        execlp("python3","python3",tool,"--export",(char*)NULL);_exit(127);
    }
    close(fds[1]);
    if(pid<0){close(fds[0]);g_idle_add(stability_preflight_done,j);return NULL;}
    char output[1100]={0};
    j->ok=bounded_child_output(pid,fds[0],output,sizeof output,20);
    if(j->ok&&strncmp(output,"PREFLIGHT\t",10)==0){
        char*line=output+10;char*tab=strchr(line,'\t');
        if(tab){*tab++=0;snprintf(j->result,sizeof j->result,"Stability preflight: %s. Report saved: %s\nConfiguration checked only; checkbox launch gates are NOT verified automatically.",line,tab);}
        else j->ok=0;
    }else j->ok=0;
    g_idle_add(stability_preflight_done,j);return NULL;
}
static void on_stability_preflight(GtkButton*b,void*d){
    (void)b;(void)d;
    if(stability_preflight_busy)return;
    StabilityPreflightJob*j=calloc(1,sizeof *j);if(!j)return;
    stability_preflight_busy=1;
    if(stability_preflight_status)set_label(stability_preflight_status,"Checking local trainer assignments, update cache, and catalog metadata without changing them…");
    pthread_t t;if(pthread_create(&t,NULL,stability_preflight_worker,j)==0)pthread_detach(t);
    else{stability_preflight_busy=0;free(j);if(stability_preflight_status)set_label(stability_preflight_status,"Could not start stability preflight; nothing changed.");}
}

static void on_scan_trainer_library(GtkButton*b,void*d){(void)b;(void)d;start_trainer_library_scan();}
static void on_refresh_trainer_library(GtkButton*b,void*d){(void)b;(void)d;refresh_trainer_library_view();}
static void on_rescan_selected_trainer(GtkButton*b,void*d){(void)b;(void)d;start_selected_trainer_scan();}
static void set_trainer_version_policy_ui(const char *value){
    pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"set-policy",value,(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer duplicate-version policy changed to: %s. Rescanning to apply it.",value);refresh_trainer_library_view();start_trainer_library_scan();}else log_line("Could not save Trainer Library version policy: %s",value);
}
static void on_policy_ask(GtkButton*b,void*d){(void)b;(void)d;set_trainer_version_policy_ui("ask");}
static void on_policy_keep(GtkButton*b,void*d){(void)b;(void)d;set_trainer_version_policy_ui("keep-current");}
static void on_policy_newest(GtkButton*b,void*d){(void)b;(void)d;set_trainer_version_policy_ui("prefer-newest");}
static void on_prune_missing_trainers(GtkButton*b,void*d){
    (void)b;(void)d;pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"prune-missing",(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer Library removed stale missing mappings from GameWeld configuration. Trainer EXE files were not deleted.");refresh_ui();start_trainer_library_scan();}else log_line("Could not prune missing Trainer Library mappings.");
}
static void on_assign_suggested_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a trainer row in Trainer Library first.");return;}int idx=trainer_game_index_by_key(G.trainer_library_pick_key);if(idx<0){log_line("This trainer has no exact suggested game. Choose the intended game in Library and use Assign to Selected Game.");return;}Game*g=&G.games[idx];if(save_local_trainer(game_key(g),G.trainer_library_pick_path)){G.selected=idx;log_line("Trainer Library assignment: %s → %s",g->name,G.trainer_library_pick_path);refresh_ui();refresh_trainer_library_view();start_selected_trainer_scan();}else log_line("Could not save Trainer Library assignment for %s.",g->name);}
static void on_select_suggested_library_game(GtkButton*b,void*d){(void)b;(void)d;int idx=trainer_game_index_by_key(G.trainer_library_pick_key);if(idx<0){log_line("This trainer has no exact suggested game to select.");return;}G.selected=idx;log_line("Trainer Library target selected: %s",G.games[idx].name);refresh_ui();refresh_trainer_library_view();}
static void launch_manager_standalone_selected(void){
    if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a readable manager row in Trainer Library first.");return;}
    TrainerManagerPlan mp={0};if(!trainer_manager_plan_for_path(G.trainer_library_pick_path,&mp)){log_line("Manager launch blocked: package fingerprint or runtime plan could not be resolved for %s.",G.trainer_library_pick_path);return;}
    if(!strcmp(mp.status,"no-runtime")){log_line("Manager launch blocked: no Wine/Proton runtime was found. Install Wine, a Heroic/Lutris Wine runner, or Steam Proton and retry. Planned prefix: %s",mp.prefix);return;}
    if(!strcmp(mp.status,"running")){pid_t sp=fork();if(sp==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_tool(),trainer_manager_tool(),"stop",G.trainer_library_pick_path,(char*)NULL);_exit(127);}if(sp<0)log_line("Could not stop standalone trainer manager %s.",mp.label);else log_line("Closing standalone trainer manager: %s…",mp.label);return;}
    pid_t p=fork();if(p==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_tool(),trainer_manager_tool(),"launch",G.trainer_library_pick_path,(char*)NULL);_exit(127);}if(p<0){log_line("Could not start standalone trainer manager launcher for %s.",mp.label);return;}
    log_line("Launching trainer manager standalone: %s • %s runtime %s • dedicated prefix %s • log %s",mp.label,mp.runtime_kind,mp.runtime,mp.prefix,mp.log);
}

static void launch_manager_for_selected_game(void){
    if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a readable manager row in Trainer Library first.");return;}
    if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first, or use Launch manager standalone.");return;}
    Game*g=&G.games[G.selected];if(lutris_test4_extended_blocked(g,"Trainer Library manager attach"))return;TrainerManagerGamePlan gp={0};if(!trainer_manager_game_plan_for(G.trainer_library_pick_path,g,&gp)){log_line("Manager/game launch plan could not be resolved for %s.",g->name);return;}
    if(!strcmp(gp.status,"running")){stop_manager_path_for_game(G.trainer_library_pick_path,g);return;}
    if(strcmp(gp.status,"ready")){log_line("Manager/game launch blocked for %s: %s (%s)",g->name,gp.reason[0]?gp.reason:"No compatible live session is available.",gp.status);return;}
    pid_t p=fork();if(p==0){int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,STDIN_FILENO);dup2(dn,STDOUT_FILENO);dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}clear_desktop_activation_env();execl(trainer_manager_game_tool(),trainer_manager_game_tool(),"launch",G.trainer_library_pick_path,g->provider,g->runner,g->appid,game_key(g),g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,g->compatdata,g->launch_id,(char*)NULL);_exit(127);}if(p<0){log_line("Could not start manager/game integration launcher for %s.",g->name);return;}
    log_line("Launching %s for running game %s • same-session %s runtime %s • prefix %s • log %s",gp.label,g->name,gp.session_kind,gp.runtime,gp.prefix,gp.log);
}

static void on_launch_manager_standalone_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(strcmp(G.trainer_library_pick_state,"Manager")){log_line("Select a trainer-manager row first.");return;}launch_manager_standalone_selected();}

static void on_launch_assigned_library_pick(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a readable trainer or manager row in Trainer Library first.");return;}
    if(!strcmp(G.trainer_library_pick_state,"Manager")){
        if(G.selected>=0&&G.selected<G.game_count){TrainerManagerGamePlan gp={0};if(trainer_manager_game_plan_for(G.trainer_library_pick_path,&G.games[G.selected],&gp)&&(!strcmp(gp.status,"ready")||!strcmp(gp.status,"running"))){launch_manager_for_selected_game();return;}log_line("The selected game does not currently expose a compatible live session for manager attachment. Start the game first, or use Launch manager standalone.");return;}
        launch_manager_standalone_selected();return;
    }
    int idx=trainer_game_index_by_key(G.trainer_library_pick_key);if(idx<0){log_line("This trainer has no assigned game target yet. Assign it before launching.");return;}
    if(G.selected!=idx){log_line("Trainer launch blocked: selected game differs from the trainer row. Re-select the trainer so its game context synchronizes.");return;}
    Game*g=&G.games[idx];if(game_is_lutris(g)&&!lutris_session_ready(g)){log_line("Direct trainer launch blocked for Lutris %s: prefix, target or configured runtime is unresolved.",g->name);return;}if(game_is_steam_shortcut(g)&&!g->shortcut_launch_supported){log_line("Direct trainer launch blocked for Steam non-Steam shortcut %s: runtime/prefix resolution is incomplete. Launch it once from Steam with compatibility enabled, then Refresh Game Sources.",g->name);return;}char assigned[2048]={0};if(!(load_local_trainer(game_key(g),assigned,sizeof assigned)&&readable_file(assigned)&&!strcmp(assigned,G.trainer_library_pick_path))){log_line("Direct launch blocked: %s is not the trainer currently assigned to %s. Assign or switch to this trainer first.",G.trainer_library_pick_path,g->name);update_trainer_library_actions();return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Direct launch blocked: trainer runtime repair is still active for %s. Wait for completion or cancel the repair first.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Trainer runtime repair is still active. Wait for completion or cancel it before launching the game.");return;}G.selected=idx;refresh_ui();log_line("Trainer Library launching %s with its assigned local trainer: %s",g->name,assigned);if(game_is_steam_shortcut(g))spawn_steam_shortcut_trainer(g,assigned);else if(game_is_steam(g))spawn_local_trainer(g->appid,assigned);else if(game_is_lutris(g))spawn_lutris_trainer(g,assigned);else spawn_heroic_trainer(g,assigned);
}

static void on_assign_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose the target game in Library first.");return;}if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a trainer row in Trainer Library first.");return;}Game*g=&G.games[G.selected];int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);if(trainer_pick_is_strong_target()&&suggested>=0&&strcmp(game_key(g),G.trainer_library_pick_key)){log_line("Assignment blocked for safety: %s is matched to %s, not %s. Use Assign to Suggested Game or select %s first.",G.trainer_library_pick_path,G.games[suggested].name,g->name,G.games[suggested].name);return;}if(save_local_trainer(game_key(g),G.trainer_library_pick_path)){log_line("Trainer Library assignment: %s → %s",g->name,G.trainer_library_pick_path);refresh_ui();refresh_trainer_library_view();start_selected_trainer_scan();}else log_line("Could not save Trainer Library assignment for %s.",g->name);}
static void on_ignore_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]){log_line("Choose a trainer row in Trainer Library first.");return;}char path[2048];snprintf(path,sizeof path,"%s",G.trainer_library_pick_path);pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"ignore",path,(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer Library will ignore: %s",path);G.trainer_library_pick_path[0]=0;G.trainer_library_pick_game[0]=0;G.trainer_library_pick_key[0]=0;G.trainer_library_pick_state[0]=0;if(G.trainer_library_pick)set_label(G.trainer_library_pick,"Select a trainer row to review its compatibility profile, suggested game/version, assign it safely, switch to an alternative version, reassign an ambiguous/unmatched trainer, or ignore it.");refresh_trainer_library_view();}else log_line("Could not add trainer to the ignore list: %s",path);}
static void on_clear_ignored_trainers(GtkButton*b,void*d){(void)b;(void)d;pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"clear-ignored",(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer Library ignore list cleared. Rescan to rediscover those trainer executables.");refresh_trainer_library_view();}else log_line("Could not clear the Trainer Library ignore list.");}
static void set_selected_trainer_profile_policy(const char*mode,const char*label){if(!G.trainer_library_pick_path[0]){log_line("Choose a trainer row in Trainer Library first.");return;}char path[2048];snprintf(path,sizeof path,"%s",G.trainer_library_pick_path);pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"set-profile-policy",path,mode,(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer launch policy changed: %s -> %s",path,label);refresh_trainer_library_view();}else log_line("Could not save trainer launch policy for: %s",path);}
static void on_profile_policy_auto(GtkButton*b,void*d){(void)b;(void)d;set_selected_trainer_profile_policy("auto","Auto Detect");}
static void on_profile_policy_managed(GtkButton*b,void*d){(void)b;(void)d;set_selected_trainer_profile_policy("managed-fling","Force Managed FLiNG (Heroic)");}
static void on_profile_policy_inherit(GtkButton*b,void*d){(void)b;(void)d;set_selected_trainer_profile_policy("inherit","Force Inherit Session");}
static void on_trainer_library_recommended_action(GtkButton*b,void*d){
    (void)b;(void)d;const char*code=G.trainer_library_action_code;
    if(!code||!*code){log_line("Trainer Library: select a row with an available recommended action first.");return;}
    if(!strcmp(code,"launch")||!strcmp(code,"launch-manager")){on_launch_assigned_library_pick(NULL,NULL);return;}
    if(!strcmp(code,"launch-manager-game")){launch_manager_for_selected_game();return;}
    if(!strcmp(code,"assign-suggested")){on_assign_suggested_library_pick(NULL,NULL);return;}
    if(!strcmp(code,"assign-selected")){on_assign_library_pick(NULL,NULL);return;}
    if(!strcmp(code,"open-folder")){on_open_selected_trainer_folder(NULL,NULL);return;}
    if(!strcmp(code,"rescan-selected")){on_rescan_selected_trainer(NULL,NULL);return;}
    if(!strcmp(code,"rescan-suggested")){int idx=trainer_game_index_by_key(G.trainer_library_pick_key);if(idx<0){log_line("Recommended rescan target is no longer available.");return;}G.selected=idx;refresh_ui();on_rescan_selected_trainer(NULL,NULL);return;}
    log_line("Trainer Library: unknown recommended action '%s'; no changes were made.",code);
}
static void on_add_trainer_folder(GtkButton*b,void*d){
    (void)b;(void)d;GtkWidget*dlg=gtk_file_chooser_dialog_new("Add Trainer Search Folder",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER,"Cancel",GTK_RESPONSE_CANCEL,"Add Folder",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);
    if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"add-root",fn,(char*)NULL);_exit(127);}int st=0;if(p>0){while(waitpid(p,&st,0)<0&&errno==EINTR){}if(WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer search folder added: %s",fn);start_trainer_library_scan();}else log_line("Could not add trainer search folder: %s",fn);}}if(fn)g_free(fn);}gtk_widget_destroy(dlg);
}
static void on_choose_local_trainer(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose local Windows trainer EXE",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Trainer",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){if(save_local_trainer(game_key(&G.games[G.selected]),fn)){log_line("Local trainer configured for %s: %s",G.games[G.selected].name,fn);}else log_line("Could not save local trainer configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();refresh_trainer_library_view();}
static void on_clear_local_trainer(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;if(save_local_trainer(game_key(&G.games[G.selected]),NULL))log_line("Local trainer cleared for %s; default launcher action restored.",G.games[G.selected].name);refresh_ui();refresh_trainer_library_view();}
static void on_stop_heroic_trainer(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("Stop Stuck Trainer is available only for Heroic sessions.");return;}char lt[2048]={0};if(!(load_local_trainer(game_key(g),lt,sizeof lt)&&readable_file(lt))){log_line("No local trainer is configured for %s.",g->name);return;}spawn_heroic_session_control(g,"stop-trainer",lt);log_line("Stopping the configured trainer for %s. If it ignores a normal close, GameWeld will force-stop that trainer process only.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Stopping stuck trainer… the game is left running. See ~/.local/state/gameweld/heroic-session-control-*.log for details.");}
static void on_reset_heroic_prefix(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("Reset Heroic Prefix is available only for Heroic games.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);spawn_heroic_session_control(g,"reset-prefix",lt);log_line("Resetting the complete Heroic Wine/Proton session for %s. This closes the game, trainer and other Windows processes in that prefix.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Resetting Heroic prefix session… this closes the game and every Windows sidecar in this prefix.");}
static void on_check_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("FLiNG runtime check currently targets Heroic prefixes only.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"status",lt);log_line("Checking trainer runtime prerequisites for %s. The status below will update automatically when the check finishes.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Checking Heroic trainer runtime... looking for wininet, .NET Framework 4.8 and .NET 8 plus a repair-only compatibility runtime.");}
static void on_download_heroic_repair_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("Managed trainer repair runtime currently targets Heroic prefixes only.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"download-helper",lt);log_line("Downloading the managed repair-only runtime for %s. This does not change Heroic's configured game runner.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Downloading GameWeld repair-only runtime (about 500 MB)... Heroic's selected Wine/Proton version will not be changed.");}
static void on_repair_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("Adaptive Trainer Runtime Repair currently targets Heroic prefixes only.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"repair",lt);log_line("Starting adaptive trainer runtime repair for %s. GameWeld keeps Heroic's selected game runner unchanged and uses a separate repair-only runtime for legacy dependencies.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Repairing trainer runtime... the game stays on its selected Wine/Proton version. GameWeld uses a separate repair-only runtime to install .NET 4.8 + .NET 8 + wininet into this prefix while the game is closed.");}
static void on_cancel_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(!game_is_heroic(g)){log_line("Cancel Runtime Repair is for Heroic prefixes only.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"cancel",lt);log_line("Cancelling any active FLiNG runtime repair for %s. After cancelling an in-progress Winetricks install, reset the Heroic prefix before launching.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Cancelling FLiNG runtime repair… then use Reset Heroic Prefix before launching if Winetricks was interrupted.");}
static void on_choose_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Windows Cheat Engine EXE",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Cheat Engine",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){if(save_cheat_engine(fn))log_line("Cheat Engine configured: %s",fn);else log_line("Could not save Cheat Engine configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_clear_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(save_cheat_engine(NULL))log_line("Cheat Engine executable cleared.");refresh_ui();}
static void on_open_cheat_engine_download(GtkButton*b,void*d){(void)b;(void)d;spawn_detached("xdg-open","https://cheatengine.org/download/CheatEngineLinux771.zip",NULL);log_line("Opened the official Cheat Engine Linux 7.7.1 download.");}
static void on_open_cheat_engine_windows_download(GtkButton*b,void*d){(void)b;(void)d;spawn_detached("xdg-open","https://cheatengine.org/downloads.php",NULL);log_line("Opened the official Cheat Engine downloads page for the Windows CE companion.");}
static void on_download_install_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}log_line("Downloading and installing official native Cheat Engine Linux 7.7.1 from cheatengine.org...");const char *ceid=game_ce_id(&G.games[G.selected]);ce_install_watch(spawn_managed_ce_download_install(ceid),ceid);if(G.cheat_table_status)set_label(G.cheat_table_status,"Installing official Cheat Engine. GameWeld will verify it automatically after the installer exits.");}
static void on_install_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}char installer[2048]={0};if(!(load_cheat_engine_installer(installer,sizeof installer)&&readable_file(installer))){GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose official Cheat Engine Linux ZIP or Windows installer",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Install with GameWeld",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){snprintf(installer,sizeof installer,"%s",fn);save_cheat_engine_installer(fn);}if(fn)g_free(fn);}gtk_widget_destroy(dlg);}if(!readable_file(installer)){log_line("Managed Cheat Engine install cancelled: no package selected.");refresh_ui();return;}log_line("Installing managed Cheat Engine package: %s",installer);const char *ceid=game_ce_id(&G.games[G.selected]);ce_install_watch(spawn_managed_ce_install(ceid,installer),ceid);if(G.cheat_table_status)set_label(G.cheat_table_status,"Cheat Engine installation started. GameWeld automatically checks for the installed executable when finished.");}
static void on_choose_cheat_engine_installer(GtkButton*b,void*d){(void)b;(void)d;GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose official Cheat Engine Linux ZIP or Windows installer",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Package",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){if(save_cheat_engine_installer(fn))log_line("Cheat Engine package saved: %s",fn);}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_detect_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}char ce[2048]={0},wce[2048]={0};if(detect_managed_cheat_engine(game_ce_id(&G.games[G.selected]),ce,sizeof ce))log_line("Managed Linux Cheat Engine detected: %s",ce);else log_line("Managed Linux Cheat Engine not detected.");if(detect_managed_windows_ce(game_ce_id(&G.games[G.selected]),wce,sizeof wce))log_line("Windows CE Proton companion ready: %s",wce);else log_line("Windows CE Proton companion not detected yet.");refresh_ui();}
static void on_choose_cheat_table(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Cheat Engine .CT table",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Table",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){const char*dot=strrchr(fn,'.');if(!dot||strcasecmp(dot,".ct"))log_line("Warning: selected file does not use the .CT extension: %s",fn);if(save_cheat_table(game_key(&G.games[G.selected]),fn))log_line("Cheat table configured for %s: %s",G.games[G.selected].name,fn);else log_line("Could not save Cheat Table configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_clear_cheat_table(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;if(save_cheat_table(game_key(&G.games[G.selected]),NULL))log_line("Cheat table cleared for %s.",G.games[G.selected].name);refresh_ui();}

static int bounded_child_output(pid_t pid,int fd,char *output,size_t capacity,int seconds);
/* Test 8: durable bounded background update queue for assigned game trainers. */
typedef struct {
    int mode, count, force, ok, enabled, budget, include_unassigned;
    char names[256][384];
    char trainer_paths[256][2048];
    char summary[1800];
    char details[2600];
    char available[1800], updates[1800], managers[1800];
} TrainerMonitorJob;
static const char *trainer_monitor_tool(void){
    static char path[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(path,sizeof path,"%s/usr/libexec/gameweld-update-monitor.py",appdir);
    else snprintf(path,sizeof path,"%s/scripts/gameweld-update-monitor.py",getenv("GAMEWELD_SOURCE_ROOT")?getenv("GAMEWELD_SOURCE_ROOT"):".");
    return path;
}
static gboolean trainer_monitor_done(void *ptr){
    TrainerMonitorJob*j=ptr;G.trainer_monitor_busy=0;
    if(j->mode!=9 && j->ok && j->enabled>=0){
        G.trainer_monitor_enabled=j->enabled;
        G.trainer_monitor_include_unassigned=j->include_unassigned;
        if(G.trainer_monitor_discovery){
            G.trainer_monitor_syncing=1;
            gtk_toggle_button_set_active((GtkToggleButton*)G.trainer_monitor_discovery,j->include_unassigned);
            G.trainer_monitor_syncing=0;
        }
        if(G.trainer_monitor_toggle)gtk_button_set_label((GtkButton*)G.trainer_monitor_toggle,j->enabled?"Pause automatic checks":"Resume automatic checks");
        if(G.trainer_monitor_budget && j->budget>0){
            char selected[16];snprintf(selected,sizeof selected,"%d",j->budget);
            G.trainer_monitor_syncing=1;
            gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_monitor_budget,selected);
            G.trainer_monitor_syncing=0;
        }
    }
    if(j->mode==9){
        if(G.trainer_dashboard_status)set_label(G.trainer_dashboard_status,j->summary[0]?j->summary:"Dashboard unavailable.");
        if(G.trainer_dashboard_available)set_label(G.trainer_dashboard_available,j->available[0]?j->available:"No trainer leads in cache.");
        if(G.trainer_dashboard_updates)set_label(G.trainer_dashboard_updates,j->updates[0]?j->updates:"No assigned trainer evidence.");
        if(G.trainer_dashboard_managers)set_label(G.trainer_dashboard_managers,j->managers[0]?j->managers:"No managers detected in cache.");
        free(j);return FALSE;
    }
    if(G.trainer_monitor_status){
        set_label(G.trainer_monitor_status,j->summary[0]?j->summary:"No update-monitor report available.");
        if(j->mode==3 && G.trainer_monitor_details){
            set_label(G.trainer_monitor_details,j->details[0]?j->details:"No individual update records currently queued.");
        }
    }
    if(j->ok)log_line("Trainer automatic updates: %s",j->summary);
    else log_line("Trainer automatic update check failed: %s",j->summary);
    free(j);return FALSE;
}
static void *trainer_monitor_worker(void *ptr){
    TrainerMonitorJob*j=ptr;int fd[2];
    if(pipe(fd)<0){snprintf(j->summary,sizeof j->summary,"Could not start update monitor: pipe unavailable.");g_idle_add(trainer_monitor_done,j);return NULL;}
    pid_t pid=fork();
    if(pid==0){
        close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);
        int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}
        const char*argv[1050];int n=0;argv[n++]="python3";argv[n++]=trainer_monitor_tool();
        char budget_arg[16];snprintf(budget_arg,sizeof budget_arg,"%d",j->budget);
        if(j->mode==1||j->mode==2){argv[n++]="set-enabled";argv[n++]=(j->mode==1)?"off":"on";}
        else if(j->mode==3){argv[n++]="status";argv[n++]="--compact";}
        else if(j->mode==9){argv[n++]="dashboard";argv[n++]="--compact";}
        else if(j->mode==6){argv[n++]="report";argv[n++]="--compact";}
        else if(j->mode==7){argv[n++]="recover-metadata";argv[n++]="--compact";}
        else if(j->mode==4){argv[n++]="set-budget";argv[n++]=budget_arg;}
        else if(j->mode==5){argv[n++]="set-discovery";argv[n++]=j->include_unassigned?"on":"off";}
        else{
            argv[n++]=(j->mode==8)?"sync-local":"scan";argv[n++]="--compact";if(j->force && j->mode==0)argv[n++]="--force";
            for(int i=0;i<j->count&&i<256;i++){
                argv[n++]="--game";argv[n++]=j->names[i];
                argv[n++]="--trainer-path";argv[n++]=j->trainer_paths[i];
            }
        }
        argv[n]=NULL;execvp("python3",(char*const*)argv);_exit(127);
    }
    close(fd[1]);char output[16384]={0};
    if(pid<0){close(fd[0]);snprintf(j->summary,sizeof j->summary,"Could not launch update-monitor helper.");g_idle_add(trainer_monitor_done,j);return NULL;}
    j->ok=bounded_child_output(pid,fd[0],output,sizeof output,(j->mode==0||j->mode==7)?105:10);
    if(j->ok){
        j->enabled=json_bool(output,"enabled",j->mode==9?G.trainer_monitor_enabled:-1);
        j->include_unassigned=json_bool(output,"include_unassigned",G.trainer_monitor_include_unassigned);
        const char *budget_key=find_key(output,"budget");
        if(budget_key){int b=0;const char *colon=strchr(budget_key,':');if(colon&&sscanf(colon+1,"%d",&b)==1)j->budget=b;}
        json_string(output,"summary",j->summary,sizeof j->summary);
        json_string(output,"details",j->details,sizeof j->details);
        if(j->mode==9){
            json_string(output,"available",j->available,sizeof j->available);
            json_string(output,"updates",j->updates,sizeof j->updates);
            json_string(output,"managers",j->managers,sizeof j->managers);
        }
        if(!j->summary[0])snprintf(j->summary,sizeof j->summary,"Update monitor completed; no confirmed downloadable release.");
    }else{
        char error[512]={0};json_string(output,"error",error,sizeof error);
        snprintf(j->summary,sizeof j->summary,"Update monitoring failed%s%s. No trainer or Wine prefix was modified.",error[0]?": ":"",error);
    }
    g_idle_add(trainer_monitor_done,j);return NULL;
}
static void trainer_monitor_submit(int mode,int force){
    if(G.trainer_monitor_busy)return;
    TrainerMonitorJob*j=calloc(1,sizeof *j);if(!j)return;
    j->mode=mode;j->force=force;j->enabled=-1;
    j->budget=12;
    j->include_unassigned=G.trainer_monitor_include_unassigned;
    if(mode==5 && G.trainer_monitor_discovery)j->include_unassigned=gtk_toggle_button_get_active((GtkToggleButton*)G.trainer_monitor_discovery);
    if(mode==4 && G.trainer_monitor_budget){
        const char*id=gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_monitor_budget);
        j->budget=id?atoi(id):12;
    }
    if(mode==0||mode==8){
        /* Include assigned titles first, then unassigned discovery. A fixed 128-title cap
         * and the helper's daily network budget keep startup work bounded. */
        for(int pass=0;pass<2;pass++)for(int i=0;i<G.game_count&&j->count<256;i++){
            char trainer[2048]={0};
            int assigned=load_local_trainer(game_key(&G.games[i]),trainer,sizeof trainer)&&readable_file(trainer);
            if((pass==0&&!assigned)||(pass==1&&(assigned||!j->include_unassigned)))continue;
            int repeat=0;for(int x=0;x<j->count;x++)if(!strcmp(j->names[x],G.games[i].name))repeat=1;
            if(!repeat){
                snprintf(j->names[j->count],sizeof j->names[0],"%s",G.games[i].name);
                snprintf(j->trainer_paths[j->count],sizeof j->trainer_paths[0],"%s",assigned?trainer:"");
                j->count++;
            }
        }
        if(j->count==0){free(j);if(G.trainer_monitor_status)set_label(G.trainer_monitor_status,"No game titles to check. Enable unassigned-game discovery or select a game.");return;}
    }
    G.trainer_monitor_busy=1;
    if(G.trainer_monitor_status)set_label(G.trainer_monitor_status,mode==0?"Checking due trainer releases in the background. No downloads or installs will run.":"Loading saved update-monitor settings…");
    pthread_t thread;
    if(pthread_create(&thread,NULL,trainer_monitor_worker,j)==0)pthread_detach(thread);
    else{G.trainer_monitor_busy=0;free(j);}
}
static void on_refresh_trainer_dashboard(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(9,0);}
static gboolean trainer_dashboard_initial(void*unused){(void)unused;trainer_monitor_submit(9,0);return FALSE;}
static gboolean trainer_monitor_tick(void*unused){(void)unused;trainer_monitor_submit(0,0);return TRUE;}
static gboolean trainer_monitor_first_tick(void*unused){(void)unused;trainer_monitor_submit(0,0);return FALSE;}
static void on_monitor_check(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(0,0);}
static void on_monitor_queue(GtkButton*b,void*d){(void)b;(void)d;if(G.trainer_monitor_details_expander)gtk_expander_set_expanded(G.trainer_monitor_details_expander,TRUE);trainer_monitor_submit(3,0);}
static void on_monitor_report(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(6,0);}
static void on_monitor_recover(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(7,0);}
static void on_monitor_local_sync(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(8,0);}
static void on_monitor_pause(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(1,0);}
static void on_monitor_resume(GtkButton*b,void*d){(void)b;(void)d;trainer_monitor_submit(2,0);}
static void on_monitor_toggle(GtkButton*b,void*d){(void)b;(void)d;
    trainer_monitor_submit(G.trainer_monitor_enabled==0?2:1,0);
}
static void on_monitor_budget(GtkComboBox*b,void*d){(void)b;(void)d;
    if(!G.trainer_monitor_syncing)trainer_monitor_submit(4,0);
}
static void on_monitor_discovery(GtkToggleButton*b,void*d){(void)b;(void)d;
    if(!G.trainer_monitor_syncing)trainer_monitor_submit(5,0);
}
static gboolean trainer_monitor_initial_status(void*d){(void)d;trainer_monitor_submit(3,0);return FALSE;}

/* Test 7 trainer downloads: verify catalog metadata and keep network off GTK thread. */
typedef struct {char game[512],key[320],provider[64],catalog_id[128],version[128],sha256[65],download_url[1024],official[200],message[2048],installed[4096];int ok,install,inspect,rollback,offline,trust_audit,source_audit;unsigned long long context_epoch;char provenance[56];} TrainerUpdateJob;
static int bounded_child_output(pid_t pid,int fd,char *output,size_t capacity,int seconds);
static int trainer_updates_command(TrainerUpdateJob*j,char *output,size_t cap){
    int fds[2];if(pipe(fds)!=0)return 0;
    pid_t pid=fork();if(pid<0){close(fds[0]);close(fds[1]);return 0;}
    if(pid==0){close(fds[0]);dup2(fds[1],STDOUT_FILENO);close(fds[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}
        if(j->install)execlp("python3","python3",trainer_updates_tool(),"install","--game",j->game,"--id",j->catalog_id,"--confirm",(char*)NULL);
        else if(j->inspect)execlp("python3","python3",trainer_updates_tool(),"stage-status","--game",j->game,"--id",j->catalog_id,(char*)NULL);
        else if(j->rollback)execlp("python3","python3",trainer_updates_tool(),"rollback","--game",j->game,"--id",j->catalog_id,"--confirm",(char*)NULL);
        else if(j->trust_audit)execlp("python3","python3",trainer_updates_tool(),"trust-report","--plain",(char*)NULL);
        else if(j->source_audit)execlp("python3","python3",trainer_updates_tool(),"sources","--plain",(char*)NULL);
        else if(j->offline)execlp("python3","python3",trainer_updates_tool(),"check","--game",j->game,"--plain","--provider",j->provider,"--catalog-provider",j->provider,(char*)NULL);
        else execlp("python3","python3",trainer_updates_tool(),"check","--game",j->game,"--plain","--official","--provider",j->provider,"--catalog-provider",j->provider,(char*)NULL);
        _exit(127);
    }
    return bounded_child_output(pid,fds[0],output,cap,(j->install?75:30));
}
/* Only the exact active game-key AND chosen provider own update evidence. */
static int trainer_update_job_matches(const TrainerUpdateJob *j){
    if(j->context_epoch!=G.trainer_updates_context_epoch||!j->key[0]||!j->provider[0]||G.selected<0||G.selected>=G.game_count)return 0;
    const char *provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
    return provider&&!strcmp(j->key,game_key(&G.games[G.selected]))&&!strcmp(j->provider,provider)
        &&!strcmp(j->game,G.games[G.selected].name);
}
static void trainer_update_disable_staging(void){
    G.trainer_updates_id[0]=0;G.trainer_updates_game[0]=0;
    G.trainer_updates_hash[0]=0;G.trainer_updates_url[0]=0;G.trainer_updates_trust[0]=0;
    G.trainer_updates_ready_key[0]=0;G.trainer_updates_ready_provider[0]=0;
    if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
    if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
}
static int trainer_update_staging_matches(void){
    if(G.trainer_updates_busy||!G.trainer_updates_id[0]||G.selected<0||G.selected>=G.game_count)return 0;
    const char *provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
    return provider&&!strcmp(game_key(&G.games[G.selected]),G.trainer_updates_ready_key)
        &&!strcmp(G.games[G.selected].name,G.trainer_updates_game)
        &&!strcmp(provider,G.trainer_updates_ready_provider);
}
static gboolean trainer_updates_done(void *user){
    TrainerUpdateJob*j=(TrainerUpdateJob*)user;
    G.trainer_updates_busy=0;
    /* Ignore late results from a game/provider that is no longer selected.
     * A completion callback must never resurrect another game's catalog ID. */
    if(j->context_epoch!=G.trainer_updates_context_epoch || (j->key[0]&&!trainer_update_job_matches(j))){
        /* No state from a superseded request may overwrite the current view.
         * A new result requires a new user-initiated check. */
        trainer_update_disable_staging();
        if(G.trainer_updates_status && G.selected>=0 && G.selected<G.game_count)
            set_label(G.trainer_updates_status,"Previous game/source check finished and was discarded. The current selection has not been checked; click Check selected game.");
        free(j);return FALSE;
    }
    if(j->trust_audit||j->source_audit){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,j->message);
    }else if(j->inspect||j->rollback){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,j->message);
        if(j->rollback&&j->ok)start_trainer_library_scan();
    }else if(j->install){
        if(j->ok&&j->installed[0]&&readable_file(j->installed)){
            log_line("Verified trainer downloaded for %s: %s. Previous assignments are unchanged.",j->game,j->installed);
            if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Checksum-pinned trainer staged. A signed manifest, if used, verifies only the pinned key. Assignments unchanged; inspect the staged copy before choosing it.");
            start_trainer_library_scan();
        }else {log_line("Trainer installation failed for %s: %s",j->game,j->message);if(G.trainer_updates_status)set_label(G.trainer_updates_status,j->message);}
    }else{
        trainer_update_disable_staging();
        if(j->catalog_id[0]){snprintf(G.trainer_updates_trust,sizeof G.trainer_updates_trust,"%s",j->provenance);snprintf(G.trainer_updates_id,sizeof G.trainer_updates_id,"%s",j->catalog_id);snprintf(G.trainer_updates_game,sizeof G.trainer_updates_game,"%s",j->game);snprintf(G.trainer_updates_hash,sizeof G.trainer_updates_hash,"%s",j->sha256);snprintf(G.trainer_updates_url,sizeof G.trainer_updates_url,"%s",j->download_url);snprintf(G.trainer_updates_ready_key,sizeof G.trainer_updates_ready_key,"%s",j->key);snprintf(G.trainer_updates_ready_provider,sizeof G.trainer_updates_ready_provider,"%s",j->provider);}
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,j->message);
        log_line("Trainer source check for %s: %s",j->game,j->message);
    }
    gboolean ready=trainer_update_staging_matches();
    if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,ready);
    if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,ready);
    if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,ready);
    free(j);return FALSE;
}
static void *trainer_updates_worker(void *user){
    TrainerUpdateJob*j=(TrainerUpdateJob*)user;char out[8192]={0};int ran=trainer_updates_command(j,out,sizeof out);
    if(!ran){snprintf(j->message,sizeof j->message,"Trainer check failed, signature/catalog was rejected, or timed out. No download or assignment occurred.");}
    else if(j->trust_audit){
        char status[96]={0},keys[20]={0},count[20]={0},reason[440]={0};
        if(sscanf(out,"TRUST\t%95[^\t]\t%19[^\t]\t%19[^\t]\t%439[^\n]",status,keys,count,reason)>=3){
            if(!strcmp(status,"key-pinned-signature"))snprintf(j->message,sizeof j->message,"Catalog signature VERIFIED against a locally pinned Ed25519 key. %s keys pinned; %s entries. The key's actual publisher identity must be checked separately.",keys,count);
            else if(!strcmp(status,"legacy-unsigned"))snprintf(j->message,sizeof j->message,"Unsigned legacy catalog: %s entries, %s keys pinned. SHA256 alone does NOT prove publisher identity. Use a signed manifest and independently verified key for stronger provenance.",count,keys);
            else if(!strcmp(status,"missing"))snprintf(j->message,sizeof j->message,"No imported catalog found. %s publisher keys pinned. Key pinning and signed manifests require independent key provenance; no download was attempted.",keys);
            else snprintf(j->message,sizeof j->message,"Catalog is REJECTED: %.390s. %s publisher keys pinned. Nothing downloaded or installed.",reason,keys);
        }else snprintf(j->message,sizeof j->message,"Could not read local catalog trust status; no download attempted.");
    }
    else if(j->source_audit){
        char result[1900]="";char *save=NULL;int count=0;
        for(char *line=strtok_r(out,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
            if(!strncmp(line,"SUMMARY\t",8)){
                char *status=line+8,*entries=strchr(status,'\t');
                if(entries){*entries++=0;snprintf(result,sizeof result,"Catalog: %s (%s entries).\n",status,entries);}
            }else if(!strncmp(line,"PROVIDER\t",9)){
                char *provider=line+9,*mode=strchr(provider,'\t');if(!mode)continue;*mode++=0;
                char *key=strchr(mode,'\t');if(!key)continue;*key++=0;
                const char *display=!strcmp(provider,"fling")?"FLiNG":!strcmp(provider,"hextrainer")?"HexTrainer":!strcmp(provider,"aurora")?"Aurora":!strcmp(provider,"cheatevolution")?"Cheat Evolution":"Wand / WeMod";
                const char *cap=!strcmp(mode,"publisher-app-managed")?"app-managed":"publisher pages only";
                char row[220];snprintf(row,sizeof row,"%s: %s; %s\n",display,cap,!strcmp(key,"user-key-pinned")?"local key pinned":"no key pinned");
                if(strlen(result)+strlen(row)+140<sizeof result)strcat(result,row);
                count++;
            }
        }
        if(count==5){strcat(result,"No official signed release feed is bundled. User-pinned keys require independent provenance; publisher pages do not authorize downloads.");
            snprintf(j->message,sizeof j->message,"%s",result);}
        else snprintf(j->message,sizeof j->message,"Could not inspect release source capabilities offline; nothing downloaded.");
    }
    else if(j->inspect){
        char current[128]={0},backup[128]={0},version[160]={0};
        json_string(out,"current",current,sizeof current);json_string(out,"backup",backup,sizeof backup);
        json_string(out,"backup_version",version,sizeof version);
        if(current[0])snprintf(j->message,sizeof j->message,"Staged %s: %s. Backup: %s%s%s%s. Offline hashes validate local bytes, not publisher identity. No trainer launched or assigned.",j->game,current,backup,version[0]?" (version ":"",version[0]?version:"",version[0]?")":"");
        else snprintf(j->message,sizeof j->message,"Could not inspect this staged trainer: %.900s",out);
    }
    else if(j->rollback){
        json_string(out,"restored",j->installed,sizeof j->installed);j->ok=j->installed[0]!=0;
        if(j->ok)snprintf(j->message,sizeof j->message,"Previous staged trainer restored for %s. Local checksum verified. Assignment unchanged; rescan to review versions.",j->game);
        else snprintf(j->message,sizeof j->message,"Rollback not performed: %.900s",out);
    }
    else if(j->install){json_string(out,"installed",j->installed,sizeof j->installed);j->ok=j->installed[0]!=0;if(!j->ok)snprintf(j->message,sizeof j->message,"Trainer download rejected: %.650s",out);}
    else {
        char *save=NULL;int already=0,source_count=0;char source_summary[1600]={0};
        for(char *line=strtok_r(out,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
            if(!strncmp(line,"SOURCE\t",7)){
                char *name=line+7,*status=strchr(name,'\t');if(!status)continue;*status++=0;
                char *detail=strchr(status,'\t');if(!detail)continue;*detail++=0;
                char *url=strchr(detail,'\t');if(url)*url=0;
                const char *display= !strcmp(name,"fling")?"FLiNG":!strcmp(name,"hextrainer")?"HexTrainer":!strcmp(name,"cheatevolution")?"Cheat Evolution":!strcmp(name,"aurora")?"Aurora":"Wand / WeMod";
                const char *tag=!strcmp(status,"official-match")?"Game page found":!strcmp(status,"managed-in-app")?"App-managed updates":!strcmp(status,"unavailable")?"Offline":"Official catalogue";
                char row[300];snprintf(row,sizeof row,"%s: %s%s%s\n",display,tag,
                    (!strcmp(name,"aurora")&&strstr(detail,"Publisher lists"))?" - ":"",
                    (!strcmp(name,"aurora")&&strstr(detail,"Publisher lists"))?detail:"");
                if(strlen(source_summary)+strlen(row)+1<sizeof source_summary)strcat(source_summary,row);
                source_count++;continue;
            }
            if(!strncmp(line,"OFFICIAL\t",9)){char *t=line+9;char *end=strchr(t,'\t');if(end)*end=0;if(!j->official[0])snprintf(j->official,sizeof j->official,"%s",t);continue;}
            if(strncmp(line,"CATALOG\t",8))continue;
            char *a=line+8,*b=strchr(a,'\t');if(!b)continue;*b++=0;
            char *c=strchr(b,'\t');if(!c)continue;*c++=0;
            char *hash=strchr(c,'\t');char *url=NULL;
            if(hash){*hash++=0;url=strchr(hash,'\t');if(url)*url++=0;}
            char *provenance=url?strchr(url,'\t'):NULL;
            if(provenance){*provenance++=0;if(!j->provenance[0])snprintf(j->provenance,sizeof j->provenance,"%s",provenance);}
            if(!strcmp(c,"available")&&!j->catalog_id[0]){snprintf(j->catalog_id,sizeof j->catalog_id,"%s",a);snprintf(j->version,sizeof j->version,"%s",b);if(hash)snprintf(j->sha256,sizeof j->sha256,"%s",hash);if(url)snprintf(j->download_url,sizeof j->download_url,"%s",url);}
            else if(!strcmp(c,"installed")){already++;if(!j->catalog_id[0]){snprintf(j->catalog_id,sizeof j->catalog_id,"%s",a);snprintf(j->version,sizeof j->version,"%s",b);if(hash)snprintf(j->sha256,sizeof j->sha256,"%s",hash);if(url)snprintf(j->download_url,sizeof j->download_url,"%s",url);}}
        }
        if(j->catalog_id[0]){
            if(!strcmp(j->provenance,"key-pinned-signature"))snprintf(j->message,sizeof j->message,"Catalog entry available for review: %s. Signature checked against a locally pinned key; publisher identity still requires independent verification. Not confirmed newer.",j->version);
            else snprintf(j->message,sizeof j->message,"Catalog entry available for review: %s (unsigned import). SHA256 does not authenticate the publisher or prove safety. Not confirmed newer.",j->version);
        }
        else if(already)snprintf(j->message,sizeof j->message,"Previously staged catalog copy found. No newer release has been verified for this selection.");
        else if(j->official[0])snprintf(j->message,sizeof j->message,"Publisher page found for %s: %.160s. No authenticated download or newer trainer is verified.",j->game,j->official);
        else snprintf(j->message,sizeof j->message,"Check completed for %s. No verified update. Publisher pages are review-only and manager apps update themselves.",j->game);
        if(source_count){char final[2048]={0};size_t pos=0;size_t n=strnlen(source_summary,sizeof source_summary-1);memcpy(final,source_summary,n);pos=n;if(pos+2<sizeof final){final[pos++]=10;final[pos++]=10;}n=strnlen(j->message,sizeof final-pos-1);memcpy(final+pos,j->message,n);final[pos+n]=0;memcpy(j->message,final,strlen(final)+1);}
    }
    g_idle_add(trainer_updates_done,j);return NULL;
}
static void start_trainer_update_job(TrainerUpdateJob*j){
    /* Immutable identity for this request, including offline/source audits. */
    j->context_epoch=G.trainer_updates_context_epoch;
    if(j->game[0]&&G.selected>=0&&G.selected<G.game_count){
        snprintf(j->key,sizeof j->key,"%s",game_key(&G.games[G.selected]));
        const char *provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
        snprintf(j->provider,sizeof j->provider,"%s",provider?provider:"fling");
    }
    pthread_t thread;
    if(pthread_create(&thread,NULL,trainer_updates_worker,j)==0)pthread_detach(thread);
    else{G.trainer_updates_busy=0;free(j);if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Could not start background trainer check.");}
}
static void on_inspect_release_sources(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy)return;
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;
    j->source_audit=1;G.trainer_updates_busy=1;
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Inspecting declared source capabilities and local key pins offline…");
    start_trainer_update_job(j);
}
static void on_check_trainer_updates(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Previous update check is still finishing. Its old result will not apply to a new game or provider. Retry this check when it finishes.");
        return;
    }
    if(G.selected<0||G.selected>=G.game_count){if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Select a game in Library first.");return;}
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;snprintf(j->game,sizeof j->game,"%s",G.games[G.selected].name);
    G.trainer_updates_busy=1;trainer_update_disable_staging();
    if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
    if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Checking publisher sources and imported checksum catalogues in the background…");
    start_trainer_update_job(j);
}
static void on_audit_trainer_catalog(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy)return;
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;
    j->trust_audit=1;G.trainer_updates_busy=1;
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Auditing local catalog signatures and pinned keys offline…");
    start_trainer_update_job(j);
}
static void on_pin_catalog_provider_key(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy)return;
    const char*provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
    if(!provider||!*provider){if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Choose the publisher in Find & Update Trainers first.");return;}
    char chosen_provider[40];snprintf(chosen_provider,sizeof chosen_provider,"%s",provider);
    GtkWidget*choose=gtk_file_chooser_dialog_new("Choose a publisher Ed25519 PUBLIC KEY (.pem)",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Continue",GTK_RESPONSE_ACCEPT,NULL);
    int chosen=gtk_dialog_run((GtkDialog*)choose);
    char*filename=chosen==GTK_RESPONSE_ACCEPT?gtk_file_chooser_get_filename((GtkFileChooser*)choose):NULL;
    gtk_widget_destroy(choose);
    if(!filename)return;
    GtkWidget*confirm=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Pin the selected provider's Ed25519 key?\n\nProvider: %s\nKey file: %.350s\n\nOnly proceed if you independently obtained and verified the publisher's public-key SHA256 fingerprint. A key file's own fingerprint does not establish who owns it.",chosen_provider,filename);
    GtkWidget*content=gtk_dialog_get_content_area((GtkDialog*)confirm);
    GtkWidget*help=label("Type the 64-character SHA256 SPKI fingerprint from the INDEPENDENT publisher channel:","muted");gtk_label_set_line_wrap((GtkLabel*)help,TRUE);pack(content,help,0);
    GtkWidget*input=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)input,"64 lowercase SHA256 hex characters");pack(content,input,0);
    gtk_widget_show_all(confirm);
    int approval=gtk_dialog_run((GtkDialog*)confirm);char expected[100]={0};
    if(approval==GTK_RESPONSE_YES)snprintf(expected,sizeof expected,"%s",gtk_entry_get_text((GtkEntry*)input));
    gtk_widget_destroy(confirm);
    if(approval!=GTK_RESPONSE_YES||strlen(expected)!=64){g_free(filename);return;}
    int pipefd[2];if(pipe(pipefd)!=0){g_free(filename);return;}
    pid_t pid=fork();if(pid==0){close(pipefd[0]);dup2(pipefd[1],STDOUT_FILENO);close(pipefd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_updates_tool(),"pin-key","--provider",chosen_provider,"--key",filename,"--expected-fingerprint",expected,"--confirm",(char*)NULL);_exit(127);}
    close(pipefd[1]);char out[1600]={0};int ok=pid>0&&bounded_child_output(pid,pipefd[0],out,sizeof out,15);
    if(pid<0)close(pipefd[0]);g_free(filename);
    char fingerprint[80]={0};json_string(out,"fingerprint",fingerprint,sizeof fingerprint);
    if(ok&&strlen(fingerprint)==64){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Provider key pinned with the independently supplied SHA256 fingerprint. This checks future signed catalogs against the same key; it does not independently prove the key belongs to the publisher.");
        log_line("Provider key pinned: %s (key fingerprint verified against user input)",chosen_provider);
    }else{
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Key pinning rejected. Check the selected provider, PEM format and independent 64-character fingerprint. Existing pinned key remains unchanged.");
        log_line("Publisher key pin rejected for %s: %.400s",chosen_provider,out);
    }
}
static void on_import_signed_trainer_catalog(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy)return;
    GtkWidget*choose=gtk_file_chooser_dialog_new("Import key-pinned signed trainer catalog",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Review signed catalog",GTK_RESPONSE_ACCEPT,NULL);
    int selected=gtk_dialog_run((GtkDialog*)choose);
    char*filename=selected==GTK_RESPONSE_ACCEPT?gtk_file_chooser_get_filename((GtkFileChooser*)choose):NULL;
    gtk_widget_destroy(choose);
    if(!filename)return;
    GtkWidget*confirm=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Verify and import this signed catalog?\n\n%.400s\n\nThe signature MUST match a separately pinned Ed25519 provider key. Verify that key's publisher identity through an independent channel. The previous imported catalog is backed up. No trainer downloads or assignments occur.",filename);
    int approval=gtk_dialog_run((GtkDialog*)confirm);gtk_widget_destroy(confirm);
    if(approval!=GTK_RESPONSE_YES){g_free(filename);return;}
    int pipefd[2];if(pipe(pipefd)!=0){g_free(filename);return;}
    pid_t pid=fork();if(pid==0){close(pipefd[0]);dup2(pipefd[1],STDOUT_FILENO);close(pipefd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_updates_tool(),"import-signed","--file",filename,"--confirm",(char*)NULL);_exit(127);}
    close(pipefd[1]);char out[2048]={0};int ok=pid>0&&bounded_child_output(pid,pipefd[0],out,sizeof out,15);
    if(pid<0)close(pipefd[0]);g_free(filename);
    char status[80]={0},provider[80]={0};json_string(out,"status",status,sizeof status);json_string(out,"provider",provider,sizeof provider);
    if(ok&&status[0]&&strcmp(status,"rejected")){
        G.trainer_updates_id[0]=0;G.trainer_updates_game[0]=0;G.trainer_updates_trust[0]=0;
        if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
        if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
        if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Signed catalog imported after verification against your pinned Ed25519 key. Independently verify key provenance. Load staged entries to review source URLs and SHA256; no executable was downloaded.");
        log_line("Signed catalog imported for provider: %s",provider);
    }else{
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Signed catalog import rejected. Check that the provider key is pinned, signature valid and catalog unexpired. No catalog change was made for a failed verification.");
        log_line("Signed catalog import rejected: %.600s",out);
    }
}
static void on_check_local_trainer_catalog(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.trainer_updates_busy){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Previous request is still finishing. Its old result cannot be staged for this selection; retry when complete.");
        return;
    }
    if(G.selected<0||G.selected>=G.game_count){if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Select a game first.");return;}
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;
    j->offline=1;snprintf(j->game,sizeof j->game,"%s",G.games[G.selected].name);
    G.trainer_updates_busy=1;trainer_update_disable_staging();
    if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
    if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Checking imported catalog and staged versions offline; no publisher requests…");
    start_trainer_update_job(j);
}
static void on_find_official_trainer(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.selected<0||G.selected>=G.game_count){log_line("Select a game before finding official trainers.");return;}
    const char *provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
    if(!provider)provider="fling";
    /* Prefer the exact page already discovered and whitelisted in local cache.
     * If absent, retain RC7's official-search fallback. No binary fetch. */
    if(!strcmp(provider,"fling")||!strcmp(provider,"hextrainer")){
        int fds[2];if(pipe(fds)==0){pid_t child=fork();
            if(child==0){close(fds[0]);dup2(fds[1],STDOUT_FILENO);close(fds[1]);
                execlp("python3","python3",trainer_monitor_tool(),"publisher-page","--game",G.games[G.selected].name,"--provider",provider,"--plain",(char*)NULL);_exit(127);}
            close(fds[1]);if(child>=0){char cached[2048]={0};
                if(bounded_child_output(child,fds[0],cached,sizeof cached,3)){
                    size_t len=strcspn(cached,"\r\n");cached[len]=0;
                    if((!strcmp(provider,"fling")&&!strncmp(cached,"https://flingtrainer.com/trainer/",33))||
                       (!strcmp(provider,"hextrainer")&&!strncmp(cached,"https://hextrainer.com/trainers/",32))){
                        spawn_detached("xdg-open",cached,NULL);
                        log_line("Opened cached official %s game-specific publisher page (not a verified download).",provider);
                        return;
                    }
                }
            }else close(fds[0]);
        }
    }
    char input[512];snprintf(input,sizeof input,"%s trainer",G.games[G.selected].name);
    char url[2048]={0};
    if(!strcmp(provider,"hextrainer"))snprintf(url,sizeof url,"https://hextrainer.com/trainers");
    else if(!strcmp(provider,"cheatevolution"))snprintf(url,sizeof url,"https://cheatevolution.com/downloads.php");
    else if(!strcmp(provider,"aurora"))snprintf(url,sizeof url,"https://www.cheathappens.com/trainers.asp");
    else if(!strcmp(provider,"wand"))snprintf(url,sizeof url,"https://wand.com/");
    else{
        snprintf(url,sizeof url,"https://flingtrainer.com/?s=");size_t n=strlen(url);
        const char hex[]="0123456789ABCDEF";
        for(const unsigned char*c=(const unsigned char*)input;*c&&n+4<sizeof url;c++){
            if(isalnum(*c)||*c=='-'||*c=='.'||*c=='_'||*c=='~')url[n++]=*c;
            else if(*c==' ')url[n++]='+';
            else {url[n++]='%';url[n++]=hex[*c>>4];url[n++]=hex[*c&15];}
        }url[n]=0;
    }
    pid_t pid=fork();if(pid==0){execlp("xdg-open","xdg-open",url,(char*)NULL);_exit(127);}
    if(pid<0)log_line("Could not open the official trainer publisher page.");
}

static void on_install_verified_trainer(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!trainer_update_staging_matches()){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Check this selected game's trusted catalog entry first.");return;
    }
    GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Stage the catalog-pinned trainer for %s?\n\nSource: %.350s\nExpected SHA256: %.64s\n\n%s\nExisting game assignment stays unchanged.",G.trainer_updates_game,G.trainer_updates_url,G.trainer_updates_hash,
        !strcmp(G.trainer_updates_trust,"key-pinned-signature")?"Ed25519 signature verified with your pinned key. Check its publisher identity independently; this is not a malware safety guarantee.":"UNSIGNED imported catalog. SHA256 does not authenticate its publisher or prove the download is safe.");
    int response=gtk_dialog_run((GtkDialog*)dlg);gtk_widget_destroy(dlg);if(response!=GTK_RESPONSE_YES)return;
    if(!trainer_update_staging_matches())return;
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;j->install=1;snprintf(j->game,sizeof j->game,"%s",G.trainer_updates_game);snprintf(j->catalog_id,sizeof j->catalog_id,"%s",G.trainer_updates_id);
    G.trainer_updates_busy=1;
    gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Staging approved checksum-pinned trainer. Key provenance and executable safety are not guaranteed…");
    start_trainer_update_job(j);
}

static void on_staged_trainer_action(GtkButton*b,void*ctx){
    (void)b;
    if(!trainer_update_staging_matches()){
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Check the selected game's imported catalog entry first.");return;
    }
    int rollback=(ctx!=NULL);
    if(rollback){
        GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
            "Restore the PREVIOUS staged trainer for %s? This swaps only GameWeld's locally staged copies. Existing game assignments stay unchanged.",G.trainer_updates_game);
        int response=gtk_dialog_run((GtkDialog*)dlg);gtk_widget_destroy(dlg);if(response!=GTK_RESPONSE_YES)return;
        if(!trainer_update_staging_matches())return;
    }
    TrainerUpdateJob*j=calloc(1,sizeof *j);if(!j)return;
    j->inspect=!rollback;j->rollback=rollback;
    snprintf(j->game,sizeof j->game,"%s",G.trainer_updates_game);
    snprintf(j->catalog_id,sizeof j->catalog_id,"%s",G.trainer_updates_id);
    G.trainer_updates_busy=1;
    if(G.trainer_updates_install_button)gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    if(G.trainer_updates_inspect_button)gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
    if(G.trainer_updates_rollback_button)gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
    if(G.trainer_updates_status)set_label(G.trainer_updates_status,rollback?"Verifying and restoring previous staged trainer offline…":"Inspecting staged trainer and backup offline…");
    start_trainer_update_job(j);
}

/* RC9 workspace navigation reads the saved update dashboard only. It never
 * starts a discovery scan or downloads/launches executables. */
/* Selecting a publisher is never the same as selecting the installed trainer.
 * Show the difference before offering an official-page review. */
static void trainer_update_context_refresh(void){
    if(!G.trainer_updates_context)return;
    if(G.selected<0||G.selected>=G.game_count){
        if(G.trainer_updates_context_key[0]||G.trainer_updates_context_provider[0]){
            G.trainer_updates_context_key[0]=0;G.trainer_updates_context_provider[0]=0;
            G.trainer_updates_context_epoch++;
            trainer_update_disable_staging();
        }
        set_label(G.trainer_updates_context,"Select a game first to review available trainer sources.");
        if(G.trainer_updates_status)set_label(G.trainer_updates_status,"Not checked — select a game.");
        return;
    }
    /* Choose the detected assigned provider once per game change. Preserve
     * an explicit user choice while checking other providers for that game. */
    static char context_game_key[320]={0};
    const char *selected_key=game_key(&G.games[G.selected]);
    if(G.trainer_updates_provider&&strcmp(context_game_key,selected_key)){
        snprintf(context_game_key,sizeof context_game_key,"%s",selected_key);
        char assigned_path[2048]={0};
        const char *default_source="fling";
        if(load_local_trainer(selected_key,assigned_path,sizeof assigned_path)){
            if(strstr(assigned_path,"/HexTrainer/")||strstr(assigned_path,"/hextrainer/"))default_source="hextrainer";
            else if(strstr(assigned_path,"/CheatEvolution/"))default_source="cheatevolution";
            else if(strstr(assigned_path,"/Aurora/")||strstr(assigned_path,"/CheatHappens/"))default_source="aurora";
            else if(strstr(assigned_path,"/Wand/" )||strstr(assigned_path,"/WeMod/"))default_source="wand";
        }
        /* A new unassigned game must never silently inherit another game's provider. */
        gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_updates_provider,default_source);
    }
    const char*provider=G.trainer_updates_provider?gtk_combo_box_get_active_id((GtkComboBox*)G.trainer_updates_provider):NULL;
    /* A saved result belongs to its exact game key AND the user-selected
     * provider. Clear the old label and stage controls on either change. */
    if(strcmp(G.trainer_updates_context_key,selected_key)||strcmp(G.trainer_updates_context_provider,provider?provider:"")){
        snprintf(G.trainer_updates_context_key,sizeof G.trainer_updates_context_key,"%s",selected_key);
        snprintf(G.trainer_updates_context_provider,sizeof G.trainer_updates_context_provider,"%s",provider?provider:"");
        G.trainer_updates_context_epoch++;
        trainer_update_disable_staging();
        if(G.trainer_updates_status){char status[768];
            snprintf(status,sizeof status,"Not checked for %s with %s. Click Check selected game to review this publisher; no verified download is available yet.",G.games[G.selected].name,provider?provider:"selected source");
            set_label(G.trainer_updates_status,status);
        }
    }
    const char*name="FLiNG";
    if(provider&&!strcmp(provider,"hextrainer"))name="HexTrainer";
    else if(provider&&!strcmp(provider,"aurora"))name="Aurora";
    else if(provider&&!strcmp(provider,"cheatevolution"))name="Cheat Evolution";
    else if(provider&&!strcmp(provider,"wand"))name="Wand / WeMod";
    char path[2048]={0},shown[4096];
    int assigned=load_local_trainer(game_key(&G.games[G.selected]),path,sizeof path);
    const char*base=assigned?strrchr(path,'/'):NULL;
    base=base?base+1:(assigned?path:"None");
    snprintf(shown,sizeof shown,"Game: %s\nAssigned trainer: %s\nSource to review: %s (separate from the assigned trainer; unverified)",G.games[G.selected].name,base,name);
    set_label(G.trainer_updates_context,shown);
}
static void on_trainer_provider_changed(GtkWidget *widget,void *unused){(void)widget;(void)unused;trainer_update_context_refresh();}
static void on_trainer_workspace_page(GtkWidget *notebook,GtkWidget *page,unsigned int index,void *unused){
    (void)notebook;(void)page;(void)unused;
    if(index==1){trainer_update_context_refresh();on_refresh_trainer_dashboard(NULL,NULL);}
}
static GtkWidget *build_trainer_library(void){
    GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,22);gtk_container_add(outer,p);
    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("TRAINER LIBRARY","page-kicker"),0);pack(ht,label("Your trainers","workspace-title"),0);pack(ht,label("Launch a trainer, find an update, or adjust a setting—all in one place.","page-subtitle"),0);pack(head,ht,1);GtkWidget*scan=button("Scan all trainers","primary-action");GtkWidget*rescan=button("Rescan selected game","action");GtkWidget*addfolder=button("Add trainer folder","action");GtkWidget*refresh=button("Refresh view","action");g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(rescan,"clicked",(GCallback)on_rescan_selected_trainer,NULL,NULL,0);g_signal_connect_data(addfolder,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(refresh,"clicked",(GCallback)on_refresh_trainer_library,NULL,NULL,0);pack(head,scan,0);pack(head,addfolder,0);pack(p,head,0);
    /* The primary notebook separates routine trainer management from update
     * discovery and rarely used settings. Callbacks retain their original owners. */
    GtkWidget*workspace=gtk_notebook_new();style(workspace,"trainer-workspace");
    GtkWidget*main_page=box(GTK_ORIENTATION_VERTICAL,12);
    GtkWidget*updates_page=box(GTK_ORIENTATION_VERTICAL,12);
    GtkWidget*advanced_page=box(GTK_ORIENTATION_VERTICAL,12);
    style(main_page,"page-shell");style(updates_page,"page-shell");style(advanced_page,"page-shell");
    margins(main_page,8);margins(updates_page,8);margins(advanced_page,8);
    gtk_notebook_append_page((GtkNotebook*)workspace,main_page,label("My Trainers",NULL));
    gtk_notebook_append_page((GtkNotebook*)workspace,updates_page,label("Find Updates",NULL));
    gtk_notebook_append_page((GtkNotebook*)workspace,advanced_page,label("Advanced",NULL));
    gtk_widget_set_vexpand(workspace,TRUE);
    g_signal_connect_data(workspace,"switch-page",(GCallback)on_trainer_workspace_page,NULL,NULL,0);
    pack(p,workspace,1);

    GtkWidget*filters=box(GTK_ORIENTATION_HORIZONTAL,8);G.trainer_library_filter=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.trainer_library_filter,"Filter game, trainer, profile, runtime, version…");G.trainer_library_sort=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"status","Sort: Status / health");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"game","Sort: Game");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"confidence","Sort: Confidence");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"version","Sort: Version");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"profile","Sort: Compatibility profile");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"policy","Sort: Launch policy");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"launch","Sort: Next launch");gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_sort,"status");G.trainer_library_readiness_filter=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"all","Readiness: All");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"managed","Readiness: Managed FLiNG");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"steam","Readiness: Steam live session");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"inherit","Readiness: Heroic existing session");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"explicit","Readiness: Explicit override");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"unassigned","Readiness: No launch target");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"manual","Readiness: Manual policy override");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"advisory","Readiness: Advisory / low confidence");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"attention","Readiness: Assignment / health attention");gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_readiness_filter,"all");G.trainer_library_attention_toggle=gtk_check_button_new_with_label("Needs attention");GtkWidget*clearfilter=button("Clear","action");g_signal_connect_data(G.trainer_library_filter,"changed",(GCallback)on_trainer_library_filter_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_sort,"changed",(GCallback)on_trainer_library_sort_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_readiness_filter,"changed",(GCallback)on_trainer_library_readiness_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_attention_toggle,"toggled",(GCallback)on_trainer_library_attention_toggled,NULL,NULL,0);g_signal_connect_data(clearfilter,"clicked",(GCallback)on_trainer_library_clear_filter,NULL,NULL,0);pack(filters,G.trainer_library_filter,1);pack(filters,G.trainer_library_sort,0);
    pack(filters,clearfilter,0);pack(main_page,filters,0);
    GtkWidget*extra_filter=gtk_expander_new("More filters");
    GtkWidget*filter_extra_row=box(GTK_ORIENTATION_HORIZONTAL,8);
    pack(filter_extra_row,G.trainer_library_readiness_filter,0);
    pack(filter_extra_row,G.trainer_library_attention_toggle,0);
    gtk_container_add(extra_filter,filter_extra_row);
    pack(main_page,extra_filter,0);

    GtkWidget*body=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*audit=box(GTK_ORIENTATION_HORIZONTAL,10);style(audit,"panel-soft");GtkWidget*audtxt=box(GTK_ORIENTATION_VERTICAL,2);pack(audtxt,label("LIBRARY STATUS","section-kicker"),0);G.trainer_library_audit=label("No Trainer Library scan has completed yet.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_audit,TRUE);pack(audtxt,G.trainer_library_audit,0);pack(audit,audtxt,1);pack(left,audit,0);
    GtkWidget*library=box(GTK_ORIENTATION_VERTICAL,6);style(library,"panel");pack(library,label("TRAINERS ON THIS PC","section-kicker"),0);GtkWidget*nb=gtk_notebook_new();G.trainer_library_tabs=nb;gtk_widget_set_vexpand(nb,TRUE);G.trainer_library_matched=trainer_tree_new();G.trainer_library_alternates=trainer_tree_new();G.trainer_library_ambiguous=trainer_tree_new();G.trainer_library_unmatched=trainer_tree_new();G.trainer_library_health=trainer_tree_new();GtkWidget*views[5]={G.trainer_library_matched,G.trainer_library_alternates,G.trainer_library_ambiguous,G.trainer_library_unmatched,G.trainer_library_health};const char*tabs[5]={"Assigned","Alternatives","Ambiguous","Unmatched","Health"};for(int i=0;i<5;i++){GtkTreeSelection*seln=gtk_tree_view_get_selection((GtkTreeView*)views[i]);gtk_tree_selection_set_mode(seln,GTK_SELECTION_SINGLE);g_signal_connect_data(seln,"changed",(GCallback)trainer_pick_changed,NULL,NULL,0);GtkWidget*tsc=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)tsc,GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);gtk_container_add(tsc,views[i]);gtk_notebook_append_page((GtkNotebook*)nb,tsc,label(tabs[i],NULL));}G.trainer_library_attention_games=trainer_attention_tree_new();GtkTreeSelection*ags=gtk_tree_view_get_selection((GtkTreeView*)G.trainer_library_attention_games);gtk_tree_selection_set_mode(ags,GTK_SELECTION_SINGLE);g_signal_connect_data(ags,"changed",(GCallback)trainer_attention_game_changed,NULL,NULL,0);GtkWidget*agsc=gtk_scrolled_window_new(NULL,NULL);gtk_container_add(agsc,G.trainer_library_attention_games);gtk_notebook_append_page((GtkNotebook*)nb,agsc,label("Game attention",NULL));gtk_widget_set_size_request(nb,-1,315);pack(library,nb,1);pack(left,library,1);
    GtkWidget*summary=box(GTK_ORIENTATION_VERTICAL,5);style(summary,"panel-soft");GtkWidget*sh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(sh,label("LAST SCAN","section-kicker"),1);pack(summary,sh,0);G.trainer_library_view=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.trainer_library_view,TRUE);gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.trainer_library_view),"No Trainer Library scan has completed yet.",-1);gtk_text_view_set_wrap_mode((GtkTextView*)G.trainer_library_view,3);
    GtkWidget*ss=gtk_scrolled_window_new(NULL,NULL);
    gtk_widget_set_size_request(ss,-1,300);gtk_container_add(ss,G.trainer_library_view);
    pack(summary,ss,1);
    GtkWidget*scan_log_exp=gtk_expander_new("View last trainer scan log");
    gtk_container_add(scan_log_exp,summary);
    gtk_expander_set_expanded(scan_log_exp,FALSE);
    pack(advanced_page,scan_log_exp,0);pack(body,left,1);

    GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_size_request(right,330,-1);
    GtkWidget*target=box(GTK_ORIENTATION_VERTICAL,6);style(target,"panel");pack(target,label("SELECTED TRAINER","section-kicker"),0);G.trainer_library_selected=label("Select a game in Library to assign or clear its trainer.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_selected,TRUE);pack(target,G.trainer_library_selected,0);G.trainer_library_quick_summary=label("Select a trainer row to see its version, health and compatibility here.","trainer-quick-summary");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_quick_summary,TRUE);
    pack(target,G.trainer_library_quick_summary,0);
    GtkWidget*technical=gtk_expander_new("Full compatibility and launch details");
    GtkWidget*technical_wrap=box(GTK_ORIENTATION_VERTICAL,4);
    G.trainer_library_pick=label("Select a trainer result to inspect matching, compatibility and next-launch behavior.","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_pick,TRUE);
    pack(technical_wrap,G.trainer_library_pick,0);
    gtk_container_add(technical,technical_wrap);
    gtk_expander_set_expanded(technical,FALSE);
    pack(target,technical,0);pack(right,target,0);
    GtkWidget*guide=box(GTK_ORIENTATION_VERTICAL,7);style(guide,"panel");GtkWidget*gh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(gh,label("SUGGESTED NEXT STEP","section-kicker"),1);G.trainer_library_recommended_action=button("No action selected","primary-action");gtk_widget_set_sensitive(G.trainer_library_recommended_action,FALSE);g_signal_connect_data(G.trainer_library_recommended_action,"clicked",(GCallback)on_trainer_library_recommended_action,NULL,NULL,0);pack(gh,G.trainer_library_recommended_action,0);pack(guide,gh,0);G.trainer_library_guidance=label("Select a result to see the safest next action.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_guidance,TRUE);pack(guide,G.trainer_library_guidance,0);pack(right,guide,0);
    GtkWidget*actions=box(GTK_ORIENTATION_VERTICAL,6);style(actions,"panel");pack(actions,label("TRAINER ACTIONS","section-kicker"),0);G.trainer_library_launch_assigned=button("Launch assigned trainer","primary-action");G.trainer_library_launch_manager_standalone=button("Launch manager standalone","action");G.trainer_library_assign_suggested=button("Assign to suggested game","action");G.trainer_library_select_suggested=button("Select suggested game","action");G.trainer_library_assign_selected=button("Assign to selected game","action");G.trainer_library_open_folder=button("Open trainer folder","action");g_signal_connect_data(G.trainer_library_launch_assigned,"clicked",(GCallback)on_launch_assigned_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_launch_manager_standalone,"clicked",(GCallback)on_launch_manager_standalone_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_assign_suggested,"clicked",(GCallback)on_assign_suggested_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_select_suggested,"clicked",(GCallback)on_select_suggested_library_game,NULL,NULL,0);g_signal_connect_data(G.trainer_library_assign_selected,"clicked",(GCallback)on_assign_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_open_folder,"clicked",(GCallback)on_open_selected_trainer_folder,NULL,NULL,0);gtk_widget_set_sensitive(G.trainer_library_launch_assigned,FALSE);gtk_widget_set_sensitive(G.trainer_library_launch_manager_standalone,FALSE);gtk_widget_set_visible(G.trainer_library_launch_manager_standalone,FALSE);gtk_widget_set_sensitive(G.trainer_library_assign_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_select_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_assign_selected,FALSE);gtk_widget_set_sensitive(G.trainer_library_open_folder,FALSE);pack(actions,G.trainer_library_launch_assigned,0);
    pack(actions,G.trainer_library_launch_manager_standalone,0);
    GtkWidget*quick_row=box(GTK_ORIENTATION_HORIZONTAL,6);
    pack(quick_row,G.trainer_library_assign_selected,1);
    pack(quick_row,G.trainer_library_open_folder,1);
    pack(actions,quick_row,0);
    GtkWidget*assign_extra=gtk_expander_new("More assignment options");
    GtkWidget*assign_extra_box=box(GTK_ORIENTATION_VERTICAL,6);
    pack(assign_extra_box,G.trainer_library_assign_suggested,0);
    pack(assign_extra_box,G.trainer_library_select_suggested,0);
    gtk_container_add(assign_extra,assign_extra_box);pack(actions,assign_extra,0);
    pack(right,actions,0);
    GtkWidget*policy=box(GTK_ORIENTATION_VERTICAL,6);style(policy,"panel");pack(policy,label("LAUNCH POLICY","section-kicker"),0);GtkWidget*pp=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*pp_auto=button("Auto","action");GtkWidget*pp_managed=button("Managed FLiNG","action");GtkWidget*pp_inherit=button("Inherit session","action");g_signal_connect_data(pp_auto,"clicked",(GCallback)on_profile_policy_auto,NULL,NULL,0);g_signal_connect_data(pp_managed,"clicked",(GCallback)on_profile_policy_managed,NULL,NULL,0);g_signal_connect_data(pp_inherit,"clicked",(GCallback)on_profile_policy_inherit,NULL,NULL,0);pack(pp,pp_auto,0);pack(pp,pp_managed,0);pack(pp,pp_inherit,0);pack(policy,pp,0);G.trainer_library_policy=label("Duplicate version policy: Ask","muted");pack(policy,G.trainer_library_policy,0);GtkWidget*dp=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*pask=button("Ask","action");GtkWidget*pkeep=button("Keep current","action");GtkWidget*pnew=button("Prefer newest","action");g_signal_connect_data(pask,"clicked",(GCallback)on_policy_ask,NULL,NULL,0);g_signal_connect_data(pkeep,"clicked",(GCallback)on_policy_keep,NULL,NULL,0);g_signal_connect_data(pnew,"clicked",(GCallback)on_policy_newest,NULL,NULL,0);pack(dp,pask,0);pack(dp,pkeep,0);pack(dp,pnew,0);pack(policy,dp,0);pack(advanced_page,policy,0);
    /* RC8: Three independent evidence categories, all sourced from the saved
     * monitor cache. No network traffic or executable operations from Refresh. */
    GtkWidget*dash=box(GTK_ORIENTATION_VERTICAL,7);style(dash,"panel");
    GtkWidget*dh=box(GTK_ORIENTATION_HORIZONTAL,6);
    pack(dh,label("WHAT GAMEWELD FOUND","section-kicker"),1);
    GtkWidget*dr=button("Refresh results","action");
    g_signal_connect_data(dr,"clicked",(GCallback)on_refresh_trainer_dashboard,NULL,NULL,0);
    pack(dh,dr,0);pack(dash,dh,0);
    G.trainer_dashboard_status=label("Loading cached update evidence…","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_dashboard_status,TRUE);
    pack(dash,G.trainer_dashboard_status,0);
    GtkWidget*dcols=box(GTK_ORIENTATION_HORIZONTAL,8);
    GtkWidget*dc1=box(GTK_ORIENTATION_VERTICAL,5);style(dc1,"panel-soft");
    pack(dc1,label("TRAINERS FOUND","section-kicker"),0);
    G.trainer_dashboard_available=label("Loading…","update-evidence");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_dashboard_available,TRUE);
    gtk_label_set_xalign((GtkLabel*)G.trainer_dashboard_available,0);
    pack(dc1,G.trainer_dashboard_available,0);pack(dcols,dc1,1);
    GtkWidget*dc2=box(GTK_ORIENTATION_VERTICAL,5);style(dc2,"panel-soft");
    pack(dc2,label("POSSIBLE UPDATES","section-kicker"),0);
    G.trainer_dashboard_updates=label("Loading…","update-evidence");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_dashboard_updates,TRUE);
    gtk_label_set_xalign((GtkLabel*)G.trainer_dashboard_updates,0);
    pack(dc2,G.trainer_dashboard_updates,0);pack(dcols,dc2,1);
    GtkWidget*dc3=box(GTK_ORIENTATION_VERTICAL,5);style(dc3,"panel-soft");
    pack(dc3,label("TRAINER APPS","section-kicker"),0);
    G.trainer_dashboard_managers=label("Loading…","update-evidence");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_dashboard_managers,TRUE);
    gtk_label_set_xalign((GtkLabel*)G.trainer_dashboard_managers,0);
    pack(dc3,G.trainer_dashboard_managers,0);
    pack(dash,dcols,0);pack(dash,dc3,0);
    pack(dash,label("Publisher leads and filename comparisons are review-only. No authenticated automatic download feed is bundled.","muted"),0);
    pack(updates_page,dash,0);
    GtkWidget*updates_columns=box(GTK_ORIENTATION_HORIZONTAL,12);
    GtkWidget*updates_left=box(GTK_ORIENTATION_VERTICAL,10);
    GtkWidget*updates_right=box(GTK_ORIENTATION_VERTICAL,10);
    pack(updates_columns,updates_left,1);pack(updates_columns,updates_right,1);
    pack(updates_page,updates_columns,0);
    pack(updates_page,label("Publisher results are suggestions to review, not verified downloads. GameWeld will never silently replace a trainer.","muted"),0);
    /* RC9: Split finding games and reviewing a selected publisher into separate tasks. */
    GtkWidget*monitor_exp=gtk_expander_new("1  ·  Find trainers for my games");
    GtkWidget*monitor=box(GTK_ORIENTATION_VERTICAL,6);style(monitor,"panel-soft");
    style(monitor_exp,"panel");gtk_container_add(monitor_exp,monitor);gtk_expander_set_expanded((GtkWidget*)monitor_exp,TRUE);
    GtkWidget*mrow=box(GTK_ORIENTATION_HORIZONTAL,6);
    GtkWidget*mcheck=button("Check for trainers","action"),*mqueue=button("View full results","action"),*mreport=button("Export report","action");
    g_signal_connect_data(mcheck,"clicked",(GCallback)on_monitor_check,NULL,NULL,0);
    g_signal_connect_data(mqueue,"clicked",(GCallback)on_monitor_queue,NULL,NULL,0);
    g_signal_connect_data(mreport,"clicked",(GCallback)on_monitor_report,NULL,NULL,0);
    pack(mrow,mcheck,0);pack(mrow,mqueue,0);pack(mrow,mreport,0);pack(monitor,mrow,0);
    GtkWidget*mtools=box(GTK_ORIENTATION_HORIZONTAL,6);
    GtkWidget*msync=button("Refresh installed versions","action");
    g_signal_connect_data(msync,"clicked",(GCallback)on_monitor_local_sync,NULL,NULL,0);pack(mtools,msync,0);
    GtkWidget*mrecover=button("Retry page details","action");
    g_signal_connect_data(mrecover,"clicked",(GCallback)on_monitor_recover,NULL,NULL,0);pack(mtools,mrecover,0);pack(monitor,mtools,0);
    GtkWidget*mrow2=box(GTK_ORIENTATION_HORIZONTAL,6);
    G.trainer_monitor_toggle=button("Pause automatic checks","action");
    G.trainer_monitor_enabled=1;
    g_signal_connect_data(G.trainer_monitor_toggle,"clicked",(GCallback)on_monitor_toggle,NULL,NULL,0);
    pack(mrow2,G.trainer_monitor_toggle,0);
    pack(mrow2,label("Daily limit:","muted"),0);
    G.trainer_monitor_budget=gtk_combo_box_text_new();
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"4","4 / day");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"8","8 / day");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"12","12 / day");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"24","24 / day");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"48","48 / day");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_monitor_budget,"96","96 / day");
    gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_monitor_budget,"12");
    g_signal_connect_data(G.trainer_monitor_budget,"changed",(GCallback)on_monitor_budget,NULL,NULL,0);
    pack(mrow2,G.trainer_monitor_budget,0);pack(monitor,mrow2,0);
    G.trainer_monitor_discovery=gtk_check_button_new_with_label("Find trainers for unassigned games");
    G.trainer_monitor_include_unassigned=1;
    gtk_toggle_button_set_active((GtkToggleButton*)G.trainer_monitor_discovery,TRUE);
    g_signal_connect_data(G.trainer_monitor_discovery,"toggled",(GCallback)on_monitor_discovery,NULL,NULL,0);
    pack(monitor,G.trainer_monitor_discovery,0);
    G.trainer_monitor_status=label("Checking previous discoveries…","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_monitor_status,TRUE);pack(monitor,G.trainer_monitor_status,0);
    GtkWidget*details_exp=gtk_expander_new("Detailed queue (review-only)");
    G.trainer_monitor_details_expander=details_exp;
    GtkWidget*details_box=box(GTK_ORIENTATION_VERTICAL,3);
    G.trainer_monitor_details=label("Choose Review queue to load the cached individual records.","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_monitor_details,TRUE);
    pack(details_box,G.trainer_monitor_details,0);gtk_container_add(details_exp,details_box);
    gtk_expander_set_expanded((GtkWidget*)details_exp,FALSE);pack(monitor,details_exp,0);
    pack(updates_left,monitor_exp,0);

    GtkWidget*updates_exp=gtk_expander_new("2  ·  Check this game for updates");
    GtkWidget*upd=box(GTK_ORIENTATION_VERTICAL,6);style(upd,"panel-soft");
    style(updates_exp,"panel");gtk_container_add(updates_exp,upd);gtk_expander_set_expanded((GtkWidget*)updates_exp,TRUE);
    G.trainer_updates_provider=gtk_combo_box_text_new();
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_updates_provider,"fling","FLiNG standalone trainers");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_updates_provider,"hextrainer","HexTrainer standalone trainers");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_updates_provider,"cheatevolution","Cheat Evolution app");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_updates_provider,"aurora","Cheat Happens Aurora / AurorAI");
    gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_updates_provider,"wand","Wand / WeMod app");
    gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_updates_provider,"fling");
    G.trainer_updates_context=label("Select a game to review the assigned trainer and the chosen source.","update-context");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_updates_context,TRUE);
    pack(upd,G.trainer_updates_context,0);
    pack(upd,G.trainer_updates_provider,0);
    g_signal_connect_data(G.trainer_updates_provider,"changed",(GCallback)on_trainer_provider_changed,NULL,NULL,0);
    GtkWidget*updates_row=box(GTK_ORIENTATION_HORIZONTAL,5);
    GtkWidget*official=button("Publisher page","action");GtkWidget*check=button("Check selected game","action");
    GtkWidget*source_status=button("What sources are supported?","action");
    g_signal_connect_data(official,"clicked",(GCallback)on_find_official_trainer,NULL,NULL,0);
    g_signal_connect_data(check,"clicked",(GCallback)on_check_trainer_updates,NULL,NULL,0);
    g_signal_connect_data(source_status,"clicked",(GCallback)on_inspect_release_sources,NULL,NULL,0);
    pack(updates_row,official,0);pack(updates_row,check,0);pack(upd,updates_row,0);
    GtkWidget*updates_row2=box(GTK_ORIENTATION_HORIZONTAL,5);
    GtkWidget*offline_check=button("Check saved downloads","action");
    g_signal_connect_data(offline_check,"clicked",(GCallback)on_check_local_trainer_catalog,NULL,NULL,0);
    pack(updates_row2,offline_check,0);pack(updates_row2,source_status,0);pack(upd,updates_row2,0);
    G.trainer_updates_install_button=button("Stage approved trainer…","action");
    gtk_widget_set_sensitive(G.trainer_updates_install_button,FALSE);
    g_signal_connect_data(G.trainer_updates_install_button,"clicked",(GCallback)on_install_verified_trainer,NULL,NULL,0);
    pack(upd,G.trainer_updates_install_button,0);
    G.trainer_updates_status=label("Select a game to review its publisher page. Downloads need a trusted or explicitly approved catalog entry.","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.trainer_updates_status,TRUE);pack(upd,G.trainer_updates_status,0);
    pack(updates_right,updates_exp,0);

    GtkWidget*security_exp=gtk_expander_new("Trusted sources and signing keys");
    GtkWidget*security=box(GTK_ORIENTATION_VERTICAL,6);style(security,"panel-soft");
    style(security_exp,"panel");gtk_container_add(security_exp,security);gtk_expander_set_expanded((GtkWidget*)security_exp,FALSE);
    GtkWidget*security_note=label("Keys are not bundled. Independently verify the publisher's Ed25519 key before pinning it. A valid signature does not prove an executable safe.","muted");
    gtk_label_set_line_wrap((GtkLabel*)security_note,TRUE);pack(security,security_note,0);
    GtkWidget*trust_check=button("Inspect catalog trust (offline)","action");
    g_signal_connect_data(trust_check,"clicked",(GCallback)on_audit_trainer_catalog,NULL,NULL,0);pack(security,trust_check,0);
    GtkWidget*sr=box(GTK_ORIENTATION_HORIZONTAL,5);
    GtkWidget*pin_provider=button("Pin selected provider key…","action");
    g_signal_connect_data(pin_provider,"clicked",(GCallback)on_pin_catalog_provider_key,NULL,NULL,0);
    GtkWidget*import_signed=button("Import signed catalog…","action");
    g_signal_connect_data(import_signed,"clicked",(GCallback)on_import_signed_trainer_catalog,NULL,NULL,0);
    pack(sr,pin_provider,0);pack(sr,import_signed,0);pack(security,sr,0);pack(advanced_page,security_exp,0);

    GtkWidget*recovery_exp=gtk_expander_new("Staged trainer backups and restore");
    GtkWidget*recovery=box(GTK_ORIENTATION_VERTICAL,6);style(recovery,"panel-soft");
    style(recovery_exp,"panel");gtk_container_add(recovery_exp,recovery);gtk_expander_set_expanded((GtkWidget*)recovery_exp,FALSE);
    GtkWidget*recovery_note=label("Only locally staged copies are inspected or restored. Existing game assignments never change automatically.","muted");
    gtk_label_set_line_wrap((GtkLabel*)recovery_note,TRUE);pack(recovery,recovery_note,0);
    GtkWidget*staging_row=box(GTK_ORIENTATION_HORIZONTAL,6);
    G.trainer_updates_inspect_button=button("Inspect staged trainer","action");
    G.trainer_updates_rollback_button=button("Restore previous staged copy…","action");
    gtk_widget_set_sensitive(G.trainer_updates_inspect_button,FALSE);
    gtk_widget_set_sensitive(G.trainer_updates_rollback_button,FALSE);
    g_signal_connect_data(G.trainer_updates_inspect_button,"clicked",(GCallback)on_staged_trainer_action,NULL,NULL,0);
    g_signal_connect_data(G.trainer_updates_rollback_button,"clicked",(GCallback)on_staged_trainer_action,(void*)1,NULL,0);
    pack(staging_row,G.trainer_updates_inspect_button,0);pack(staging_row,G.trainer_updates_rollback_button,0);
    pack(recovery,staging_row,0);pack(advanced_page,recovery_exp,0);
    GtkWidget*preflight=box(GTK_ORIENTATION_VERTICAL,6);style(preflight,"panel-soft");
    pack(preflight,label("STABILITY PREFLIGHT — READ ONLY","section-kicker"),0);
    pack(preflight,label("Read-only checks for missing trainer files and update state, plus a per-game launch checklist for real CachyOS field testing.","muted"),0);
    GtkWidget*preflight_button=button("Export stability and launcher checklist","action");
    g_signal_connect_data(preflight_button,"clicked",(GCallback)on_stability_preflight,NULL,NULL,0);
    pack(preflight,preflight_button,0);
    stability_preflight_status=label("Not run. Exports stability-preflight.md with assigned-game launch checklist to private GameWeld state.","muted");
    gtk_label_set_line_wrap((GtkLabel*)stability_preflight_status,TRUE);
    pack(preflight,stability_preflight_status,0);
    pack(advanced_page,preflight,0);
    GtkWidget*maint=box(GTK_ORIENTATION_VERTICAL,6);style(maint,"panel");pack(maint,label("MAINTENANCE","section-kicker"),0);GtkWidget*mr1=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*manual=button("Choose EXE…","action");GtkWidget*clear=button("Clear assignment","action");g_signal_connect_data(manual,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);pack(mr1,manual,0);pack(mr1,clear,0);pack(maint,mr1,0);GtkWidget*mr2=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*ignore=button("Ignore selected","action");GtkWidget*clearignore=button("Clear ignored","action");GtkWidget*prune=button("Prune missing","action");g_signal_connect_data(ignore,"clicked",(GCallback)on_ignore_library_pick,NULL,NULL,0);g_signal_connect_data(clearignore,"clicked",(GCallback)on_clear_ignored_trainers,NULL,NULL,0);g_signal_connect_data(prune,"clicked",(GCallback)on_prune_missing_trainers,NULL,NULL,0);pack(mr2,ignore,0);pack(mr2,clearignore,0);pack(mr2,prune,0);pack(maint,mr2,0);pack(advanced_page,maint,0);
    GtkWidget*more=box(GTK_ORIENTATION_HORIZONTAL,8);
    pack(more,rescan,0);pack(more,refresh,0);
    GtkWidget*scan_extra=gtk_expander_new("Scan and view maintenance");
    gtk_container_add(scan_extra,more);pack(advanced_page,scan_extra,0);
    pack(body,right,0);pack(main_page,body,1);
    gtk_notebook_set_current_page((GtkNotebook*)workspace,0);
    return outer;
}

static GtkWidget *build_setup(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,20);gtk_container_add(outer,p);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("SETUP","page-kicker"),0);pack(ht,label("Compatibility & runtime","workspace-title"),0);pack(ht,label("Compatibility Engine v2 models trainer requirements while GameWeld keeps runtime ownership launcher-native and leaves your normal Proton installations untouched.","page-subtitle"),0);
    if(pc2_discovery_only()){
        GtkWidget*scope=label("The status below checks GameWeld's optional isolated Wand compatibility tool. It is NOT required for the independent DeckCheatz 1.x + your chosen Proton + WeMod path.","muted");
        gtk_label_set_line_wrap((GtkLabel*)scope,TRUE);pack(ht,scope,0);
    }
    pack(p,ht,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*c=box(GTK_ORIENTATION_VERTICAL,8);style(c,"panel");pack(c,label("CORE STATUS","section-kicker"),0);G.setup_status=label("Checking…","metric-value");pack(c,G.setup_status,0);G.setup_detail=label("Checking compatibility…","muted");gtk_label_set_line_wrap((GtkLabel*)G.setup_detail,TRUE);pack(c,G.setup_detail,0);GtkWidget*row=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*i=button("Install / repair","primary-action");GtkWidget*v=button("Verify","action");g_signal_connect_data(i,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(v,"clicked",(GCallback)on_verify,NULL,NULL,0);pack(row,i,0);pack(row,v,0);pack(c,row,0);pack(left,c,0);GtkWidget*safety=box(GTK_ORIENTATION_VERTICAL,7);style(safety,"panel-soft");pack(safety,label("ISOLATED BY DESIGN","section-kicker"),0);GtkWidget*sd=label("Compatibility changes stay inside GameWeld's managed tool. Normal Steam Proton and Heroic runner configuration remain yours.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(safety,sd,0);pack(left,safety,0);GtkWidget*what=box(GTK_ORIENTATION_VERTICAL,8);style(what,"panel");pack(what,label("WHAT GAMEWELD MANAGES","section-kicker"),0);pack(what,label("• Steam and Proton-GE detection\n• Isolated GameWeld Steam compatibility tool\n• Proven crypt32 compatibility payload\n• Runtime verification before launch\n• Compatibility Engine v2 trainer recipes\n• No replacement of your normal Proton-GE installs","muted"),0);pack(right,what,0);GtkWidget*next=box(GTK_ORIENTATION_VERTICAL,8);style(next,"panel-soft");pack(next,label("WHEN TO USE THIS PAGE","section-kicker"),0);GtkWidget*nd=label("Use Repair only when Diagnostics reports a compatibility problem or after changing major runtime packages. Otherwise leave a working launch path alone.","muted");gtk_label_set_line_wrap((GtkLabel*)nd,TRUE);pack(next,nd,0);pack(right,next,0);pack(cols,left,1);pack(cols,right,1);pack(p,cols,1);return outer;}
static GtkWidget *build_diag(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,20);gtk_container_add(outer,p);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("SUPPORT","page-kicker"),0);pack(ht,label("Diagnostics & support","workspace-title"),0);pack(ht,label("Inspect only the selected game's launch path and export a privacy-scoped bundle when you need help.","page-subtitle"),0);pack(p,ht,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*health=box(GTK_ORIENTATION_VERTICAL,9);style(health,"panel");pack(health,label("TRAINER HEALTH","section-kicker"),0);GtkWidget*h=button("Run selected-game health check","primary-action");g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);pack(health,h,0);G.health_detail=label("Launch the selected game with its configured trainer provider, then run this check to inspect trainer and command health.","muted");gtk_label_set_line_wrap((GtkLabel*)G.health_detail,TRUE);pack(health,G.health_detail,0);pack(cols,health,1);GtkWidget*support=box(GTK_ORIENTATION_VERTICAL,9);style(support,"panel");pack(support,label("SUPPORT BUNDLE","section-kicker"),0);GtkWidget*sd=label("Exports resolved launcher/runtime/prefix metadata, trainer diagnostics, matching Trainer Library rows and selected-app logs. Trainer EXE bytes, browser data and unrelated logs are excluded.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(support,sd,0);GtkWidget*sb=button("Export selected support bundle","primary-action");g_signal_connect_data(sb,"clicked",(GCallback)on_export_support_bundle,NULL,NULL,0);pack(support,sb,0);G.support_bundle_status=label("Saved to Downloads when created.","good");gtk_label_set_line_wrap((GtkLabel*)G.support_bundle_status,TRUE);pack(support,G.support_bundle_status,0);pack(cols,support,1);pack(p,cols,0);GtkWidget*scope=box(GTK_ORIENTATION_VERTICAL,8);style(scope,"panel-soft");pack(scope,label("PRIVACY SCOPE","section-kicker"),0);pack(scope,label("Support exports are selected-game scoped. GameWeld does not include a global environment dump, browser data, trainer binaries or unrelated game logs.","muted"),0);pack(p,scope,0);return outer;}

/* Preserve an explicitly chosen existing Wand client across PC2 UI sessions.
 * This file contains only the selected client/prefix paths, never credentials. */
static void pc2_wand_choice_path(char *out,size_t cap){
    const char*xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg&&xdg[0]=='/')snprintf(out,cap,"%s/gameweld/wand-selected-client.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/wand-selected-client.tsv",home&&home[0]=='/'?home:"/tmp");
}
static int pc2_wand_choice_clean(const char *v){
    if(!v||v[0]!='/')return 0;
    for(const char*p=v;*p;p++)if(*p=='\t'||*p=='\n'||*p=='\r')return 0;
    return 1;
}
static void pc2_save_wand_choice(const char*prefix,const char*install){
    if(!pc2_wand_choice_clean(prefix)||!pc2_wand_choice_clean(install))return;
    char path[4096],dir[4096];pc2_wand_choice_path(path,sizeof path);
    snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');
    if(!slash)return;*slash=0;
    if(g_mkdir_with_parents(dir,0700)!=0)return;
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC|O_NOFOLLOW,0600);
    if(fd<0)return;
    struct stat st;
    if(fstat(fd,&st)==0&&S_ISREG(st.st_mode))
        dprintf(fd,"%s\t%s\n",prefix,install);
    close(fd);
}
static int pc2_load_wand_choice(char *prefix,size_t pcap,char *install,size_t icap){
    char path[4096];pc2_wand_choice_path(path,sizeof path);
    FILE*f=fopen(path,"r");if(!f)return 0;
    char line[4096];int ok=0;
    if(fgets(line,sizeof line,f)){
        line[strcspn(line,"\r\n")]=0;
        char*tab=strchr(line,'\t');
        if(tab){*tab++=0;
            if(pc2_wand_choice_clean(line)&&pc2_wand_choice_clean(tab)){
                snprintf(prefix,pcap,"%.*s",(int)(pcap?pcap-1:0),line);
                snprintf(install,icap,"%s",tab);
                ok=1;
            }
        }
    }
    fclose(f);return ok;
}
/* The integrated PC2 WeMod Enhancer can adopt an unambiguous install from the
  * existing Wand/WeMod discovery without changing the user's manual choice. */
static GtkWidget *pc2_wemod_install_entry=NULL;
/* Test 6: read-only installation discovery in a background worker. */
typedef struct {char product[32],source[72],version[110],prefix[2048],install[2048];} WandDetected;
typedef struct {char *text;int ok;} WandDetectJob;
static WandDetected wand_detected[200];
static int wand_detected_count=0;
static GtkWidget *wand_detected_combo=NULL;
static int wand_detect_busy=0,wand_detect_updating=0;
static void wand_detect_changed(GtkComboBox *cb,gpointer data){
    (void)data;
    if(wand_detect_updating)return;
    int idx=gtk_combo_box_get_active(cb);
    if(idx<0||idx>=wand_detected_count)return;
    WandDetected *it=&wand_detected[idx];
    wand_detect_updating=1;
    if(G.wand_patcher_prefix_entry)gtk_entry_set_text((GtkEntry*)G.wand_patcher_prefix_entry,it->prefix);
    if(G.wand_patcher_install_entry)gtk_entry_set_text((GtkEntry*)G.wand_patcher_install_entry,it->install);
    if(pc2_wemod_install_entry&&it->install[0]&&!gtk_entry_get_text((GtkEntry*)pc2_wemod_install_entry)[0])
        gtk_entry_set_text((GtkEntry*)pc2_wemod_install_entry,it->install);
    wand_detect_updating=0;
    pc2_save_wand_choice(it->prefix,it->install);
    if(G.wand_patcher_status){char msg[420];snprintf(msg,sizeof msg,"Detected %s (%s). Ready to inspect; no files changed.",it->product,it->version);set_label(G.wand_patcher_status,msg);}
}
static void wand_detect_manual_prefix(GtkEditable *editable,gpointer unused){
    (void)editable;(void)unused;
    if(wand_detect_updating)return;
    if(wand_detected_combo){wand_detect_updating=1;gtk_combo_box_set_active((GtkComboBox*)wand_detected_combo,-1);wand_detect_updating=0;}
    if(G.wand_patcher_install_entry)gtk_entry_set_text((GtkEntry*)G.wand_patcher_install_entry,"");
}
static gboolean wand_detect_finished(void *data){
    WandDetectJob *j=data;
    wand_detect_busy=0;
    if(!j->ok){set_label(G.wand_patcher_status,"Automatic detection failed. Use Choose Wine prefix only if needed.");goto done;}
    if(!wand_detected_combo)goto done;
    char previous_prefix[2048]={0},previous_install[2048]={0};
    if(G.wand_patcher_prefix_entry)snprintf(previous_prefix,sizeof previous_prefix,"%s",gtk_entry_get_text((GtkEntry*)G.wand_patcher_prefix_entry));
    if(G.wand_patcher_install_entry)snprintf(previous_install,sizeof previous_install,"%s",gtk_entry_get_text((GtkEntry*)G.wand_patcher_install_entry));
    if(!previous_prefix[0]&&!previous_install[0])
        pc2_load_wand_choice(previous_prefix,sizeof previous_prefix,previous_install,sizeof previous_install);
    wand_detect_updating=1;
    gtk_combo_box_text_remove_all((GtkComboBoxText*)wand_detected_combo);
    wand_detected_count=0;
    int total=0,scanned=0,truncated=0;
    char *save=NULL;
    for(char *ln=strtok_r(j->text,"\n",&save);ln;ln=strtok_r(NULL,"\n",&save)){
        if(!strncmp(ln,"FOUND\t",6)){
            char *fields[5]={0};int count=0;char *split=NULL;
            for(char *it=strtok_r(ln+6,"\t",&split);it&&count<5;it=strtok_r(NULL,"\t",&split))fields[count++]=it;
            if(count==5&&wand_detected_count<200){
                WandDetected *p=&wand_detected[wand_detected_count++];
                snprintf(p->product,sizeof p->product,"%s",fields[0]);snprintf(p->source,sizeof p->source,"%s",fields[1]);
                snprintf(p->version,sizeof p->version,"%s",fields[2]);snprintf(p->prefix,sizeof p->prefix,"%s",fields[3]);
                snprintf(p->install,sizeof p->install,"%s",fields[4]);
                char caption[2450];snprintf(caption,sizeof caption,"%s %s  |  %s  |  %s",p->product,p->version,p->source,p->prefix);
                gtk_combo_box_text_append_text((GtkComboBoxText*)wand_detected_combo,caption);
            }
        }else if(!strncmp(ln,"STATUS\t",7)){
            sscanf(ln,"STATUS\t%d\t%d\t%d",&total,&scanned,&truncated);
        }
    }
    int matching=-1;
    if(previous_prefix[0]&&previous_install[0])for(int i=0;i<wand_detected_count;i++){
        if(!strcmp(previous_prefix,wand_detected[i].prefix)&&!strcmp(previous_install,wand_detected[i].install)){matching=i;break;}
    }
    /* Select automatically ONLY when there is one installation and no earlier choice. */
    int choice=matching>=0?matching:(!previous_prefix[0]&&wand_detected_count==1?0:-1);
    if(choice>=0){
        WandDetected*it=&wand_detected[choice];
        gtk_entry_set_text((GtkEntry*)G.wand_patcher_prefix_entry,it->prefix);
        gtk_entry_set_text((GtkEntry*)G.wand_patcher_install_entry,it->install);
        if(pc2_wemod_install_entry&&it->install[0]&&!gtk_entry_get_text((GtkEntry*)pc2_wemod_install_entry)[0])
            gtk_entry_set_text((GtkEntry*)pc2_wemod_install_entry,it->install);
    }else if(previous_prefix[0]&&previous_install[0]){
        gtk_entry_set_text((GtkEntry*)G.wand_patcher_prefix_entry,"");
        gtk_entry_set_text((GtkEntry*)G.wand_patcher_install_entry,"");
    }
    if(!wand_detected_count)gtk_combo_box_text_append_text((GtkComboBoxText*)wand_detected_combo,"No Wand installation detected");
    gtk_combo_box_set_active((GtkComboBox*)wand_detected_combo,choice);
    wand_detect_updating=0;
    if(choice>=0){
        set_label(G.wand_patcher_status,matching>=0?"Previous client selection preserved; choose Patch WeMod when ready. No files changed.":"Found one existing Wand/WeMod client; choose Patch WeMod when ready. No files changed.");
    }else if(previous_prefix[0]&&previous_install[0]){
        set_label(G.wand_patcher_status,"Previous client selection could not be confirmed. Choose the correct app-version folder before patching or restoring.");
    }else if(wand_detected_count){
        set_label(G.wand_patcher_status,"Multiple Wand/WeMod installs found. Select the correct one above before proceeding; no files changed.");
    }else{
        set_label(G.wand_patcher_status,"No existing Wand/WeMod client detected. Choose the app-version folder manually, or use PC1 to install/configure Wand. PC2 does not reinstall Proton.");
    }
    log_line("Wand auto-detection: %d installations in %d Wine prefixes; truncated=%d.",total,scanned,truncated);
done:
    free(j->text);free(j);return FALSE;
}
/* Limit helper output and time without blocking the GTK main loop.  Child runs in
 * its own process group so timeout does not leave a subprocess holding the pipe. */
static int bounded_child_output(pid_t pid,int fd,char *output,size_t capacity,int seconds){
    int status=0,finished=0;size_t used=0;time_t deadline=time(NULL)+seconds;
    fcntl(fd,F_SETFL,fcntl(fd,F_GETFL,0)|O_NONBLOCK);
    while(time(NULL)<deadline){
        struct pollfd pfd={.fd=fd,.events=POLLIN|POLLHUP};
        int r=poll(&pfd,1,150);
        if(r>0){char block[4096];ssize_t n;
            while((n=read(fd,block,sizeof block))>0){
                size_t take=(size_t)n<capacity-used-1?(size_t)n:capacity-used-1;
                if(take){memcpy(output+used,block,take);used+=take;}
                if(used==capacity-1){output[used]=0;kill(-pid,SIGKILL);kill(pid,SIGKILL);waitpid(pid,&status,0);close(fd);return 0;}
            }
        }
        pid_t done=waitpid(pid,&status,WNOHANG);
        if(done==pid){finished=1;break;}
        if(done<0&&errno!=EINTR)break;
    }
    if(!finished){kill(-pid,SIGKILL);kill(pid,SIGKILL);while(waitpid(pid,&status,0)<0&&errno==EINTR){} }
    /* Drain buffered output after successful process completion. */
    if(finished){char block[4096];ssize_t n;while((n=read(fd,block,sizeof block))>0){
        size_t take=(size_t)n<capacity-used-1?(size_t)n:capacity-used-1;
        if(take){memcpy(output+used,block,take);used+=take;}
    }}
    close(fd);output[used]=0;
    return finished&&WIFEXITED(status)&&WEXITSTATUS(status)==0;
}

static void *wand_detect_worker(void *data){
    WandDetectJob *j=data;
    j->text=calloc(1,131073);
    if(!j->text){g_idle_add(wand_detect_finished,j);return NULL;}
    int pipefd[2];
    if(pipe(pipefd)!=0){g_idle_add(wand_detect_finished,j);return NULL;}
    pid_t pid=fork();
    if(pid==0){
        setpgid(0,0);
        close(pipefd[0]);dup2(pipefd[1],STDOUT_FILENO);close(pipefd[1]);
        const char *tool=wand_patcher_tool();
        char path[2200];const char *slash=strrchr(tool,'/');
        if(slash)snprintf(path,sizeof path,"%.*s/gameweld-wand-discovery.py",(int)(slash-tool),tool);
        else snprintf(path,sizeof path,"gameweld-wand-discovery.py");
        char *const argv[]={"python3",path,"--tsv",NULL};execvp("python3",argv);_exit(127);
    }
    close(pipefd[1]);
    if(pid<0){close(pipefd[0]);g_idle_add(wand_detect_finished,j);return NULL;}
    j->ok=bounded_child_output(pid,pipefd[0],j->text,131073,35);
    g_idle_add(wand_detect_finished,j);return NULL;
}
static void wand_detect_start(void){
    if(wand_detect_busy)return;
    wand_detect_busy=1;
    if(G.wand_patcher_status)set_label(G.wand_patcher_status,"Looking for installed Wand/WeMod in Steam, Lutris, Heroic and Wine…");
    WandDetectJob*j=calloc(1,sizeof *j);pthread_t thread;
    if(!j){wand_detect_busy=0;return;}
    if(pthread_create(&thread,NULL,wand_detect_worker,j)==0)pthread_detach(thread);
    else{wand_detect_busy=0;free(j);set_label(G.wand_patcher_status,"Could not start automatic detection. Choose manually.");}
}
static void on_wand_detect(GtkButton *b,gpointer d){(void)b;(void)d;wand_detect_start();}

/* Read-only per-game GUI readiness. The subprocess only queries installed
 * Bridge state. A result from a previously selected game is never allowed to
 * update the current game's Play/Setup button. */
typedef struct {
    char appid[192],result[2048],game_dir[2048];
    unsigned generation;
    int ok;
} PC2BridgeReadiness;
static char pc2_bridge_ready_appid[192]={0};
static char pc2_bridge_ready_state[24]="blocked";
static char pc2_bridge_ready_reason[2048]={0};
static unsigned pc2_bridge_readiness_generation=0;
/* The settings-level repair button is enabled only by a matching read-only
 * preflight reporting a verified launcher update. */
static GtkWidget *pc2_steam_bridge_quick_upgrade=NULL;
static void pc2_quick_upgrade_state(int update_available, int is_current){
    if(!pc2_steam_bridge_quick_upgrade)return;
    GtkWidget *button=pc2_steam_bridge_quick_upgrade;
    GtkStyleContext *style=gtk_widget_get_style_context(button);
    gtk_style_context_remove_class(style,"primary-action");
    if(update_available)gtk_style_context_add_class(style,"primary-action");
    gtk_button_set_label((GtkButton*)button,
        update_available?"Update Steam Bridge":
        is_current?"Steam Bridge is up to date":"Update Steam Bridge");
    gtk_widget_set_sensitive(button,update_available);
}

static int pc2_bridge_has_stale_launcher(const char *state,const char *reason){
    /* Only this exact, source-verified failure routes to launcher-only repair.
     * Other repair conditions must not silently alter the Steam Bridge. */
    return state && reason && !strcmp(state,"repair") &&
        strstr(reason,"Installed Steam Bridge launcher is outdated or unverified:")!=NULL &&
        strstr(reason,"UPDATE AVAILABLE (")!=NULL;
}
static void pc2_bridge_apply_primary(const char *state,const char *reason){
    /* The primary PC2 WeMod flow is provider-native, not Steam Bridge.
     * Legacy Bridge status must never cause the main Play button to claim
     * a trainer is ready or demand a change to Steam compatibility. */
    (void)state;(void)reason;
    GtkWidget *buttons[]={G.pc2_deckcheatz_overview_play,G.pc2_deckcheatz_library_play};
    for(int i=0;i<2;i++)if(buttons[i]){
        gtk_button_set_label((GtkButton*)buttons[i],
            pc2_steam_wemod_allowed()?"Play via Steam + WeMod (private test)":
            pc2_native_wrapper_allowed()?"Launch native Rust wrapper + WeMod (experimental)":
            pc2_steam_launch_allowed()?"Play via Steam + DeckCheatz":"Set up DeckCheatz for Steam");
        gtk_widget_set_sensitive(buttons[i],TRUE);
    }
    if(G.pc2_deckcheatz_overview_status)
        set_label(G.pc2_deckcheatz_overview_status,
            pc2_steam_wemod_allowed()?
            "Steam launches normally; separate consented WeMod client handoff follows. Attachment unverified.":
            pc2_native_wrapper_allowed()?
            "Rust direct-wrapper test; bypasses Steam supervisor. Consent required; trainer unverified.":
            pc2_steam_launch_allowed()?
            "Uses Steam\x27s saved per-game Launch Options after consent. Trainer not yet verified.":
            "Copy the DeckCheatz Steam launch option in Settings. No configuration modified.");
    if(G.pc2_deckcheatz_library_status)
        set_label(G.pc2_deckcheatz_library_status,
            pc2_steam_wemod_allowed()?
            "Steam-managed mode. No Steam Bridge or Proton selection; WeMod attachment not verified.":
            pc2_native_wrapper_allowed()?
            "Native Rust wrapper mode enabled. Steam Launch Options unchanged; game and trainer unverified.":
            pc2_steam_launch_allowed()?
            "Steam-managed wrapper launch enabled with explicit confirmation; no direct WeMod injection.":
            "Configure DeckCheatz in Steam Properties before using Play via Steam.");
}

static gboolean pc2_bridge_readiness_done(gpointer data){
    PC2BridgeReadiness *job=data;
    if(job->generation==pc2_bridge_readiness_generation &&
       G.selected>=0&&G.selected<G.game_count &&
       !strcmp(G.games[G.selected].appid,job->appid)){
        const char *state="blocked";
        char reason[2048]="Cannot check GameWeld Bridge readiness. Check Settings.";
        if(job->ok){
            char *sep=strchr(job->result,'\t');
            if(sep){
                *sep=0;
                if(!strcmp(job->result,"play")||!strcmp(job->result,"setup")||
                   !strcmp(job->result,"enable")||!strcmp(job->result,"steam")||
                   !strcmp(job->result,"repair")||
                   !strcmp(job->result,"runtime")){
                    state=job->result;
                    snprintf(reason,sizeof reason,"%s",sep+1);
                    reason[strcspn(reason,"\r\n")]=0;
                }
            }
        }
        snprintf(pc2_bridge_ready_state,sizeof pc2_bridge_ready_state,"%.*s",(int)sizeof(pc2_bridge_ready_state)-1,state);
        snprintf(pc2_bridge_ready_reason,sizeof pc2_bridge_ready_reason,"%s",reason);
        pc2_bridge_apply_primary(state,reason);
    }
    free(job);
    return FALSE;
}
static void *pc2_bridge_readiness_worker(void *data){
    PC2BridgeReadiness *job=data;
    int pipes[2];
    if(pipe(pipes)!=0){g_idle_add(pc2_bridge_readiness_done,job);return NULL;}
    pid_t child=fork();
    if(child==0){
        close(pipes[0]);dup2(pipes[1],STDOUT_FILENO);
        dup2(pipes[1],STDERR_FILENO);close(pipes[1]);
        const char *appdir=getenv("APPDIR");
        char helper[2048];
        if(appdir&&*appdir)
            snprintf(helper,sizeof helper,"%s/usr/libexec/gameweld-steam-compat-bridge.py",appdir);
        else snprintf(helper,sizeof helper,"gameweld-steam-compat-bridge.py");
        char *const args[]={"python3",helper,"ui-state","--appid",job->appid,
            "--game-dir",job->game_dir,NULL};
        execvp("python3",args);
        _exit(127);
    }
    close(pipes[1]);
    if(child<0){close(pipes[0]);g_idle_add(pc2_bridge_readiness_done,job);return NULL;}
    job->ok=bounded_child_output(child,pipes[0],job->result,sizeof job->result,8);
    g_idle_add(pc2_bridge_readiness_done,job);
    return NULL;
}
static void pc2_bridge_readiness_for_game(Game *g){
    if(!pc2_provider_controls_allowed()||!g||!g->appid[0])return;
    if(!strcmp(g->appid,pc2_bridge_ready_appid)){
        pc2_bridge_apply_primary(pc2_bridge_ready_state,pc2_bridge_ready_reason);
        return;
    }
    snprintf(pc2_bridge_ready_appid,sizeof pc2_bridge_ready_appid,"%s",g->appid);
    pc2_quick_upgrade_state(0,0);
    snprintf(pc2_bridge_ready_state,sizeof pc2_bridge_ready_state,"checking");
    pc2_bridge_readiness_generation++;
    pc2_bridge_apply_primary("checking","Checking saved Steam Bridge configuration…");
    PC2BridgeReadiness *job=calloc(1,sizeof *job);
    if(!job)return;
    snprintf(job->appid,sizeof job->appid,"%s",g->appid);
    snprintf(job->game_dir,sizeof job->game_dir,"%s",g->install_dir);
    job->generation=pc2_bridge_readiness_generation;
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_bridge_readiness_worker,job)==0)
        pthread_detach(thread);
    else{
        free(job);
        pc2_bridge_apply_primary("blocked","Could not check Steam Bridge; use Settings.");
    }
}
static void pc2_bridge_readiness_invalidate(void){
    pc2_quick_upgrade_state(0,0);
    pc2_bridge_ready_appid[0]=0;
    pc2_bridge_ready_state[0]=0;
    pc2_bridge_readiness_generation++;
}

/* Steam compatibility bridge management is deliberately isolated from the
 * original live-Wine launcher. Status is read-only; per-game toggles require
 * confirmation and take effect only on the next Steam launch. */
typedef struct {
    char action[24],appid[192],game[256],output[4096];
    char game_dir[2048],steam_root[1024],provider[32],prefix[2048],runner[2048];
    char source_url[1024],source_bytes[32];
    int ok;
} PC2SteamBridgeJob;
static int pc2_steam_bridge_busy=0;
static GtkWidget *pc2_steam_bridge_status=NULL;
static GtkWidget *pc2_shared_wemod_status=NULL;
static GtkWidget *pc2_shared_wemod_choices=NULL;
static GtkWidget *pc2_shared_wemod_download=NULL;
static GtkWidget *pc2_shared_wemod_cancel=NULL;
static volatile sig_atomic_t pc2_cache_child_pid=0;
static volatile sig_atomic_t pc2_cache_cancel_requested=0;
typedef struct { int percent; char stage[16]; } PC2CacheProgressEvent;
static gboolean pc2_cache_progress_update(gpointer data){
    PC2CacheProgressEvent *event=data;
    if(pc2_steam_bridge_busy && pc2_shared_wemod_status){
        char message[256];
        if(!strcmp(event->stage,"VERIFY"))
            snprintf(message,sizeof message,
                "Transfer reached 100%%. Validating ZIP and CRC; NOT SAVED for staging yet.");
        else if(!strcmp(event->stage,"CACHED"))
            snprintf(message,sizeof message,
                "ZIP verified and written to GameWeld cache. Finalizing download receipt...");
        else if(!strcmp(event->stage,"STAGE")||!strcmp(event->stage,"STAGED"))
            snprintf(message,sizeof message,
                "Preparing isolated .NET template: %d%%. Original game prefix untouched.",
                event->percent);
        else
            snprintf(message,sizeof message,
                "Transferring prepared ZIP: %d%%. Staging unavailable until validation completes.",
                event->percent);
        set_label(pc2_shared_wemod_status,message);
    }
    free(event);
    return FALSE;
}
static void pc2_cache_report_line(const char *line,char *result,
                                   size_t capacity,size_t *used){
    if(!strncmp(line,"PROGRESS\t",9)){
        char stage[16]={0};
        long long current=0,total=0;
        if(sscanf(line+9,"%15[^\t]\t%lld\t%lld",stage,&current,&total)==3
           &&total>0&&current>=0&&current<=total){
            PC2CacheProgressEvent *event=calloc(1,sizeof *event);
            if(event){
                snprintf(event->stage,sizeof event->stage,"%s",stage);
                event->percent=(int)(100*current/total);
                g_idle_add(pc2_cache_progress_update,event);
            }
        }
        return;
    }
    size_t n=strlen(line);
    if(*used+n+2<capacity){
        memcpy(result+*used,line,n);
        *used+=n;
        result[(*used)++]='\n';
        result[*used]=0;
    }
}
static int pc2_cache_collect_output(pid_t pid,int fd,char *result,
                                    size_t capacity,int seconds){
    int status=0,finished=0;size_t used=0,line_used=0;
    char line[2048]={0};
    time_t deadline=time(NULL)+seconds;
    fcntl(fd,F_SETFL,fcntl(fd,F_GETFL,0)|O_NONBLOCK);
    while(time(NULL)<deadline){
        struct pollfd pfd={.fd=fd,.events=POLLIN|POLLHUP};
        if(poll(&pfd,1,200)>0){
            char block[4096];ssize_t n;
            while((n=read(fd,block,sizeof block))>0){
                for(ssize_t i=0;i<n;i++){
                    if(block[i]=='\n'){
                        line[line_used]=0;
                        pc2_cache_report_line(line,result,capacity,&used);
                        line_used=0;
                    }else if(line_used+1<sizeof line)
                        line[line_used++]=block[i];
                }
            }
        }
        pid_t completed=waitpid(pid,&status,WNOHANG);
        if(completed==pid){finished=1;break;}
        if(completed<0&&errno!=EINTR)break;
    }
    if(!finished){
        kill(pid,SIGINT);
        kill(-pid,SIGINT);
        /* Interrupt first to let Python remove its temporary file. */
        for(int i=0;i<10;i++){
            if(waitpid(pid,&status,WNOHANG)==pid){finished=1;break;}
            usleep(100000);
        }
        if(!finished){
            kill(pid,SIGKILL);kill(-pid,SIGKILL);
            while(waitpid(pid,&status,0)<0&&errno==EINTR){}
        }
    }else{
        char block[4096];ssize_t n;
        while((n=read(fd,block,sizeof block))>0){
            for(ssize_t i=0;i<n;i++){
                if(block[i]=='\n'){
                    line[line_used]=0;
                    pc2_cache_report_line(line,result,capacity,&used);
                    line_used=0;
                }else if(line_used+1<sizeof line)
                    line[line_used++]=block[i];
            }
        }
    }
    if(line_used){line[line_used]=0;
        pc2_cache_report_line(line,result,capacity,&used);}
    close(fd);
    return finished&&WIFEXITED(status)&&WEXITSTATUS(status)==0;
}

typedef struct {
    char tag[128],name[256],url[1024];
    long long bytes;
} PC2PreparedChoice;
static PC2PreparedChoice pc2_prepared_choices[4];
static int pc2_prepared_choice_count=0;
static void pc2_prepared_choice_update(GtkComboBox *box, gpointer unused){
    (void)unused;
    if(!pc2_shared_wemod_download)return;
    int index=gtk_combo_box_get_active(box);
    gtk_widget_set_sensitive(pc2_shared_wemod_download,
        pc2_provider_controls_allowed() &&
        index>=0 && index<pc2_prepared_choice_count);
}
static void pc2_prepared_choices_clear(void){
    pc2_prepared_choice_count=0;
    if(pc2_shared_wemod_choices){
        gtk_combo_box_text_remove_all((GtkComboBoxText*)pc2_shared_wemod_choices);
        gtk_combo_box_set_active((GtkComboBox*)pc2_shared_wemod_choices,-1);
    }
    if(pc2_shared_wemod_download)gtk_widget_set_sensitive(pc2_shared_wemod_download,FALSE);
}
static void pc2_prepared_catalog_display(const char *raw){
    pc2_prepared_choices_clear();
    char *copy=g_strdup(raw ? raw : "");
    char *save=NULL;
    GString *summary=g_string_new("");
    int skipped_rejected=0;
    for(char *line=strtok_r(copy,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
        if(!strncmp(line,"ASSET\t",6)){
            gchar **cols=g_strsplit(line,"\t",5);
            if(g_strv_length(cols)==5 && pc2_prepared_choice_count<4 &&
               strlen(cols[1])<128 && strlen(cols[2])<256 &&
               strlen(cols[4])<1024 &&
               g_str_has_prefix(cols[4],
                   "https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/")){
                char *end=NULL;
                gint64 size=g_ascii_strtoll(cols[3],&end,10);
                if(end&&!*end&&size>=1000000&&size<=3000000000LL){
                    PC2PreparedChoice *choice=&pc2_prepared_choices[pc2_prepared_choice_count++];
                    snprintf(choice->tag,sizeof choice->tag,"%s",cols[1]);
                    snprintf(choice->name,sizeof choice->name,"%s",cols[2]);
                    snprintf(choice->url,sizeof choice->url,"%s",cols[4]);
                    choice->bytes=size;
                    if(pc2_shared_wemod_choices){
                        char label[512];
                        snprintf(label,sizeof label,"%s — %s (%.1f MiB)",
                                 choice->tag,choice->name,(double)size/1048576.0);
                        gtk_combo_box_text_append_text(
                            (GtkComboBoxText*)pc2_shared_wemod_choices,label);
                    }
                }
            }
            g_strfreev(cols);
        }else if(!strncmp(line,"BLOCKED\t",8)){
            /* Already rejected locally: intentionally NOT added to dropdown. */
            skipped_rejected++;
        }else{
            g_string_append(summary,line);
            g_string_append_c(summary,'\n');
        }
    }
    /* GTK may implicitly select the first row when items are appended.
     * An unverified 900+ MiB third-party prefix must never be selected
     * automatically, especially when no matching Proton version is known. */
    if(pc2_shared_wemod_choices)
        gtk_combo_box_set_active((GtkComboBox*)pc2_shared_wemod_choices,-1);
    if(pc2_shared_wemod_download)
        gtk_widget_set_sensitive(pc2_shared_wemod_download,FALSE);
    if(pc2_shared_wemod_status){
        char concise[1024];
        if(pc2_prepared_choice_count)
            snprintf(concise,sizeof concise,
                "%d possible prepared prefix release(s) found; %d previously "
                "rejected release(s) excluded. Select manually to review "
                "source and size. No release is runtime-verified; "
                "GameWeld did not download or install anything.",
                pc2_prepared_choice_count,skipped_rejected);
        else if(skipped_rejected)
            snprintf(concise,sizeof concise,
                "%d previously rejected prepared release(s) excluded from "
                "downloads because of unsafe case-only ZIP collisions. "
                "No verified replacement available in this catalog result. "
                "Do not retry the same archive; no files downloaded.",
                skipped_rejected);
        else
            snprintf(concise,sizeof concise,
                "No safe release choices found. The catalog may be offline "
                "or the release metadata may not match accepted ZIP rules. "
                "%.500s",summary->str);
        set_label(pc2_shared_wemod_status,concise);
    }
    g_string_free(summary,TRUE);
    g_free(copy);
}
static GtkWidget *pc2_native_route_status=NULL;
static const char *pc2_steam_bridge_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-steam-compat-bridge.py",appdir);
    else snprintf(p,sizeof p,"gameweld-steam-compat-bridge.py");
    return p;
}
static const char *pc2_prepared_prefix_catalog_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-deckcheatz-prefix-catalog.py",appdir);
    else snprintf(p,sizeof p,"gameweld-deckcheatz-prefix-catalog.py");
    return p;
}
static const char *pc2_prepared_prefix_cache_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-prepared-prefix-cache.py",appdir);
    else snprintf(p,sizeof p,"gameweld-prepared-prefix-cache.py");
    return p;
}
static const char *pc2_native_route_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-wemod-native-route.py",appdir);
    else snprintf(p,sizeof p,"gameweld-wemod-native-route.py");
    return p;
}
static const char *pc2_live_attach_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-wemod-live-attach.py",appdir);
    else snprintf(p,sizeof p,"gameweld-wemod-live-attach.py");
    return p;
}
static const char *pc2_prepared_prefix_stage_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-prepared-prefix-stage.py",appdir);
    else snprintf(p,sizeof p,"gameweld-prepared-prefix-stage.py");
    return p;
}
static const char *pc2_prepared_import_helper(void){
    static char path[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(path,sizeof path,"%s/usr/libexec/gameweld-prepared-prefix-import.py",appdir);
    else snprintf(path,sizeof path,"gameweld-prepared-prefix-import.py");
    return path;
}
static gboolean pc2_steam_bridge_done(gpointer data){
    PC2SteamBridgeJob*j=data;
    pc2_steam_bridge_busy=0;
    if(!strcmp(j->action,"prefix-cache")||!strcmp(j->action,"prefix-stage")){
        if(pc2_shared_wemod_cancel)
            gtk_widget_set_sensitive(pc2_shared_wemod_cancel,FALSE);
        if(pc2_shared_wemod_choices)
            pc2_prepared_choice_update((GtkComboBox*)pc2_shared_wemod_choices,NULL);
    }
    const char *msg=j->output[0]?j->output:(j->ok?"Complete.":"Steam Bridge operation failed.");
    if(!strcmp(j->action,"prefix-catalog")){
        if(j->ok)pc2_prepared_catalog_display(msg);
        else{
            pc2_prepared_choices_clear();
            if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,msg);
        }
    }else if(!strcmp(j->action,"prefix-cache")){
        if(pc2_cache_cancel_requested)msg="Cache download cancelled. "
            "Any incomplete temporary file should have been discarded. "
            "No game prefix was changed.";
        if(pc2_shared_wemod_status){
            if(j->ok && !pc2_cache_cancel_requested){
                const char *base=getenv("XDG_CACHE_HOME");
                char fallback[1024]={0},saved[1664];
                if(!base || !*base){
                    const char *home=getenv("HOME");
                    if(home && *home)
                        snprintf(fallback,sizeof fallback,"%s/.cache",home);
                    else snprintf(fallback,sizeof fallback,"%s","(unknown user cache)");
                    base=fallback;
                }
                snprintf(saved,sizeof saved,
                    "Step 1 complete — verified ZIP saved. Cache location: %.900s/"
                    "gameweld/prepared-wemod/downloads. "
                    "Next: Step 2 — Stage downloaded .NET prefix (isolated). "
                    "Game prefixes and Steam settings unchanged.",base);
                set_label(pc2_shared_wemod_status,saved);
            }else set_label(pc2_shared_wemod_status,msg);
        }
    }else if(!strcmp(j->action,"prefix-stage")){
#ifdef GAMEWELD_PC2_GTK_ACTION_SMOKE
        fprintf(stderr, "PC2_GTK_SMOKE_PREFIX_STAGE_HELPER_DONE status=%d\n", j->ok);
#endif
        if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
            j->ok ? "Step 2 complete — prepared .NET template staged privately. "
                    "Next: select a Steam game and use Step 3 to review compatibility. "
                    "Game prefixes and saves remain unchanged." : msg);
    }else if(!strcmp(j->action,"native-route")||!strcmp(j->action,"live-attach-preview")||!strcmp(j->action,"prepared-import-preview")){
        if(pc2_native_route_status)set_label(pc2_native_route_status,msg);
        if(G.pc2_deckcheatz_overview_status)
            set_label(G.pc2_deckcheatz_overview_status,
                "WeMod setup is a read-only preview. No game or trainer launched.");
    }else if(pc2_steam_bridge_status)set_label(pc2_steam_bridge_status,msg);
    if(pc2_steam_bridge_quick_upgrade &&
       (!strcmp(j->action,"preflight")||!strcmp(j->action,"upgrade"))){
        int selected_matches=G.selected>=0&&G.selected<G.game_count &&
            !strcmp(G.games[G.selected].appid,j->appid);
        int update_available=!strcmp(j->action,"preflight")&&j->ok&&
            selected_matches &&
            strstr(j->output,"Next action: REPAIR")!=NULL &&
            strstr(j->output,"Installed Steam Bridge: UPDATE AVAILABLE (")!=NULL;
        int is_current=!strcmp(j->action,"preflight")&&j->ok&&
            selected_matches &&
            strstr(j->output,"Installed Steam Bridge: UP TO DATE")!=NULL;
        pc2_quick_upgrade_state(update_available,is_current);
    }
    log_line("Steam Bridge [%s] for %s (%s): %s — %.2000s",
        j->action,j->game,j->appid,j->ok?"OK":"FAILED",msg);
    if(j->ok&&(!strcmp(j->action,"setup")||!strcmp(j->action,"trainer-on")||
              !strcmp(j->action,"trainer-off")||!strcmp(j->action,"upgrade"))){
        pc2_bridge_readiness_invalidate();
        if(G.selected>=0&&G.selected<G.game_count &&
           game_is_steam(&G.games[G.selected]) &&
           !game_is_steam_shortcut(&G.games[G.selected]))
            pc2_bridge_readiness_for_game(&G.games[G.selected]);
    }
    if(!strcmp(j->action,"play")){
        const char*state=j->ok?
            "Steam Play request accepted. Game and WeMod startup are NOT YET VERIFIED; check both windows.":
            "Steam Bridge launch was not confirmed. See Activity for the reported reason.";
        if(G.pc2_deckcheatz_overview_status)set_label(G.pc2_deckcheatz_overview_status,state);
        if(G.pc2_deckcheatz_library_status)set_label(G.pc2_deckcheatz_library_status,state);
    }
    free(j);return FALSE;
}
static void *pc2_steam_bridge_worker(void *data){
    PC2SteamBridgeJob*j=data;
    int pipefd[2];
    if(pipe(pipefd)!=0){
        snprintf(j->output,sizeof j->output,"Failed to create Steam Bridge diagnostic pipe.");
        g_idle_add(pc2_steam_bridge_done,j);return NULL;
    }
    pid_t pid=fork();
    if(pid==0){
        setpgid(0,0);
        close(pipefd[0]);dup2(pipefd[1],STDOUT_FILENO);dup2(pipefd[1],STDERR_FILENO);close(pipefd[1]);
        const char *argv[24];int n=0;
        argv[n++]="python3";
        if(!strcmp(j->action,"prefix-catalog")){
            /* Shared catalog sends no game identifier to the provider. */
            argv[n++]=pc2_prepared_prefix_catalog_helper();
            argv[n++]="--machine-lines";
        }else if(!strcmp(j->action,"prefix-cache")){
            argv[n++]=pc2_prepared_prefix_cache_helper();
            argv[n++]="--release-asset-url";argv[n++]=j->source_url;
            argv[n++]="--declared-size";argv[n++]=j->source_bytes;
            argv[n++]="--approve-cache-download";
            argv[n++]="--progress";
        }else if(!strcmp(j->action,"prefix-stage")){
            argv[n++]=pc2_prepared_prefix_stage_helper();
            argv[n++]="--release-asset-url";argv[n++]=j->source_url;
            argv[n++]="--approve-stage";
            argv[n++]="--progress";
        }else if(!strcmp(j->action,"prepared-import-preview")){
            argv[n++]=pc2_prepared_import_helper();
            argv[n++]="--appid";argv[n++]=j->appid;
            argv[n++]="--install-dir";argv[n++]=j->game_dir;
            argv[n++]="--release-asset-url";argv[n++]=j->source_url;
            argv[n++]="--format";argv[n++]="summary";
        }else if(!strcmp(j->action,"live-attach-preview")){
            argv[n++]=pc2_live_attach_helper();
            argv[n++]="--appid";argv[n++]=j->appid;
            argv[n++]="--install-dir";argv[n++]=j->game_dir;
            argv[n++]="--format";argv[n++]="summary";
        }else if(!strcmp(j->action,"native-route")){
            argv[n++]=pc2_native_route_helper();
            argv[n++]="--provider";argv[n++]=j->provider;
            argv[n++]="--game-id";argv[n++]=j->appid;
            argv[n++]="--format";argv[n++]="summary";
            if(j->game_dir[0]){argv[n++]="--install-dir";argv[n++]=j->game_dir;}
            if(j->prefix[0]){argv[n++]="--prefix";argv[n++]=j->prefix;}
            if(j->runner[0]){argv[n++]="--runner";argv[n++]=j->runner;}
        }else{
            argv[n++]=pc2_steam_bridge_helper();argv[n++]=j->action;
            if(j->appid[0]){argv[n++]="--appid";argv[n++]=j->appid;}
        }
        if(!strcmp(j->action,"setup")||!strcmp(j->action,"status")||!strcmp(j->action,"preflight")||!strcmp(j->action,"netfx-plan")||!strcmp(j->action,"prefix-catalog")||!strcmp(j->action,"netfx-status")){
            if(strcmp(j->action,"prefix-catalog")&&j->game_dir[0]){
                argv[n++]="--game-dir";argv[n++]=j->game_dir;
            }
            if(strcmp(j->action,"prefix-catalog")&&j->steam_root[0]){
                argv[n++]="--steam-root";argv[n++]=j->steam_root;
            }
        }
        if(strcmp(j->action,"status")&&strcmp(j->action,"preflight")&&strcmp(j->action,"netfx-plan")&&strcmp(j->action,"prefix-catalog")&&strcmp(j->action,"prefix-cache")&&strcmp(j->action,"prefix-stage")&&strcmp(j->action,"native-route")&&strcmp(j->action,"live-attach-preview")&&strcmp(j->action,"prepared-import-preview")&&strcmp(j->action,"netfx-status"))argv[n++]="--confirm";
        argv[n]=NULL;
        execvp("python3",(char *const*)argv);_exit(127);
    }
    close(pipefd[1]);
    if(pid<0){
        close(pipefd[0]);snprintf(j->output,sizeof j->output,"Failed to launch Steam Bridge helper.");
    }else{
        if(!strcmp(j->action,"prefix-cache")||!strcmp(j->action,"prefix-stage")){
            pc2_cache_child_pid=pid;
            if(pc2_cache_cancel_requested)kill(pid,SIGINT);
            j->ok=pc2_cache_collect_output(pid,pipefd[0],
                                           j->output,sizeof j->output,900);
            pc2_cache_child_pid=0;
        }else
            j->ok=bounded_child_output(pid,pipefd[0],j->output,sizeof j->output,
                                       !strcmp(j->action,"play")?35:12);
        if(!j->ok&&!j->output[0])snprintf(j->output,sizeof j->output,"Steam Bridge helper failed or timed out.");
    }
    g_idle_add(pc2_steam_bridge_done,j);
    return NULL;
}
static void pc2_steam_bridge_action(const char *action){
    if(!pc2_provider_controls_allowed()||pc2_steam_bridge_busy)return;
    int global_upgrade=!strcmp(action,"upgrade");
    int global_catalog=!strcmp(action,"prefix-catalog");
    int global_cache=!strcmp(action,"prefix-cache");
    int global_stage=!strcmp(action,"prefix-stage");
    int native_route=!strcmp(action,"native-route");
    int live_preview=!strcmp(action,"live-attach-preview");
    int import_preview=!strcmp(action,"prepared-import-preview");
    Game *g=NULL;
    if(!global_upgrade&&!global_catalog&&!global_cache&&!global_stage){
        if(G.selected<0||G.selected>=G.game_count){
            if(pc2_steam_bridge_status)set_label(pc2_steam_bridge_status,
                "Select a supported game in Library first.");
            return;
        }
        g=&G.games[G.selected];
        if(import_preview || live_preview){
            if(!game_is_steam(g)||game_is_steam_shortcut(g)||!g->appid[0]){
                if(pc2_native_route_status)set_label(pc2_native_route_status,
                    "Live WeMod preview requires an installed Steam Windows game.");
                return;
            }
        }else if(native_route){
            if(!game_is_steam(g)&&!game_is_heroic(g)&&!game_is_lutris(g)){
                if(pc2_native_route_status)set_label(pc2_native_route_status,
                    "Select a Steam, Heroic or Lutris Windows game.");
                return;
            }
            if(!game_key(g)[0])return;
        }else if(!game_is_steam(g)||game_is_steam_shortcut(g)||!g->appid[0]){
            if(pc2_steam_bridge_status)set_label(pc2_steam_bridge_status,
                "Legacy Steam Bridge supports installed Steam Windows titles only.");
            return;
        }
    }
    if(strcmp(action,"status")&&strcmp(action,"preflight")&&strcmp(action,"netfx-plan")&&strcmp(action,"prefix-catalog")&&strcmp(action,"prefix-cache")&&strcmp(action,"prefix-stage")&&strcmp(action,"native-route")&&strcmp(action,"live-attach-preview")&&strcmp(action,"prepared-import-preview")&&strcmp(action,"netfx-status")){
        char question[1024];
        if(global_upgrade){
            snprintf(question,sizeof question,
                "Update the installed GameWeld Steam Bridge launcher?\n\n"
                "This copies the current GameWeld launcher to the private Steam "
                "compatibility tool directory and keeps an SHA-256-named backup "
                "of the previous version. It will not modify Steam Compatibility "
                "selections, game prefixes, WeMod or your per-game settings.\n\n"
                "Close running games first and restart Steam after updating. Continue?");
        }else if(!strcmp(action,"play")){
            snprintf(question,sizeof question,
                "Launch %s through Steam with WeMod?\n\n"
                "Steam must already have GameWeld Bridge selected as this "
                "game's Compatibility tool, and WeMod auto-start must be enabled. "
                "GameWeld will check the saved Bridge configuration and request "
                "Steam Play. It will NOT launch a second Proton, modify Steam "
                "settings, or start another instance of an already-running game.\n\n"
                "Game window and trainer activation remain unverified until "
                "observed in-game. Continue?",g->name);
        }else if(!strcmp(action,"trainer-gpu-off")||!strcmp(action,"trainer-gpu-on")){
            snprintf(question,sizeof question,
                "%s WeMod GPU rendering for %s (Steam AppID %s)?\n\n"
                "This is a reversible per-game display troubleshooting option. "
                "It adds --disable-gpu ONLY to WeMod.exe on the next launch. "
                "Game graphics, Steam compatibility, Proton, other game settings and "
                "working titles such as Astrometica are not changed. "
                "This does not guarantee a blank WeMod screen is fixed.\n\n"
                "Close the game and WeMod first. Continue?",
                !strcmp(action,"trainer-gpu-off")?"DISABLE":"RESTORE NORMAL",
                g->name,g->appid);
        }else if(!strcmp(action,"setup")){
            snprintf(question,sizeof question,
                "Set up GameWeld Steam Bridge for %s (AppID %s)?\n\n"
                "This registers GameWeld Bridge with Steam (if absent) and creates "
                "a NEW game-only configuration using exact Proton evidence and the "
                "managed WeMod installation. It never overwrites an existing game's "
                "Bridge configuration or changes Steam's Compatibility selection.\n\n"
                "Restart Steam afterward and select GameWeld Bridge (Experimental) "
                "under this game's Compatibility tab. Continue?",g->name,g->appid);
        }else{
            const char *enabled=!strcmp(action,"trainer-on")?"ENABLE":"DISABLE";
            snprintf(question,sizeof question,
                "%s WeMod auto-start for %s (Steam AppID %s)?\n\n"
                "This changes only GameWeld's existing per-game Bridge configuration. "
                "It will NOT change Steam Compatibility selection, launch options, "
                "Proton, or running processes.\n\n"
                "Close the game first. The change takes effect on the NEXT Steam launch. Continue?",
                enabled,g->name,g->appid);
        }
        GtkWidget *dialog=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,
            GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,"%s",question);
        int reply=gtk_dialog_run((GtkDialog*)dialog);
        gtk_widget_destroy(dialog);
        if(reply!=GTK_RESPONSE_YES)return;
    }
    PC2SteamBridgeJob*j=calloc(1,sizeof *j);if(!j)return;
    snprintf(j->action,sizeof j->action,"%s",action);
    if(!global_upgrade&&!global_catalog&&!global_cache&&!global_stage){
        snprintf(j->appid,sizeof j->appid,"%s",(native_route&&!game_is_steam(g))?game_key(g):g->appid);
        if(native_route){
            snprintf(j->provider,sizeof j->provider,"%s",
                game_is_steam(g)?"steam":game_is_heroic(g)?"heroic":"lutris");
            snprintf(j->prefix,sizeof j->prefix,"%s",g->prefix);
            snprintf(j->runner,sizeof j->runner,"%s",g->wine_bin);
        }
        snprintf(j->game,sizeof j->game,"%.*s",(int)sizeof(j->game)-1,g->name);
        snprintf(j->game_dir,sizeof j->game_dir,"%s",g->install_dir);
        snprintf(j->steam_root,sizeof j->steam_root,"%s",g->steam_root);
    }else{
        snprintf(j->game,sizeof j->game,"%s",
                 global_catalog?"Shared WeMod setup":
                 global_cache?"Shared prepared WeMod cache":"Installed GameWeld Bridge");
    }
    if(global_cache || global_stage){
        pc2_cache_cancel_requested=0;
        int selected=pc2_shared_wemod_choices?
            gtk_combo_box_get_active((GtkComboBox*)pc2_shared_wemod_choices):-1;
        if(global_cache || global_stage){
            if(selected<0 || selected>=pc2_prepared_choice_count){
                if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
                    "Select a prepared release before downloading or staging.");
                free(j);
                return;
            }
            const PC2PreparedChoice *choice=&pc2_prepared_choices[selected];
            snprintf(j->source_url,sizeof j->source_url,"%s",choice->url);
            if(global_cache)
                snprintf(j->source_bytes,sizeof j->source_bytes,"%lld",choice->bytes);
        }
    }
    if(import_preview){
        int choice=pc2_shared_wemod_choices?
            gtk_combo_box_get_active((GtkComboBox*)pc2_shared_wemod_choices):-1;
        if(choice<0 || choice>=pc2_prepared_choice_count){
            if(pc2_native_route_status)set_label(pc2_native_route_status,
                "Select the prepared release in Step 1 before reviewing compatibility.");
            free(j);
            return;
        }
        snprintf(j->source_url,sizeof j->source_url,"%s",
                 pc2_prepared_choices[choice].url);
    }
    pc2_steam_bridge_busy=1;
    if(global_catalog){
        pc2_prepared_choices_clear();
        if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
            "Checking prepared WeMod releases for a shared GameWeld setup…");
    }else if(global_cache){
        if(pc2_shared_wemod_download)
            gtk_widget_set_sensitive(pc2_shared_wemod_download,FALSE);
        if(pc2_shared_wemod_cancel)
            gtk_widget_set_sensitive(pc2_shared_wemod_cancel,TRUE);
        if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
            "Downloading and checking the selected third-party ZIP into a "
            "separate cache only. No game prefix is being changed…");
    }else if(global_stage){
        if(pc2_shared_wemod_cancel)
            gtk_widget_set_sensitive(pc2_shared_wemod_cancel,TRUE);
        if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
            "Staging the exact selected .NET ZIP into private GameWeld cache. "
            "Your games and Proton prefixes are untouched…");
    }else if(import_preview){
        if(pc2_native_route_status)set_label(pc2_native_route_status,
            "Checking version compatibility of a prepared .NET prefix. No game changes…");
    }else if(live_preview){
        if(pc2_native_route_status)set_label(pc2_native_route_status,
            "Previewing the selected Steam game's existing Proton context… No launch or game changes.");
    }else if(native_route){
        if(pc2_native_route_status)set_label(pc2_native_route_status,
            "Checking provider-native setup without changing Steam or game prefixes…");
    }else if(pc2_steam_bridge_status)set_label(pc2_steam_bridge_status,
        !strcmp(action,"play")?"Asking Steam to launch the selected game with its saved Compatibility setting…":
        !strcmp(action,"setup")?"Setting up a new game-only Steam Bridge configuration…":
        "Checking selected game's Steam Bridge configuration…");
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_steam_bridge_worker,j)==0)pthread_detach(thread);
    else{pc2_steam_bridge_busy=0;free(j);if(pc2_steam_bridge_status)
        set_label(pc2_steam_bridge_status,"Failed to start Steam Bridge helper thread.");}
}
static void on_pc2_native_route(GtkButton*b,void*d){
    (void)b;(void)d;pc2_steam_bridge_action("native-route");
}
static void on_pc2_prepared_import_preview(GtkButton*b,void*d){
    (void)b;(void)d;pc2_steam_bridge_action("prepared-import-preview");
}
static void on_pc2_live_attach_preview(GtkButton*b,void*d){
    (void)b;(void)d;pc2_steam_bridge_action("live-attach-preview");
}
static void on_pc2_bridge_status(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("preflight");}
static void on_pc2_bridge_upgrade(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("upgrade");}
static void on_pc2_bridge_play(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("play");}
static void on_pc2_bridge_primary(GtkButton*b,void*d){
    (void)b;(void)d;
    if(pc2_discovery_only()){
        /* Steam wraps %command% using the user-configured DeckCheatz launcher.
         * Use the established, confirmed Steam game-only handoff worker. */
        if(pc2_steam_wemod_allowed())pc2_steam_launch_selected(0);
        else if(pc2_native_wrapper_allowed())pc2_native_wrapper_action(1);
        else pc2_steam_launch_selected(1);
        return;
    }
    pc2_steam_bridge_action("native-route");
}

/* Transitional function name retained for older overview callbacks.
 * Its behavior is now a read-only provider-native check, NOT a Steam launch.
 * A working legacy Bridge can still be used from Advanced maintenance. */
static void pc2_launch_with_steam_bridge(Game *game){
    if(!game||!game_is_steam(game)||game_is_steam_shortcut(game)){
        log_line("Native WeMod setup: select an installed Steam Windows title.");
        return;
    }
    log_line("Native WeMod setup: checking %s without requiring Steam Bridge. "
             "No game or trainer launch was attempted.",game->name);
    pc2_steam_bridge_action("native-route");
}

static void on_pc2_bridge_setup(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("setup");}
static void on_pc2_bridge_enable(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("trainer-on");}
static void on_pc2_bridge_disable(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("trainer-off");}
static void on_pc2_bridge_gpu_off(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("trainer-gpu-off");}
static void on_pc2_bridge_gpu_on(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("trainer-gpu-on");}
static void on_pc2_bridge_netfx_status(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("netfx-status");}
static void on_pc2_bridge_netfx_plan(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("netfx-plan");}
static void on_pc2_bridge_prefix_catalog(GtkButton*b,void*d){(void)b;(void)d;pc2_steam_bridge_action("prefix-catalog");}
static void on_pc2_prepared_stage(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!pc2_provider_controls_allowed() || pc2_steam_bridge_busy)return;
    int selected=pc2_shared_wemod_choices?
        gtk_combo_box_get_active((GtkComboBox*)pc2_shared_wemod_choices):-1;
    if(selected<0 || selected>=pc2_prepared_choice_count){
        if(pc2_shared_wemod_status)set_label(pc2_shared_wemod_status,
            "Choose the prepared .NET release first, then download and stage it.");
        return;
    }
    GtkWidget*dialog=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Stage the cached prepared .NET environment for compatibility testing?\n\n"
        "This extracts the exact release selected above from GameWeld's private cache. "
        "No Steam game, Proton prefix, registry, saves or launch options are changed. "
        "The ZIP is third-party and remains untrusted. Continue?");
    int answer=gtk_dialog_run((GtkDialog*)dialog);
    gtk_widget_destroy(dialog);
    if(answer==GTK_RESPONSE_YES)pc2_steam_bridge_action("prefix-stage");
}
static void on_pc2_prepared_cache_cancel(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!pc2_steam_bridge_busy)return;
    pc2_cache_cancel_requested=1;
    pid_t child=pc2_cache_child_pid;
    if(child>0)kill(child,SIGINT);
    if(pc2_shared_wemod_cancel)
        gtk_widget_set_sensitive(pc2_shared_wemod_cancel,FALSE);
    if(pc2_shared_wemod_status)
        set_label(pc2_shared_wemod_status,
            "Cancelling cache-only download; asking the helper to "
            "discard its incomplete temporary file...");
}
static void on_pc2_prepared_prefix_cache(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!pc2_provider_controls_allowed() ||
       pc2_steam_bridge_busy || !pc2_shared_wemod_choices)return;
    int index=gtk_combo_box_get_active((GtkComboBox*)pc2_shared_wemod_choices);
    if(index<0||index>=pc2_prepared_choice_count)return;
    const PC2PreparedChoice *choice=&pc2_prepared_choices[index];
    GtkWidget *dialog=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Download %s (%0.1f MiB) from DeckCheatz?\n\n"
        "Release: %s\n\n"
        "This third-party ZIP will be stored in GameWeld's separate cache ONLY. "
        "It will NOT be installed, extracted, executed or copied to your game. "
        "Publisher identity and game compatibility are NOT verified. "
        "Steam, Heroic, Lutris, your game prefixes and WeMod accounts will not "
        "be changed.\n\nContinue with this cache-only download?",
        choice->name,(double)choice->bytes/1048576.0,choice->tag);
    int response=gtk_dialog_run((GtkDialog*)dialog);
    gtk_widget_destroy(dialog);
    if(response==GTK_RESPONSE_YES)pc2_steam_bridge_action("prefix-cache");
}

/* WeMod Enhancer is integrated into GameWeld PC2. The Linux release's
 * Python CLI is used, not its separate GUI or the Windows Wand WPF tool.
 * Installation and patching require explicit confirmation and are isolated
 * from PC1 and the legacy GameWeld Proton/provider handlers. */
static GtkWidget *pc2_wemod_status=NULL;
static GtkWidget *pc2_wemod_helper_status=NULL;
static int pc2_wemod_busy=0;
typedef struct {
    char action[20],install[2048],output[4096];
    char appid[192],game_name[256],game_provider[32],game_dir[2048];
    char game_prefix[2048],wine_prefix[2048],runtime_hint[32];
    int success;
} PC2WeModJob;
static const char *pc2_wemod_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-wemod-enhancer.py",appdir);
    else snprintf(p,sizeof p,"gameweld-wemod-enhancer.py");
    return p;
}
static const char *pc2_native_bridge_helper(void){
    static char p[2048];const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-wand-native-bridge.py",appdir);
    else snprintf(p,sizeof p,"gameweld-wand-native-bridge.py");
    return p;
}
static gboolean pc2_wemod_done(void *data){
    PC2WeModJob*j=data;
    pc2_wemod_busy=0;
    const char*txt=j->output[0]?j->output:(j->success?"Completed.":"Command failed.");
    size_t n=strlen(txt);
    if(pc2_wemod_helper_status)set_label(pc2_wemod_helper_status,n>1400?txt+n-1400:txt);
    log_line("%s [%s] %s: %.1000s",
        !strncmp(j->action,"native-",7)?"GameWeld Managed Wand":"WeMod Enhancer",
        j->action,j->success?(!strcmp(j->action,"live-launch")||!strcmp(j->action,"live-render")?"HANDOFF SENT (window not verified)":!strcmp(j->action,"native-managed")?"SESSION REQUESTED (game/trainer not verified)":"OK"):"FAILED",txt);
    free(j);
    return FALSE;
}
static void *pc2_wemod_worker(void *data){
    PC2WeModJob*j=data;int pipefd[2];
    if(pipe(pipefd)!=0){
        snprintf(j->output,sizeof j->output,"Could not capture WeMod Enhancer output.");
        g_idle_add(pc2_wemod_done,j);return NULL;
    }
    pid_t pid=fork();
    if(pid==0){
        close(pipefd[0]);dup2(pipefd[1],STDOUT_FILENO);dup2(pipefd[1],STDERR_FILENO);close(pipefd[1]);
        const char*argv[32];int n=0;
        int native=!strncmp(j->action,"native-",7);
        argv[n++]="python3";argv[n++]=native?pc2_native_bridge_helper():pc2_wemod_helper();
        argv[n++]=!strcmp(j->action,"native-check")?"check":!strcmp(j->action,"native-managed")?"play":!strcmp(j->action,"live-render")?"live-launch":j->action;
        if(!strcmp(j->action,"live-render"))argv[n++]="--software-render";
        if(!native&&j->install[0]){argv[n++]="--install-dir";argv[n++]=j->install;}
        if(!native&&j->wine_prefix[0]){argv[n++]="--wine-prefix";argv[n++]=j->wine_prefix;}
        if(!strcmp(j->action,"game-test")||!strcmp(j->action,"live-launch")||!strcmp(j->action,"live-render")||native){
            argv[n++]="--game-provider";argv[n++]=j->game_provider;
            argv[n++]="--appid";argv[n++]=j->appid;
            if(!native){argv[n++]="--game-name";argv[n++]=j->game_name;}
            argv[n++]="--game-dir";argv[n++]=j->game_dir;
            if(!native){argv[n++]="--game-prefix";argv[n++]=j->game_prefix;
                argv[n++]="--runtime-hint";argv[n++]=j->runtime_hint;}
        }
        if(!strcmp(j->action,"install")||!strcmp(j->action,"patch")||
           !strcmp(j->action,"restore")||!strcmp(j->action,"launch-test")||
           !strcmp(j->action,"live-launch")||!strcmp(j->action,"live-render")||
           !strcmp(j->action,"native-managed"))
            argv[n++]="--confirm";
        argv[n]=NULL;
        execvp("python3",(char*const*)argv);_exit(127);
    }
    close(pipefd[1]);
    if(pid<0){
        close(pipefd[0]);snprintf(j->output,sizeof j->output,"Could not start WeMod Enhancer helper.");
    }else{
        j->success=bounded_child_output(pid,pipefd[0],j->output,sizeof j->output,220);
        if(!j->success&&!j->output[0])snprintf(j->output,sizeof j->output,"WeMod Enhancer operation failed or timed out.");
    }
    g_idle_add(pc2_wemod_done,j);
    return NULL;
}
static void pc2_wemod_action(const char*action){
    if(!pc2_provider_controls_allowed())return;
    if(pc2_wemod_busy){log_line("WeMod Enhancer: operation already running.");return;}
    const char*install=pc2_wemod_install_entry?
        gtk_entry_get_text((GtkEntry*)pc2_wemod_install_entry):"";
    if(!strcmp(action,"patch")||!strcmp(action,"restore")||
       !strcmp(action,"install")||!strcmp(action,"launch-test")||
       !strcmp(action,"live-launch")||!strcmp(action,"live-render")||
       !strcmp(action,"native-managed")){
        const char*message=!strcmp(action,"patch")?
            "Install WeMod Enhancer from the pinned upstream Linux release if necessary, then PATCH the selected WeMod client?\\n\\n"
            "The upstream patch modifies WeMod's application files, subscription display, update behavior and integrity handling. "
            "It creates an original-file backup, and a Restore option is available. "
            "Close WeMod before continuing. No game or Proton settings are changed.":
            !strcmp(action,"restore")?
            "Restore the original WeMod files from the upstream WeMod Enhancer backup?\\n\\n"
            "Close WeMod before continuing. No game or Proton settings are changed.":
            !strcmp(action,"launch-test")?
            "Launch the selected patched Wand client in its EXISTING Wine prefix?\\n\\n"
            "This only tests whether Wand opens. It requests native-first version.dll loading; "
            "it does NOT start a selected game, join its Proton session, or prove trainer attachment.":
            !strcmp(action,"live-render")?
            "Retry Wand with GPU rendering disabled using the running Steam game's exact Proton/prefix?\\n\\n"
            "CLOSE the existing blank Wand window first. Astrometica must still be running. "
            "Only the new Wand child gets --disable-gpu and --disable-gpu-compositing. "
            "A startup log is saved in GameWeld's private state. This may modify the game's Wine prefix state; no Steam settings are changed.":
            !strcmp(action,"native-managed")?
            "Start a NEW GameWeld-managed Proton session containing the selected game AND Wand?\\n\\n"
            "CLOSE the selected Steam game and any existing Wand windows FIRST. The integrated launcher checks exact game identity, "
            "the isolated verified GE Proton Wand SHA256 tool, a uniquely patched Wand client and DWriteCore. "
            "It may copy an existing DWriteCore DLL beside Wand and modify the game's Wine prefix while starting. "
            "No external wandctl, downloads, repatching, or Steam launch option changes. Continue?":
            !strcmp(action,"live-launch")?
            "Launch patched Wand with the ALREADY RUNNING Steam game's exact Proton runtime/prefix?\\n\\n"
            "Requires an observed Windows .exe game process and verified patch files. This may change Wine state inside the game's prefix. "
            "No Steam Launch Options are changed. Trainer attachment and login remain unverified. Continue?":
            "Download and install the pinned upstream WeMod Enhancer Linux CLI into GameWeld's private tools directory? "
            "This does not modify WeMod until Patch is selected.";
        GtkWidget*dialog=gtk_message_dialog_new((GtkWindow*)G.window,GTK_DIALOG_MODAL,
            GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,"%s",message);
        int answer=gtk_dialog_run((GtkDialog*)dialog);
        gtk_widget_destroy(dialog);
        if(answer!=GTK_RESPONSE_YES){log_line("WeMod Enhancer %s cancelled.",action);return;}
    }
    PC2WeModJob*j=calloc(1,sizeof *j);if(!j)return;
    snprintf(j->action,sizeof j->action,"%s",action);
    if(install&&*install)snprintf(j->install,sizeof j->install,"%s",install);
    int selected_prefix=wand_detected_combo?gtk_combo_box_get_active((GtkComboBox*)wand_detected_combo):-1;
    if(selected_prefix>=0&&selected_prefix<wand_detected_count)
        snprintf(j->wine_prefix,sizeof j->wine_prefix,"%s",wand_detected[selected_prefix].prefix);
    if(!strcmp(action,"game-test")||!strcmp(action,"live-launch")||!strcmp(action,"live-render")||
       !strcmp(action,"native-check")||!strcmp(action,"native-managed")){
        if(G.selected<0||G.selected>=G.game_count){
            log_line("Wand game test requires a game selected in Overview or Library.");
            if(pc2_wemod_helper_status)set_label(pc2_wemod_helper_status,"Select the game you want to test in Overview or Library first.");
            free(j);return;
        }
        Game*g=&G.games[G.selected];
        if(!strcmp(action,"game-test"))
            log_line("Wand patch check is read-only: it does NOT launch the game or trainer.");
        else if(!strncmp(action,"native-",7))
            log_line("GameWeld managed Wand [%s] selected for %s (Steam app %s). This is the integrated one-Proton-session path, not a separate Wand Native CLI.",action,g->name,g->appid);
        else
            log_line("Wand live launch requested for selected game %s (Steam app %s). The recovered active-wineserver + X11 method is selected; actual UI remains unverified.",g->name,g->appid);
        snprintf(j->game_name,sizeof j->game_name,"%s",g->name);
        snprintf(j->game_provider,sizeof j->game_provider,"%s",
            game_is_steam_shortcut(g)?"other":game_is_steam(g)?"steam":game_is_heroic(g)?"heroic":game_is_lutris(g)?"lutris":"other");
        snprintf(j->appid,sizeof j->appid,"%s",g->appid);
        snprintf(j->game_dir,sizeof j->game_dir,"%s",g->install_dir);
        if(g->prefix[0])snprintf(j->game_prefix,sizeof j->game_prefix,"%s",g->prefix);
        snprintf(j->runtime_hint,sizeof j->runtime_hint,"unknown");
        if(strncmp(action,"native-",7)&&game_is_steam(g)&&!game_is_steam_shortcut(g)){
            int valid=j->appid[0]&&j->appid[0]!='0'&&strlen(j->appid)<=10;
            for(const char*q=j->appid;*q;q++)if(!isdigit((unsigned char)*q))valid=0;
            if(valid){
                char endpoint[180],*response=NULL;int code=0;
                snprintf(endpoint,sizeof endpoint,"/api/steam-native-executable?appid=%s",j->appid);
                if(http_request("GET",endpoint,NULL,&response,&code)>=0&&code==200&&response){
                    const char*field=strstr(response,"\"native_elf_candidate_count\"");
                    if(field){const char*colon=strchr(field,':');if(colon&&strtol(colon+1,NULL,10)>0)
                        snprintf(j->runtime_hint,sizeof j->runtime_hint,"native");}
                }
                free(response);response=NULL;code=0;
                if(strcmp(j->runtime_hint,"native")){
                    snprintf(endpoint,sizeof endpoint,"/api/steam-process-roles?appid=%s",j->appid);
                    if(http_request("GET",endpoint,NULL,&response,&code)>=0&&code==200&&response&&
                       strstr(response,"windows_executable_candidate"))
                        snprintf(j->runtime_hint,sizeof j->runtime_hint,"windows-associated");
                }
                free(response);
            }
        }
    }
    if(!strcmp(action,"launch-test")&&!j->wine_prefix[0]){
        log_line("Wand smoke test: select an existing detected Wine installation; none was selected.");
        if(pc2_wemod_helper_status)set_label(pc2_wemod_helper_status,
            "Select an existing Wand installation from the list; a known Wine prefix is required for this launch.");
        free(j);return;
    }
    pc2_wemod_busy=1;
    if(pc2_wemod_helper_status)set_label(pc2_wemod_helper_status,
        !strcmp(action,"status")?"Checking the WeMod Enhancer helper...":
        !strcmp(action,"verify")||!strcmp(action,"game-test")?
            "Inspecting patched Wand files and selected game's runtime (read-only)...":
        !strcmp(action,"launch-test")?"Requesting Wand test launch with existing Wine prefix...":
        !strcmp(action,"live-launch")?"Checking the running game's exact Proton runtime before Wand handoff...":
        !strcmp(action,"live-render")?"Retrying Wand with GPU off in the game's live Proton session...":
        !strcmp(action,"native-check")?"Checking GameWeld's integrated managed session prerequisites (read-only)...":
        !strcmp(action,"native-managed")?"Checking managed Proton/Wand readiness before requesting one game + Wand session...":
        "Running upstream WeMod Enhancer. Keep the WeMod client closed during this operation.");
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_wemod_worker,j)==0)pthread_detach(thread);
    else {pc2_wemod_busy=0;free(j);if(pc2_wemod_helper_status)set_label(pc2_wemod_helper_status,"Could not start helper thread.");}
}
static void on_pc2_wemod_detect(GtkButton*b,void*d){(void)b;(void)d;wand_detect_start();pc2_wemod_action("status");}
static void on_pc2_wemod_install(GtkButton*b,void*d){(void)b;(void)d;pc2_wemod_action("install");}
static void on_pc2_wemod_patch(GtkButton*b,void*d){(void)b;(void)d;pc2_wemod_action("patch");}
static void on_pc2_wemod_restore(GtkButton*b,void*d){(void)b;(void)d;pc2_wemod_action("restore");}
static void on_pc2_wemod_verify_selected(GtkButton*b,void*d){(void)b;(void)d;pc2_wemod_action("game-test");}

/* Optional DeckCheatz 1.x provider: discovery from the GUI with zero Steam
 * LaunchOptions changes, zero trainer/game starts, and no bundled AGPL code.
 * Actual direct game launch remains a separately consented, UNVERIFIED
 * provider path. The source helper runs only on button click. */
static GtkWidget *pc2_deckcheatz_update_status=NULL;
static void on_pc2_deckcheatz_detect(GtkButton*b,void*d){
    (void)b;(void)d;
    if(!pc2_provider_controls_allowed())return;
    char helper[2048];
    const char*appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(helper,sizeof helper,
        "%s/usr/libexec/gameweld-deckcheatz-direct.py",appdir);
    else snprintf(helper,sizeof helper,"gameweld-deckcheatz-direct.py");
    int fd[2];
    if(pipe(fd)!=0){log_line("DeckCheatz 1.x detection: could not open output pipe.");
        if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,"DeckCheatz detection failed: cannot create scanner pipe.");return;}
    pid_t pid=fork();
    if(pid==0){
        close(fd[0]);dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);
        clear_desktop_activation_env();
        execlp("python3","python3",helper,"--discover",(char*)NULL);
        _exit(127);
    }
    close(fd[1]);
    if(pid<0){close(fd[0]);log_line("DeckCheatz 1.x detection: could not start scanner.");
        if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,"DeckCheatz detection failed: scanner could not start.");return;}
    char output[4096]={0};
    int status=bounded_child_output(pid,fd[0],output,sizeof output,10);
    if(!status){
        log_line("DeckCheatz 1.x discovery failed. Existing Steam games/LaunchOptions unchanged.");
        if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
            "Detection failed or timed out. Existing installations were not changed.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz discovery unavailable; no game or trainer launched.");
        return;
    }
    if(strstr(output,"\"available_count\": 0")){
        log_line("DeckCheatz 1.x: not yet installed. Click Install DeckCheatz 1.x (managed), or select Preview to download automatically after consent. Steam LaunchOptions unchanged.");
        if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
            "DeckCheatz not detected. You can install a separate managed checkout after confirmation.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz 1.x not installed. GameWeld can download it on first use. No game or trainer launched.");
    }else{
        log_line("DeckCheatz 1.x detected (read-only). GameWeld direct launch requires per-game EXE, Proton and prefix selection plus explicit consent; real handoff NOT yet validated.");
        if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
            "DeckCheatz detected. No Steam Launch Options were changed; direct launch remains experimental.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz 1.x detected. No Steam launch options needed; direct launch still experimental.");
    }
}


/* GameWeld installs the upstream AGPL application as a separate per-user
 * external git checkout. It never bundles upstream source, changes Steam
 * launch options or executes DeckCheatz just to install it.
 * Download is prompted on first DeckCheatz use, and the original action
 * resumes when installation succeeds without blocking the GTK event loop. */
typedef struct {
    int resume_mode; /* -1=install only; 0=preview; 1=experimental test */
    int selected_index;
    int ok;
    int operation; /* 0=install, 1=check updates, 2=update, 3=adopt */
    char helper[4096];
    char output[8192];
} PC2DeckCheatzInstallJob;

static int pc2_deckcheatz_install_busy=0;
static void pc2_deckcheatz_flow(int experimental_launch);

static int pc2_deckcheatz_find_launcher(char *target,size_t cap){
    if(target&&cap)target[0]=0;
    const char *home=getenv("HOME");
    const char *xdg=getenv("XDG_DATA_HOME");
    const char *custom=getenv("GAMEWELD_DECKCHEATZ_LAUNCHER");
    char paths[5][4096]={{0}};
    int count=0;
    if(custom&&*custom)snprintf(paths[count++],sizeof paths[0],"%s",custom);
    if(xdg&&xdg[0]=='/'){
        snprintf(paths[count++],sizeof paths[0],"%s/gameweld/deckcheatz/wemod",xdg);
    }
    if(home&&*home){
        snprintf(paths[count++],sizeof paths[0],"%s/.local/share/gameweld/deckcheatz/wemod",home);
        snprintf(paths[count++],sizeof paths[0],"%s/wemod-launcher/wemod",home);
        snprintf(paths[count++],sizeof paths[0],"%s/Games/wemod-launcher/wemod",home);
    }
    for(int i=0;i<count;i++){
        struct stat st;
        if(paths[i][0]&&strlen(paths[i])<cap&&
            stat(paths[i],&st)==0&&S_ISREG(st.st_mode)){
            snprintf(target,cap,"%s",paths[i]);return 1;
        }
    }
    return 0;
}
/* Steam's localconfig.vdf is NEVER edited from GameWeld. It is per-account
 * and may be overwritten by the running Steam client. The copy flow first
 * reads the exact selected game's launch option using a bounded helper, then
 * saves an exclusive private original-string backup after consent. Only then
 * does it copy a conservative, conflict-free merge to the clipboard. */
static int pc2_steam_option_helper_run(const char *mode,const char *appid,
                                     const char *launcher,char *out,size_t cap,
                                     int verified_empty,int session_wrapper){
    if(!appid||!*appid||!mode||!*mode||cap<64)return 0;
    out[0]=0;
    const char *appdir=getenv("APPDIR");char helper[4096]={0};
    if(appdir&&*appdir)
        snprintf(helper,sizeof helper,"%s/usr/libexec/gameweld-steam-launch-options-preserve.py",appdir);
    else
        snprintf(helper,sizeof helper,"gameweld-steam-launch-options-preserve.py");
    int fd[2];if(pipe(fd)!=0)return 0;
    pid_t pid=fork();
    if(pid<0){close(fd[0]);close(fd[1]);return 0;}
    if(pid==0){
        close(fd[0]);setsid();
        dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);
        clear_desktop_activation_env();
        char *argv[16];int n=0;
        argv[n++]="python3";argv[n++]=helper;
        argv[n++]=(char*)mode;argv[n++]="--appid";argv[n++]=(char*)appid;
        if(launcher&&*launcher){argv[n++]="--launcher";argv[n++]=(char*)launcher;}
        if(session_wrapper)argv[n++]="--session-wrapper";
        if(verified_empty)argv[n++]="--verified-empty-in-steam";
        argv[n]=NULL;
        execvp("python3",argv);
        _exit(127);
    }
    close(fd[1]);
    return bounded_child_output(pid,fd[0],out,cap,20);
}
static void pc2_steam_option_message(const char *subject,const char *description,
                                    const char *content){
    GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_INFO,GTK_BUTTONS_OK,
        "%s\n\n%s",subject,description);
    if(content&&*content){
        GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);
        GtkWidget*view=gtk_text_view_new();
        gtk_widget_set_size_request(sc,750,180);
        gtk_text_view_set_editable((GtkTextView*)view,FALSE);
        gtk_text_view_set_cursor_visible((GtkTextView*)view,FALSE);
        gtk_text_view_set_wrap_mode((GtkTextView*)view,2);
        gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)view),content,-1);
        gtk_container_add(sc,view);
        gtk_box_pack_start(gtk_dialog_get_content_area((GtkDialog*)dlg),sc,TRUE,TRUE,0);
        gtk_widget_show_all(dlg);
    }
    gtk_dialog_run((GtkDialog*)dlg);
    gtk_widget_destroy(dlg);
}
static void on_pc2_deckcheatz_copy_steam_option(GtkButton*b,void*d){
    (void)b;
    int session_wrapper=d!=NULL;
    if(G.selected<0||G.selected>=G.game_count ||
       !game_is_steam(&G.games[G.selected]) ||
       game_is_steam_shortcut(&G.games[G.selected])){
        pc2_steam_option_message("Select an installed Steam Windows game",
            "GameWeld can only preserve options for an installed Steam game with a valid AppID.",NULL);
        return;
    }
    Game*g=&G.games[G.selected];
    if(session_wrapper){
        GtkWidget*agree=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
            "Install a private GameWeld one-session Steam launcher?\n\n"
            "This installs only a local user-owned helper. It will NOT change "
            "Steam, any Proton prefix or the selected game's files.\n\n"
            "You will copy the one-time Steam launch option manually. "
            "After that, GameWeld Play can arm DeckCheatz for one session "
            "and revert to ordinary game execution automatically. "
            "The session shim remains configured in Steam until you restore "
            "your backed-up original. Continue?");
        int accept=gtk_dialog_run((GtkDialog*)agree)==GTK_RESPONSE_YES;
        gtk_widget_destroy(agree);
        if(!accept)return;
        char result[4096]={0};
        if(!pc2_deckcheatz_session_helper("install",g->appid,NULL,result,sizeof result) ||
           (!strstr(result,"\"SESSION_WRAPPER_INSTALLED\"") &&
            !strstr(result,"\"SESSION_WRAPPER_ALREADY_INSTALLED\""))){
            pc2_steam_option_message("One-session launcher installation refused",
                "GameWeld did not change Steam. Review the private installer error "
                "below and keep using your existing working launch option.",result);
            return;
        }
    }
    char launcher[4096]={0};
    if(!pc2_deckcheatz_find_launcher(launcher,sizeof launcher)){
        pc2_steam_option_message("DeckCheatz launcher missing",
            "Install the managed DeckCheatz wemod launcher before generating a Steam command.",NULL);
        return;
    }
    char *preview=calloc(1,65536),*saved=calloc(1,65536);
    char *original=calloc(1,18000),*merged=calloc(1,36000),*confirmed=calloc(1,36000),*confirmed_original=calloc(1,18000);
    char *decision=calloc(1,100);
    if(!preview||!saved||!original||!merged||!confirmed||!confirmed_original||!decision){
        log_line("Steam option protection: cannot allocate bounded inspection output.");
        goto done;
    }
    int verified_empty=0;
    if(!pc2_steam_option_helper_run("--preview",g->appid,launcher,
                                    preview,65536,0,session_wrapper)){
        pc2_steam_option_message("Steam options inspection blocked",
            "GameWeld did NOT copy a replacement or edit Steam. "
            "The cause may be an unrecognized DeckCheatz launcher, Steam "
            "account ambiguity, or an unreadable Steam configuration. "
            "The specific diagnostic is displayed below; existing options "
            "remain unchanged.",
            preview);
        goto done;
    }
    /* An explicit empty ON-DISK LaunchOptions field does not prove Steam's
     * running UI is empty. Do not copy or back it up until the user has
     * checked this same game's CURRENT Steam Properties themselves. */
    if(strstr(preview,"\"NEEDS_STEAM_UI_EMPTY_CHECK\"")){
        GtkWidget*verify=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_INFO,GTK_BUTTONS_YES_NO,
            "Steam's saved file reports EMPTY Launch Options for %.140s.\n\n"
            "But Steam may currently have different options in memory. "
            "If this game already uses a working DeckCheatz command, "
            "do NOT continue: select No and keep those options.\n\n"
            "Open THIS game's Steam Properties > General > Launch Options "
            "and verify that the field is CURRENTLY completely empty.\n\n"
            "Did you personally confirm it is empty?",g->name);
        int accepted=gtk_dialog_run((GtkDialog*)verify)==GTK_RESPONSE_YES;
        gtk_widget_destroy(verify);
        if(!accepted){
            log_line("Steam on-disk options were empty but live UI was not verified. "
                     "No original backup, clipboard change or Steam edit.");
            goto done;
        }
        verified_empty=1;
        if(!pc2_steam_option_helper_run("--preview",g->appid,launcher,
                                       preview,65536,verified_empty,session_wrapper)){
            pc2_steam_option_message("Could not verify Steam launch options",
                "Steam's saved state changed or became unreadable. "
                "No backup or clipboard changes were made.",preview);
            goto done;
        }
    }
    json_string(preview,"original_launch_option",original,18000);
    json_string(preview,"proposed_launch_option",merged,36000);
    json_string(preview,"merge_status",decision,100);
    if(json_bool(preview,"requires_manual_review",1) ||
       !merged[0] || !decision[0]){
        pc2_steam_option_message("Manual Steam launch-option review required",
            "The game has shell wrappers or other options that GameWeld "
            "cannot reorder safely. NO replacement was copied. "
            "Preserve your existing Steam setting and review the command below:",
            original);
        goto done;
    }
    if(!strcmp(decision,"ALREADY_CONFIGURED")){
        pc2_steam_option_message("DeckCheatz options already configured",
            "The selected game's current launch option matches the "
            "working DeckCheatz recipe. No overwrite is necessary.",original);
        goto done;
    }
    GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Preserve and copy Steam Launch Options for %.140s?\n\n"
        "After reviewing the ORIGINAL and PROPOSED commands, GameWeld "
        "will FIRST save the disk original privately under "
        "~/.local/state/gameweld/steam-option-backups, "
        "then copy the proposed combined text to your clipboard.\n\n"
        "Steam itself will NOT be modified. You must paste manually in Steam "
        "Properties > General > Launch Options. Continue?",g->name);
    GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);
    GtkWidget*view=gtk_text_view_new();
    gtk_widget_set_size_request(sc,760,210);
    gtk_text_view_set_editable((GtkTextView*)view,FALSE);
    gtk_text_view_set_cursor_visible((GtkTextView*)view,FALSE);
    gtk_text_view_set_wrap_mode((GtkTextView*)view,2);
    char*comparison=malloc(strlen(original)+strlen(merged)+130);
    if(comparison){
        snprintf(comparison,strlen(original)+strlen(merged)+130,
                 "ORIGINAL:\n%s\n\nPROPOSED:\n%s",original,merged);
        gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)view),comparison,-1);
        free(comparison);
    }
    gtk_container_add(sc,view);
    gtk_box_pack_start(gtk_dialog_get_content_area((GtkDialog*)dlg),sc,TRUE,TRUE,0);
    gtk_widget_show_all(dlg);
    int yes=gtk_dialog_run((GtkDialog*)dlg)==GTK_RESPONSE_YES;
    gtk_widget_destroy(dlg);
    if(!yes){log_line("Steam Launch Options merge cancelled; no backup or clipboard changes.");goto done;}
    if(!pc2_steam_option_helper_run("--save-original",g->appid,launcher,
                                    saved,65536,verified_empty,session_wrapper)){
        pc2_steam_option_message("Original-command backup not saved",
            "GameWeld refuses to overwrite an existing backup or copy an "
            "unprotected Steam replacement. Your Steam settings are unchanged.",saved);
        goto done;
    }
    json_string(saved,"proposed_launch_option",confirmed,36000);
    json_string(saved,"original_launch_option",confirmed_original,18000);
    if(strcmp(original,confirmed_original) || strcmp(merged,confirmed) ||
       !strstr(saved,"\"ORIGINAL_BACKUP_SAVED\"")){
        pc2_steam_option_message("Steam options changed during preparation",
            "The proposed command no longer matches the preview. "
            "No replacement has been copied. Steam remains unchanged.",NULL);
        goto done;
    }
    GtkClipboard*clip=gtk_clipboard_get(gdk_atom_intern_static_string("CLIPBOARD"));
    if(!clip){log_line("Steam option protection: clipboard unavailable; Steam unchanged.");goto done;}
    gtk_clipboard_set_text(clip,merged,-1);
    pc2_steam_option_message("Original options backed up; merged command copied",
        "Paste this in the selected game's Steam Properties > General > Launch Options. "
        "A separate Restore Original button can copy back your pre-GameWeld options. "
        "GameWeld has not edited Steam.",merged);
    log_line("Saved exact original Steam options for AppID %s; copied safe combined command. Steam itself unchanged.",g->appid);
done:
    free(preview);free(saved);free(original);free(merged);free(confirmed);free(confirmed_original);free(decision);
}
static void on_pc2_deckcheatz_setup_session(GtkButton*b,void*d){
    (void)d;
    on_pc2_deckcheatz_copy_steam_option(b,(void*)1);
}
static void on_pc2_deckcheatz_restore_steam_option(GtkButton*b,void*d){
    (void)b;(void)d;
    if(G.selected<0||G.selected>=G.game_count ||
       !game_is_steam(&G.games[G.selected]) ||
       game_is_steam_shortcut(&G.games[G.selected])){
        pc2_steam_option_message("Select a Steam game",
            "Choose the same Steam game you backed up to restore its original launch option.",NULL);
        return;
    }
    char *result=calloc(1,65536),*original=calloc(1,18000);
    if(!result||!original)goto done;
    if(!pc2_steam_option_helper_run("--restore-original",
            G.games[G.selected].appid,NULL,result,65536,0,0)){
        pc2_steam_option_message("Original launch options backup unavailable",
            "No matching GameWeld backup exists for the selected game and Steam account. "
            "Nothing was copied or changed.",result);
        goto done;
    }
    json_string(result,"original_launch_option",original,18000);
    if(!strstr(result,"\"COPY_ORIGINAL_TO_STEAM_MANUALLY\""))goto done;
    GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "Copy the saved ORIGINAL Steam launch option for %.140s?\n\n"
        "This replaces only clipboard text. You must paste it into Steam "
        "Properties > General > Launch Options. A blank original is valid "
        "and means clearing that field. Continue?",G.games[G.selected].name);
    int accepted=gtk_dialog_run((GtkDialog*)dlg)==GTK_RESPONSE_YES;
    gtk_widget_destroy(dlg);
    if(accepted){
        GtkClipboard*clip=gtk_clipboard_get(gdk_atom_intern_static_string("CLIPBOARD"));
        if(clip)gtk_clipboard_set_text(clip,original,-1);
        pc2_steam_option_message("Original Steam launch option copied",
            "Paste the saved original text into Steam's Launch Options field. "
            "GameWeld has not modified Steam.",original[0]?original:"(original field was empty)");
    }
done:
    free(result);free(original);
}

static gboolean pc2_deckcheatz_install_done(void *data){
    PC2DeckCheatzInstallJob *j=(PC2DeckCheatzInstallJob*)data;
    pc2_deckcheatz_install_busy=0;
    char launcher[4096]={0};
    int installed=j->ok&&pc2_deckcheatz_find_launcher(launcher,sizeof launcher);
    if(j->operation==1){
        if(j->ok&&strstr(j->output,"\"update_available\": true")){
            log_line("DeckCheatz managed update available. Close WeMod before updating.");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Update available. Close WeMod, then choose Update DeckCheatz (opt-in).");
        }else if(j->ok&&strstr(j->output,"\"result\": \"up_to_date\"")){
            log_line("DeckCheatz managed installation is up to date.");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Managed DeckCheatz is up to date.");
        }else if(j->ok&&strstr(j->output,"\"result\": \"not_managed\"")){
            log_line("DeckCheatz checkout is user-managed; GameWeld will not overwrite it.");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "External/unmanaged checkout: update it through its original installation method.");
        }else {
            log_line("DeckCheatz update check did not complete: %.700s",j->output);
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Update check failed; see the Activity log.");
        }
        free(j);return FALSE;
    }
    if(j->operation==3){
        if(j->ok&&strstr(j->output,"\"result\": \"adopted\"")){
            log_line("Clean existing DeckCheatz checkout enrolled in GameWeld managed updates. No files replaced.");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Existing 1.x checkout enrolled. You can now check and apply managed updates.");
        }else{
            log_line("DeckCheatz checkout adoption refused; no existing files changed: %.700s",j->output);
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Could not enrol this checkout. See Activity for validation details.");
        }
        free(j);return FALSE;
    }
    if(j->operation==2){
        if(j->ok&&strstr(j->output,"\"result\": \"updated\"")){
            char rollback[4096]={0};
            json_string(j->output,"rollback_path",rollback,sizeof rollback);
            log_line("DeckCheatz update completed; previous checkout retained: %s",
                     rollback[0]?rollback:"(path recorded in installer)");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "DeckCheatz updated. The previous checkout was kept as a rollback backup.");
        }else if(j->ok&&strstr(j->output,"\"result\": \"up_to_date\"")){
            log_line("DeckCheatz already up to date.");
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Managed DeckCheatz is up to date.");
        }else{
            log_line("DeckCheatz update blocked/failed; current checkout preserved: %.700s",j->output);
            if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
                "Update not applied. Existing checkout preserved; see Activity.");
        }
        free(j);return FALSE;
    }
    if(installed){
        log_line("DeckCheatz 1.x managed install: ready (%s). Steam options unchanged.",launcher);
        if(strstr(j->output,"\"tkinter\": false"))
            log_line("DeckCheatz warning: Python Tkinter is missing. Install your distribution's Tk package (CachyOS/Arch: tk) before running upstream dialogs.");
        if(strstr(j->output,"\"venv\": false"))
            log_line("DeckCheatz warning: Python venv module is missing; upstream may need the distribution's python-venv package.");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz managed 1.x is installed. You can preview or test the selected game.");
        if(j->resume_mode>=0){
            if(j->selected_index==G.selected && G.selected>=0){
                log_line("Resuming the selected DeckCheatz action after managed installation.");
                pc2_deckcheatz_flow(j->resume_mode);
            }else log_line("DeckCheatz installed; game selection changed. Choose the game and launch action again.");
        }
    }else{
        log_line("DeckCheatz managed download/verification failed. Nothing launched: %.700s",
                 j->output[0]?j->output:"installer returned no result");
        if(G.library_detail_status)set_label(G.library_detail_status,
            "DeckCheatz managed install failed. See Activity for details. Game and prefix unchanged.");
    }
    free(j);
    return FALSE;
}
static void *pc2_deckcheatz_install_worker(void *data){
    PC2DeckCheatzInstallJob *j=(PC2DeckCheatzInstallJob*)data;
    int fd[2];
    if(pipe(fd)!=0){
        snprintf(j->output,sizeof j->output,"Could not create installation pipe");
        g_idle_add(pc2_deckcheatz_install_done,j);return NULL;
    }
    pid_t child=fork();
    if(child==0){
        close(fd[0]);setsid();
        dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);
        clear_desktop_activation_env();
        if(j->operation==1)
            execlp("python3","python3",j->helper,"--check-update",(char*)NULL);
        else if(j->operation==2)
            execlp("python3","python3",j->helper,"--update","--confirm",(char*)NULL);
        else if(j->operation==3)
            execlp("python3","python3",j->helper,"--adopt","--confirm",(char*)NULL);
        else
            execlp("python3","python3",j->helper,"--install","--confirm",(char*)NULL);
        _exit(127);
    }
    close(fd[1]);
    if(child<0){
        close(fd[0]);
        snprintf(j->output,sizeof j->output,"Could not fork installer");
        g_idle_add(pc2_deckcheatz_install_done,j);return NULL;
    }
    j->ok=bounded_child_output(child,fd[0],j->output,sizeof j->output,180);
    g_idle_add(pc2_deckcheatz_install_done,j);
    return NULL;
}
static void pc2_deckcheatz_request_install(int resume_mode){
    if(!pc2_provider_controls_allowed())return;
    if(pc2_deckcheatz_install_busy){
        log_line("DeckCheatz managed installation already in progress.");return;
    }
    char existing[4096]={0};
    if(pc2_deckcheatz_find_launcher(existing,sizeof existing)){
        log_line("DeckCheatz 1.x already installed at %s; no download required.",existing);
        if(resume_mode>=0)pc2_deckcheatz_flow(resume_mode);
        return;
    }
    GtkWidget*consent=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "GameWeld can automatically download and install DeckCheatz 1.x.\n\n"
        "Download from: https://github.com/DeckCheatz/wemod-launcher.git (main branch)\n"
        "Install in your user GameWeld data directory; no sudo needed.\n"
        "DeckCheatz is independent AGPL-3.0 software, not bundled with GameWeld.\n\n"
        "This only downloads the external launcher; it will NOT start WeMod, "
        "change Steam Launch Options or modify a game Wine prefix.\n\n"
        "Download and install now?");
    int yes=(gtk_dialog_run((GtkDialog*)consent)==GTK_RESPONSE_YES);
    gtk_widget_destroy(consent);
    if(!yes){log_line("DeckCheatz managed installation cancelled by user.");return;}
    PC2DeckCheatzInstallJob *j=calloc(1,sizeof *j);
    if(!j){log_line("DeckCheatz managed installation could not allocate worker.");return;}
    const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)
        snprintf(j->helper,sizeof j->helper,"%s/usr/libexec/gameweld-deckcheatz-install.py",appdir);
    else snprintf(j->helper,sizeof j->helper,"gameweld-deckcheatz-install.py");
    j->resume_mode=resume_mode;
    j->selected_index=G.selected;
    pc2_deckcheatz_install_busy=1;
    log_line("DeckCheatz managed 1.x download requested; preparing official upstream checkout...");
    if(G.library_detail_status)set_label(G.library_detail_status,
        "Downloading official DeckCheatz 1.x to GameWeld user data. No Steam/game changes.");
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_deckcheatz_install_worker,j)==0)
        pthread_detach(thread);
    else {
        pc2_deckcheatz_install_busy=0;free(j);
        log_line("DeckCheatz managed installer worker could not start.");
    }
}
static void on_pc2_deckcheatz_install(GtkButton*b,void*d){
    (void)b;(void)d;pc2_deckcheatz_request_install(-1);
}
static void pc2_deckcheatz_request_update(int operation){
    if(!pc2_provider_controls_allowed())return;
    if(pc2_deckcheatz_install_busy){
        log_line("DeckCheatz install/update operation already in progress.");return;
    }
    if(operation!=1){
        GtkWidget*dlg=gtk_message_dialog_new((GtkWindow*)G.window,
            GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
            "%s",
            operation==3?
                "Manage this existing DeckCheatz 1.x checkout in GameWeld?\n\n"
                "This adds only a small version metadata file; it does not download or "
                "replace DeckCheatz source. The checkout must be an unchanged official "
                "main-branch clone at GameWeld's managed path.\n\n"
                "Close WeMod before enrolling. If files are modified or the source is "
                "unrecognized, GameWeld refuses to adopt it. Continue?":
                "Update the GameWeld-managed DeckCheatz 1.x checkout from upstream?\n\n"
                "Close WeMod and any running DeckCheatz sessions before updating. "
                "Existing manually installed checkouts and local changes will not be overwritten.\n\n"
                "The working checkout is kept as a rollback backup. Steam launch "
                "options and game Wine prefixes will not be changed by the update.\n\n"
                "The new upstream version still needs gameplay testing. Continue?");
        int yes=(gtk_dialog_run((GtkDialog*)dlg)==GTK_RESPONSE_YES);
        gtk_widget_destroy(dlg);
        if(!yes){log_line("DeckCheatz managed update cancelled.");return;}
    }
    PC2DeckCheatzInstallJob*j=calloc(1,sizeof *j);
    if(!j){log_line("DeckCheatz updater could not allocate job.");return;}
    const char*appdir=getenv("APPDIR");
    if(appdir&&*appdir)
        snprintf(j->helper,sizeof j->helper,"%s/usr/libexec/gameweld-deckcheatz-install.py",appdir);
    else snprintf(j->helper,sizeof j->helper,"gameweld-deckcheatz-install.py");
    j->resume_mode=-1;
    j->selected_index=G.selected;
    j->operation=operation;
    pc2_deckcheatz_install_busy=1;
    log_line("%s",operation==1?
        "Checking official DeckCheatz upstream revision (read-only)...":
        operation==3?"Validating clean existing DeckCheatz checkout for adoption...":
        "Updating managed DeckCheatz after consent; retaining a backup...");
    if(pc2_deckcheatz_update_status)set_label(pc2_deckcheatz_update_status,
        operation==1?"Checking official 1.x update status...":
        operation==3?"Inspecting existing source before managed enrolment...":
        "Verifying new checkout while preserving the previous installation...");
    pthread_t thread;
    if(pthread_create(&thread,NULL,pc2_deckcheatz_install_worker,j)==0)
        pthread_detach(thread);
    else {
        pc2_deckcheatz_install_busy=0;free(j);
        log_line("DeckCheatz update worker could not start.");
    }
}
static void on_pc2_deckcheatz_check_update(GtkButton*b,void*d){
    (void)b;(void)d;pc2_deckcheatz_request_update(1);
}
static void on_pc2_deckcheatz_update(GtkButton*b,void*d){
    (void)b;(void)d;pc2_deckcheatz_request_update(2);
}
static void on_pc2_deckcheatz_adopt(GtkButton*b,void*d){
    (void)b;(void)d;pc2_deckcheatz_request_update(3);
}

/* DeckCheatz PC2 preview stays strictly read-only. The separately labelled
 * experimental button reuses the same validated plan, displays the preview,
 * then requires explicit permission for game launch/prefix modifications.
 * Neither path edits Steam LaunchOptions or invokes a shell. */
static int pc2_deckcheatz_folder(const char *p){
    struct stat st;
    return p && *p && stat(p,&st)==0 && S_ISDIR(st.st_mode);
}
static int pc2_deckcheatz_file(const char *p){
    struct stat st;
    return p && *p && stat(p,&st)==0 && S_ISREG(st.st_mode);
}
static int pc2_deckcheatz_choose(const char *title,int folder,const char *start,
                                 char *dest,size_t cap){
    GtkWidget *dlg=gtk_file_chooser_dialog_new(title,(GtkWindow*)G.window,
        folder?GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER:GTK_FILE_CHOOSER_ACTION_OPEN,
        "Cancel",GTK_RESPONSE_CANCEL,"Select",GTK_RESPONSE_ACCEPT,NULL);
    if(start && pc2_deckcheatz_folder(start))
        gtk_file_chooser_set_current_folder((GtkFileChooser*)dlg,start);
    int ok=0;
    if(gtk_dialog_run((GtkDialog*)dlg)==GTK_RESPONSE_ACCEPT){
        char *pick=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);
        if(pick && strlen(pick)<cap){snprintf(dest,cap,"%s",pick);ok=1;}
        if(pick)g_free(pick);
    }
    gtk_widget_destroy(dlg);
    return ok;
}
static void pc2_deckcheatz_show_preview(const char *result){
    GtkWidget *dlg=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,0,2,"DeckCheatz 1.x — read-only launch plan");
    GtkWidget *sc=gtk_scrolled_window_new(NULL,NULL);
    GtkWidget *view=gtk_text_view_new();
    gtk_widget_set_size_request(sc,800,460);
    gtk_text_view_set_editable((GtkTextView*)view,FALSE);
    gtk_text_view_set_cursor_visible((GtkTextView*)view,FALSE);
    gtk_text_view_set_monospace((GtkTextView*)view,TRUE);
    gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)view),result,-1);
    gtk_container_add(sc,view);
    gtk_box_pack_start(gtk_dialog_get_content_area((GtkDialog*)dlg),sc,TRUE,TRUE,0);
    gtk_widget_show_all(dlg);
    gtk_dialog_run((GtkDialog*)dlg);
    gtk_widget_destroy(dlg);
}
static void pc2_deckcheatz_flow(int experimental_launch){
    if(!pc2_provider_controls_allowed())return;
    if(G.selected<0 || G.selected>=G.game_count){
        log_line("DeckCheatz preview: select an installed Steam game first.");return;
    }
    Game *g=&G.games[G.selected];
    if(!game_is_steam(g) || game_is_steam_shortcut(g)){
        log_line("DeckCheatz 1.x preview currently supports installed Steam games only.");return;
    }
    if(!g->install_dir[0] || !pc2_deckcheatz_folder(g->install_dir)){
        log_line("DeckCheatz preview blocked: %s has no resolved Steam install folder.",g->name);return;
    }
    char launcher[4096]={0},exe[4096]={0},proton[4096]={0};
    char compat[4096]={0},steam[4096]={0},candidate[4096]={0};
    const char *home=getenv("HOME");
    if(!pc2_deckcheatz_find_launcher(launcher,sizeof launcher)){
        log_line("DeckCheatz is not installed. GameWeld can download official 1.x automatically.");
        pc2_deckcheatz_request_install(experimental_launch);
        return;
    }
    if(g->executable[0] && pc2_deckcheatz_file(g->executable))
        snprintf(exe,sizeof exe,"%s",g->executable);
    else if(!pc2_deckcheatz_choose("Select the Windows game EXE",0,
                                  g->install_dir,exe,sizeof exe)){
        log_line("DeckCheatz preview cancelled: no game EXE selected.");return;
    }
    if(g->compat_tool_path[0]){
        if(pc2_deckcheatz_file(g->compat_tool_path))
            snprintf(proton,sizeof proton,"%s",g->compat_tool_path);
        else {
            snprintf(candidate,sizeof candidate,"%s/proton",g->compat_tool_path);
            if(pc2_deckcheatz_file(candidate))
                snprintf(proton,sizeof proton,"%s",candidate);
        }
    }
    /* When game discovery does not expose Proton, try the same Steam runtime
     * resolution used by the shortcut provider before prompting the user. */
    if(g->steam_root[0] && pc2_deckcheatz_folder(g->steam_root))
        snprintf(steam,sizeof steam,"%s",g->steam_root);
    else {
        const char *sr=getenv("STEAM_COMPAT_CLIENT_INSTALL_PATH");
        if(sr && *sr && pc2_deckcheatz_folder(sr))
            snprintf(steam,sizeof steam,"%s",sr);
        if(!steam[0] && home){
            snprintf(candidate,sizeof candidate,"%s/.steam/root",home);
            if(pc2_deckcheatz_folder(candidate))snprintf(steam,sizeof steam,"%s",candidate);
        }
        if(!steam[0] && home){
            snprintf(candidate,sizeof candidate,"%s/.local/share/Steam",home);
            if(pc2_deckcheatz_folder(candidate))snprintf(steam,sizeof steam,"%s",candidate);
        }
    }
    snprintf(candidate,sizeof candidate,"%s/steamapps",steam);
    if(!steam[0] || !pc2_deckcheatz_folder(candidate)){
        if(!pc2_deckcheatz_choose("Select Steam root folder (containing steamapps)",1,
                                 NULL,steam,sizeof steam)){
            log_line("DeckCheatz preview cancelled: Steam root not selected.");return;
        }
    }
    if(g->compatdata[0] && pc2_deckcheatz_folder(g->compatdata))
        snprintf(compat,sizeof compat,"%s",g->compatdata);
    if(!compat[0]){
        snprintf(candidate,sizeof candidate,"%s/steamapps/compatdata/%s",steam,g->appid);
        if(pc2_deckcheatz_folder(candidate))snprintf(compat,sizeof compat,"%s",candidate);
    }
    if(!compat[0]){
        /* Game-specific compatdata may be in a separate Steam library. */
        snprintf(candidate,sizeof candidate,"%s/../../compatdata/%s",g->install_dir,g->appid);
        if(pc2_deckcheatz_folder(candidate))snprintf(compat,sizeof compat,"%s",candidate);
    }
    if(!compat[0] && !pc2_deckcheatz_choose(
            "Select existing compatdata folder for this Steam AppID",1,
            NULL,compat,sizeof compat)){
        log_line("DeckCheatz preview cancelled: no existing game prefix selected.");return;
    }

    if(!pc2_deckcheatz_file(proton)){
        char locator[4096]={0},discovery[16384]={0};
        const char *dev=getenv("APPDIR");
        if(dev && *dev)snprintf(locator,sizeof locator,
            "%s/usr/libexec/gameweld-deckcheatz-proton.py",dev);
        else snprintf(locator,sizeof locator,"gameweld-deckcheatz-proton.py");
        int lookupfd[2];
        if(pipe(lookupfd)==0){
            pid_t lookup=fork();
            if(lookup==0){
                close(lookupfd[0]);setsid();
                dup2(lookupfd[1],STDOUT_FILENO);
                dup2(lookupfd[1],STDERR_FILENO);
                close(lookupfd[1]);
                clear_desktop_activation_env();
                execlp("python3","python3",locator,
                    "--appid",g->appid,
                    "--steam-root",steam,
                    "--install-dir",g->install_dir,
                    "--compatdata",compat,
                    "--preferred-name",g->compat_tool,
                    "--preferred-path",g->compat_tool_path,
                    (char*)NULL);
                _exit(127);
            }
            close(lookupfd[1]);
            if(lookup>0){
                int success=bounded_child_output(lookup,lookupfd[0],
                    discovery,sizeof discovery,12);
                if(success){
                    char resolved[4096]={0};
                    json_string(discovery,"selected",resolved,sizeof resolved);
                    if(pc2_deckcheatz_file(resolved) &&
                       !strcmp(strrchr(resolved,'/')?strrchr(resolved,'/')+1:resolved,"proton")){
                        snprintf(proton,sizeof proton,"%s",resolved);
                        log_line("DeckCheatz: automatically found the selected Steam game's Proton launcher: %s",proton);
                    }
                }
            }else{
                close(lookupfd[0]);
            }
        }
    }
    if(!pc2_deckcheatz_file(proton)){
        char browse[4096]={0};
        if(pc2_deckcheatz_folder(g->compat_tool_path))
            snprintf(browse,sizeof browse,"%s",g->compat_tool_path);
        else {
            snprintf(candidate,sizeof candidate,"%s/compatibilitytools.d",steam);
            if(pc2_deckcheatz_folder(candidate))
                snprintf(browse,sizeof browse,"%s",candidate);
            else {
                snprintf(candidate,sizeof candidate,"%s/steamapps/common",steam);
                if(pc2_deckcheatz_folder(candidate))
                    snprintf(browse,sizeof browse,"%s",candidate);
            }
        }
        log_line("DeckCheatz: Steam's Proton version could not be automatically resolved for %s. Please choose the executable file named proton inside the installed Proton or GE-Proton folder.",g->name);
        if(!pc2_deckcheatz_choose("Select the file named proton (inside GE-Proton or Steam Proton)",0,
                                 browse[0]?browse:NULL,proton,sizeof proton)){
            log_line("DeckCheatz preview cancelled: Proton file not selected. This is not a DeckCheatz installation failure.");return;
        }
    }
    if(strcmp(strrchr(proton,'/')?strrchr(proton,'/')+1:proton,"proton") ||
       !pc2_deckcheatz_file(proton)){
        log_line("DeckCheatz preview blocked: select the launcher file literally named proton.");return;
    }
    const char *appdir=getenv("APPDIR");char helper[4096]={0};
    if(appdir && *appdir)snprintf(helper,sizeof helper,
        "%s/usr/libexec/gameweld-deckcheatz-direct.py",appdir);
    else snprintf(helper,sizeof helper,"gameweld-deckcheatz-direct.py");
    if(!pc2_deckcheatz_file(helper) && !strchr(helper,'/')){
        log_line("DeckCheatz preview requires its GameWeld source helper on PATH.");return;
    }
    int fd[2];if(pipe(fd)!=0){log_line("DeckCheatz preview: pipe unavailable.");return;}
    pid_t pid=fork();
    if(pid<0){close(fd[0]);close(fd[1]);log_line("DeckCheatz preview: process unavailable.");return;}
    if(pid==0){
        close(fd[0]);setsid();dup2(fd[1],STDOUT_FILENO);dup2(fd[1],STDERR_FILENO);close(fd[1]);
        clear_desktop_activation_env();
        execlp("python3","python3",helper,"--preview","--appid",g->appid,
            "--launcher",launcher,"--proton",proton,"--game-exe",exe,
            "--install-dir",g->install_dir,"--compatdata",compat,
            "--steam-root",steam,(char*)NULL);
        _exit(127);
    }
    close(fd[1]);
    char output[16384]={0};
    int ok=bounded_child_output(pid,fd[0],output,sizeof output,12);
    if(!ok){
        log_line("DeckCheatz preview blocked for %s; no launch or Steam option changes occurred.",g->name);
        if(!output[0])snprintf(output,sizeof output,"GameWeld preview helper failed without output.");
    }else{
        log_line("DeckCheatz read-only preview generated for %s; no game/trainer launched.",g->name);
    }
    pc2_deckcheatz_show_preview(output);
    if(!ok || !experimental_launch)return;

    /* This provider has no real-game field validation. The preview is always
     * presented first and game/prefix changes require an explicit Yes. */
    GtkWidget*consent=gtk_message_dialog_new((GtkWindow*)G.window,
        GTK_DIALOG_MODAL,GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO,
        "EXPERIMENTAL direct DeckCheatz 1.x launch for %s (Steam AppID %s).\n\n"
        "This will start an external WeMod launcher and a separate Proton process, "
        "without using Steam's launch supervisor. The game or SteamAPI may fail.\n\n"
        "DeckCheatz can download components or MODIFY the existing Wine prefix:\n%s\n\n"
        "Back up the prefix if you need a rollback, close all game/Steam Play sessions "
        "using this prefix, and only test offline/single-player.\n\n"
        "GameWeld will NOT edit Steam Launch Options. Continue?",
        g->name,g->appid,compat);
    int approved=(gtk_dialog_run((GtkDialog*)consent)==GTK_RESPONSE_YES);
    gtk_widget_destroy(consent);
    if(!approved){
        log_line("DeckCheatz experimental test cancelled; prefix and Steam settings left untouched.");return;
    }
    /* The launcher helper repeats all path checks and refuses duplicate AppIDs.
     * A double-fork detaches the lengthy game session from GTK, while output
     * is kept in a private file. Queued != started and exit 0 != trainer success. */
    const char*state=getenv("XDG_STATE_HOME");
    char statebase[4096]={0},logdir[4096]={0},logpath[4096]={0};
    if(state&&*state&&state[0]=='/')snprintf(statebase,sizeof statebase,"%s",state);
    else if(home&&*home)snprintf(statebase,sizeof statebase,"%s/.local/state",home);
    if(!statebase[0] ||
       snprintf(logdir,sizeof logdir,"%s/gameweld/deckcheatz",statebase)>=(int)sizeof logdir ||
       g_mkdir_with_parents(logdir,0700)!=0){
        log_line("DeckCheatz experiment blocked: private log directory unavailable.");return;
    }
    if(snprintf(logpath,sizeof logpath,"%s/%s-%ld-%ld.log",logdir,g->appid,
                (long)time(NULL),(long)getpid())>=(int)sizeof logpath){
        log_line("DeckCheatz experiment blocked: log path too long.");return;
    }
    int logfd=open(logpath,O_CREAT|O_EXCL|O_WRONLY,0600);
    if(logfd<0){log_line("DeckCheatz experiment blocked: cannot create private log file.");return;}
    close(logfd);
    pid_t first=fork();
    if(first<0){
        unlink(logpath);
        log_line("DeckCheatz experiment blocked: unable to start launcher helper.");return;
    }
    if(first==0){
        pid_t child=fork();
        if(child<0)_exit(126);
        if(child>0)_exit(0);
        setsid();
        int out=open(logpath,O_WRONLY|O_APPEND);
        if(out<0)_exit(126);
        int input=open("/dev/null",O_RDONLY);
        if(input>=0){dup2(input,STDIN_FILENO);if(input>2)close(input);}
        dup2(out,STDOUT_FILENO);dup2(out,STDERR_FILENO);
        if(out>2)close(out);
        clear_desktop_activation_env();
        execlp("python3","python3","-u",helper,"--launch","--appid",g->appid,
            "--launcher",launcher,"--proton",proton,"--game-exe",exe,
            "--install-dir",g->install_dir,"--compatdata",compat,
            "--steam-root",steam,
            "--confirm-prefix-changes","--experimental-direct-launch",(char*)NULL);
        dprintf(STDERR_FILENO,"GameWeld: could not execute experimental DeckCheatz helper.\\n");
        _exit(127);
    }
    int intermediate=0;
    pid_t waited;
    do {waited=waitpid(first,&intermediate,0);} while(waited<0 && errno==EINTR);
    if(waited!=first || !WIFEXITED(intermediate) || WEXITSTATUS(intermediate)!=0){
        log_line("DeckCheatz experimental handoff failed to queue; inspect %s",logpath);
        return;
    }
    log_line("DeckCheatz experimental handoff REQUESTED for %s. Not yet verified: game window, WeMod window or trainer attach. Diagnostic log: %s",g->name,logpath);
}
static void on_pc2_deckcheatz_preview(GtkButton*b,void*d){
    (void)b;(void)d;pc2_deckcheatz_flow(0);
}

static void on_pc2_wemod_choose(GtkButton*b,void*d){
    (void)b;(void)d;
    GtkWidget*dialog=gtk_file_chooser_dialog_new("Choose WeMod folder containing WeMod.exe",
        (GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER,
        "Cancel",GTK_RESPONSE_CANCEL,"Use Folder",GTK_RESPONSE_ACCEPT,NULL);
    if(gtk_dialog_run((GtkDialog*)dialog)==GTK_RESPONSE_ACCEPT){
        char*folder=gtk_file_chooser_get_filename((GtkFileChooser*)dialog);
        if(folder&&pc2_wemod_install_entry)
            gtk_entry_set_text((GtkEntry*)pc2_wemod_install_entry,folder);
        if(folder)g_free(folder);
    }
    gtk_widget_destroy(dialog);
}
static void on_settings_open_wemod(GtkButton *button, void *notebook){
    (void)button;
    gtk_notebook_set_current_page((GtkNotebook*)notebook,1);
}
static GtkWidget *build_settings(void){
    GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,22);gtk_container_add(outer,p);
    GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);
    pack(ht,label("SETTINGS","page-kicker"),0);
    pack(ht,label("GameWeld Settings","workspace-title"),0);
    pack(ht,label("Game-first controls with DeckCheatz, WeMod and advanced providers organised into separate tabs.","page-subtitle"),0);
    pack(p,ht,0);
    GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);
    GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);
    pack(cols,left,1);pack(cols,right,1);
    GtkWidget*deckpage=NULL;
    if(1){
        GtkWidget*tabs=gtk_notebook_new();
        GtkWidget*quick=box(GTK_ORIENTATION_VERTICAL,12);
        GtkWidget*first=card("Play with WeMod",
            "For Steam Windows games, the validated Steam Bridge launches the game and WeMod "
            "inside the same Proton runtime. Open Advanced Providers to inspect an existing "
            "Steam Bridge setup. First-time compatibility-tool registration is still manual. "
            "Other provider launchers remain separate options.",
            NULL);
        pack(quick,first,0);
        GtkWidget*open_wemod=button("Open WeMod & DeckCheatz setup","primary-action");
        g_signal_connect_data(open_wemod,"clicked",(GCallback)on_settings_open_wemod,tabs,NULL,0);
        pack(quick,open_wemod,0);
        pack(quick,card("Tested game: Astrometica",
            "GameWeld Steam Bridge + Proton Experimental + Steam Linux Runtime 4 "
            "successfully launched Astrometica and WeMod together; the trainer worked in-game "
            "on one CachyOS system. Other games still need individual validation.",NULL),0);
        pack(quick,card("Keep your installation working",
            "DeckCheatz downloads, version checks and opt-in updates are under the DeckCheatz tab. "
            "Source-level trainer providers, compatibility fixes and patch diagnostics are under Advanced Providers. "
            "GameWeld does not perform background DeckCheatz updates.",NULL),0);
        pack(quick,card("Window size",
            "GameWeld remembers your last normal-window size and opens in a comfortable "
            "window on each display. Restore the default after changing monitors or scaling.",NULL),0);
        GtkWidget*window_reset=button("Reset window size","action");
        g_signal_connect_data(window_reset,"clicked",(GCallback)on_pc2_window_size_reset,NULL,NULL,0);
        pack(quick,window_reset,0);
        deckpage=box(GTK_ORIENTATION_VERTICAL,12);
        GtkWidget*advancedpage=box(GTK_ORIENTATION_VERTICAL,12);
        pack(advancedpage,card("Optional integrations and maintenance",
            "Use WeMod & DeckCheatz for the recommended Steam setup. Expand the tools below only for Wand, WeMod Enhancer patching, local trainers or Cheat Engine.",NULL),0);
        GtkWidget*advanced_expander=gtk_expander_new("Wand, WeMod Enhancer, Cheat Engine and local trainers (advanced)");
        gtk_expander_set_expanded(advanced_expander,FALSE);
        gtk_container_add(advanced_expander,cols);
        pack(advancedpage,advanced_expander,0);
        gtk_notebook_append_page((GtkNotebook*)tabs,quick,label("Quick Start",NULL));
        gtk_notebook_append_page((GtkNotebook*)tabs,deckpage,label("WeMod & DeckCheatz",NULL));
        gtk_notebook_append_page((GtkNotebook*)tabs,advancedpage,label("Advanced Providers",NULL));
        gtk_notebook_set_current_page((GtkNotebook*)tabs,0);
        pack(p,tabs,1);
    }else pack(p,cols,1);
    GtkWidget*nc=box(GTK_ORIENTATION_VERTICAL,8);style(nc,"card");pack(nc,label("Native CT Profile (No Cheat Engine)","card-title"),0);GtkWidget*nd=label("GameWeld can directly run converted table logic for supported games without Cheat Engine. Resonance: A Plague Tale Legacy has a built-in conversion of Paul44's v1.1 table with God Mode, Invisible, Resonance Points, FOV and Console controls. The original .CT is not redistributed.","muted");gtk_label_set_line_wrap((GtkLabel*)nd,TRUE);pack(nc,nd,0);GtkWidget*nr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*nen=button("Enable Native Profile","action");GtkWidget*ndis=button("Disable Native Profile","action");g_signal_connect_data(nen,"clicked",(GCallback)on_enable_native_profile,NULL,NULL,0);g_signal_connect_data(ndis,"clicked",(GCallback)on_disable_native_profile,NULL,NULL,0);pack(nr,nen,0);pack(nr,ndis,0);pack(nc,nr,0);G.native_profile_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.native_profile_status,TRUE);pack(nc,G.native_profile_status,0);pack(left,nc,0);
    if(1){
        GtkWidget*dc=box(GTK_ORIENTATION_VERTICAL,8);style(dc,"card");
        pack(dc,label("DeckCheatz 1.x — Managed Updates","card-title"),0);
        GtkWidget*note=label("Check for upstream 1.x fixes or explicitly update a GameWeld-managed checkout. No background updates. The previous version is retained for rollback and manually installed checkouts are left untouched.","muted");
        gtk_label_set_line_wrap((GtkLabel*)note,TRUE);pack(dc,note,0);
        GtkWidget*install_actions=box(GTK_ORIENTATION_HORIZONTAL,8);
        GtkWidget*detect=button("Detect installed DeckCheatz","action");
        GtkWidget*install=button("Install DeckCheatz (managed)","primary-action");
        g_signal_connect_data(detect,"clicked",(GCallback)on_pc2_deckcheatz_detect,NULL,NULL,0);
        g_signal_connect_data(install,"clicked",(GCallback)on_pc2_deckcheatz_install,NULL,NULL,0);
        pack(install_actions,detect,1);pack(install_actions,install,1);pack(dc,install_actions,0);
        GtkWidget*bar=box(GTK_ORIENTATION_HORIZONTAL,8);
        GtkWidget*check=button("Check DeckCheatz updates","action");
        GtkWidget*update=button("Update DeckCheatz (opt-in)","action");
        g_signal_connect_data(check,"clicked",(GCallback)on_pc2_deckcheatz_check_update,NULL,NULL,0);
        g_signal_connect_data(update,"clicked",(GCallback)on_pc2_deckcheatz_update,NULL,NULL,0);
        pack(bar,check,1);pack(bar,update,1);pack(dc,bar,0);
        GtkWidget*adopt=button("Manage existing DeckCheatz checkout","action");
        g_signal_connect_data(adopt,"clicked",(GCallback)on_pc2_deckcheatz_adopt,NULL,NULL,0);
        pack(dc,adopt,0);
        pc2_deckcheatz_update_status=label("No check performed yet. Existing installs are unchanged.","muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_deckcheatz_update_status,TRUE);
        pack(dc,pc2_deckcheatz_update_status,0);pack(deckpage,dc,0);
    }
    GtkWidget*lc=box(GTK_ORIENTATION_VERTICAL,8);style(lc,"card");pack(lc,label("Local Trainer Provider (Unlimited)","card-title"),0);GtkWidget*desc=label("GameWeld can discover standalone Windows trainer EXEs automatically or you can choose one manually. Discovery uses standard XDG/Home folders, folders you add, and the install paths reported by Steam/Heroic/Lutris; it never assumes a specific username, /mnt/games, drive layout or distro. Steam uses the proven live Proton-session handoff. Heroic games from Epic, GOG and Amazon stay launcher-native: GameWeld launches through the detected Heroic runner. For local trainers on affected Wine/Proton 11+ builds, GameWeld uses its pinned GE-Proton10-34 + Wine-Wayland compatibility session. Epic/Legendary launches through Heroic's authenticated Legendary backend with an explicit UMU environment; the trainer joins it with UMU runinprefix. GOG/Amazon retain the verified temporary Heroic handshake.","muted");gtk_label_set_line_wrap((GtkLabel*)desc,TRUE);pack(lc,desc,0);G.local_trainer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.local_trainer_entry,"No local trainer configured");pack(lc,G.local_trainer_entry,0);GtkWidget*lr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*choose=button("Choose Trainer EXE","action");GtkWidget*scan=button("Scan / Auto-Match Trainers","action");GtkWidget*addfolder=button("Add Trainer Folder","action");GtkWidget*clear=button("Clear Trainer","action");g_signal_connect_data(choose,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(addfolder,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);pack(lr,choose,0);pack(lr,scan,0);pack(lr,addfolder,0);pack(lr,clear,0);pack(lc,lr,0);GtkWidget*hr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*stop=button("Stop Stuck Trainer","action");GtkWidget*reset=button("Reset Heroic Prefix (Closes Game)","action");g_signal_connect_data(stop,"clicked",(GCallback)on_stop_heroic_trainer,NULL,NULL,0);g_signal_connect_data(reset,"clicked",(GCallback)on_reset_heroic_prefix,NULL,NULL,0);pack(hr,stop,0);pack(hr,reset,0);pack(lc,hr,0);GtkWidget*compat=label("Validated FLiNG recipe: normal desktop windows are used. The engine is game-agnostic and scoped to the exact Heroic installation discovered for the selected title. On affected Wine/Proton 11+ builds, game and trainer share pinned GE-Proton10-34 with Wine-Wayland. Epic/Legendary uses matching UMU runinprefix instead of host Wine, so a trainer cannot be deferred until after game exit.","muted");gtk_label_set_line_wrap((GtkLabel*)compat,TRUE);pack(lc,compat,0);G.local_trainer_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.local_trainer_status,TRUE);pack(lc,G.local_trainer_status,0);pack(left,lc,0);
    GtkWidget*cc=box(GTK_ORIENTATION_VERTICAL,8);style(cc,"card");pack(cc,label("Managed Cheat Engine Provider (.CT)","card-title"),0);GtkWidget*cd=label("GameWeld uses the official Cheat Engine Linux package as the native bridge and a shared Windows CE companion in windowsbin. Steam handoff joins the verified Proton session; Heroic handoff waits for the real game process and asks Heroic to launch Windows CE as an alternate executable using that game's configured Wine/Proton runner. Install the bridge and Windows companion once. Cheat Engine itself is not bundled inside GameWeld.","muted");gtk_label_set_line_wrap((GtkLabel*)cd,TRUE);pack(cc,cd,0);G.cheat_engine_installer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_installer_entry,"Official CheatEngineLinux771.zip or Windows CE installer/ZIP");pack(cc,G.cheat_engine_installer_entry,0);G.cheat_engine_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_entry,"Managed native Linux CE appears here after install");pack(cc,G.cheat_engine_entry,0);G.cheat_table_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_table_entry,"No .CT table configured for selected game");pack(cc,G.cheat_table_entry,0);GtkWidget*cr0=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceauto=button("Download + Install Linux CE","action");GtkWidget*cedl=button("Open Official Linux ZIP","action");GtkWidget*cewin=button("Open Official Windows CE","action");GtkWidget*cei=button("Choose CE Package","action");g_signal_connect_data(ceauto,"clicked",(GCallback)on_download_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cedl,"clicked",(GCallback)on_open_cheat_engine_download,NULL,NULL,0);g_signal_connect_data(cewin,"clicked",(GCallback)on_open_cheat_engine_windows_download,NULL,NULL,0);g_signal_connect_data(cei,"clicked",(GCallback)on_choose_cheat_engine_installer,NULL,NULL,0);pack(cr0,ceauto,0);pack(cr0,cedl,0);pack(cr0,cewin,0);pack(cr0,cei,0);pack(cc,cr0,0);GtkWidget*cr1=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceinstall=button("Install Selected Package","action");GtkWidget*ced=button("Detect / Refresh CE","action");GtkWidget*cce=button("Choose Existing CE","action");GtkWidget*cct=button("Choose .CT Table","action");g_signal_connect_data(ceinstall,"clicked",(GCallback)on_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(ced,"clicked",(GCallback)on_detect_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cce,"clicked",(GCallback)on_choose_cheat_engine,NULL,NULL,0);g_signal_connect_data(cct,"clicked",(GCallback)on_choose_cheat_table,NULL,NULL,0);pack(cr1,ceinstall,0);pack(cr1,ced,0);pack(cr1,cce,0);pack(cr1,cct,0);pack(cc,cr1,0);GtkWidget*cr2=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*cte=button("Clear External CE","action");GtkWidget*ctt=button("Clear Table","action");g_signal_connect_data(cte,"clicked",(GCallback)on_clear_cheat_engine,NULL,NULL,0);g_signal_connect_data(ctt,"clicked",(GCallback)on_clear_cheat_table,NULL,NULL,0);pack(cr2,cte,0);pack(cr2,ctt,0);pack(cc,cr2,0);G.cheat_table_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.cheat_table_status,TRUE);pack(cc,G.cheat_table_status,0);pack(right,cc,0);
    if(1){
        /* The Steam compatibility bridge is the validated PC2 Steam/WeMod
         * route. Put it first; keep the earlier failed live-host-Wine launch
         * experiments out of the everyday interface. */
        GtkWidget*shared_card=box(GTK_ORIENTATION_VERTICAL,9);style(shared_card,"card");
        pack(shared_card,label("Prepared WeMod setup — All game libraries","card-title"),0);
        GtkWidget*shared_note=label(
            "One GameWeld-managed prepared setup library for Steam, Heroic and Lutris. "
            "Find a compatible prepared setup without selecting a game. "
            "This currently checks releases only; installation, backup and rollback "
            "are not yet enabled.","muted");
        gtk_label_set_line_wrap((GtkLabel*)shared_note,TRUE);
        pack(shared_card,shared_note,0);
        GtkWidget*ready_prefix=button("Find prepared WeMod setup","action");
        g_signal_connect_data(ready_prefix,"clicked",(GCallback)on_pc2_bridge_prefix_catalog,NULL,NULL,0);
        pack(shared_card,ready_prefix,0);
        GtkWidget*prefix_choice_note=label(
            "Review an available release below. Version-label matches do not "
            "prove a working WeMod trainer or a trusted publisher.","muted");
        gtk_label_set_line_wrap((GtkLabel*)prefix_choice_note,TRUE);
        pack(shared_card,prefix_choice_note,0);
        pc2_shared_wemod_choices=gtk_combo_box_text_new();
        g_signal_connect_data(pc2_shared_wemod_choices,"changed",
            (GCallback)pc2_prepared_choice_update,NULL,NULL,0);
        pack(shared_card,pc2_shared_wemod_choices,0);
        pc2_shared_wemod_download=button(
            "Step 1 — Download selected prepared setup (cache only)","action");
        gtk_widget_set_sensitive(pc2_shared_wemod_download,FALSE);
        g_signal_connect_data(pc2_shared_wemod_download,"clicked",
            (GCallback)on_pc2_prepared_prefix_cache,NULL,NULL,0);
        pack(shared_card,pc2_shared_wemod_download,0);
        GtkWidget*prepared_stage_button=button("Step 2 — Stage downloaded .NET prefix (isolated)","action");
        g_signal_connect_data(prepared_stage_button,"clicked",
            (GCallback)on_pc2_prepared_stage,NULL,NULL,0);
        pack(shared_card,prepared_stage_button,0);
        pc2_shared_wemod_cancel=button("Cancel cache download","action");
        gtk_widget_set_sensitive(pc2_shared_wemod_cancel,FALSE);
        g_signal_connect_data(pc2_shared_wemod_cancel,"clicked",
            (GCallback)on_pc2_prepared_cache_cancel,NULL,NULL,0);
        pack(shared_card,pc2_shared_wemod_cancel,0);
        pc2_shared_wemod_status=label(
            "No setup checked yet. No game files or settings will be changed.","muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_shared_wemod_status,TRUE);
        pack(shared_card,pc2_shared_wemod_status,0);
        pack(deckpage,shared_card,0);
        GtkWidget*native_card=box(GTK_ORIENTATION_VERTICAL,9);style(native_card,"card");
        pack(native_card,label("Game connection — No Steam Bridge required","card-title"),0);
        GtkWidget*native_note=label(
            "Select any supported Steam, Heroic or Lutris game. GameWeld checks "
            "its original launcher and runtime context. A prepared WeMod setup "
            "must still be verified with that game before Play is enabled.","muted");
        gtk_label_set_line_wrap((GtkLabel*)native_note,TRUE);
        pack(native_card,native_note,0);
        GtkWidget*native_check=button("Check game WeMod connection","action");
        g_signal_connect_data(native_check,"clicked",
            (GCallback)on_pc2_native_route,NULL,NULL,0);
        pack(native_card,native_check,0);
        GtkWidget*copy_steam_deckcheatz=button("Copy DeckCheatz Steam launch option","action");
        g_signal_connect_data(copy_steam_deckcheatz,"clicked",
            (GCallback)on_pc2_deckcheatz_copy_steam_option,NULL,NULL,0);
        pack(native_card,copy_steam_deckcheatz,0);
        GtkWidget*one_shot_setup=button("Set up one-session DeckCheatz","action");
        g_signal_connect_data(one_shot_setup,"clicked",
            (GCallback)on_pc2_deckcheatz_setup_session,NULL,NULL,0);
        pack(native_card,one_shot_setup,0);
        GtkWidget*restore_steam_original=button("Restore original Steam launch option","action");
        g_signal_connect_data(restore_steam_original,"clicked",
            (GCallback)on_pc2_deckcheatz_restore_steam_option,NULL,NULL,0);
        pack(native_card,restore_steam_original,0);
        GtkWidget*live_attach_preview=button("Preview no-options WeMod handoff (read-only)","action");
        g_signal_connect_data(live_attach_preview,"clicked",
            (GCallback)on_pc2_live_attach_preview,NULL,NULL,0);
        pack(native_card,live_attach_preview,0);
        GtkWidget*prepared_import_preview=button("Step 3 — Review prepared .NET prefix (read-only)","action");
        g_signal_connect_data(prepared_import_preview,"clicked",
            (GCallback)on_pc2_prepared_import_preview,NULL,NULL,0);
        pack(native_card,prepared_import_preview,0);
        pc2_native_route_status=label(
            "Select a Steam, Heroic or Lutris game, then check its WeMod setup. "
            "No game will be launched or modified.","muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_native_route_status,TRUE);
        style(pc2_native_route_status,"game-connection-summary");
        pack(native_card,pc2_native_route_status,0);
        pack(deckpage,native_card,0);
        GtkWidget*bridge_card=box(GTK_ORIENTATION_VERTICAL,9);style(bridge_card,"card");
        pack(bridge_card,label("Steam Bridge — Game + WeMod","card-title"),0);
        GtkWidget*bridge_note=label(
            "Run Steam Windows games with WeMod in the same Proton runtime. "
            "Astrometica has passed a live in-game test. Select a game to inspect its "
            "saved Bridge setup or change whether WeMod starts with the next launch. "
            "First-time setup registers the tool; select it under Steam Compatibility after restarting Steam.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)bridge_note,TRUE);
        pack(bridge_card,bridge_note,0);
        GtkWidget*bridge_status=button("Check WeMod readiness","action");
        GtkWidget*bridge_setup=button("Steam Bridge: Set up selected game","action");
        g_signal_connect_data(bridge_status,"clicked",(GCallback)on_pc2_bridge_status,NULL,NULL,0);
        g_signal_connect_data(bridge_setup,"clicked",(GCallback)on_pc2_bridge_setup,NULL,NULL,0);
        GtkWidget*bridge_first=box(GTK_ORIENTATION_HORIZONTAL,8);
        pack(bridge_first,bridge_status,1);
        pack(bridge_first,bridge_setup,1);
        pack(bridge_card,bridge_first,0);
        GtkWidget*bridge_controls=box(GTK_ORIENTATION_HORIZONTAL,8);
        GtkWidget*bridge_enable=button("Steam Bridge: Enable WeMod next launch","primary-action");
        GtkWidget*bridge_disable=button("Steam Bridge: Disable WeMod next launch","action");
        g_signal_connect_data(bridge_enable,"clicked",(GCallback)on_pc2_bridge_enable,NULL,NULL,0);
        g_signal_connect_data(bridge_disable,"clicked",(GCallback)on_pc2_bridge_disable,NULL,NULL,0);
        pack(bridge_controls,bridge_enable,1);
        pack(bridge_controls,bridge_disable,1);
        pack(bridge_card,bridge_controls,0);
        GtkWidget*gpu_helper=gtk_expander_new("WeMod blank/white window — per-game display fix");
        gtk_expander_set_expanded(gpu_helper,FALSE);
        GtkWidget*gpu_box=box(GTK_ORIENTATION_VERTICAL,6);
        GtkWidget*gpu_help=label(
            "If WeMod is blank for this game but works for others, try disabling "
            "WeMod's hardware-accelerated UI only for this title. Close the game "
            "before changing; this does not modify game graphics. Revert if worse.","muted");
        gtk_label_set_line_wrap((GtkLabel*)gpu_help,TRUE);
        pack(gpu_box,gpu_help,0);
        GtkWidget*gpu_actions=box(GTK_ORIENTATION_HORIZONTAL,8);
        GtkWidget*gpu_off=button("WeMod display: Try GPU off for this game","action");
        GtkWidget*gpu_on=button("WeMod display: Restore normal for this game","action");
        g_signal_connect_data(gpu_off,"clicked",(GCallback)on_pc2_bridge_gpu_off,NULL,NULL,0);
        g_signal_connect_data(gpu_on,"clicked",(GCallback)on_pc2_bridge_gpu_on,NULL,NULL,0);
        pack(gpu_actions,gpu_off,1);
        pack(gpu_actions,gpu_on,1);
        pack(gpu_box,gpu_actions,0);
        GtkWidget*netfx_check=button("Check Windows .NET in this game (read-only)","action");
        g_signal_connect_data(netfx_check,"clicked",(GCallback)on_pc2_bridge_netfx_status,NULL,NULL,0);
        pack(gpu_box,netfx_check,0);
        gtk_container_add(gpu_helper,gpu_box);
        pack(bridge_card,gpu_helper,0);
        pc2_steam_bridge_status=label(
            "Select an installed Steam game, then choose Check WeMod readiness.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_steam_bridge_status,TRUE);
        pack(bridge_card,pc2_steam_bridge_status,0);
        GtkWidget*netfx_plan=button("Plan safe .NET test (read-only)","action");
        g_signal_connect_data(netfx_plan,"clicked",(GCallback)on_pc2_bridge_netfx_plan,NULL,NULL,0);
        /* Keep the legacy .NET experiment plan under advanced maintenance;
         * ordinary players should only see the ready-made WeMod setup path. */
        pc2_steam_bridge_quick_upgrade=button("Update Steam Bridge","action");
        g_signal_connect_data(pc2_steam_bridge_quick_upgrade,"clicked",
            (GCallback)on_pc2_bridge_upgrade,NULL,NULL,0);
        gtk_widget_set_sensitive(pc2_steam_bridge_quick_upgrade,FALSE);
        pack(bridge_card,pc2_steam_bridge_quick_upgrade,0);
        GtkWidget*bridge_maintenance=gtk_expander_new("Steam Bridge Maintenance (advanced)");
        gtk_expander_set_expanded(bridge_maintenance,FALSE);
        GtkWidget*bridge_maintenance_box=box(GTK_ORIENTATION_VERTICAL,7);
        margins(bridge_maintenance_box,7);
        pack(bridge_maintenance_box,netfx_plan,0);
        GtkWidget*bridge_upgrade_info=label(
            "If status reports UPDATE AVAILABLE, this installs the current GameWeld "
            "Bridge launcher with a backup. Close running games and restart Steam "
            "afterward. Existing per-game settings and the WeMod installation are preserved.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)bridge_upgrade_info,TRUE);
        pack(bridge_maintenance_box,bridge_upgrade_info,0);
        GtkWidget*bridge_upgrade=button("Steam Bridge: Update installed launcher","action");
        g_signal_connect_data(bridge_upgrade,"clicked",
            (GCallback)on_pc2_bridge_upgrade,NULL,NULL,0);
        pack(bridge_maintenance_box,bridge_upgrade,0);
        gtk_container_add(bridge_maintenance,bridge_maintenance_box);
        pack(bridge_card,bridge_maintenance,0);
        GtkWidget*legacy_bridge=gtk_expander_new(
            "Legacy Steam Bridge — optional compatibility fallback");
        gtk_expander_set_expanded(legacy_bridge,FALSE);
        GtkWidget*legacy_bridge_play=button(
            "Legacy: Play using existing Steam Bridge","action");
        g_signal_connect_data(legacy_bridge_play,"clicked",
            (GCallback)on_pc2_bridge_play,NULL,NULL,0);
        pack(bridge_card,legacy_bridge_play,0);
        gtk_container_add(legacy_bridge,bridge_card);
        pack(deckpage,legacy_bridge,0);

        /* Patch/restore is specialist maintenance, not another game-launch
         * method. It remains available but starts collapsed to avoid
         * overwhelming the verified game-first Steam Bridge workflow. */
        GtkWidget*advanced_wemod=gtk_expander_new("WeMod Enhancer — Patch / Restore (advanced)");
        gtk_expander_set_expanded(advanced_wemod,FALSE);
        GtkWidget*eh=box(GTK_ORIENTATION_VERTICAL,9);style(eh,"card");
        margins(eh,8);
        GtkWidget*info=label(
            "Select the correct existing Wand/WeMod client before modifying files. "
            "Patch and Restore operate on this client only and use its original-file backup. "
            "Close WeMod first; no Steam settings are changed.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)info,TRUE);
        pack(eh,info,0);
        pack(eh,label("EXISTING WAND / WEMOD INSTALLATIONS","section-kicker"),0);
        wand_detected_combo=gtk_combo_box_text_new();
        gtk_combo_box_text_append_text((GtkComboBoxText*)wand_detected_combo,
            "Searching Steam, Heroic, Lutris and Wine installations...");
        gtk_combo_box_set_active((GtkComboBox*)wand_detected_combo,0);
        g_signal_connect_data(wand_detected_combo,"changed",
            (GCallback)wand_detect_changed,NULL,NULL,0);
        pack(eh,wand_detected_combo,0);
        pc2_wemod_install_entry=gtk_entry_new();
        gtk_entry_set_placeholder_text((GtkEntry*)pc2_wemod_install_entry,
            "Wand/WeMod folder containing resources/app.asar");
        pack(eh,pc2_wemod_install_entry,0);
        G.wand_patcher_prefix_entry=gtk_entry_new();
        G.wand_patcher_install_entry=pc2_wemod_install_entry;
        GtkWidget*choose=button("WeMod Enhancer: Choose Folder","action");
        g_signal_connect_data(choose,"clicked",(GCallback)on_pc2_wemod_choose,NULL,NULL,0);
        pack(eh,choose,0);
        GtkWidget*controls=box(GTK_ORIENTATION_HORIZONTAL,7);
        GtkWidget*detect=button("WeMod Enhancer: Detect","action");
        GtkWidget*install=button("WeMod Enhancer: Install Helper","action");
        GtkWidget*patch=button("WeMod Enhancer: Patch WeMod","primary-action");
        GtkWidget*restore=button("WeMod Enhancer: Restore Original","action");
        g_signal_connect_data(detect,"clicked",(GCallback)on_pc2_wemod_detect,NULL,NULL,0);
        g_signal_connect_data(install,"clicked",(GCallback)on_pc2_wemod_install,NULL,NULL,0);
        g_signal_connect_data(patch,"clicked",(GCallback)on_pc2_wemod_patch,NULL,NULL,0);
        g_signal_connect_data(restore,"clicked",(GCallback)on_pc2_wemod_restore,NULL,NULL,0);
        pack(controls,detect,0);pack(controls,install,0);
        pack(controls,patch,0);pack(controls,restore,0);
        pack(eh,controls,0);
        GtkWidget*verify=button("Verify Wand Patch + Game (no launch)","action");
        g_signal_connect_data(verify,"clicked",
            (GCallback)on_pc2_wemod_verify_selected,NULL,NULL,0);
        pack(eh,verify,0);
        pc2_wemod_status=label(
            "Choose an existing Wand/WeMod installation before patching or restoring.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_wemod_status,TRUE);
        G.wand_patcher_status=pc2_wemod_status;
        pack(eh,pc2_wemod_status,0);
        pc2_wemod_helper_status=label(
            "WeMod Enhancer helper status: click Detect to inspect.",
            "muted");
        gtk_label_set_line_wrap((GtkLabel*)pc2_wemod_helper_status,TRUE);
        pack(eh,pc2_wemod_helper_status,0);
        gtk_container_add(advanced_wemod,eh);
        pack(right,advanced_wemod,0);
        wand_detect_start();
    }
    GtkWidget*legacy_clean=gtk_expander_new("Legacy Steam Hook Cleanup (advanced)");
    gtk_expander_set_expanded(legacy_clean,FALSE);
    GtkWidget*scard=box(GTK_ORIENTATION_VERTICAL,8);style(scard,"card");
    margins(scard,8);
    GtkWidget*sd=label("Only for older GameWeld installs that left wand-steam-wrap inside Steam Launch Options. Creates a backup before removing that obsolete launch hook; normal Steam Bridge setups do not require this.","muted");
    gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(scard,sd,0);
    GtkWidget*sbtn=button("Remove Legacy Steam Hooks","action");
    g_signal_connect_data(sbtn,"clicked",(GCallback)on_clean_legacy_hooks,NULL,NULL,0);
    pack(scard,sbtn,0);
    G.steam_cleanup_status=label("After cleanup, restart Steam once.","muted");
    gtk_label_set_line_wrap((GtkLabel*)G.steam_cleanup_status,TRUE);
    pack(scard,G.steam_cleanup_status,0);
    gtk_container_add(legacy_clean,scard);
    pack(right,legacy_clean,0);pack(right,card("Safety","Use native profiles, local trainers and Cheat Engine tables for single-player/offline games. Do not use them in anti-cheat protected or competitive multiplayer modes. No provider bypasses anti-cheat systems.",NULL),0);return outer;}
static GtkWidget *build_about(void){
    if(pc2_discovery_only()){
        GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);
        gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
        GtkWidget*page=box(GTK_ORIENTATION_VERTICAL,14);margins(page,24);
        gtk_container_add(outer,page);
        GtkWidget*head=box(GTK_ORIENTATION_VERTICAL,4);
        pack(head,label("ABOUT","page-kicker"),0);
        pack(head,label("GameWeld PC2","workspace-title"),0);
        GtkWidget*sub=label("A game-first Linux launcher and trainer manager. PC2 is a development build; PC1 remains the stable reference.","muted");
        gtk_label_set_line_wrap((GtkLabel*)sub,TRUE);pack(head,sub,0);pack(page,head,0);
        GtkWidget*intro=card("What GameWeld does",
            "Finds installed Steam, Steam shortcuts, Heroic and Lutris games in one Library. "
            "Provides game-specific trainer options without requiring users to edit Steam Launch Options.",NULL);
        pack(page,intro,0);
        GtkWidget*deck=card("DeckCheatz + WeMod",
            "The default provider-native setup check supports Steam, Heroic and Lutris "
            "without GameWeld Steam Bridge. Prepared release discovery is available "
            "for all game libraries; opt-in download-to-cache and in-game trainer "
            "attachment are separate steps. The previous Steam Bridge is an "
            "optional legacy fallback; it is not the default.",NULL);
        pack(page,deck,0);
        GtkWidget*tested=card("Validation",
            "Astrometica launched through Proton Experimental and a WeMod trainer worked "
            "in-game on one CachyOS test system. Other titles and machines must be tested "
            "separately. Managed DeckCheatz updates remain opt-in with rollback backups.",NULL);
        pack(page,tested,0);
        GtkWidget*design=card("Safety and licensing",
            "GameWeld does not bundle DeckCheatz's AGPL source or silently update game "
            "Wine prefixes. Trainer tools are intended for offline single-player use, "
            "not competitive or anti-cheat protected multiplayer.",NULL);
        pack(page,design,0);
        return outer;
    }
    GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,16);margins(p,24);gtk_container_add(outer,p);GtkWidget*hero=box(GTK_ORIENTATION_VERTICAL,6);gtk_widget_set_halign(hero,GTK_ALIGN_CENTER);GtkWidget*wm=asset_image("gameweld-brand-logo.png",540,180);if(wm){gtk_widget_set_halign(wm,GTK_ALIGN_CENTER);pack(hero,wm,0);}else{wm=label("GameWeld",NULL);gtk_widget_set_name(wm,"section-title");gtk_widget_set_halign(wm,GTK_ALIGN_CENTER);pack(hero,wm,0);}GtkWidget*v=label("0.7.0 PC1 • Game & Trainer Management","page-subtitle");gtk_widget_set_halign(v,GTK_ALIGN_CENTER);pack(hero,v,0);pack(p,hero,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*c1=box(GTK_ORIENTATION_VERTICAL,8);style(c1,"panel");pack(c1,label("WHAT IT DOES","section-kicker"),0);pack(c1,label("Unified Steam, Steam non-Steam shortcut, Heroic and Lutris game discovery\nLutris Test 4 keeps the Test 3 GE-Proton/UMU and classic Wine resolver, launches through Lutris, validates the exact live prefix/runtime owner, and hands assigned/custom local trainers into that same session with no generic fallback\nTrainer Library with conservative automatic matching\nDedicated Aurora / Cheat Evolution manager launch prefixes\nOverview Launch With hub for assigned trainers, Cheat Engine .CT tables, WeMod, Aurora, Cheat Evolution and custom trainer EXEs\nSteam non-Steam Cheat Evolution uses a field-validated restart-free live attach path: configured shortcuts keep Steam rungameid, while unconfigured shortcuts start only the selected resolved Windows target through Steam’s already-running runtime service with STEAM_COMPAT_LAUNCHER_SERVICE=proton injected for that launch. Steam stays open, shortcuts.vdf is never edited, exact App0/service provenance validation rejects unrelated Steam sessions, and the UI now reports restart-free handoff readiness explicitly\nSelected-game launch choices stay visible on Overview; each game can save or reset a one-click default while manager buttons retain explicit launch/close control\nSaved defaults drive the primary Play action; manager defaults now enforce game-first ordering before manager attachment\nSerialized Steam WeMod provider preparation with staging recovery and correct one-shot gate arming\nHeroic WeMod retains verified native .NET 4.8 + DWriteCore preparation, repairs stale GameWeld temporary Wand-runner residue before launch, refreshes the true Heroic game runtime from disk, follows exact launcher-to-game executable handoffs, then attaches Wand through the same live Heroic Wine prefix; readiness rejects Proton/UMU argv wrappers and requires both exact processes to remain live\nSteam shortcut local-trainer handoff now rejects Steam runtime wrappers as fake game PIDs and waits for the final mapped game window to remain stable before starting the trainer, preventing early attachment to black bootstrap surfaces\nLive manager attachment to compatible running game sessions\nCompatibility Engine v2 recipe inspection\nValidated live-session trainer handoff\nManaged Heroic FLiNG compatibility sessions\nPrivacy-scoped diagnostics and support bundles","muted"),0);GtkWidget*c2=box(GTK_ORIENTATION_VERTICAL,8);style(c2,"panel");pack(c2,label("DESIGN PRINCIPLES","section-kicker"),0);pack(c2,label("Game-first navigation\nOne clear primary action per context\nLauncher-native runtime ownership\nVisible readiness before launch\nAdvanced controls kept out of the main workflow","muted"),0);pack(cols,c1,1);pack(cols,c2,1);pack(p,cols,0);GtkWidget*f=label("Open source • MIT • Play more, your way.","muted");gtk_widget_set_halign(f,GTK_ALIGN_CENTER);pack(p,f,0);return outer;}

static void build_ui(void){
    int initial_w=1480,initial_h=900;recommended_window_geometry(&initial_w,&initial_h);
    if(pc2_discovery_only()){
        int physical_w=0,physical_h=0;
        pc2_primary_monitor_pixels(&physical_w,&physical_h);
        log_line("PC2 monitor sizing: windowed %dx%d logical; physical monitor %dx%d. Resize/maximize only by user choice.",
            initial_w,initial_h,physical_w,physical_h);
    }
    G.window=gtk_window_new(GTK_WINDOW_TOPLEVEL);gtk_window_set_title((GtkWindow*)G.window,"GameWeld");gtk_window_set_icon_name((GtkWindow*)G.window,"gameweld");gtk_window_set_default_size((GtkWindow*)G.window,initial_w,initial_h);gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);gtk_window_set_decorated((GtkWindow*)G.window,TRUE);g_signal_connect_data(G.window,"destroy",(GCallback)on_destroy,NULL,NULL,0);if(pc2_discovery_only())g_signal_connect_data(G.window,"configure-event",(GCallback)pc2_window_configure,NULL,NULL,0);
    GtkWidget*titlebar=box(GTK_ORIENTATION_HORIZONTAL,12);gtk_widget_set_name(titlebar,"app-titlebar");gtk_widget_set_size_request(titlebar,-1,54);gtk_widget_set_margin_start(titlebar,14);gtk_widget_set_margin_end(titlebar,10);
    GtkWidget*titlebrand=box(GTK_ORIENTATION_HORIZONTAL,10);gtk_widget_set_name(titlebrand,"title-brand");GtkWidget*wm=asset_image("gameweld-app-icon.png",36,36);if(!wm){wm=label("GW",NULL);gtk_widget_set_name(wm,"wandmark");}pack(titlebrand,wm,0);GtkWidget*bt=box(GTK_ORIENTATION_VERTICAL,0);GtkWidget*brand=label("GameWeld",NULL);gtk_widget_set_name(brand,"brand");pack(bt,brand,0);GtkWidget*ver=label(pc2_discovery_only()?"PC2 DISCOVERY TEST":"0.7.0",NULL);gtk_widget_set_name(ver,"brandver");pack(bt,ver,0);pack(titlebrand,bt,0);pack(titlebar,titlebrand,0);
    GtkWidget*grow=box(GTK_ORIENTATION_HORIZONTAL,0);pack(titlebar,grow,1);GtkWidget*searchwrap=box(GTK_ORIENTATION_HORIZONTAL,0);gtk_widget_set_name(searchwrap,"global-search-wrap");G.search_scope=gtk_combo_box_text_new();gtk_widget_set_name(G.search_scope,"global-search-scope");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"all","All games");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"steam","Steam");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"shortcut","Steam shortcuts");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"heroic","Heroic");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"lutris","Lutris");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"trainers","Trainers");gtk_combo_box_set_active_id((GtkComboBox*)G.search_scope,"all");gtk_widget_set_size_request(G.search_scope,126,36);g_signal_connect_data(G.search_scope,"changed",(GCallback)on_search_scope_changed,NULL,NULL,0);pack(searchwrap,G.search_scope,0);G.search=gtk_entry_new();gtk_widget_set_name(G.search,"global-search-entry");gtk_entry_set_placeholder_text((GtkEntry*)G.search,"Search all games…");gtk_entry_set_icon_from_icon_name((GtkEntry*)G.search,GTK_ENTRY_ICON_PRIMARY,"system-search-symbolic");gtk_widget_set_size_request(G.search,250,36);g_signal_connect_data(G.search,"changed",(GCallback)on_search,NULL,NULL,0);pack(searchwrap,G.search,0);pack(titlebar,searchwrap,0);GtkWidget*grow2=box(GTK_ORIENTATION_HORIZONTAL,0);pack(titlebar,grow2,1);G.top_steam_status=label("Detecting Steam, Heroic and Lutris…","muted");pack(titlebar,G.top_steam_status,0);pack(titlebar,gtk_separator_new(GTK_ORIENTATION_VERTICAL),0);GtkWidget*mi=button("—","windowctl");GtkWidget*ma=button("□","windowctl");GtkWidget*cl=button("×","windowctl");gtk_widget_set_name(cl,"closectl");g_signal_connect_data(mi,"clicked",(GCallback)on_minimize,NULL,NULL,0);g_signal_connect_data(ma,"clicked",(GCallback)on_maximize,NULL,NULL,0);g_signal_connect_data(cl,"clicked",(GCallback)on_close_btn,NULL,NULL,0);pack(titlebar,mi,0);pack(titlebar,ma,0);pack(titlebar,cl,0);gtk_window_set_titlebar((GtkWindow*)G.window,titlebar);
    GtkWidget*root=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(root,"root");gtk_container_add(G.window,root);GtkWidget*nav=box(GTK_ORIENTATION_HORIZONTAL,5);gtk_widget_set_name(nav,"navstrip");G.nav_home=make_nav("go-home-symbolic","Overview",(GCallback)nav_home);G.nav_library=make_nav("view-grid-symbolic","Library",(GCallback)nav_library);G.nav_trainers=make_nav("applications-engineering-symbolic","Trainer Library",(GCallback)nav_trainers);G.nav_setup=make_nav("emblem-system-symbolic","Compatibility",(GCallback)nav_setup);G.nav_diag=make_nav("help-browser-symbolic","Support",(GCallback)nav_diag);G.nav_settings=make_nav("preferences-system-symbolic","Settings",(GCallback)nav_settings);G.nav_about=make_nav("dialog-information-symbolic","About",(GCallback)nav_about);pack(nav,G.nav_home,0);pack(nav,G.nav_library,0);pack(nav,G.nav_trainers,0);pack(nav,gtk_separator_new(GTK_ORIENTATION_VERTICAL),0);pack(nav,G.nav_setup,0);pack(nav,G.nav_diag,0);GtkWidget*ng=box(GTK_ORIENTATION_HORIZONTAL,0);pack(nav,ng,1);GtkWidget*hint=label("Ctrl+F Search","command-hint");pack(nav,hint,0);pack(nav,G.nav_settings,0);pack(nav,G.nav_about,0);pack(root,nav,0);
    G.stack=gtk_stack_new();gtk_stack_set_hhomogeneous((GtkStack*)G.stack,FALSE);gtk_stack_set_vhomogeneous((GtkStack*)G.stack,FALSE);gtk_widget_set_hexpand(G.stack,TRUE);gtk_widget_set_vexpand(G.stack,TRUE);gtk_stack_add_named((GtkStack*)G.stack,build_home(),"home");gtk_stack_add_named((GtkStack*)G.stack,build_library(),"library");gtk_stack_add_named((GtkStack*)G.stack,build_trainer_library(),"trainers");gtk_stack_add_named((GtkStack*)G.stack,build_setup(),"setup");gtk_stack_add_named((GtkStack*)G.stack,build_diag(),"diag");gtk_stack_add_named((GtkStack*)G.stack,build_settings(),"settings");gtk_stack_add_named((GtkStack*)G.stack,build_about(),"about");pack(root,G.stack,1);
    {const char*start=getenv("WAND_NATIVE_START_PAGE");if(start&&!*start)start=NULL;if(start&&!strcmp(start,"library"))nav_activate(G.nav_library,"library");else if(start&&!strcmp(start,"trainers"))nav_activate(G.nav_trainers,"trainers");else if(start&&!strcmp(start,"setup"))nav_activate(G.nav_setup,"setup");else if(start&&!strcmp(start,"diag"))nav_activate(G.nav_diag,"diag");else if(start&&!strcmp(start,"settings"))nav_activate(G.nav_settings,"settings");else if(start&&!strcmp(start,"about"))nav_activate(G.nav_about,"about");else nav_activate(G.nav_home,"home");}
    if(G.game_count>0){
        int last=0;
        if(pc2_discovery_only()){
            for(int i=0;i<pc2_recents.count;i++){
                int saved=pc2_recent_index_of(pc2_recents.keys[i]);
                if(saved>=0){last=saved;break;}
            }
        }
        G.selected=last;
        gtk_list_box_select_row((GtkListBox*)G.game_list,(GtkListBoxRow*)G.game_rows[last]);
    }
    refresh_ui();
    if(pc2_discovery_only())pc2_recent_render();log_line("Refreshing installed game sources (Steam, Heroic, Lutris)...");log_line("Steam games detected: %d (%d installed manifest(s) + %d non-Steam shortcut(s))",G.steam_game_count,G.steam_manifest_game_count,G.steam_shortcut_count);log_line("Heroic games detected: %d",G.heroic_game_count);log_line("Lutris games detected: %d (resolved entries can launch; local trainer handoff uses verified live sessions in Test 4)",G.lutris_game_count);if(G.wand_installed)log_line("Steam trainer provider ready");if(G.wand_healthy)log_line("Steam Proton tool ready: GE-Proton-Wand-SHA256");log_line("GameWeld providers ready. Smart Prepare Wand is in Settings; automatic compatibility checks never start an unverified patcher.");if(G.legacy_wrapper_neutralized)log_line("Legacy Steam wand-steam-wrap neutralized; direct Steam Play will no longer auto-start Wand. Backup: %s",G.legacy_wrapper_backup);GtkCssProvider*prov=gtk_css_provider_new();gtk_css_provider_load_from_data(prov,CSS,-1,NULL);gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),prov,GTK_STYLE_PROVIDER_PRIORITY_USER);g_object_unref(prov);gtk_widget_show_all(G.window);{const char*sp=getenv("WAND_NATIVE_START_PAGE");if(sp&&*sp&&(!strcmp(sp,"library")||!strcmp(sp,"trainers")||!strcmp(sp,"setup")||!strcmp(sp,"diag")||!strcmp(sp,"settings")||!strcmp(sp,"about")))gtk_stack_set_visible_child_name((GtkStack*)G.stack,sp);}if(pc2_discovery_only())log_line("PC2 discovery-only: legacy action buttons are blocked and trainer/monitor background jobs are disabled.");else start_trainer_library_scan();if(pc2_discovery_only()){
        /* One startup correction only, for stale KWin development sizes. */
        g_timeout_add(180,pc2_startup_fit_window,NULL);
    }else{
        g_idle_add(force_mockup_geometry,NULL);
        g_timeout_add(180,force_mockup_geometry,NULL);
    }g_timeout_add(1000,heroic_session_status_tick,NULL);if(!pc2_discovery_only()){g_timeout_add(1500,trainer_monitor_initial_status,NULL);g_timeout_add(2800,trainer_dashboard_initial,NULL);g_timeout_add(45000,trainer_monitor_first_tick,NULL);g_timeout_add(1800000,trainer_monitor_tick,NULL);}
}


#ifdef GAMEWELD_PC2_GTK_ACTION_SMOKE
/* Native CI alone: exercise the same global action that crashed on CachyOS.
 * It can only stage to the isolated test HOME (which has no downloaded ZIP);
 * the expected failure is handled without changing game files. */
static gboolean pc2_gtk_smoke_prefix_stage(gpointer ignored){
    (void)ignored;
    fprintf(stderr, "PC2_GTK_SMOKE_PREFIX_STAGE_BEGIN\n");
    /* Simulate an explicitly chosen release in the empty test HOME. This
     * invokes the Python staging helper without any ZIP or game writes. */
    if(pc2_shared_wemod_choices){
        pc2_prepared_choice_count=1;
        snprintf(pc2_prepared_choices[0].tag,
                 sizeof pc2_prepared_choices[0].tag, "%s", "PfxVer10.1");
        snprintf(pc2_prepared_choices[0].name,
                 sizeof pc2_prepared_choices[0].name, "%s", "GE-Proton10.1.zip");
        snprintf(pc2_prepared_choices[0].url,
                 sizeof pc2_prepared_choices[0].url, "%s",
                 "https://github.com/DeckCheatz/BuiltPrefixes-dev/"
                 "releases/download/PfxVer10.1/GE-Proton10.1.zip");
        pc2_prepared_choices[0].bytes=1000000;
        gtk_combo_box_text_append_text((GtkComboBoxText*)pc2_shared_wemod_choices,
                                        "Synthetic DeckCheatz release (CI only)");
        gtk_combo_box_set_active((GtkComboBox*)pc2_shared_wemod_choices,0);
    }
    pc2_steam_bridge_action("prefix-stage");
    fprintf(stderr, "PC2_GTK_SMOKE_PREFIX_STAGE_DISPATCHED\n");
    return FALSE;
}
#endif

int main(int argc,char**argv){memset(&G,0,sizeof G);G.selected=-1;clear_desktop_activation_env();if(argc==2&&!strcmp(argv[1],"--pc2-provider-controls-status")){printf("PC2 provider controls: %s\n",pc2_provider_controls_allowed()?"enabled":"disabled");return 0;}if(argc==2&&!strcmp(argv[1],"--pc2-launch-gate-status")){printf("PC2 Steam game-only launch: %s\n",pc2_steam_launch_allowed()?"enabled":"disabled");return 0;}if(argc>1&&!strcmp(argv[1],"--cleanup-steam-hooks")){if(pc2_discovery_only()){fprintf(stderr,"PC2 discovery-only: Steam hook cleanup disabled.\\n");return 3;}char backup[2048]={0};int files=0;int n=cleanup_legacy_steam_hooks(backup,sizeof backup,&files);if(n>0){printf("Removed legacy wand-steam-wrap Launch Options from %d Steam config file(s).\n",files);if(backup[0])printf("Last backup: %s\n",backup);printf("Restart Steam once before testing direct Play.\n");return 0;}printf("No legacy wand-steam-wrap Launch Options found.\n");return 0;}G.legacy_wrapper_neutralized=pc2_discovery_only()?0:neutralize_legacy_wrapper();gtk_init(&argc,&argv);if(!start_backend()){fprintf(stderr,"Could not start GameWeld backend.\n");return 2;}char *e=NULL;if(!refresh_model(&e)){fprintf(stderr,"Backend status failed: %s\n",e?e:"unknown");free(e);}if(pc2_discovery_only())pc2_recent_load();build_ui();
#ifdef GAMEWELD_PC2_GTK_ACTION_SMOKE
g_idle_add(pc2_gtk_smoke_prefix_stage,NULL);
#endif
gtk_main();if(G.backend_pid>0){kill(G.backend_pid,SIGTERM);waitpid(G.backend_pid,NULL,WNOHANG);}return 0;}
