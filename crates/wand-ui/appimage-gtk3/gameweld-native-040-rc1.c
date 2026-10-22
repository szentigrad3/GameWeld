#define _GNU_SOURCE
#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <pthread.h>
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
typedef struct _GtkFileChooser GtkFileChooser;
typedef struct _GtkStyleContext GtkStyleContext;
typedef struct _GtkCssProvider GtkCssProvider;
typedef struct _GdkScreen GdkScreen;
typedef struct _GdkPixbuf GdkPixbuf;
typedef void (*GCallback)(void);
typedef unsigned long gulong;
typedef int gboolean;
typedef unsigned int guint;
typedef long gssize;
typedef void *gpointer;

extern void gtk_init(int *, char ***);
extern GtkWidget *gtk_window_new(int);
extern void gtk_window_set_title(GtkWindow *, const char *);
extern void gtk_window_set_default_size(GtkWindow *, int, int);
extern void gtk_window_resize(GtkWindow *, int, int);
extern void gtk_window_set_position(GtkWindow *, int);
extern void gtk_window_set_icon_name(GtkWindow *, const char *);
extern GtkWidget *gtk_box_new(int, int);
extern void gtk_box_pack_start(void *, GtkWidget *, gboolean, gboolean, guint);
extern void gtk_box_pack_end(void *, GtkWidget *, gboolean, gboolean, guint);
extern GtkWidget *gtk_label_new(const char *);
extern void gtk_label_set_text(GtkLabel *, const char *);
extern void gtk_label_set_markup(GtkLabel *, const char *);
extern void gtk_label_set_xalign(GtkLabel *, float);
extern void gtk_label_set_yalign(GtkLabel *, float);
extern void gtk_label_set_line_wrap(GtkLabel *, gboolean);
extern GtkWidget *gtk_button_new(void);
extern GtkWidget *gtk_button_new_with_label(const char *);
extern void gtk_button_set_label(GtkButton *, const char *);
extern GtkWidget *gtk_entry_new(void);
extern void gtk_entry_set_text(GtkEntry *, const char *);
extern void gtk_entry_set_placeholder_text(GtkEntry *, const char *);
extern void gtk_entry_set_icon_from_icon_name(GtkEntry *, int, const char *);
extern const char *gtk_entry_get_text(GtkEntry *);
extern GtkWidget *gtk_combo_box_text_new(void);
extern void gtk_combo_box_text_append(GtkComboBoxText *, const char *, const char *);
extern const char *gtk_combo_box_get_active_id(GtkComboBox *);
extern gboolean gtk_combo_box_set_active_id(GtkComboBox *, const char *);
extern GtkWidget *gtk_check_button_new_with_label(const char *);
extern gboolean gtk_toggle_button_get_active(GtkToggleButton *);
extern void gtk_toggle_button_set_active(GtkToggleButton *, gboolean);
extern GtkWidget *gtk_file_chooser_dialog_new(const char *, GtkWindow *, int, const char *, int, ...);
extern int gtk_dialog_run(GtkDialog *);
extern char *gtk_file_chooser_get_filename(GtkFileChooser *);
extern void g_free(void *);
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
extern GtkWidget *gtk_scrolled_window_new(void *, void *);
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
extern void gtk_style_context_add_provider_for_screen(GdkScreen *, void *, guint);
extern void gtk_main(void);
extern void gtk_main_quit(void);
extern gulong g_signal_connect_data(void *, const char *, GCallback, void *, void *, int);
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
    GtkWidget *local_trainer_entry;
    GtkWidget *local_trainer_status;
    GtkWidget *trainer_library_view;
    GtkWidget *trainer_library_selected;
    GtkWidget *trainer_library_pick;
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
".windowctl{background:transparent;color:#8793a2;border:0;box-shadow:none;padding:4px 9px;font-size:13px;border-radius:6px}"
".windowctl:hover{background:#171c24;color:#ffffff}#closectl:hover{background:#b23a4a;color:#ffffff}"
"list{background:transparent}row{background:#0f141b;color:#d9e1e9;border-radius:9px;margin:3px 0;border:1px solid #1d2530}row:hover{background:#151b24;border-color:#313b49}row:selected{background:#201a35;color:white;border-color:#5a4290}"
".library-row{padding:0}"
".game-row-title{font-size:12px;font-weight:900;color:#f5f7fa}.game-thumb{background:#090c11;border:1px solid #242d38;border-radius:7px;padding:2px}"
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
static GtkWidget *button(const char *s, const char *cls) {
    GtkWidget *w = gtk_button_new_with_label(s); if (cls) style(w, cls); return w;
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
    size_t j=0; while(*p && *p!='\"' && j+1<cap){ if(*p=='\\' && p[1]){p++; if(*p=='n')dst[j++]='\n'; else if(*p=='t')dst[j++]='\t'; else dst[j++]=*p++;} else dst[j++]=*p++; } dst[j]=0;
}
static const char *game_key(const Game *g){return (g&&g->key[0])?g->key:(g?g->appid:"");}
static int game_is_steam_shortcut(const Game *g){return g&&(!strcmp(g->provider,"steam-shortcut")||!strcmp(g->runner,"steam-shortcut"));}
static const char *steam_shortcut_preview_backend(const Game *g){if(!game_is_steam_shortcut(g))return "unassigned";if(g->shortcut_launch_supported)return "steam-shortcut-resolved";if(!strncmp(g->resolution_state,"native-or-script",16)||!strcmp(g->target_kind,"linux-appimage")||!strcmp(g->target_kind,"script"))return "steam-shortcut-native";return "steam-shortcut";}
static int game_is_steam(const Game *g){return !g||!g->provider[0]||!strcmp(g->provider,"steam")||game_is_steam_shortcut(g);}
static const char *game_ce_id(const Game *g){return game_is_steam(g)?g->appid:"0";}
static const char *heroic_provider_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-provider.py",a);else snprintf(p,sizeof p,"gameweld-heroic-provider.py");return p;}
static const char *heroic_launch_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-launch.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-launch.sh");return p;}
static const char *heroic_cheat_table_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-cheat-table.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-cheat-table.sh");return p;}
static const char *heroic_local_trainer_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-local-trainer.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-local-trainer.sh");return p;}
static const char *heroic_session_control_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-session-control.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-session-control.sh");return p;}
static const char *heroic_trainer_runtime_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-trainer-runtime.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-trainer-runtime.sh");return p;}
static const char *trainer_library_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-library.py",a);else snprintf(p,sizeof p,"gameweld-trainer-library.py");return p;}
static const char *support_bundle_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-support-bundle.py",a);else snprintf(p,sizeof p,"gameweld-support-bundle.py");return p;}
static const char *steam_shortcuts_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-steam-shortcuts.py",a);else snprintf(p,sizeof p,"gameweld-steam-shortcuts.py");return p;}

static void state_safe_id(const char *in,char *out,size_t cap){size_t j=0;if(!cap)return;for(size_t i=0;in&&in[i]&&j+1<cap;i++){unsigned char c=(unsigned char)in[i];out[j++]=(isalnum(c)||c=='_'||c=='.'||c=='-')?(char)c:'_';}out[j]=0;}
static int heroic_runtime_repair_active_ui(const Game*g){
    if(!g||game_is_steam(g))return 0;
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
    if(!g||game_is_steam(g))return 0;
    char rr[128],aa[256],path[2048],line[4096],state[64]={0};long gp=0,tp=0;
    state_safe_id(g->runner,rr,sizeof rr);state_safe_id(g->appid,aa,sizeof aa);
    const char*x=getenv("XDG_STATE_HOME"),*h=getenv("HOME");
    if(x&&*x)snprintf(path,sizeof path,"%s/gameweld/heroic-managed-session-%s-%s.state",x,rr,aa);
    else snprintf(path,sizeof path,"%s/.local/state/gameweld/heroic-managed-session-%s-%s.state",h?h:".",rr,aa);
    FILE*f=fopen(path,"r");if(!f)return 0;
    while(fgets(line,sizeof line,f)){
        line[strcspn(line,"\r\n")]=0;
        if(!strncmp(line,"state=",6))snprintf(state,sizeof state,"%s",line+6);
        else if(!strncmp(line,"game_pid=",9))gp=strtol(line+9,NULL,10);
        else if(!strncmp(line,"trainer_pid=",12))tp=strtol(line+12,NULL,10);
        else if(launch&&launch_cap&&!strncmp(line,"launch_path=",12))snprintf(launch,launch_cap,"%s",line+12);
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
    if(start>=MAX_GAMES)return start;char cmd[4096];snprintf(cmd,sizeof cmd,"python3 '%s' list 2>/dev/null",steam_shortcuts_tool());FILE*f=popen(cmd,"r");if(!f)return start;char line[16384];int count=start;
    while(count<MAX_GAMES&&fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(!line[0]||line[0]!='{')continue;Game*g=&G.games[count];memset(g,0,sizeof *g);json_string(line,"appid",g->appid,sizeof g->appid);json_string(line,"gameid",g->launch_id,sizeof g->launch_id);json_string(line,"key",g->key,sizeof g->key);json_string(line,"provider",g->provider,sizeof g->provider);json_string(line,"runner",g->runner,sizeof g->runner);json_string(line,"name",g->name,sizeof g->name);json_string(line,"install_dir",g->install_dir,sizeof g->install_dir);json_string(line,"executable",g->executable,sizeof g->executable);json_string(line,"prefix",g->prefix,sizeof g->prefix);json_string(line,"compatdata",g->compatdata,sizeof g->compatdata);json_string(line,"target_kind",g->target_kind,sizeof g->target_kind);json_string(line,"compat_tool",g->compat_tool,sizeof g->compat_tool);json_string(line,"compat_tool_path",g->compat_tool_path,sizeof g->compat_tool_path);json_string(line,"compat_tool_source",g->compat_tool_source,sizeof g->compat_tool_source);json_string(line,"resolution_state",g->resolution_state,sizeof g->resolution_state);json_string(line,"resolution_label",g->resolution_label,sizeof g->resolution_label);json_string(line,"launch_uri",g->launch_uri,sizeof g->launch_uri);g->shortcut_runtime_resolved=json_bool(line,"runtime_resolved",0);g->shortcut_prefix_found=json_bool(line,"prefix_found",0);g->shortcut_runtime_found=json_bool(line,"runtime_found",0);g->shortcut_launch_supported=json_bool(line,"launch_supported",0);if(g->appid[0]&&g->name[0]&&g->key[0])count++;}
    pclose(f);return count;
}

static int append_heroic_games(int start){
    if(start>=MAX_GAMES)return start;char cmd[4096];snprintf(cmd,sizeof cmd,"python3 '%s' list 2>/dev/null",heroic_provider_tool());FILE*f=popen(cmd,"r");if(!f)return start;char line[16384];int count=start;
    while(count<MAX_GAMES&&fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(!line[0]||line[0]!='{')continue;Game*g=&G.games[count];memset(g,0,sizeof *g);json_string(line,"appid",g->appid,sizeof g->appid);json_string(line,"key",g->key,sizeof g->key);json_string(line,"provider",g->provider,sizeof g->provider);json_string(line,"runner",g->runner,sizeof g->runner);json_string(line,"name",g->name,sizeof g->name);json_string(line,"install_dir",g->install_dir,sizeof g->install_dir);json_string(line,"executable",g->executable,sizeof g->executable);json_string(line,"prefix",g->prefix,sizeof g->prefix);json_string(line,"wine_type",g->wine_type,sizeof g->wine_type);json_string(line,"wine_bin",g->wine_bin,sizeof g->wine_bin);json_string(line,"wine_name",g->wine_name,sizeof g->wine_name);json_string(line,"art_path",g->art_path,sizeof g->art_path);json_string(line,"heroic_root",g->heroic_root,sizeof g->heroic_root);if(g->appid[0]&&g->name[0])count++;}
    pclose(f);return count;
}

static int refresh_model(char **err) {
    char *body=NULL; int code=0; if(http_request("GET","/api/status",NULL,&body,&code)<0){*err=strdup("Could not contact GameWeld backend.");return 0;}
    if(code!=200){*err=body;return 0;}
    G.wand_installed=json_bool(body,"wand_installed",0); G.wand_healthy=json_bool(body,"wand_healthy",0); G.base_compatible=json_bool(body,"base_compatible",0);
    json_string(body,"base_proton",G.base_proton,sizeof G.base_proton); json_string(body,"wand_tool",G.wand_tool,sizeof G.wand_tool); json_string(body,"verify_message",G.verify_message,sizeof G.verify_message);
    G.steam_manifest_game_count=parse_games(body); int steam_after_shortcuts=append_steam_shortcut_games(G.steam_manifest_game_count); G.steam_shortcut_count=steam_after_shortcuts-G.steam_manifest_game_count; G.steam_game_count=steam_after_shortcuts; G.game_count=append_heroic_games(G.steam_game_count); G.heroic_game_count=G.game_count-G.steam_game_count; if(G.selected>=G.game_count)G.selected=G.game_count?0:-1; free(body); return 1;
}

static const char *proton_gate_repair(void){
    static char p[2048]; const char *appdir=getenv("APPDIR");
    if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/wand-proton-launcher-repair.sh",appdir);
    else snprintf(p,sizeof p,"wand-proton-launcher-repair.sh");
    return p;
}
static void ensure_proton_gate(void){
    pid_t p=fork();
    if(p==0){execl(proton_gate_repair(),proton_gate_repair(),"--quiet",(char*)NULL);_exit(127);}
    if(p>0){int st=0;while(waitpid(p,&st,0)<0&&errno==EINTR){} }
}
static int arm_wand_launch(const char *appid){
    if(!appid||!*appid)return 0;
    const char *runtime=getenv("XDG_RUNTIME_DIR"); char dir[2048],path[2200];
    if(runtime&&*runtime)snprintf(dir,sizeof dir,"%s/gameweld",runtime);
    else snprintf(dir,sizeof dir,"/tmp/gameweld-%ld",(long)getuid());
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
    char cmd[4096];snprintf(cmd,sizeof cmd,"mkdir -p -- '%s'",dir);if(system(cmd)!=0)return 0;
    char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char *tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(trainer&&*trainer)fprintf(out,"%s\t%s\n",appid,trainer);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}

static int readable_file(const char *path);
static void set_label(GtkWidget *w,const char *s);
static void refresh_ui(void);

enum { TL_GAME=0, TL_CONF, TL_VERSION, TL_HEALTH, TL_PROFILE, TL_POLICY, TL_LAUNCH, TL_REASON, TL_TRAINER, TL_FOLDER, TL_PATH, TL_KEY, TL_STATE, TL_ARCH, TL_RUNTIME, TL_ELEVATION, TL_PCONF, TL_SIGNALS, TL_RECOMMENDATION, TL_COLS };

static GtkWidget *trainer_tree_new(void){
    GtkListStore *store=gtk_list_store_new(TL_COLS,g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"));
    GtkWidget *view=gtk_tree_view_new_with_model((GtkTreeModel*)store);
    g_object_unref(store);
    gtk_tree_view_set_headers_visible((GtkTreeView*)view,TRUE);
    GtkCellRenderer *r=gtk_cell_renderer_text_new();
    gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Status",r,"text",TL_STATE,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Game",r,"text",TL_GAME,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Confidence",r,"text",TL_CONF,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Version",r,"text",TL_VERSION,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Health",r,"text",TL_HEALTH,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Compatibility profile",r,"text",TL_PROFILE,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Launch policy",r,"text",TL_POLICY,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Next launch",r,"text",TL_LAUNCH,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Trainer",r,"text",TL_TRAINER,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Source folder",r,"text",TL_FOLDER,NULL);
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

static int trainer_pick_is_strong_target(void){
    return !strcmp(G.trainer_library_pick_state,"Matched")||!strcmp(G.trainer_library_pick_state,"Assigned")||!strcmp(G.trainer_library_pick_state,"Alternative");
}

static void update_trainer_library_actions(void){
    int have_pick=G.trainer_library_pick_path[0]&&readable_file(G.trainer_library_pick_path);
    int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);
    int selected_ok=G.selected>=0&&G.selected<G.game_count;
    int selected_matches=suggested>=0&&selected_ok&&!strcmp(game_key(&G.games[G.selected]),G.trainer_library_pick_key);
    int launchable=0;
    if(have_pick&&suggested>=0){
        char assigned[2048]={0};
        if(load_local_trainer(game_key(&G.games[suggested]),assigned,sizeof assigned)&&readable_file(assigned)&&!strcmp(assigned,G.trainer_library_pick_path)&&(!game_is_steam_shortcut(&G.games[suggested])||G.games[suggested].shortcut_launch_supported))launchable=1;
    }
    if(G.trainer_library_assign_suggested)gtk_widget_set_sensitive(G.trainer_library_assign_suggested,have_pick&&suggested>=0);
    if(G.trainer_library_select_suggested)gtk_widget_set_sensitive(G.trainer_library_select_suggested,suggested>=0);
    if(G.trainer_library_assign_selected){
        int safe=have_pick&&selected_ok;
        if(safe&&trainer_pick_is_strong_target()&&suggested>=0&&!selected_matches)safe=0;
        gtk_widget_set_sensitive(G.trainer_library_assign_selected,safe);
    }
    if(G.trainer_library_open_folder)gtk_widget_set_sensitive(G.trainer_library_open_folder,have_pick);
    if(G.trainer_library_launch_assigned)gtk_widget_set_sensitive(G.trainer_library_launch_assigned,launchable);
}

static int trainer_profile_policy_label_for_path(const char*path,char*out,size_t cap){if(!out||!cap)return 0;out[0]=0;if(!path||!*path)return 0;int fd[2];if(pipe(fd)!=0)return 0;pid_t p=fork();if(p<0){close(fd[0]);close(fd[1]);return 0;}if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}execlp("python3","python3",trainer_library_tool(),"profile-policy",path,(char*)NULL);_exit(127);}close(fd[1]);char buf[1024]={0};ssize_t n=read(fd[0],buf,sizeof buf-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(n<=0||!WIFEXITED(st)||WEXITSTATUS(st)!=0)return 0;buf[n]=0;buf[strcspn(buf,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(buf,"\t",&save);char*mode=strtok_r(NULL,"\t",&save);char*label=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"PROFILE_POLICY")||!mode)return 0;snprintf(out,cap,"%s",(label&&*label)?label:mode);return 1;}

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
    int low=(pconf&&(!strcmp(pconf,"Low")))||(profile&&(!strcmp(profile,"Unknown Windows trainer")||!strcmp(profile,"Possible FLiNG trainer")));
    if(!strcmp(st,"Missing")||!strcmp(he,"Missing")){
        snprintf(msg,sizeof msg,"Attention: assigned trainer file is missing.\nWhy: %s\nRecommended: rescan the suggested game first so GameWeld can recover an exact moved filename. If it cannot be recovered, use Remove Missing Mappings or Clear Selected Game Assignment; trainer EXE files are never deleted.",(reason&&*reason)?reason:"The stored assignment path is no longer readable.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"rescan-suggested");button="Rescan Suggested Game";enable=1;}else button="Use Remove Missing Mappings";
    }else if(!strcmp(st,"Ambiguous")){
        snprintf(msg,sizeof msg,"Attention: multiple plausible trainers matched this game.\nWhy: %s\nRecommended: inspect the selected candidate, then explicitly assign it to the suggested game only if it is the intended trainer. GameWeld will not choose an ambiguous candidate automatically.",(reason&&*reason)?reason:"The scan found more than one strong candidate.");
        if(suggested>=0){snprintf(G.trainer_library_action_code,sizeof G.trainer_library_action_code,"assign-suggested");button="Assign This Candidate";enable=1;}
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
    set_label(G.trainer_library_guidance,msg);gtk_button_set_label((GtkButton*)G.trainer_library_recommended_action,button);gtk_widget_set_sensitive(G.trainer_library_recommended_action,enable);
}

static void trainer_pick_changed(GtkTreeSelection *sel,void*d){
    (void)d;GtkTreeModel*m=NULL;GtkTreeIter it;
    if(!gtk_tree_selection_get_selected(sel,&m,&it))return;
    char *game=NULL,*conf=NULL,*version=NULL,*health=NULL,*profile=NULL,*reason=NULL,*path=NULL,*key=NULL,*state=NULL,*folder=NULL,*arch=NULL,*runtime=NULL,*elevation=NULL,*pconf=NULL,*signals=NULL,*recommendation=NULL;
    gtk_tree_model_get(m,&it,TL_GAME,&game,TL_CONF,&conf,TL_VERSION,&version,TL_HEALTH,&health,TL_PROFILE,&profile,TL_REASON,&reason,TL_PATH,&path,TL_KEY,&key,TL_STATE,&state,TL_FOLDER,&folder,TL_ARCH,&arch,TL_RUNTIME,&runtime,TL_ELEVATION,&elevation,TL_PCONF,&pconf,TL_SIGNALS,&signals,TL_RECOMMENDATION,&recommendation,-1);
    if(path&&*path){
        snprintf(G.trainer_library_pick_path,sizeof G.trainer_library_pick_path,"%s",path);
        snprintf(G.trainer_library_pick_game,sizeof G.trainer_library_pick_game,"%s",game?game:"");
        snprintf(G.trainer_library_pick_key,sizeof G.trainer_library_pick_key,"%s",key?key:"");
        snprintf(G.trainer_library_pick_state,sizeof G.trainer_library_pick_state,"%s",state?state:"");
        if(G.trainer_library_pick){
            char msg[6144];int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);
            snprintf(msg,sizeof msg,"Selected trainer: %s\nStatus: %s • Health: %s • Suggested game: %s%s%s%s%s\nCompatibility profile: %s%s%s\nArchitecture: %s • Runtime: %s\nElevation: %s",path,(state&&*state)?state:"UNMATCHED",(health&&*health)?health:"—",(game&&*game)?game:"unmatched",(conf&&*conf)?" • confidence ":"",(conf&&*conf)?conf:"",(version&&*version)?" • version ":"",(version&&*version)?version:"",(profile&&*profile)?profile:"Unknown",(pconf&&*pconf&&strcmp(pconf,"—"))?" • detection confidence ":"",(pconf&&*pconf&&strcmp(pconf,"—"))?pconf:"",(arch&&*arch)?arch:"Unknown",(runtime&&*runtime)?runtime:"Unknown",(elevation&&*elevation)?elevation:"Not declared");
            if(signals&&*signals&&strcmp(signals,"—")){strncat(msg,"\nSignals: ",sizeof msg-strlen(msg)-1);strncat(msg,signals,sizeof msg-strlen(msg)-1);}
            if(recommendation&&*recommendation&&strcmp(recommendation,"—")){strncat(msg,"\nSuggested GameWeld profile: ",sizeof msg-strlen(msg)-1);strncat(msg,recommendation,sizeof msg-strlen(msg)-1);}
            char policy_label[512];if(trainer_profile_policy_label_for_path(path,policy_label,sizeof policy_label)){strncat(msg,"\nLaunch policy: ",sizeof msg-strlen(msg)-1);strncat(msg,policy_label,sizeof msg-strlen(msg)-1);}
            const char*preview_backend="unassigned";if(suggested>=0)preview_backend=game_is_steam_shortcut(&G.games[suggested])?steam_shortcut_preview_backend(&G.games[suggested]):(game_is_steam(&G.games[suggested])?"steam":"heroic");TrainerLaunchPreview preview={0};if(trainer_launch_preview_for_path(path,preview_backend,&preview)){strncat(msg,"\nEffective next launch: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.label,sizeof msg-strlen(msg)-1);if(preview.runtime[0]&&strcmp(preview.runtime,"—")){strncat(msg,"\nRuntime: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.runtime,sizeof msg-strlen(msg)-1);}if(preview.elevation[0]&&strcmp(preview.elevation,"—")){strncat(msg,"\nLaunch elevation: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.elevation,sizeof msg-strlen(msg)-1);}if(preview.reason[0]){strncat(msg,"\nLaunch-plan reason: ",sizeof msg-strlen(msg)-1);strncat(msg,preview.reason,sizeof msg-strlen(msg)-1);}}
            char current_assignment[2048]={0};int ready_launch=suggested>=0&&load_local_trainer(game_key(&G.games[suggested]),current_assignment,sizeof current_assignment)&&readable_file(current_assignment)&&!strcmp(current_assignment,path);strncat(msg,ready_launch?"\nTrainer Library launch: Ready — this is the trainer currently assigned to the suggested game.":"\nTrainer Library launch: Assign this trainer to its game before launching it directly from Trainer Library.",sizeof msg-strlen(msg)-1);
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
    if(!view||!path||!*path)return;GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)view);if(!m)return;GtkListStore*st=(GtkListStore*)m;GtkTreeIter it;const char*base=strrchr(path,'/');base=base?base+1:path;char conf[64];if(score&&atoi(score)>0)snprintf(conf,sizeof conf,"%s%%",score);else snprintf(conf,sizeof conf,"—");const char *shown_state=!strcmp(state?state:"","ASSIGNED")?"Assigned":(!strcmp(state?state:"","MATCH")?"Matched":(!strcmp(state?state:"","ALTERNATE")?"Alternative":(!strcmp(state?state:"","AMBIG")?"Ambiguous":(!strcmp(state?state:"","MISSING")?"Missing":"Unmatched"))));char prof[512];snprintf(prof,sizeof prof,"%s%s%s%s%s",(profile&&*profile)?profile:"Unknown",(pconf&&*pconf&&strcmp(pconf,"—"))?" (":"",(pconf&&*pconf&&strcmp(pconf,"—"))?pconf:"",(pconf&&*pconf&&strcmp(pconf,"—"))?")":"",(arch&&*arch&&strcmp(arch,"—"))?"":"");if(arch&&*arch&&strcmp(arch,"—")){strncat(prof," • ",sizeof prof-strlen(prof)-1);strncat(prof,arch,sizeof prof-strlen(prof)-1);}gtk_list_store_append(st,&it);gtk_list_store_set(st,&it,TL_GAME,(game&&*game)?game:"—",TL_CONF,conf,TL_VERSION,(version&&*version)?version:"—",TL_HEALTH,(health&&*health)?health:"—",TL_PROFILE,prof,TL_POLICY,(policy&&*policy)?policy:"Automatic",TL_LAUNCH,(launch&&*launch)?launch:"No launch target assigned",TL_REASON,reason?reason:"",TL_TRAINER,base,TL_FOLDER,source?source:"",TL_PATH,path,TL_KEY,key?key:"",TL_STATE,shown_state,TL_ARCH,arch?arch:"",TL_RUNTIME,runtime?runtime:"",TL_ELEVATION,elevation?elevation:"",TL_PCONF,pconf?pconf:"",TL_SIGNALS,signals?signals:"",TL_RECOMMENDATION,recommendation?recommendation:"",-1);
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
    char backup[4096];time_t now=time(NULL);snprintf(backup,sizeof backup,"%s.wand-native-backup-%ld",path,(long)now);
    FILE*src=fopen(path,"rb"),*dst=fopen(backup,"wb");if(!src||!dst){if(src)fclose(src);if(dst)fclose(dst);for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
    char buf[16384];size_t r;while((r=fread(buf,1,sizeof buf,src))>0)fwrite(buf,1,r,dst);fclose(src);fclose(dst);
    char tmp[4096];snprintf(tmp,sizeof tmp,"%s.wand-native-tmp-%ld",path,(long)getpid());FILE*out=fopen(tmp,"w");if(!out){for(size_t i=0;i<count;i++)free(lines[i]);free(lines);return 0;}
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
    char user[4096];snprintf(user,sizeof user,"%s/userdata",canon);struct stat st;if(stat(user,&st)!=0||!S_ISDIR(st.st_mode))return;
    if(steam_root_seen(roots,*count,canon))return;snprintf(roots[*count],4096,"%s",canon);(*count)++;
}
static void discover_running_steam_roots(char roots[][4096],int *count,int max){
    DIR*d=opendir("/proc");if(!d)return;struct dirent*de;
    while((de=readdir(d))){if(!isdigit((unsigned char)de->d_name[0]))continue;char cp[256];snprintf(cp,sizeof cp,"/proc/%s/cmdline",de->d_name);FILE*f=fopen(cp,"rb");if(!f)continue;char buf[16384];size_t n=fread(buf,1,sizeof buf-1,f);fclose(f);if(!n)continue;buf[n]=0;
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
        while((de=readdir(d))){if(de->d_name[0]=='.')continue;char p1[4096];snprintf(p1,sizeof p1,"%s/%s",base,de->d_name);add_steam_root(roots,count,max,p1);DIR*d2=opendir(p1);if(!d2)continue;struct dirent*de2;while((de2=readdir(d2))){if(de2->d_name[0]=='.')continue;char p2[4096];snprintf(p2,sizeof p2,"%s/%s",p1,de2->d_name);add_steam_root(roots,count,max,p2);}closedir(d2);
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
    for(int ri=0;ri<root_count;ri++){char userroot[4096];snprintf(userroot,sizeof userroot,"%s/userdata",roots[ri]);DIR*d=opendir(userroot);if(!d)continue;
        struct dirent*de;while((de=readdir(d))){if(de->d_name[0]=='.')continue;int numeric=1;for(const char*q=de->d_name;*q;q++)if(!isdigit((unsigned char)*q)){numeric=0;break;}if(!numeric)continue;
            char cfg[4096];snprintf(cfg,sizeof cfg,"%s/%s/config/localconfig.vdf",userroot,de->d_name);struct stat st;if(stat(cfg,&st)!=0||!S_ISREG(st.st_mode))continue;
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
    if(out&&cap)out[0]=0;char p[2048];cheat_engine_installer_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;char line[4096];if(!fgets(line,sizeof line,f)){fclose(f);return 0;}fclose(f);line[strcspn(line,"\r\n")]=0;if(!*line)return 0;snprintf(out,cap,"%s",line);return 1;
}
static int save_cheat_engine_installer(const char *exe){
    char path[2048],dir[2048];cheat_engine_installer_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;char cmd[4096];snprintf(cmd,sizeof cmd,"mkdir -p -- '%s'",dir);if(system(cmd)!=0)return 0;
    if(!exe||!*exe){unlink(path);return 1;}FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%s\n",exe);fclose(f);return 1;
}
static int readable_file(const char *path);
static const char *cheat_engine_manager(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-cheat-engine-manager.sh",appdir);else snprintf(p,sizeof p,"gameweld-cheat-engine-manager.sh");return p;}
static int detect_managed_cheat_engine(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char cmd[4096];snprintf(cmd,sizeof cmd,"'%s' detect %s 2>/dev/null",cheat_engine_manager(),appid);FILE*f=popen(cmd,"r");if(!f)return 0;char line[4096];int ok=0;if(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(*line&&readable_file(line)){snprintf(out,cap,"%s",line);ok=1;}}pclose(f);return ok;
}
static int detect_managed_windows_ce(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char cmd[4096];snprintf(cmd,sizeof cmd,"'%s' windows-detect %s 2>/dev/null",cheat_engine_manager(),appid);FILE*f=popen(cmd,"r");if(!f)return 0;char line[4096];int ok=0;if(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;if(*line&&readable_file(line)){snprintf(out,cap,"%s",line);ok=1;}}pclose(f);return ok;
}
static void spawn_managed_ce_install(const char *appid,const char *installer){pid_t p=fork();if(p==0){execl(cheat_engine_manager(),cheat_engine_manager(),"install",appid,installer,(char*)NULL);_exit(127);}}
static void spawn_managed_ce_download_install(const char *appid){pid_t p=fork();if(p==0){execl(cheat_engine_manager(),cheat_engine_manager(),"download-install",appid,(char*)NULL);_exit(127);}}
static int load_cheat_table(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char p[2048];cheat_tables_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char *tab=strchr(line,'\t');if(!tab)continue;*tab=0;char *v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,appid)&&*v){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_cheat_table(const char *appid,const char *table){
    if(!appid||!*appid)return 0;char path[2048],dir[2048];cheat_tables_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;
    char cmd[4096];snprintf(cmd,sizeof cmd,"mkdir -p -- '%s'",dir);if(system(cmd)!=0)return 0;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char *tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(table&&*table)fprintf(out,"%s\t%s\n",appid,table);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}
static int load_cheat_engine(char *out,size_t cap){
    if(out&&cap)out[0]=0;char p[2048];cheat_engine_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;char line[4096];if(!fgets(line,sizeof line,f)){fclose(f);return 0;}fclose(f);line[strcspn(line,"\r\n")]=0;if(!*line)return 0;snprintf(out,cap,"%s",line);return 1;
}
static int save_cheat_engine(const char *exe){
    char path[2048],dir[2048];cheat_engine_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;char cmd[4096];snprintf(cmd,sizeof cmd,"mkdir -p -- '%s'",dir);if(system(cmd)!=0)return 0;
    if(!exe||!*exe){unlink(path);return 1;}FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%s\n",exe);fclose(f);return 1;
}
static const char *cheat_table_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-cheat-table.sh",appdir);else snprintf(p,sizeof p,"gameweld-cheat-table.sh");return p;}
static void spawn_cheat_table(const char *appid,const char *ce,const char *table){pid_t p=fork();if(p==0){execl(cheat_table_launcher(),cheat_table_launcher(),appid,ce,table,(char*)NULL);_exit(127);}}

static void native_profiles_path(char *out,size_t cap){
    const char *xdg=getenv("XDG_CONFIG_HOME"),*home=getenv("HOME");
    if(xdg&&*xdg)snprintf(out,cap,"%s/gameweld/native-profiles.tsv",xdg);
    else snprintf(out,cap,"%s/.config/gameweld/native-profiles.tsv",home?home:".");
}
static const char *available_native_profile(const char *appid){return appid&&!strcmp(appid,"2713000")?"resonance-paul44-v1.1":NULL;}
static int load_native_profile(const char *appid,char *out,size_t cap){
    if(out&&cap)out[0]=0;if(!appid||!*appid)return 0;char p[2048];native_profiles_path(p,sizeof p);FILE*f=fopen(p,"r");if(!f)return 0;
    char line[4096];int ok=0;while(fgets(line,sizeof line,f)){char*tab=strchr(line,'\t');if(!tab)continue;*tab=0;char*v=tab+1;v[strcspn(v,"\r\n")]=0;if(!strcmp(line,appid)&&*v){snprintf(out,cap,"%s",v);ok=1;break;}}fclose(f);return ok;
}
static int save_native_profile(const char *appid,const char *profile){
    if(!appid||!*appid)return 0;char path[2048],dir[2048];native_profiles_path(path,sizeof path);snprintf(dir,sizeof dir,"%s",path);char*slash=strrchr(dir,'/');if(slash)*slash=0;char cmd[4096];snprintf(cmd,sizeof cmd,"mkdir -p -- '%s'",dir);if(system(cmd)!=0)return 0;char tmp[2100];snprintf(tmp,sizeof tmp,"%s.tmp",path);FILE*in=fopen(path,"r"),*out=fopen(tmp,"w");if(!out){if(in)fclose(in);return 0;}char line[4096];
    if(in){while(fgets(line,sizeof line,in)){char copy[4096];snprintf(copy,sizeof copy,"%s",line);char*tab=strchr(copy,'\t');if(tab){*tab=0;if(!strcmp(copy,appid))continue;}fputs(line,out);}fclose(in);}if(profile&&*profile)fprintf(out,"%s\t%s\n",appid,profile);fclose(out);if(rename(tmp,path)!=0){unlink(tmp);return 0;}return 1;
}
static const char *native_profile_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-native-profile.sh",appdir);else snprintf(p,sizeof p,"gameweld-native-profile.sh");return p;}
static void spawn_native_profile(const char *appid,const char *profile){pid_t p=fork();if(p==0){execl(native_profile_launcher(),native_profile_launcher(),appid,profile,(char*)NULL);_exit(127);}}

static void refresh_ui(void);
static gboolean heroic_session_status_tick(void *unused);

static gboolean job_done(void *vp);

typedef enum { JOB_SETUP, JOB_VERIFY, JOB_HEALTH, JOB_PLAY, JOB_REFRESH } JobType;
typedef struct { JobType type; char appid[32]; char *message; int success; } Job;

static void *job_worker(void *vp) {
    Job *j=vp; char *body=NULL; int code=0; char path[256],data[128];
    if(j->type==JOB_SETUP){ http_request("POST","/api/install","{}",&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_VERIFY){ http_request("GET","/api/verify",NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_HEALTH){ snprintf(path,sizeof path,"/api/health?appid=%s",j->appid); http_request("GET",path,NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_PLAY){ snprintf(data,sizeof data,"{\"appid\":\"%s\"}",j->appid); http_request("POST","/api/set-game",data,&body,&code); j->success=(code>=200&&code<300); if(j->success){ ensure_proton_gate(); if(!arm_wand_launch(j->appid)){ j->success=0; free(body); body=strdup("Could not arm the one-shot Wand launch marker."); } else { pid_t p=fork(); if(p==0){clear_desktop_activation_env(); execlp("steam","steam","-applaunch",j->appid,(char*)NULL);_exit(127);} } } }
    else { char *e=NULL; j->success=refresh_model(&e); body=e; }
    if(body){ char msg[1800]={0}; json_string(body,"message",msg,sizeof msg); if(!msg[0])json_string(body,"error",msg,sizeof msg); if(!msg[0])json_string(body,"data",msg,sizeof msg); if(!msg[0])snprintf(msg,sizeof msg,"%s",body); j->message=strdup(msg); free(body);} else j->message=strdup(j->success?"Completed successfully.":"Operation failed.");
    g_idle_add(job_done,j); return NULL;
}
static void start_job(JobType type,const char *appid,const char *doing) {
    Job *j=calloc(1,sizeof *j); j->type=type; if(appid)snprintf(j->appid,sizeof j->appid,"%s",appid);
    log_line("%s",doing); if(G.play_button)gtk_widget_set_sensitive(G.play_button,FALSE); pthread_t t; pthread_create(&t,NULL,job_worker,j); pthread_detach(t);
}

static gboolean job_done(void *vp) {
    Job *j=vp; log_line("%s: %s",j->success?"OK":"FAILED",j->message?j->message:""); char *e=NULL; refresh_model(&e); free(e); refresh_ui();
    if(G.play_button)gtk_widget_set_sensitive(G.play_button,TRUE);
    if(j->type==JOB_HEALTH && G.health_detail)gtk_label_set_text((GtkLabel*)G.health_detail,j->message?j->message:"");
    if((j->type==JOB_SETUP||j->type==JOB_VERIFY) && G.setup_detail)gtk_label_set_text((GtkLabel*)G.setup_detail,j->message?j->message:"");
    free(j->message); free(j); return FALSE;
}


static int readable_file(const char *path){struct stat st;return path&&*path&&stat(path,&st)==0&&S_ISREG(st.st_mode)&&access(path,R_OK)==0;}

typedef struct { char manifest[2048]; int matched,assigned,ambiguous,missing,health_issues,candidates,roots,failed,merge_report,selected_only; } TrainerScanJob;
static int trainer_scan_active=0;

static void tsv_field(FILE *f,const char *s){for(const unsigned char*p=(const unsigned char*)(s?s:"");*p;p++)fputc((*p=='\t'||*p=='\r'||*p=='\n')?' ':*p,f);}
static gboolean trainer_scan_done(void *vp){TrainerScanJob*j=vp;trainer_scan_active=0;if(j->failed)log_line("Trainer Library scan failed; existing trainer assignments were left unchanged.");else if(j->selected_only)log_line("Selected-game trainer rescan complete: %d trainer EXE(s) discovered • %d healthy/recovered assignment(s) • %d newly assigned • %d ambiguous • %d missing assignment(s) • %d not found.",j->candidates,j->assigned,j->matched,j->ambiguous,j->health_issues,j->missing);else log_line("Trainer Library scan complete: %d trainer EXE(s) discovered • %d healthy/recovered assignment(s) • %d auto-matched • %d ambiguous • %d missing assignment(s) • %d unassigned games not found.",j->candidates,j->assigned,j->matched,j->ambiguous,j->health_issues,j->missing);refresh_ui();refresh_trainer_library_view();free(j);return FALSE;}
static void *trainer_scan_worker(void *vp){
    TrainerScanJob*j=vp;int fd[2];if(pipe(fd)!=0){j->failed=1;unlink(j->manifest);g_idle_add(trainer_scan_done,j);return NULL;}pid_t p=fork();
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}if(j->merge_report)execlp("python3","python3",trainer_library_tool(),"auto-match","--manifest",j->manifest,"--merge-report",(char*)NULL);else execlp("python3","python3",trainer_library_tool(),"auto-match","--manifest",j->manifest,(char*)NULL);_exit(127);}
    close(fd[1]);FILE*f=fdopen(fd[0],"r");char line[8192];if(!f){close(fd[0]);j->failed=1;}else while(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;char*kind=strtok(line,"\t");char*key=strtok(NULL,"\t");char*score=strtok(NULL,"\t");char*path=strtok(NULL,"\t");if(!kind)continue;if(!strcmp(kind,"STATS")){j->candidates=key?atoi(key):0;j->roots=score?atoi(score):0;continue;}if(!key)continue;if(!strcmp(kind,"ASSIGNED")){j->assigned++;}else if(!strcmp(kind,"MATCH")&&path&&readable_file(path)){char cur[2048]={0};if(load_local_trainer(key,cur,sizeof cur)&&readable_file(cur)){j->assigned++;/* Existing assignment wins unless the user explicitly chose Prefer newest in the helper. */}else if(save_local_trainer(key,path))j->matched++;else j->failed=1;}else if(!strcmp(kind,"AMBIG"))j->ambiguous++;else if(!strcmp(kind,"MISSING"))j->health_issues++;else if(!strcmp(kind,"NONE"))j->missing++;}
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
    while((e=readdir(d))){if(e->d_name[0]=='.'||!image_name(e->d_name))continue;if(require_prefix&&appid&&strncmp(e->d_name,appid,alen)!=0)continue;snprintf(p,sizeof p,"%s/%s",dir,e->d_name);long long sc=art_score(p,cover);if(sc>*best_score){*best_score=sc;snprintf(best,cap,"%s",p);}}
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
        snprintf(p,sizeof p,"%s/%s",roots[i],g->appid);
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
    if(g&&strcmp(G.artwork_appid,game_key(g))){snprintf(G.artwork_appid,sizeof G.artwork_appid,"%s",game_key(g));if(hh||hc)log_line("Artwork loaded for %s%s%s",g->name,hh?" • hero":"",hc?" • cover":"");else log_line("No cached artwork found yet for %s (%s %s).",g->name,game_is_steam(g)?"Steam":"Heroic",g->appid);}
}

static gboolean force_mockup_geometry(void *unused){
    (void)unused;
    /* KWin can restore an old development window size after GTK's default-size
     * hint. Clamp the preferred desktop geometry to the active screen instead
     * of forcing a window larger than a 1080p/small test display. */
    GdkScreen*screen=gdk_screen_get_default();
    int sw=screen?gdk_screen_get_width(screen):1480;
    int sh=screen?gdk_screen_get_height(screen):900;
    int ww=sw>1520?1480:sw-40; if(ww<1080)ww=1080;
    int wh=sh>960?900:sh-60; if(wh<680)wh=680;
    gtk_window_resize((GtkWindow*)G.window,ww,wh);
    gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    return FALSE;
}
static void spawn_detached(const char *a,const char *b,const char *c){pid_t p=fork();if(p==0){clear_desktop_activation_env();if(c)execlp(a,a,b,c,(char*)NULL);else if(b)execlp(a,a,b,(char*)NULL);else execlp(a,a,(char*)NULL);_exit(127);}}
static void set_label(GtkWidget *w,const char *s){ if(w)gtk_label_set_text((GtkLabel*)w,s?s:""); }
static void selected_changed(GtkListBox *list,GtkListBoxRow *row,void *data){(void)list;(void)data;if(!row)return; int idx=gtk_list_box_row_get_index(row); if(idx>=0&&idx<G.game_count){G.selected=idx;refresh_ui();}}

static void refresh_ui(void) {
    char b[4096]; Game *g=(G.selected>=0&&G.selected<G.game_count)?&G.games[G.selected]:NULL;
    long managed_game_pid=0,managed_trainer_pid=0;char managed_launch[128]={0};
    int managed_state=g?heroic_managed_session_state(g,&managed_game_pid,&managed_trainer_pid,managed_launch,sizeof managed_launch):0;
    if(G.quick_store)gtk_widget_set_visible(G.quick_store,g&&game_is_steam(g)&&!game_is_steam_shortcut(g));
    if(G.top_steam_status){
        snprintf(b,sizeof b,"<span foreground=\"#f4f6fa\" weight=\"bold\">Game Sources</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Steam %d • Heroic %d</span>\n<span foreground=\"#aeb9c7\">%d installed manifests • %d non-Steam shortcuts</span>",G.steam_game_count,G.heroic_game_count,G.steam_manifest_game_count,G.steam_shortcut_count);
        gtk_label_set_markup((GtkLabel*)G.top_steam_status,b);
    }
    if(g){
        const char *src=game_is_steam(g)?"Steam":"Heroic";
        refresh_artwork(g);set_label(G.hero_name,g->name);
        if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"Steam • Non-Steam Shortcut • App ID: %s",g->appid);
        else if(game_is_steam(g))snprintf(b,sizeof b,"Steam • App ID: %s",g->appid);
        else snprintf(b,sizeof b,"Heroic • %s • ID: %s",g->runner,g->appid);
        set_label(G.hero_meta,b);
        if(G.library_detail_name)set_label(G.library_detail_name,g->name);
        if(G.library_detail_meta)set_label(G.library_detail_meta,b);
        if(G.library_detail_status){if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"%s\n%s",g->shortcut_launch_supported?"Live Steam shortcut handoff ready":"Shortcut discovered; runtime handoff still needs resolution",g->resolution_label[0]?g->resolution_label:"Resolution pending");else if(game_is_steam(g))snprintf(b,sizeof b,"Steam launch path ready • trainer handoff uses the live game-selected Proton session");else snprintf(b,sizeof b,"Heroic launch path ready • %s runner • %s",g->runner,g->wine_name[0]?g->wine_name:"launcher-managed runtime");set_label(G.library_detail_status,b);}
        if(G.library_detail_path){snprintf(b,sizeof b,"Install path: %s",g->install_dir[0]?g->install_dir:"Not reported");set_label(G.library_detail_path,b);}
        if(G.game_detected_detail){if(game_is_steam_shortcut(g))snprintf(b,sizeof b,"%s\nSteam • Non-Steam Shortcut • App ID %s\nRungameid: %s\nTarget: %s\nResolution: %s",g->name,g->appid,g->launch_id[0]?g->launch_id:"—",g->executable[0]?g->executable:"—",g->resolution_label[0]?g->resolution_label:"Pending");else snprintf(b,sizeof b,"%s\n%s • %s",g->name,src,game_is_steam(g)?g->appid:g->runner);set_label(G.game_detected_detail,b);}
        if(game_is_steam_shortcut(g)){
            if(g->shortcut_launch_supported)gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Non-Steam shortcut detected</span>\n<span foreground=\"#aeb9c7\">🎮   Target:      </span><span foreground=\"#28e57b\" weight=\"bold\">Shortcut identity resolved</span>\n<span foreground=\"#aeb9c7\">⚙   Handoff:     </span><span foreground=\"#28e57b\" weight=\"bold\">Runtime/prefix resolved • live handoff enabled</span>");
            else gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Non-Steam shortcut detected</span>\n<span foreground=\"#aeb9c7\">🎮   Target:      </span><span foreground=\"#28e57b\" weight=\"bold\">Library-visible</span>\n<span foreground=\"#aeb9c7\">⚙   Handoff:     </span><span foreground=\"#efb85b\" weight=\"bold\">Resolution incomplete</span>");
            if(g->prefix[0])snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix);else snprintf(b,sizeof b,"▰   Prefix:      Not created/resolved");set_label(G.right_prefix,b);
        }else if(game_is_steam(g)){
            gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Detected</span>\n<span foreground=\"#aeb9c7\">🎮   Game:        </span><span foreground=\"#28e57b\" weight=\"bold\">Installed</span>\n<span foreground=\"#aeb9c7\">⚙   Runner:      Steam Play</span>");
            set_label(G.right_prefix,g->wand_found?"▰   Prefix:      Compatible":"▰   Prefix:      Detected");
        }else{
            if(managed_state==1)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Running (GameWeld managed)\nPID: %ld",g->runner,managed_game_pid);else if(managed_state==2)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Closed • trainer still running\nTrainer PID: %ld",g->runner,managed_trainer_pid);else snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Installed",g->runner);set_label(G.right_game,b);
            snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix[0]?g->prefix:"Heroic managed");set_label(G.right_prefix,b);
        }
    } else {
        if(G.game_detected_detail)set_label(G.game_detected_detail,"No game selected");set_image_path(G.hero_image,NULL,520,180);set_image_path(G.cover_image,NULL,155,220);G.artwork_appid[0]=0;set_label(G.hero_name,"Select a game");set_label(G.hero_meta,"Steam / Heroic");gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">Game source:     Not selected\n🎮   Game:        Not detected\n⚙   Runner:      —</span>");set_label(G.right_prefix,"▰   Prefix:      —");
    }
    if(g&&!game_is_steam(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Heroic\n✣   Trainers:    Local / Cheat Engine</span>");
        if(managed_state==1)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#28e57b\" weight=\"bold\">GameWeld managed</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Actual game process running</span>");else if(managed_state==2)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#efb85b\" weight=\"bold\">Trainer remains</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Game process exited</span>");else snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Heroic:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Direct live-prefix ready</span>",g->wine_name[0]?g->wine_name:(g->wine_type[0]?g->wine_type:"Launcher-managed"));gtk_label_set_markup((GtkLabel*)G.right_proton,b);
    } else if(g&&game_is_steam_shortcut(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Steam non-Steam shortcut</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     Discovery + assignment ready</span>");
        if(g->shortcut_launch_supported){snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Runtime + compatdata resolved • live handoff enabled</span>",g->compat_tool[0]?g->compat_tool:"Resolved Steam Play tool");gtk_label_set_markup((GtkLabel*)G.right_proton,b);}else{snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">%s</span>",g->compat_tool[0]?g->compat_tool:"Not resolved",g->resolution_label[0]?g->resolution_label:"Refresh after Steam creates the shortcut prefix");gtk_label_set_markup((GtkLabel*)G.right_proton,b);}
    } else {
        if(G.wand_installed)gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Steam compatibility</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     </span><span foreground=\"#28e57b\" weight=\"bold\">Available</span>");else gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Steam compatibility not installed\n✣   Trainer:     Unavailable</span>");
        if(G.wand_healthy)gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">GE-Proton-Wand-SHA256</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Ready to Launch</span>");else gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">Needs setup</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Setup required</span>");
    }
    set_label(G.game_ready,g?(managed_state==1?"Running":(managed_state==2?"Trainer active":(game_is_steam_shortcut(g)?"Shortcut detected":"Installed"))):"Not detected");set_label(G.wand_ready,(g&&!game_is_steam(g))?"Heroic":(g&&game_is_steam_shortcut(g)?"Discovery ready":(G.wand_installed?"Ready":"Needs setup")));set_label(G.compat_ready,(g&&!game_is_steam(g))?(managed_state?"Managed session":"Launcher-managed"):(g&&game_is_steam_shortcut(g)?(g->shortcut_launch_supported?"Live handoff ready":"Resolution pending"):(G.wand_healthy?"Configured":"Needs repair")));
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
    if(G.play_title)set_label(G.play_title,managed_state==1?"GAME RUNNING":(managed_state==2?"TRAINER STILL RUNNING":(has_native?"PLAY WITH NATIVE TRAINER":(use_ct?"PLAY WITH CHEAT TABLE":(has_local?"PLAY WITH LOCAL TRAINER":((g&&game_is_steam_shortcut(g))?"LAUNCH STEAM SHORTCUT":((g&&!game_is_steam(g))?"PLAY THROUGH HEROIC":(g?"PLAY WITH STEAM TRAINER":"PLAY WITH TRAINER"))))))));
    if(G.play_subtitle)set_label(G.play_subtitle,managed_state==1?"GameWeld is tracking the actual Heroic game process • trainer shares the managed UMU session":(managed_state==2?"The game has exited but the trainer is still active • close it or use Stop Stuck Trainer":(has_native?"Built-in Resonance trainer • no Cheat Engine • unlimited local profile":(use_ct?"Launch game + Cheat Engine table (local / unlimited)":(has_local?"Launch game + your local trainer (local / unlimited)":((g&&game_is_steam_shortcut(g))?"Launch through the shortcut’s Steam rungameid; assigned trainers use the validated live Proton session":((g&&!game_is_steam(g))?"Launch with Heroic using its configured Wine/Proton runner":(g?"Launch through Steam with the configured trainer provider":"Select a game to see its configured launch path"))))))));
    if(G.play_button)gtk_widget_set_sensitive(G.play_button,managed_state==0);
    if(G.native_profile_status){
        if(!g)set_label(G.native_profile_status,"Select a game first.");
        else if(!game_is_steam(g))set_label(G.native_profile_status,"Native converted-table profiles are currently available for selected Steam titles only.");
        else if(has_native)set_label(G.native_profile_status,"Enabled: Resonance v1.1 native profile. God Mode, Invisible, Resonance Points, FOV and Console run without Cheat Engine.");
        else if(native_available)set_label(G.native_profile_status,"Native profile available for this game. Enable it to run the converted Resonance table features without Cheat Engine.");
        else set_label(G.native_profile_status,"No built-in native table profile is available for this game yet.");
    }
    if(G.local_trainer_entry)gtk_entry_set_text((GtkEntry*)G.local_trainer_entry,has_local_mapping?lt:"");
    if(G.local_trainer_status){if(managed_state==1){snprintf(b,sizeof b,"Managed Heroic session active: game PID %ld%s. Running state comes from the actual process, not Heroic’s PLAY/PLAYING badge.",managed_game_pid,managed_trainer_pid?" • trainer active":"");set_label(G.local_trainer_status,b);}else if(managed_state==2){snprintf(b,sizeof b,"Game process has exited; trainer PID %ld is still active. Close it normally or use Stop Stuck Trainer.",managed_trainer_pid);set_label(G.local_trainer_status,b);}else if(has_local){snprintf(b,sizeof b,"Local trainer configured for %s.%s",g->name,has_native?" Native profile currently takes priority for PLAY.":(use_ct?" Cheat Table currently takes priority for PLAY.":" PLAY uses this trainer."));set_label(G.local_trainer_status,b);}else if(has_local_mapping){snprintf(b,sizeof b,"Trainer mapping exists for %s, but the EXE is missing: %s. Use Trainer Library rescan to recover it or clear the stale mapping.",g->name,lt);set_label(G.local_trainer_status,b);}else set_label(G.local_trainer_status,g?"No local trainer configured for this game.":"Select a game first.");}
    if(G.cheat_engine_entry)gtk_entry_set_text((GtkEntry*)G.cheat_engine_entry,has_ce?ce:"");
    if(G.cheat_engine_installer_entry)gtk_entry_set_text((GtkEntry*)G.cheat_engine_installer_entry,has_ce_installer?ce_installer:"");
    if(G.cheat_table_entry)gtk_entry_set_text((GtkEntry*)G.cheat_table_entry,has_ct?ct:"");
    if(G.cheat_table_status){
        if(!g)set_label(G.cheat_table_status,"Select a game first.");
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
        if(g){if(has_local)snprintf(b,sizeof b,"Selected game: %s\nAssigned trainer: %s\nHealth: Valid",g->name,lt);else if(has_local_mapping)snprintf(b,sizeof b,"Selected game: %s\nAssigned trainer: %s\nHealth: Missing",g->name,lt);else snprintf(b,sizeof b,"Selected game: %s\nAssigned trainer: none",g->name);set_label(G.trainer_library_selected,b);}
        else set_label(G.trainer_library_selected,"Select a game in Library to assign or clear its trainer.");
    }
    update_trainer_library_actions();
    if(G.setup_status)set_label(G.setup_status,G.wand_healthy?"✓ Steam compatibility ready":"Steam compatibility setup required");
    if(G.setup_detail){snprintf(b,sizeof b,"%s\nBase Proton: %s\nGameWeld tool: %s",G.verify_message[0]?G.verify_message:"Not checked",G.base_proton[0]?G.base_proton:"Not detected",G.wand_tool[0]?G.wand_tool:"Not installed");set_label(G.setup_detail,b);}
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
static void on_play(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}char lt[2048]={0},ct[2048]={0},ce[2048]={0},np[128]={0};Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){if(!g->shortcut_launch_supported){log_line("Steam non-Steam shortcut %s cannot use trainer handoff because its Steam Play runtime/prefix is unresolved. Launch it once from Steam with compatibility enabled, then Refresh Game Sources.",g->name);return;}const char*k=game_key(g);if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through its validated live Steam non-Steam shortcut Proton session + local trainer: %s",g->name,lt);spawn_steam_shortcut_trainer(g,lt);return;}log_line("No local trainer is assigned to %s; launching the Steam non-Steam shortcut normally through rungameid %s.",g->name,g->launch_id);spawn_steam_shortcut_normal(g);return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Game launch is blocked until it finishes or you press Cancel Runtime Repair in Settings.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Trainer runtime repair is still active. Wait for completion or cancel it before launching the game.");return;}const char*k=game_key(g);const char*native_available=game_is_steam(g)?available_native_profile(g->appid):NULL;if(native_available&&load_native_profile(k,np,sizeof np)&&!strcmp(np,native_available)){log_line("Launching %s through Steam + native trainer profile: %s",g->name,np);spawn_native_profile(g->appid,np);return;}if(load_cheat_table(k,ct,sizeof ct)&&readable_file(ct)){if((load_cheat_engine(ce,sizeof ce)&&readable_file(ce))||detect_managed_cheat_engine(game_ce_id(g),ce,sizeof ce)){log_line("Launching %s through %s + Cheat Engine table: %s",g->name,game_is_steam(g)?"Steam":"Heroic",ct);if(game_is_steam(g))spawn_cheat_table(g->appid,ce,ct);else spawn_heroic_table(g,ce,ct);return;}}if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through %s + local trainer: %s",g->name,game_is_steam(g)?"Steam":"Heroic",lt);if(game_is_steam(g))spawn_local_trainer(g->appid,lt);else spawn_heroic_trainer(g,lt);return;}if(game_is_steam(g))start_job(JOB_PLAY,g->appid,"Preparing game and launching with the Steam compatibility provider…");else{log_line("No trainer/table configured for %s; launching normally through Heroic.",g->name);spawn_heroic_normal(g);}}
static void on_play_normal(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){if(!g->launch_uri[0]){log_line("Steam non-Steam shortcut %s has no rungameid launch URI.",g->name);return;}spawn_steam_shortcut_normal(g);log_line("Launching Steam non-Steam shortcut %s normally through rungameid %s…",g->name,g->launch_id);return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Normal Heroic launch is blocked until repair completes or is cancelled.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"FLiNG runtime repair is active; normal Heroic launch is temporarily blocked to protect the prefix.");return;}if(game_is_steam(g)){spawn_detached("steam","-applaunch",g->appid);log_line("Launching normally through Steam…");}else{spawn_heroic_normal(g);log_line("Launching normally through Heroic (%s)…",g->runner);}}
static void on_steam_page(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Non-Steam shortcuts do not have a Steam store page.");return;}if(game_is_steam(g)){char u[256];snprintf(u,sizeof u,"steam://store/%s",g->appid);spawn_detached("xdg-open",u,NULL);}else log_line("Store-page shortcut is not wired for Heroic %s games yet.",g->runner);}
static void on_game_folder(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;if(G.games[G.selected].install_dir[0])spawn_detached("xdg-open",G.games[G.selected].install_dir,NULL);}
static void on_open_selected_trainer_folder(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]){log_line("Select a trainer row first.");return;}char dir[2048];snprintf(dir,sizeof dir,"%s",G.trainer_library_pick_path);char *slash=strrchr(dir,'/');if(slash&&slash!=dir)*slash=0;else if(slash==dir)slash[1]=0;else snprintf(dir,sizeof dir,".");spawn_detached("xdg-open",dir,NULL);log_line("Opened trainer folder: %s",dir);}
static void on_minimize(GtkButton*b,void*d){(void)b;(void)d;gtk_window_iconify((GtkWindow*)G.window);}
static void on_maximize(GtkButton*b,void*d){(void)b;(void)d;static int m=0;if(m){gtk_window_unmaximize((GtkWindow*)G.window);m=0;}else{gtk_window_maximize((GtkWindow*)G.window);m=1;}}
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
            "--version","0.4.0-rc1","--name",g->name,"--key",game_key(g),"--provider",g->provider,"--appid",g->appid,"--launch-id",g->launch_id,"--runner",g->runner,
            "--target-kind",g->target_kind,"--executable",g->executable,"--install-dir",g->install_dir,"--prefix",g->prefix,"--compatdata",g->compatdata,
            "--compat-tool",g->compat_tool,"--compat-tool-path",g->compat_tool_path,"--compat-tool-source",g->compat_tool_source,"--resolution-state",g->resolution_state,"--resolution",g->resolution_label,
            "--trainer",trainer,(char*)NULL);_exit(127);
    }
    close(fd[1]);char out[4096]={0};ssize_t n=read(fd[0],out,sizeof out-1);close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}
    if(n>0){out[n]=0;while(n>0&&(out[n-1]=='\n'||out[n-1]=='\r'))out[--n]=0;}
    if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0&&out[0]){log_line("Support bundle exported for %s: %s",g->name,out);if(G.support_bundle_status){char msg[4600];snprintf(msg,sizeof msg,"Selected-game support bundle created:\n%s\n\nContains only this game's launch metadata, Trainer Library diagnostics and matching GameWeld logs. Trainer EXE bytes and unrelated game logs are not included.",out);set_label(G.support_bundle_status,msg);}}
    else{log_line("Support bundle export failed for %s: %s",g->name,out[0]?out:"unknown error");if(G.support_bundle_status)set_label(G.support_bundle_status,"Support bundle export failed. See Activity Log for details.");}
}

static void on_health(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Steam non-Steam shortcut resolution for %s: %s | target=%s | tool=%s | compatdata=%s | live-session validation ready.",g->name,g->resolution_label[0]?g->resolution_label:"unresolved",g->target_kind[0]?g->target_kind:"unknown",g->compat_tool[0]?g->compat_tool:"unresolved",g->compatdata[0]?g->compatdata:"not found");return;}if(!game_is_steam(g)){log_line("Heroic launch diagnostics are recorded in ~/.local/state/gameweld/heroic-*.log.");return;}start_job(JOB_HEALTH,g->appid,"Checking trainer health…");}
static void on_refresh(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_REFRESH,NULL,"Refreshing Steam, Heroic and GameWeld status…");}

static void nav_activate(GtkWidget *active,const char *page){GtkWidget *all[]={G.nav_home,G.nav_library,G.nav_trainers,G.nav_setup,G.nav_diag,G.nav_settings,G.nav_about};for(int i=0;i<7;i++)if(all[i])unstyle(all[i],"nav-active");style(active,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,page);}
static void nav_home(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_home,"home");}
static void nav_library(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_library,"library");}
static void nav_trainers(GtkButton*b,void*d){(void)b;(void)d;refresh_trainer_library_view();nav_activate(G.nav_trainers,"trainers");}
static void nav_setup(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_setup,"setup");}
static void nav_diag(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_diag,"diag");}
static void nav_settings(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_settings,"settings");}
static void nav_about(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_about,"about");}

static const char *global_search_scope_id(void){const char*id=G.search_scope?gtk_combo_box_get_active_id((GtkComboBox*)G.search_scope):NULL;return(id&&*id)?id:"all";}
static int game_matches_global_scope(Game*g,const char*scope){
    if(!scope||!strcmp(scope,"all"))return 1;
    if(!strcmp(scope,"steam"))return game_is_steam(g)&&!game_is_steam_shortcut(g);
    if(!strcmp(scope,"shortcut"))return game_is_steam_shortcut(g);
    if(!strcmp(scope,"heroic"))return !game_is_steam(g);
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
static void on_destroy(GtkWidget*w,void*d){(void)w;(void)d;if(G.backend_pid>0)kill(G.backend_pid,SIGTERM);gtk_main_quit();}

static GtkWidget *card(const char *title,const char *detail,GtkWidget **detail_out){GtkWidget *c=box(GTK_ORIENTATION_VERTICAL,6);style(c,"card");margins(c,4);GtkWidget*t=label(title,"card-title");pack(c,t,0);GtkWidget*x=label(detail,"muted");gtk_label_set_line_wrap((GtkLabel*)x,TRUE);pack(c,x,0);if(detail_out)*detail_out=x;return c;}

static GtkWidget *icon_named(const char *name,int px){GtkWidget*i=gtk_image_new_from_icon_name(name,GTK_ICON_SIZE_BUTTON);if(i)gtk_image_set_pixel_size((GtkImage*)i,px);return i;}
static GtkWidget *make_nav(const char *icon,const char *txt,GCallback cb){GtkWidget*b=gtk_button_new();style(b,"nav");GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,7);GtkWidget*i=icon_named(icon,16);if(i){style(i,"nav-icon");pack(r,i,0);}GtkWidget*l=label(txt,"nav-label");pack(r,l,0);gtk_container_add(b,r);g_signal_connect_data(b,"clicked",cb,NULL,NULL,0);return b;}
static GtkWidget *quick_button(const char *icon,const char *txt){GtkWidget*b=gtk_button_new();style(b,"action");GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*i=icon_named(icon,18);if(i)pack(r,i,0);GtkWidget*l=label(txt,"quick-label");pack(r,l,1);GtkWidget*ch=label("›","quick-chevron");pack(r,ch,0);gtk_container_add(b,r);return b;}

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
    GtkWidget*b=gtk_button_new();gtk_widget_set_name(b,primary?"play":"normal");
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

    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("OVERVIEW","page-kicker"),0);pack(ht,label("Your game, runtime and trainer in one place","workspace-title"),0);pack(ht,label("GameWeld keeps the launcher-native session intact and shows what will happen before you press Play.","page-subtitle"),0);pack(head,ht,1);GtkWidget*online=label("●  Services ready","good");gtk_widget_set_name(online,"status-pill");pack(head,online,0);pack(page,head,0);

    GtkWidget*spot=box(GTK_ORIENTATION_HORIZONTAL,16);gtk_widget_set_name(spot,"spotlight");
    GtkWidget*copy=box(GTK_ORIENTATION_VERTICAL,12);gtk_widget_set_name(copy,"spotlight-copy");gtk_widget_set_size_request(copy,390,-1);
    pack(copy,label("CURRENT GAME","eyebrow"),0);
    GtkWidget*idrow=box(GTK_ORIENTATION_HORIZONTAL,13);GtkWidget*cover=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(cover,"cover-frame");G.cover_image=gtk_image_new();gtk_widget_set_size_request(G.cover_image,155,220);pack(cover,G.cover_image,0);pack(idrow,cover,0);
    GtkWidget*ids=box(GTK_ORIENTATION_VERTICAL,7);G.hero_name=label("Select a game",NULL);gtk_widget_set_name(G.hero_name,"game-title");gtk_label_set_line_wrap((GtkLabel*)G.hero_name,TRUE);pack(ids,G.hero_name,0);G.hero_meta=label("Steam / Heroic • App ID —",NULL);gtk_widget_set_name(G.hero_meta,"meta");gtk_label_set_line_wrap((GtkLabel*)G.hero_meta,TRUE);pack(ids,G.hero_meta,0);pack(ids,meta_chip("LOCAL / SINGLE PLAYER"),0);G.game_detected_detail=label("Choose a game from Library to review its trainer, runtime and exact launch path before starting the session.","muted");gtk_label_set_line_wrap((GtkLabel*)G.game_detected_detail,TRUE);pack(ids,G.game_detected_detail,1);pack(idrow,ids,1);pack(copy,idrow,1);
    GtkWidget*plays=box(GTK_ORIENTATION_HORIZONTAL,8);gtk_widget_set_name(plays,"launch-panel");G.play_button=launch_button(1);g_signal_connect_data(G.play_button,"clicked",(GCallback)on_play,NULL,NULL,0);pack(plays,G.play_button,1);GtkWidget*normal=launch_button(0);gtk_widget_set_size_request(normal,170,62);g_signal_connect_data(normal,"clicked",(GCallback)on_play_normal,NULL,NULL,0);pack(plays,normal,0);pack(copy,plays,0);pack(spot,copy,0);
    GtkWidget*art=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(art,"hero-art");G.hero_image=gtk_image_new();gtk_widget_set_size_request(G.hero_image,520,300);pack(art,G.hero_image,1);pack(spot,art,1);pack(page,spot,0);

    GtkWidget*lower=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*readiness=box(GTK_ORIENTATION_VERTICAL,9);style(readiness,"panel");gtk_widget_set_size_request(readiness,300,-1);pack(readiness,label("SESSION READINESS","section-kicker"),0);
    GtkWidget*m1=box(GTK_ORIENTATION_HORIZONTAL,10);style(m1,"metric");GtkWidget*m1t=box(GTK_ORIENTATION_VERTICAL,2);pack(m1t,label("GAME","metric-name"),0);G.game_ready=label("Waiting","metric-value");pack(m1t,G.game_ready,0);pack(m1,m1t,1);GtkWidget*m1i=icon_named("applications-games-symbolic",18);if(m1i)pack(m1,m1i,0);pack(readiness,m1,0);
    GtkWidget*m2=box(GTK_ORIENTATION_HORIZONTAL,10);style(m2,"metric");GtkWidget*m2t=box(GTK_ORIENTATION_VERTICAL,2);pack(m2t,label("TRAINER","metric-name"),0);G.wand_ready=label("Waiting","metric-value");pack(m2t,G.wand_ready,0);pack(m2,m2t,1);GtkWidget*m2i=icon_named("applications-engineering-symbolic",18);if(m2i)pack(m2,m2i,0);pack(readiness,m2,0);
    GtkWidget*m3=box(GTK_ORIENTATION_HORIZONTAL,10);style(m3,"metric");GtkWidget*m3t=box(GTK_ORIENTATION_VERTICAL,2);pack(m3t,label("RUNTIME","metric-name"),0);G.compat_ready=label("Waiting","metric-value");pack(m3t,G.compat_ready,0);pack(m3,m3t,1);GtkWidget*m3i=icon_named("emblem-system-symbolic",18);if(m3i)pack(m3,m3i,0);pack(readiness,m3,0);pack(lower,readiness,0);

    GtkWidget*activity=box(GTK_ORIENTATION_VERTICAL,8);style(activity,"panel");GtkWidget*ah=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*aht=box(GTK_ORIENTATION_VERTICAL,1);pack(aht,label("ACTIVITY","section-kicker"),0);pack(aht,label("Current session events","card-title"),0);pack(ah,aht,1);GtkWidget*clear=button("Clear","action");pack(ah,clear,0);pack(activity,ah,0);G.activity=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.activity,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.activity,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.activity,TRUE);gtk_widget_set_name(G.activity,"logframe");GtkWidget*asc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(asc,-1,220);gtk_container_add(asc,G.activity);pack(activity,asc,1);pack(lower,activity,1);

    GtkWidget*context=box(GTK_ORIENTATION_VERTICAL,9);style(context,"panel");gtk_widget_set_size_request(context,275,-1);pack(context,label("SESSION CONTEXT","section-kicker"),0);G.right_game=label("Game source: Not selected\nGame: —\nRuntime: —","muted");gtk_label_set_line_wrap((GtkLabel*)G.right_game,TRUE);pack(context,G.right_game,0);G.right_prefix=label("Prefix: —","good");gtk_label_set_line_wrap((GtkLabel*)G.right_prefix,TRUE);pack(context,G.right_prefix,0);pack(context,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);G.right_wand=label("Provider: —\nTrainer: —","muted");gtk_label_set_line_wrap((GtkLabel*)G.right_wand,TRUE);pack(context,G.right_wand,0);G.right_proton=label("Runtime: —\nStatus: —","good");gtk_label_set_line_wrap((GtkLabel*)G.right_proton,TRUE);pack(context,G.right_proton,0);pack(context,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(context,label("QUICK ACTIONS","section-kicker"),0);GtkWidget*h=quick_button("utilities-system-monitor-symbolic","Check trainer health");GtkWidget*rp=quick_button("applications-engineering-symbolic","Repair compatibility");GtkWidget*gf=quick_button("folder-open-symbolic","Open game folder");GtkWidget*sp=quick_button("external-link-symbolic","Open store page");G.quick_store=sp;g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);g_signal_connect_data(rp,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(gf,"clicked",(GCallback)on_game_folder,NULL,NULL,0);g_signal_connect_data(sp,"clicked",(GCallback)on_steam_page,NULL,NULL,0);pack(context,h,0);pack(context,rp,0);pack(context,gf,0);pack(context,sp,0);pack(lower,context,0);pack(page,lower,1);
    return outer;
}

static GtkWidget *build_library(void){
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,22);
    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("LIBRARY","page-kicker"),0);pack(ht,label("All detected games","workspace-title"),0);pack(ht,label("Steam, Steam shortcuts and Heroic titles in one working set.","page-subtitle"),0);pack(head,ht,1);char count[64];snprintf(count,sizeof count,"%d games",G.game_count);GtkWidget*ct=label(count,"good");gtk_widget_set_name(ct,"status-pill");pack(head,ct,0);pack(p,head,0);
    GtkWidget*body=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*listpanel=box(GTK_ORIENTATION_VERTICAL,8);style(listpanel,"panel");pack(listpanel,label("GAMES","section-kicker"),0);GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_vexpand(sc,TRUE);G.game_list=gtk_list_box_new();g_signal_connect_data(G.game_list,"row-selected",(GCallback)selected_changed,NULL,NULL,0);
    for(int i=0;i<G.game_count;i++){GtkWidget*r=gtk_list_box_row_new();style(r,"library-row");G.game_rows[i]=r;GtkWidget*rb=box(GTK_ORIENTATION_HORIZONTAL,11);margins(rb,7);GtkWidget*thumb=gtk_image_new();style(thumb,"game-thumb");char art[2048]={0};if(!resolve_game_art(&G.games[i],1,art,sizeof art))resolve_game_art(&G.games[i],0,art,sizeof art);set_image_path(thumb,art[0]?art:NULL,52,70);pack(rb,thumb,0);GtkWidget*txt=box(GTK_ORIENTATION_VERTICAL,3);pack(txt,label(G.games[i].name,"game-row-title"),0);char x[384];if(game_is_steam_shortcut(&G.games[i]))snprintf(x,sizeof x,"Steam shortcut • %s",G.games[i].appid);else if(game_is_steam(&G.games[i]))snprintf(x,sizeof x,"Steam • %s",G.games[i].appid);else snprintf(x,sizeof x,"Heroic • %s",G.games[i].runner);pack(txt,label(x,"muted"),0);pack(rb,txt,1);GtkWidget*installed=label("Ready","good");gtk_widget_set_name(installed,"status-pill");pack(rb,installed,0);gtk_container_add(r,rb);gtk_list_box_insert((GtkListBox*)G.game_list,r,-1);}gtk_container_add(sc,G.game_list);pack(listpanel,sc,1);pack(body,listpanel,1);
    GtkWidget*inspect=box(GTK_ORIENTATION_VERTICAL,11);gtk_widget_set_name(inspect,"library-inspector");gtk_widget_set_size_request(inspect,410,-1);pack(inspect,label("SELECTED GAME","section-kicker"),0);G.library_detail_name=label("Select a game",NULL);gtk_widget_set_name(G.library_detail_name,"library-name");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_name,TRUE);pack(inspect,G.library_detail_name,0);G.library_detail_meta=label("Steam / Heroic","library-meta");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_meta,TRUE);pack(inspect,G.library_detail_meta,0);pack(inspect,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(inspect,label("LAUNCH READINESS","section-kicker"),0);G.library_detail_status=label("Choose a game to inspect its runtime and trainer handoff.","muted");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_status,TRUE);pack(inspect,G.library_detail_status,0);G.library_detail_path=label("Install path: —","good");gtk_label_set_line_wrap((GtkLabel*)G.library_detail_path,TRUE);pack(inspect,G.library_detail_path,0);GtkWidget*lb1=button("Launch with configured trainer","primary-action");GtkWidget*lb2=button("Play normally","action");GtkWidget*lb3=button("Open game folder","action");g_signal_connect_data(lb1,"clicked",(GCallback)on_play,NULL,NULL,0);g_signal_connect_data(lb2,"clicked",(GCallback)on_play_normal,NULL,NULL,0);g_signal_connect_data(lb3,"clicked",(GCallback)on_game_folder,NULL,NULL,0);pack(inspect,lb1,0);pack(inspect,lb2,0);pack(inspect,lb3,0);pack(inspect,gtk_separator_new(GTK_ORIENTATION_HORIZONTAL),0);pack(inspect,label("TIP","section-kicker"),0);GtkWidget*tip=label("Use the search dropdown above to choose All games, Steam, Steam shortcuts, Heroic, or Trainers. Trainer searches jump directly to Trainer Library.","muted");gtk_label_set_line_wrap((GtkLabel*)tip,TRUE);pack(inspect,tip,0);pack(body,inspect,0);pack(p,body,1);return p;
}


static void on_enable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}Game*g=&G.games[G.selected];if(game_is_steam_shortcut(g)){log_line("Native converted-table profiles are not enabled for Steam non-Steam shortcuts.");return;}if(!game_is_steam(g)){log_line("Native converted-table profiles are currently Steam-only.");return;}const char*p=available_native_profile(g->appid);if(!p){log_line("No native trainer profile is available for %s yet.",g->name);return;}if(save_native_profile(game_key(g),p))log_line("Native trainer profile enabled for %s: %s",g->name,p);else log_line("Could not save native profile configuration.");refresh_ui();}
static void on_disable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(save_native_profile(game_key(g),NULL))log_line("Native trainer profile disabled for %s.",g->name);refresh_ui();}

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
static void on_launch_assigned_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a readable assigned trainer row in Trainer Library first.");return;}int idx=trainer_game_index_by_key(G.trainer_library_pick_key);if(idx<0){log_line("This trainer has no assigned game target yet. Assign it before launching.");return;}Game*g=&G.games[idx];if(game_is_steam_shortcut(g)&&!g->shortcut_launch_supported){log_line("Direct trainer launch blocked for Steam non-Steam shortcut %s: runtime/prefix resolution is incomplete. Launch it once from Steam with compatibility enabled, then Refresh Game Sources.",g->name);return;}char assigned[2048]={0};if(!(load_local_trainer(game_key(g),assigned,sizeof assigned)&&readable_file(assigned)&&!strcmp(assigned,G.trainer_library_pick_path))){log_line("Direct launch blocked: %s is not the trainer currently assigned to %s. Assign or switch to this trainer first.",G.trainer_library_pick_path,g->name);update_trainer_library_actions();return;}if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Direct launch blocked: trainer runtime repair is still active for %s. Wait for completion or cancel the repair first.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Trainer runtime repair is still active. Wait for completion or cancel it before launching the game.");return;}G.selected=idx;refresh_ui();log_line("Trainer Library launching %s with its assigned local trainer: %s",g->name,assigned);if(game_is_steam_shortcut(g))spawn_steam_shortcut_trainer(g,assigned);else if(game_is_steam(g))spawn_local_trainer(g->appid,assigned);else spawn_heroic_trainer(g,assigned);}
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
    if(!strcmp(code,"launch")){on_launch_assigned_library_pick(NULL,NULL);return;}
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
static void on_stop_heroic_trainer(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("Stop Stuck Trainer is for Heroic sessions; Steam uses the existing Steam provider lifecycle.");return;}char lt[2048]={0};if(!(load_local_trainer(game_key(g),lt,sizeof lt)&&readable_file(lt))){log_line("No local trainer is configured for %s.",g->name);return;}spawn_heroic_session_control(g,"stop-trainer",lt);log_line("Stopping the configured trainer for %s. If it ignores a normal close, GameWeld will force-stop that trainer process only.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Stopping stuck trainer… the game is left running. See ~/.local/state/gameweld/heroic-session-control-*.log for details.");}
static void on_reset_heroic_prefix(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("Reset Heroic Prefix is available only for Heroic games.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);spawn_heroic_session_control(g,"reset-prefix",lt);log_line("Resetting the complete Heroic Wine/Proton session for %s. This closes the game, trainer and other Windows processes in that prefix.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Resetting Heroic prefix session… this closes the game and every Windows sidecar in this prefix.");}
static void on_check_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("FLiNG runtime check currently targets Heroic prefixes; Steam uses its own compatdata tooling.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"status",lt);log_line("Checking trainer runtime prerequisites for %s. The status below will update automatically when the check finishes.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Checking Heroic trainer runtime... looking for wininet, .NET Framework 4.8 and .NET 8 plus a repair-only compatibility runtime.");}
static void on_download_heroic_repair_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("Managed trainer repair runtime currently targets Heroic prefixes.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"download-helper",lt);log_line("Downloading the managed repair-only runtime for %s. This does not change Heroic's configured game runner.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Downloading GameWeld repair-only runtime (about 500 MB)... Heroic's selected Wine/Proton version will not be changed.");}
static void on_repair_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("Adaptive Trainer Runtime Repair currently targets Heroic prefixes; Steam compatibility repair is separate.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"repair",lt);log_line("Starting adaptive trainer runtime repair for %s. GameWeld keeps Heroic's selected game runner unchanged and uses a separate repair-only runtime for legacy dependencies.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Repairing trainer runtime... the game stays on its selected Wine/Proton version. GameWeld uses a separate repair-only runtime to install .NET 4.8 + .NET 8 + wininet into this prefix while the game is closed.");}
static void on_cancel_heroic_trainer_runtime(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Heroic game first.");return;}Game*g=&G.games[G.selected];if(game_is_steam(g)){log_line("Cancel Runtime Repair is for Heroic prefixes.");return;}char lt[2048]={0};load_local_trainer(game_key(g),lt,sizeof lt);start_heroic_runtime_job(g,"cancel",lt);log_line("Cancelling any active FLiNG runtime repair for %s. After cancelling an in-progress Winetricks install, reset the Heroic prefix before launching.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Cancelling FLiNG runtime repair… then use Reset Heroic Prefix before launching if Winetricks was interrupted.");}
static void on_choose_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Windows Cheat Engine EXE",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Cheat Engine",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){if(save_cheat_engine(fn))log_line("Cheat Engine configured: %s",fn);else log_line("Could not save Cheat Engine configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_clear_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(save_cheat_engine(NULL))log_line("Cheat Engine executable cleared.");refresh_ui();}
static void on_open_cheat_engine_download(GtkButton*b,void*d){(void)b;(void)d;spawn_detached("xdg-open","https://cheatengine.org/download/CheatEngineLinux771.zip",NULL);log_line("Opened the official Cheat Engine Linux 7.7.1 download.");}
static void on_open_cheat_engine_windows_download(GtkButton*b,void*d){(void)b;(void)d;spawn_detached("xdg-open","https://cheatengine.org/downloads.php",NULL);log_line("Opened the official Cheat Engine downloads page for the Windows CE companion.");}
static void on_download_install_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}log_line("Downloading and installing official native Cheat Engine Linux 7.7.1 from cheatengine.org...");spawn_managed_ce_download_install(game_ce_id(&G.games[G.selected]));if(G.cheat_table_status)set_label(G.cheat_table_status,"Downloading/installing native Cheat Engine 7.7.1. The managed CE bridge is shared across Steam and Heroic games. Click Detect / Refresh CE when complete.");}
static void on_install_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}char installer[2048]={0};if(!(load_cheat_engine_installer(installer,sizeof installer)&&readable_file(installer))){GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose official Cheat Engine Linux ZIP or Windows installer",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Install with GameWeld",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){snprintf(installer,sizeof installer,"%s",fn);save_cheat_engine_installer(fn);}if(fn)g_free(fn);}gtk_widget_destroy(dlg);}if(!readable_file(installer)){log_line("Managed Cheat Engine install cancelled: no package selected.");refresh_ui();return;}log_line("Installing managed Cheat Engine package: %s",installer);spawn_managed_ce_install(game_ce_id(&G.games[G.selected]),installer);if(G.cheat_table_status)set_label(G.cheat_table_status,"Cheat Engine installation started. Linux ZIPs install the native bridge; Windows CE packages install in GameWeld's dedicated setup prefix and then populate the shared windowsbin companion for all games. Click Detect / Refresh CE after the installer closes.");}
static void on_choose_cheat_engine_installer(GtkButton*b,void*d){(void)b;(void)d;GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose official Cheat Engine Linux ZIP or Windows installer",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Package",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){if(save_cheat_engine_installer(fn))log_line("Cheat Engine package saved: %s",fn);}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_detect_managed_cheat_engine(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}char ce[2048]={0},wce[2048]={0};if(detect_managed_cheat_engine(game_ce_id(&G.games[G.selected]),ce,sizeof ce))log_line("Managed Linux Cheat Engine detected: %s",ce);else log_line("Managed Linux Cheat Engine not detected.");if(detect_managed_windows_ce(game_ce_id(&G.games[G.selected]),wce,sizeof wce))log_line("Windows CE Proton companion ready: %s",wce);else log_line("Windows CE Proton companion not detected yet.");refresh_ui();}
static void on_choose_cheat_table(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}GtkWidget*dlg=gtk_file_chooser_dialog_new("Choose Cheat Engine .CT table",(GtkWindow*)G.window,GTK_FILE_CHOOSER_ACTION_OPEN,"Cancel",GTK_RESPONSE_CANCEL,"Use Table",GTK_RESPONSE_ACCEPT,NULL);int r=gtk_dialog_run((GtkDialog*)dlg);if(r==GTK_RESPONSE_ACCEPT){char*fn=gtk_file_chooser_get_filename((GtkFileChooser*)dlg);if(fn&&*fn){const char*dot=strrchr(fn,'.');if(!dot||strcasecmp(dot,".ct"))log_line("Warning: selected file does not use the .CT extension: %s",fn);if(save_cheat_table(game_key(&G.games[G.selected]),fn))log_line("Cheat table configured for %s: %s",G.games[G.selected].name,fn);else log_line("Could not save Cheat Table configuration.");}if(fn)g_free(fn);}gtk_widget_destroy(dlg);refresh_ui();}
static void on_clear_cheat_table(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;if(save_cheat_table(game_key(&G.games[G.selected]),NULL))log_line("Cheat table cleared for %s.",G.games[G.selected].name);refresh_ui();}

static GtkWidget *build_trainer_library(void){
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,22);
    GtkWidget*head=box(GTK_ORIENTATION_HORIZONTAL,10);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("TRAINER LIBRARY","page-kicker"),0);pack(ht,label("Assignments, compatibility and launch policy","workspace-title"),0);pack(ht,label("Conservative matching with explicit control over every trainer-to-game relationship.","page-subtitle"),0);pack(head,ht,1);GtkWidget*scan=button("Scan all trainers","primary-action");GtkWidget*rescan=button("Rescan selected game","action");GtkWidget*addfolder=button("Add trainer folder","action");GtkWidget*refresh=button("Refresh view","action");g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(rescan,"clicked",(GCallback)on_rescan_selected_trainer,NULL,NULL,0);g_signal_connect_data(addfolder,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(refresh,"clicked",(GCallback)on_refresh_trainer_library,NULL,NULL,0);pack(head,scan,0);pack(head,rescan,0);pack(head,addfolder,0);pack(head,refresh,0);pack(p,head,0);

    GtkWidget*filters=box(GTK_ORIENTATION_HORIZONTAL,8);G.trainer_library_filter=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.trainer_library_filter,"Filter game, trainer, profile, runtime, version…");G.trainer_library_sort=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"status","Sort: Status / health");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"game","Sort: Game");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"confidence","Sort: Confidence");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"version","Sort: Version");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"profile","Sort: Compatibility profile");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"policy","Sort: Launch policy");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"launch","Sort: Next launch");gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_sort,"status");G.trainer_library_readiness_filter=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"all","Readiness: All");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"managed","Readiness: Managed FLiNG");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"steam","Readiness: Steam live session");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"inherit","Readiness: Heroic existing session");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"explicit","Readiness: Explicit override");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"unassigned","Readiness: No launch target");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"manual","Readiness: Manual policy override");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"advisory","Readiness: Advisory / low confidence");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_readiness_filter,"attention","Readiness: Assignment / health attention");gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_readiness_filter,"all");G.trainer_library_attention_toggle=gtk_check_button_new_with_label("Needs attention");GtkWidget*clearfilter=button("Clear","action");g_signal_connect_data(G.trainer_library_filter,"changed",(GCallback)on_trainer_library_filter_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_sort,"changed",(GCallback)on_trainer_library_sort_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_readiness_filter,"changed",(GCallback)on_trainer_library_readiness_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_attention_toggle,"toggled",(GCallback)on_trainer_library_attention_toggled,NULL,NULL,0);g_signal_connect_data(clearfilter,"clicked",(GCallback)on_trainer_library_clear_filter,NULL,NULL,0);pack(filters,G.trainer_library_filter,1);pack(filters,G.trainer_library_sort,0);pack(filters,G.trainer_library_readiness_filter,0);pack(filters,G.trainer_library_attention_toggle,0);pack(filters,clearfilter,0);pack(p,filters,0);

    GtkWidget*body=box(GTK_ORIENTATION_HORIZONTAL,14);
    GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*audit=box(GTK_ORIENTATION_HORIZONTAL,10);style(audit,"panel-soft");GtkWidget*audtxt=box(GTK_ORIENTATION_VERTICAL,2);pack(audtxt,label("COMPATIBILITY READINESS","section-kicker"),0);G.trainer_library_audit=label("No Trainer Library scan has completed yet.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_audit,TRUE);pack(audtxt,G.trainer_library_audit,0);pack(audit,audtxt,1);pack(left,audit,0);
    GtkWidget*library=box(GTK_ORIENTATION_VERTICAL,6);style(library,"panel");pack(library,label("RESULTS","section-kicker"),0);GtkWidget*nb=gtk_notebook_new();G.trainer_library_tabs=nb;gtk_widget_set_vexpand(nb,TRUE);G.trainer_library_matched=trainer_tree_new();G.trainer_library_alternates=trainer_tree_new();G.trainer_library_ambiguous=trainer_tree_new();G.trainer_library_unmatched=trainer_tree_new();G.trainer_library_health=trainer_tree_new();GtkWidget*views[5]={G.trainer_library_matched,G.trainer_library_alternates,G.trainer_library_ambiguous,G.trainer_library_unmatched,G.trainer_library_health};const char*tabs[5]={"Assigned","Alternatives","Ambiguous","Unmatched","Health"};for(int i=0;i<5;i++){GtkTreeSelection*seln=gtk_tree_view_get_selection((GtkTreeView*)views[i]);gtk_tree_selection_set_mode(seln,GTK_SELECTION_SINGLE);g_signal_connect_data(seln,"changed",(GCallback)trainer_pick_changed,NULL,NULL,0);GtkWidget*tsc=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)tsc,GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);gtk_container_add(tsc,views[i]);gtk_notebook_append_page((GtkNotebook*)nb,tsc,label(tabs[i],NULL));}G.trainer_library_attention_games=trainer_attention_tree_new();GtkTreeSelection*ags=gtk_tree_view_get_selection((GtkTreeView*)G.trainer_library_attention_games);gtk_tree_selection_set_mode(ags,GTK_SELECTION_SINGLE);g_signal_connect_data(ags,"changed",(GCallback)trainer_attention_game_changed,NULL,NULL,0);GtkWidget*agsc=gtk_scrolled_window_new(NULL,NULL);gtk_container_add(agsc,G.trainer_library_attention_games);gtk_notebook_append_page((GtkNotebook*)nb,agsc,label("Game attention",NULL));pack(library,nb,1);pack(left,library,1);
    GtkWidget*summary=box(GTK_ORIENTATION_VERTICAL,5);style(summary,"panel-soft");GtkWidget*sh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(sh,label("LAST SCAN","section-kicker"),1);pack(summary,sh,0);G.trainer_library_view=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.trainer_library_view,TRUE);gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.trainer_library_view),"No Trainer Library scan has completed yet.",-1);GtkWidget*ss=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(ss,-1,125);gtk_container_add(ss,G.trainer_library_view);pack(summary,ss,1);pack(left,summary,0);pack(body,left,1);

    GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_size_request(right,445,-1);
    GtkWidget*target=box(GTK_ORIENTATION_VERTICAL,6);style(target,"panel");pack(target,label("SELECTION","section-kicker"),0);G.trainer_library_selected=label("Select a game in Library to assign or clear its trainer.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_selected,TRUE);pack(target,G.trainer_library_selected,0);G.trainer_library_pick=label("Select a trainer result to inspect matching, compatibility and next-launch behavior.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_pick,TRUE);pack(target,G.trainer_library_pick,0);pack(right,target,0);
    GtkWidget*guide=box(GTK_ORIENTATION_VERTICAL,7);style(guide,"panel");GtkWidget*gh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(gh,label("ACTION GUIDANCE","section-kicker"),1);G.trainer_library_recommended_action=button("No action selected","primary-action");gtk_widget_set_sensitive(G.trainer_library_recommended_action,FALSE);g_signal_connect_data(G.trainer_library_recommended_action,"clicked",(GCallback)on_trainer_library_recommended_action,NULL,NULL,0);pack(gh,G.trainer_library_recommended_action,0);pack(guide,gh,0);G.trainer_library_guidance=label("Select a result to see the safest next action.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_guidance,TRUE);pack(guide,G.trainer_library_guidance,0);pack(right,guide,0);
    GtkWidget*actions=box(GTK_ORIENTATION_VERTICAL,6);style(actions,"panel");pack(actions,label("ASSIGNMENT","section-kicker"),0);G.trainer_library_launch_assigned=button("Launch assigned trainer","primary-action");G.trainer_library_assign_suggested=button("Assign to suggested game","action");G.trainer_library_select_suggested=button("Select suggested game","action");G.trainer_library_assign_selected=button("Assign to selected game","action");G.trainer_library_open_folder=button("Open trainer folder","action");g_signal_connect_data(G.trainer_library_launch_assigned,"clicked",(GCallback)on_launch_assigned_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_assign_suggested,"clicked",(GCallback)on_assign_suggested_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_select_suggested,"clicked",(GCallback)on_select_suggested_library_game,NULL,NULL,0);g_signal_connect_data(G.trainer_library_assign_selected,"clicked",(GCallback)on_assign_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_open_folder,"clicked",(GCallback)on_open_selected_trainer_folder,NULL,NULL,0);gtk_widget_set_sensitive(G.trainer_library_launch_assigned,FALSE);gtk_widget_set_sensitive(G.trainer_library_assign_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_select_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_assign_selected,FALSE);gtk_widget_set_sensitive(G.trainer_library_open_folder,FALSE);pack(actions,G.trainer_library_launch_assigned,0);pack(actions,G.trainer_library_assign_suggested,0);pack(actions,G.trainer_library_select_suggested,0);pack(actions,G.trainer_library_assign_selected,0);pack(actions,G.trainer_library_open_folder,0);pack(right,actions,0);
    GtkWidget*policy=box(GTK_ORIENTATION_VERTICAL,6);style(policy,"panel");pack(policy,label("LAUNCH POLICY","section-kicker"),0);GtkWidget*pp=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*pp_auto=button("Auto","action");GtkWidget*pp_managed=button("Managed FLiNG","action");GtkWidget*pp_inherit=button("Inherit session","action");g_signal_connect_data(pp_auto,"clicked",(GCallback)on_profile_policy_auto,NULL,NULL,0);g_signal_connect_data(pp_managed,"clicked",(GCallback)on_profile_policy_managed,NULL,NULL,0);g_signal_connect_data(pp_inherit,"clicked",(GCallback)on_profile_policy_inherit,NULL,NULL,0);pack(pp,pp_auto,0);pack(pp,pp_managed,0);pack(pp,pp_inherit,0);pack(policy,pp,0);G.trainer_library_policy=label("Duplicate version policy: Ask","muted");pack(policy,G.trainer_library_policy,0);GtkWidget*dp=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*pask=button("Ask","action");GtkWidget*pkeep=button("Keep current","action");GtkWidget*pnew=button("Prefer newest","action");g_signal_connect_data(pask,"clicked",(GCallback)on_policy_ask,NULL,NULL,0);g_signal_connect_data(pkeep,"clicked",(GCallback)on_policy_keep,NULL,NULL,0);g_signal_connect_data(pnew,"clicked",(GCallback)on_policy_newest,NULL,NULL,0);pack(dp,pask,0);pack(dp,pkeep,0);pack(dp,pnew,0);pack(policy,dp,0);pack(right,policy,0);
    GtkWidget*maint=box(GTK_ORIENTATION_VERTICAL,6);style(maint,"panel");pack(maint,label("MAINTENANCE","section-kicker"),0);GtkWidget*mr1=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*manual=button("Choose EXE…","action");GtkWidget*clear=button("Clear assignment","action");g_signal_connect_data(manual,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);pack(mr1,manual,1);pack(mr1,clear,1);pack(maint,mr1,0);GtkWidget*mr2=box(GTK_ORIENTATION_HORIZONTAL,6);GtkWidget*ignore=button("Ignore selected","action");GtkWidget*clearignore=button("Clear ignored","action");GtkWidget*prune=button("Prune missing","action");g_signal_connect_data(ignore,"clicked",(GCallback)on_ignore_library_pick,NULL,NULL,0);g_signal_connect_data(clearignore,"clicked",(GCallback)on_clear_ignored_trainers,NULL,NULL,0);g_signal_connect_data(prune,"clicked",(GCallback)on_prune_missing_trainers,NULL,NULL,0);pack(mr2,ignore,1);pack(mr2,clearignore,1);pack(mr2,prune,1);pack(maint,mr2,0);pack(right,maint,0);pack(body,right,0);pack(p,body,1);return p;
}

static GtkWidget *build_setup(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,20);gtk_container_add(outer,p);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("SETUP","page-kicker"),0);pack(ht,label("Compatibility runtime","workspace-title"),0);pack(ht,label("GameWeld maintains its own compatibility tool and leaves your normal Proton installations untouched.","page-subtitle"),0);pack(p,ht,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*c=box(GTK_ORIENTATION_VERTICAL,8);style(c,"panel");pack(c,label("CORE STATUS","section-kicker"),0);G.setup_status=label("Checking…","metric-value");pack(c,G.setup_status,0);G.setup_detail=label("Checking compatibility…","muted");gtk_label_set_line_wrap((GtkLabel*)G.setup_detail,TRUE);pack(c,G.setup_detail,0);GtkWidget*row=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*i=button("Install / repair","primary-action");GtkWidget*v=button("Verify","action");g_signal_connect_data(i,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(v,"clicked",(GCallback)on_verify,NULL,NULL,0);pack(row,i,0);pack(row,v,0);pack(c,row,0);pack(left,c,0);GtkWidget*safety=box(GTK_ORIENTATION_VERTICAL,7);style(safety,"panel-soft");pack(safety,label("ISOLATED BY DESIGN","section-kicker"),0);GtkWidget*sd=label("Compatibility changes stay inside GameWeld's managed tool. Normal Steam Proton and Heroic runner configuration remain yours.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(safety,sd,0);pack(left,safety,0);GtkWidget*what=box(GTK_ORIENTATION_VERTICAL,8);style(what,"panel");pack(what,label("WHAT GAMEWELD MANAGES","section-kicker"),0);pack(what,label("• Steam and Proton-GE detection\n• Isolated GameWeld Steam compatibility tool\n• Proven crypt32 compatibility payload\n• Runtime verification before launch\n• No replacement of your normal Proton-GE installs","muted"),0);pack(right,what,0);GtkWidget*next=box(GTK_ORIENTATION_VERTICAL,8);style(next,"panel-soft");pack(next,label("WHEN TO USE THIS PAGE","section-kicker"),0);GtkWidget*nd=label("Use Repair only when Diagnostics reports a compatibility problem or after changing major runtime packages. Otherwise leave a working launch path alone.","muted");gtk_label_set_line_wrap((GtkLabel*)nd,TRUE);pack(next,nd,0);pack(right,next,0);pack(cols,left,1);pack(cols,right,1);pack(p,cols,1);return outer;}
static GtkWidget *build_diag(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,20);gtk_container_add(outer,p);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("SUPPORT","page-kicker"),0);pack(ht,label("Diagnostics & support","workspace-title"),0);pack(ht,label("Inspect only the selected game's launch path and export a privacy-scoped bundle when you need help.","page-subtitle"),0);pack(p,ht,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*health=box(GTK_ORIENTATION_VERTICAL,9);style(health,"panel");pack(health,label("TRAINER HEALTH","section-kicker"),0);GtkWidget*h=button("Run selected-game health check","primary-action");g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);pack(health,h,0);G.health_detail=label("Launch the selected game with its configured trainer provider, then run this check to inspect trainer and command health.","muted");gtk_label_set_line_wrap((GtkLabel*)G.health_detail,TRUE);pack(health,G.health_detail,0);pack(cols,health,1);GtkWidget*support=box(GTK_ORIENTATION_VERTICAL,9);style(support,"panel");pack(support,label("SUPPORT BUNDLE","section-kicker"),0);GtkWidget*sd=label("Exports resolved launcher/runtime/prefix metadata, trainer diagnostics, matching Trainer Library rows and selected-app logs. Trainer EXE bytes, browser data and unrelated logs are excluded.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(support,sd,0);GtkWidget*sb=button("Export selected support bundle","primary-action");g_signal_connect_data(sb,"clicked",(GCallback)on_export_support_bundle,NULL,NULL,0);pack(support,sb,0);G.support_bundle_status=label("Saved to Downloads when created.","good");gtk_label_set_line_wrap((GtkLabel*)G.support_bundle_status,TRUE);pack(support,G.support_bundle_status,0);pack(cols,support,1);pack(p,cols,0);GtkWidget*scope=box(GTK_ORIENTATION_VERTICAL,8);style(scope,"panel-soft");pack(scope,label("PRIVACY SCOPE","section-kicker"),0);pack(scope,label("Support exports are selected-game scoped. GameWeld does not include a global environment dump, browser data, trainer binaries or unrelated game logs.","muted"),0);pack(p,scope,0);return outer;}
static GtkWidget *build_settings(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,14);margins(p,22);gtk_container_add(outer,p);GtkWidget*ht=box(GTK_ORIENTATION_VERTICAL,2);pack(ht,label("PROVIDERS & ADVANCED","page-kicker"),0);pack(ht,label("Settings","workspace-title"),0);pack(ht,label("Provider configuration, compatibility tools and maintenance controls.","page-subtitle"),0);pack(p,ht,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*left=box(GTK_ORIENTATION_VERTICAL,10);GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);pack(cols,left,1);pack(cols,right,1);pack(p,cols,1);
    GtkWidget*nc=box(GTK_ORIENTATION_VERTICAL,8);style(nc,"card");pack(nc,label("Native CT Profile (No Cheat Engine)","card-title"),0);GtkWidget*nd=label("GameWeld can directly run converted table logic for supported games without Cheat Engine. Resonance: A Plague Tale Legacy has a built-in conversion of Paul44's v1.1 table with God Mode, Invisible, Resonance Points, FOV and Console controls. The original .CT is not redistributed.","muted");gtk_label_set_line_wrap((GtkLabel*)nd,TRUE);pack(nc,nd,0);GtkWidget*nr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*nen=button("Enable Native Profile","action");GtkWidget*ndis=button("Disable Native Profile","action");g_signal_connect_data(nen,"clicked",(GCallback)on_enable_native_profile,NULL,NULL,0);g_signal_connect_data(ndis,"clicked",(GCallback)on_disable_native_profile,NULL,NULL,0);pack(nr,nen,0);pack(nr,ndis,0);pack(nc,nr,0);G.native_profile_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.native_profile_status,TRUE);pack(nc,G.native_profile_status,0);pack(left,nc,0);
    GtkWidget*lc=box(GTK_ORIENTATION_VERTICAL,8);style(lc,"card");pack(lc,label("Local Trainer Provider (Unlimited)","card-title"),0);GtkWidget*desc=label("GameWeld can discover standalone Windows trainer EXEs automatically or you can choose one manually. Discovery uses standard XDG/Home folders, folders you add, and the install paths reported by Steam/Heroic; it never assumes a specific username, /mnt/games, drive layout or distro. Steam uses the proven live Proton-session handoff. Heroic games from Epic, GOG and Amazon stay launcher-native: GameWeld launches through the detected Heroic runner. For local trainers on affected Wine/Proton 11+ builds, GameWeld uses its pinned GE-Proton10-34 + Wine-Wayland compatibility session. Epic/Legendary launches through Heroic's authenticated Legendary backend with an explicit UMU environment; the trainer joins it with UMU runinprefix. GOG/Amazon retain the verified temporary Heroic handshake.","muted");gtk_label_set_line_wrap((GtkLabel*)desc,TRUE);pack(lc,desc,0);G.local_trainer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.local_trainer_entry,"No local trainer configured");pack(lc,G.local_trainer_entry,0);GtkWidget*lr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*choose=button("Choose Trainer EXE","action");GtkWidget*scan=button("Scan / Auto-Match Trainers","action");GtkWidget*addfolder=button("Add Trainer Folder","action");GtkWidget*clear=button("Clear Trainer","action");g_signal_connect_data(choose,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(addfolder,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);pack(lr,choose,0);pack(lr,scan,0);pack(lr,addfolder,0);pack(lr,clear,0);pack(lc,lr,0);GtkWidget*hr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*stop=button("Stop Stuck Trainer","action");GtkWidget*reset=button("Reset Heroic Prefix (Closes Game)","action");g_signal_connect_data(stop,"clicked",(GCallback)on_stop_heroic_trainer,NULL,NULL,0);g_signal_connect_data(reset,"clicked",(GCallback)on_reset_heroic_prefix,NULL,NULL,0);pack(hr,stop,0);pack(hr,reset,0);pack(lc,hr,0);GtkWidget*compat=label("Heroic FLiNG compatibility engine: normal desktop windows are used. The engine is game-agnostic and scoped to the exact Heroic installation discovered for the selected title. On affected Wine/Proton 11+ builds, game and trainer share pinned GE-Proton10-34 with Wine-Wayland. Epic/Legendary uses matching UMU runinprefix instead of host Wine, so a trainer cannot be deferred until after game exit.","muted");gtk_label_set_line_wrap((GtkLabel*)compat,TRUE);pack(lc,compat,0);G.local_trainer_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.local_trainer_status,TRUE);pack(lc,G.local_trainer_status,0);pack(left,lc,0);
    GtkWidget*cc=box(GTK_ORIENTATION_VERTICAL,8);style(cc,"card");pack(cc,label("Managed Cheat Engine Provider (.CT)","card-title"),0);GtkWidget*cd=label("GameWeld uses the official Cheat Engine Linux package as the native bridge and a shared Windows CE companion in windowsbin. Steam handoff joins the verified Proton session; Heroic handoff waits for the real game process and asks Heroic to launch Windows CE as an alternate executable using that game's configured Wine/Proton runner. Install the bridge and Windows companion once. Cheat Engine itself is not bundled inside GameWeld.","muted");gtk_label_set_line_wrap((GtkLabel*)cd,TRUE);pack(cc,cd,0);G.cheat_engine_installer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_installer_entry,"Official CheatEngineLinux771.zip or Windows CE installer/ZIP");pack(cc,G.cheat_engine_installer_entry,0);G.cheat_engine_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_entry,"Managed native Linux CE appears here after install");pack(cc,G.cheat_engine_entry,0);G.cheat_table_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_table_entry,"No .CT table configured for selected game");pack(cc,G.cheat_table_entry,0);GtkWidget*cr0=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceauto=button("Download + Install Linux CE","action");GtkWidget*cedl=button("Open Official Linux ZIP","action");GtkWidget*cewin=button("Open Official Windows CE","action");GtkWidget*cei=button("Choose CE Package","action");g_signal_connect_data(ceauto,"clicked",(GCallback)on_download_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cedl,"clicked",(GCallback)on_open_cheat_engine_download,NULL,NULL,0);g_signal_connect_data(cewin,"clicked",(GCallback)on_open_cheat_engine_windows_download,NULL,NULL,0);g_signal_connect_data(cei,"clicked",(GCallback)on_choose_cheat_engine_installer,NULL,NULL,0);pack(cr0,ceauto,0);pack(cr0,cedl,0);pack(cr0,cewin,0);pack(cr0,cei,0);pack(cc,cr0,0);GtkWidget*cr1=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceinstall=button("Install Selected Package","action");GtkWidget*ced=button("Detect / Refresh CE","action");GtkWidget*cce=button("Choose Existing CE","action");GtkWidget*cct=button("Choose .CT Table","action");g_signal_connect_data(ceinstall,"clicked",(GCallback)on_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(ced,"clicked",(GCallback)on_detect_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cce,"clicked",(GCallback)on_choose_cheat_engine,NULL,NULL,0);g_signal_connect_data(cct,"clicked",(GCallback)on_choose_cheat_table,NULL,NULL,0);pack(cr1,ceinstall,0);pack(cr1,ced,0);pack(cr1,cce,0);pack(cr1,cct,0);pack(cc,cr1,0);GtkWidget*cr2=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*cte=button("Clear External CE","action");GtkWidget*ctt=button("Clear Table","action");g_signal_connect_data(cte,"clicked",(GCallback)on_clear_cheat_engine,NULL,NULL,0);g_signal_connect_data(ctt,"clicked",(GCallback)on_clear_cheat_table,NULL,NULL,0);pack(cr2,cte,0);pack(cr2,ctt,0);pack(cc,cr2,0);G.cheat_table_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.cheat_table_status,TRUE);pack(cc,G.cheat_table_status,0);pack(right,cc,0);
    GtkWidget*scard=box(GTK_ORIENTATION_VERTICAL,8);style(scard,"card");pack(scard,label("Steam Direct Launch Cleanup","card-title"),0);GtkWidget*sd=label("Older pre-GameWeld builds could leave the legacy wand-steam-wrap hook in a game's Steam Launch Options. Steam can still invoke that obsolete hook and leave a terminal attached to the game. This cleanup removes only LaunchOptions entries that still reference wand-steam-wrap and creates a timestamped localconfig.vdf backup first.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(scard,sd,0);GtkWidget*sbtn=button("Remove Legacy Steam Hooks","action");g_signal_connect_data(sbtn,"clicked",(GCallback)on_clean_legacy_hooks,NULL,NULL,0);pack(scard,sbtn,0);G.steam_cleanup_status=label("After cleanup, restart Steam once before testing direct Play.","good");gtk_label_set_line_wrap((GtkLabel*)G.steam_cleanup_status,TRUE);pack(scard,G.steam_cleanup_status,0);pack(right,scard,0);pack(right,card("Safety","Use native profiles, local trainers and Cheat Engine tables for single-player/offline games. Do not use them in anti-cheat protected or competitive multiplayer modes. No provider bypasses anti-cheat systems.",NULL),0);return outer;}
static GtkWidget *build_about(void){GtkWidget*outer=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)outer,GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);style(outer,"page-shell");GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,16);margins(p,24);gtk_container_add(outer,p);GtkWidget*hero=box(GTK_ORIENTATION_VERTICAL,6);gtk_widget_set_halign(hero,GTK_ALIGN_CENTER);GtkWidget*wm=asset_image("gameweld-brand-logo.png",540,180);if(wm){gtk_widget_set_halign(wm,GTK_ALIGN_CENTER);pack(hero,wm,0);}else{wm=label("GameWeld",NULL);gtk_widget_set_name(wm,"section-title");gtk_widget_set_halign(wm,GTK_ALIGN_CENTER);pack(hero,wm,0);}GtkWidget*v=label("0.4.0 RC1 • release candidate","page-subtitle");gtk_widget_set_halign(v,GTK_ALIGN_CENTER);pack(hero,v,0);pack(p,hero,0);GtkWidget*cols=box(GTK_ORIENTATION_HORIZONTAL,14);GtkWidget*c1=box(GTK_ORIENTATION_VERTICAL,8);style(c1,"panel");pack(c1,label("WHAT IT DOES","section-kicker"),0);pack(c1,label("Unified Steam, Steam non-Steam shortcut and Heroic game discovery\nTrainer Library with conservative automatic matching\nValidated live-session trainer handoff\nManaged Heroic FLiNG compatibility sessions\nPrivacy-scoped diagnostics and support bundles","muted"),0);GtkWidget*c2=box(GTK_ORIENTATION_VERTICAL,8);style(c2,"panel");pack(c2,label("DESIGN PRINCIPLES","section-kicker"),0);pack(c2,label("Game-first navigation\nOne clear primary action per context\nLauncher-native runtime ownership\nVisible readiness before launch\nAdvanced controls kept out of the main workflow","muted"),0);pack(cols,c1,1);pack(cols,c2,1);pack(p,cols,0);GtkWidget*f=label("Open source • MIT • Play more, your way.","muted");gtk_widget_set_halign(f,GTK_ALIGN_CENTER);pack(p,f,0);return outer;}

static void build_ui(void){
    G.window=gtk_window_new(GTK_WINDOW_TOPLEVEL);gtk_window_set_title((GtkWindow*)G.window,"GameWeld");gtk_window_set_icon_name((GtkWindow*)G.window,"gameweld");gtk_window_set_default_size((GtkWindow*)G.window,1480,900);gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);gtk_window_set_decorated((GtkWindow*)G.window,TRUE);g_signal_connect_data(G.window,"destroy",(GCallback)on_destroy,NULL,NULL,0);
    GtkWidget*titlebar=box(GTK_ORIENTATION_HORIZONTAL,12);gtk_widget_set_name(titlebar,"app-titlebar");gtk_widget_set_size_request(titlebar,-1,54);gtk_widget_set_margin_start(titlebar,14);gtk_widget_set_margin_end(titlebar,10);
    GtkWidget*titlebrand=box(GTK_ORIENTATION_HORIZONTAL,10);gtk_widget_set_name(titlebrand,"title-brand");GtkWidget*wm=asset_image("gameweld-app-icon.png",36,36);if(!wm){wm=label("GW",NULL);gtk_widget_set_name(wm,"wandmark");}pack(titlebrand,wm,0);GtkWidget*bt=box(GTK_ORIENTATION_VERTICAL,0);GtkWidget*brand=label("GameWeld",NULL);gtk_widget_set_name(brand,"brand");pack(bt,brand,0);GtkWidget*ver=label("0.4.0 • RC1",NULL);gtk_widget_set_name(ver,"brandver");pack(bt,ver,0);pack(titlebrand,bt,0);pack(titlebar,titlebrand,0);
    GtkWidget*grow=box(GTK_ORIENTATION_HORIZONTAL,0);pack(titlebar,grow,1);GtkWidget*searchwrap=box(GTK_ORIENTATION_HORIZONTAL,0);gtk_widget_set_name(searchwrap,"global-search-wrap");G.search_scope=gtk_combo_box_text_new();gtk_widget_set_name(G.search_scope,"global-search-scope");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"all","All games");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"steam","Steam");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"shortcut","Steam shortcuts");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"heroic","Heroic");gtk_combo_box_text_append((GtkComboBoxText*)G.search_scope,"trainers","Trainers");gtk_combo_box_set_active_id((GtkComboBox*)G.search_scope,"all");gtk_widget_set_size_request(G.search_scope,126,36);g_signal_connect_data(G.search_scope,"changed",(GCallback)on_search_scope_changed,NULL,NULL,0);pack(searchwrap,G.search_scope,0);G.search=gtk_entry_new();gtk_widget_set_name(G.search,"global-search-entry");gtk_entry_set_placeholder_text((GtkEntry*)G.search,"Search all games…");gtk_entry_set_icon_from_icon_name((GtkEntry*)G.search,GTK_ENTRY_ICON_PRIMARY,"system-search-symbolic");gtk_widget_set_size_request(G.search,250,36);g_signal_connect_data(G.search,"changed",(GCallback)on_search,NULL,NULL,0);pack(searchwrap,G.search,0);pack(titlebar,searchwrap,0);GtkWidget*grow2=box(GTK_ORIENTATION_HORIZONTAL,0);pack(titlebar,grow2,1);G.top_steam_status=label("Detecting game sources…","muted");pack(titlebar,G.top_steam_status,0);pack(titlebar,gtk_separator_new(GTK_ORIENTATION_VERTICAL),0);GtkWidget*mi=button("—","windowctl");GtkWidget*ma=button("□","windowctl");GtkWidget*cl=button("×","windowctl");gtk_widget_set_name(cl,"closectl");g_signal_connect_data(mi,"clicked",(GCallback)on_minimize,NULL,NULL,0);g_signal_connect_data(ma,"clicked",(GCallback)on_maximize,NULL,NULL,0);g_signal_connect_data(cl,"clicked",(GCallback)on_close_btn,NULL,NULL,0);pack(titlebar,mi,0);pack(titlebar,ma,0);pack(titlebar,cl,0);gtk_window_set_titlebar((GtkWindow*)G.window,titlebar);
    GtkWidget*root=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_name(root,"root");gtk_container_add(G.window,root);GtkWidget*nav=box(GTK_ORIENTATION_HORIZONTAL,5);gtk_widget_set_name(nav,"navstrip");G.nav_home=make_nav("go-home-symbolic","Overview",(GCallback)nav_home);G.nav_library=make_nav("view-grid-symbolic","Library",(GCallback)nav_library);G.nav_trainers=make_nav("applications-engineering-symbolic","Trainer Library",(GCallback)nav_trainers);G.nav_setup=make_nav("emblem-system-symbolic","Compatibility",(GCallback)nav_setup);G.nav_diag=make_nav("help-browser-symbolic","Support",(GCallback)nav_diag);G.nav_settings=make_nav("preferences-system-symbolic","Settings",(GCallback)nav_settings);G.nav_about=make_nav("dialog-information-symbolic","About",(GCallback)nav_about);pack(nav,G.nav_home,0);pack(nav,G.nav_library,0);pack(nav,G.nav_trainers,0);pack(nav,gtk_separator_new(GTK_ORIENTATION_VERTICAL),0);pack(nav,G.nav_setup,0);pack(nav,G.nav_diag,0);GtkWidget*ng=box(GTK_ORIENTATION_HORIZONTAL,0);pack(nav,ng,1);GtkWidget*hint=label("Ctrl+F Search","command-hint");pack(nav,hint,0);pack(nav,G.nav_settings,0);pack(nav,G.nav_about,0);pack(root,nav,0);
    G.stack=gtk_stack_new();gtk_stack_set_hhomogeneous((GtkStack*)G.stack,FALSE);gtk_stack_set_vhomogeneous((GtkStack*)G.stack,FALSE);gtk_widget_set_hexpand(G.stack,TRUE);gtk_widget_set_vexpand(G.stack,TRUE);gtk_stack_add_named((GtkStack*)G.stack,build_home(),"home");gtk_stack_add_named((GtkStack*)G.stack,build_library(),"library");gtk_stack_add_named((GtkStack*)G.stack,build_trainer_library(),"trainers");gtk_stack_add_named((GtkStack*)G.stack,build_setup(),"setup");gtk_stack_add_named((GtkStack*)G.stack,build_diag(),"diag");gtk_stack_add_named((GtkStack*)G.stack,build_settings(),"settings");gtk_stack_add_named((GtkStack*)G.stack,build_about(),"about");pack(root,G.stack,1);
    {const char*start=getenv("WAND_NATIVE_START_PAGE");if(start&&!*start)start=NULL;if(start&&!strcmp(start,"library"))nav_activate(G.nav_library,"library");else if(start&&!strcmp(start,"trainers"))nav_activate(G.nav_trainers,"trainers");else if(start&&!strcmp(start,"setup"))nav_activate(G.nav_setup,"setup");else if(start&&!strcmp(start,"diag"))nav_activate(G.nav_diag,"diag");else if(start&&!strcmp(start,"settings"))nav_activate(G.nav_settings,"settings");else if(start&&!strcmp(start,"about"))nav_activate(G.nav_about,"about");else nav_activate(G.nav_home,"home");}
    if(G.game_count>0){G.selected=0;gtk_list_box_select_row((GtkListBox*)G.game_list,(GtkListBoxRow*)G.game_rows[0]);}refresh_ui();log_line("Refreshing installed game sources...");log_line("Steam games detected: %d (%d installed manifest(s) + %d non-Steam shortcut(s))",G.steam_game_count,G.steam_manifest_game_count,G.steam_shortcut_count);log_line("Heroic games detected: %d",G.heroic_game_count);if(G.wand_installed)log_line("Steam trainer provider ready");if(G.wand_healthy)log_line("Steam Proton tool ready: GE-Proton-Wand-SHA256");log_line("GameWeld providers ready.");if(G.legacy_wrapper_neutralized)log_line("Legacy Steam wand-steam-wrap neutralized; direct Steam Play will no longer auto-start Wand. Backup: %s",G.legacy_wrapper_backup);GtkCssProvider*prov=gtk_css_provider_new();gtk_css_provider_load_from_data(prov,CSS,-1,NULL);gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),prov,GTK_STYLE_PROVIDER_PRIORITY_USER);g_object_unref(prov);gtk_widget_show_all(G.window);{const char*sp=getenv("WAND_NATIVE_START_PAGE");if(sp&&*sp&&(!strcmp(sp,"library")||!strcmp(sp,"trainers")||!strcmp(sp,"setup")||!strcmp(sp,"diag")||!strcmp(sp,"settings")||!strcmp(sp,"about")))gtk_stack_set_visible_child_name((GtkStack*)G.stack,sp);}start_trainer_library_scan();g_idle_add(force_mockup_geometry,NULL);g_timeout_add(180,force_mockup_geometry,NULL);g_timeout_add(1000,heroic_session_status_tick,NULL);
}

int main(int argc,char**argv){memset(&G,0,sizeof G);G.selected=-1;clear_desktop_activation_env();if(argc>1&&!strcmp(argv[1],"--cleanup-steam-hooks")){char backup[2048]={0};int files=0;int n=cleanup_legacy_steam_hooks(backup,sizeof backup,&files);if(n>0){printf("Removed legacy wand-steam-wrap Launch Options from %d Steam config file(s).\n",files);if(backup[0])printf("Last backup: %s\n",backup);printf("Restart Steam once before testing direct Play.\n");return 0;}printf("No legacy wand-steam-wrap Launch Options found.\n");return 0;}G.legacy_wrapper_neutralized=neutralize_legacy_wrapper();gtk_init(&argc,&argv);if(!start_backend()){fprintf(stderr,"Could not start GameWeld backend.\n");return 2;}char *e=NULL;if(!refresh_model(&e)){fprintf(stderr,"Backend status failed: %s\n",e?e:"unknown");free(e);}build_ui();gtk_main();if(G.backend_pid>0){kill(G.backend_pid,SIGTERM);waitpid(G.backend_pid,NULL,WNOHANG);}return 0;}
