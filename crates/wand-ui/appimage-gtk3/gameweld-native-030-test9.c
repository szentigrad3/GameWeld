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
    char key[320];
    char provider[32];
    char runner[48];
    char name[384];
    char install_dir[1024];
    char executable[1024];
    char prefix[1024];
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
    GtkWidget *trainer_library_attention_toggle;
    GtkWidget *trainer_library_policy;
    GtkWidget *trainer_library_assign_suggested;
    GtkWidget *trainer_library_select_suggested;
    GtkWidget *trainer_library_assign_selected;
    GtkWidget *trainer_library_open_folder;
    char trainer_library_pick_path[2048];
    char trainer_library_pick_game[512];
    char trainer_library_pick_key[320];
    char trainer_library_pick_state[64];
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
    GtkWidget *quick_store;
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
"window{background:#07101b}"
"#root{background-image:linear-gradient(145deg,#0a1421,#070d16 58%,#0a111c)}"
"#app-titlebar{background:#0a121e;border-bottom:1px solid #243347}"
"#title-brand{background-image:linear-gradient(180deg,#121e2e,#0d1623);border-right:1px solid #263548}"
"#sidebar{background-image:linear-gradient(180deg,#121e2e,#0d1623);border-right:1px solid #263548}"
"#topbar{background:#0a121e;border-bottom:1px solid #243347;min-height:78px}"
"#brand{color:#f7f8fb;font-size:24px;font-weight:800}"
"#brandver{color:#aeb8c6;font-size:12px}"
"#wandmark{color:#a53cff;font-size:40px;font-weight:900}"
".nav{background:transparent;color:#e2e7ef;border:0;border-radius:10px;padding:16px 15px;font-size:17px;box-shadow:none;min-height:54px}"
".nav:hover{background:rgba(255,255,255,.055)}"
".nav-active{background-color:#552693;background-image:linear-gradient(90deg,#7430d0,#4b247f);color:white;font-weight:700;border-left:4px solid #b23cff}"
"entry{background:#152132;color:#e9eef6;border:1px solid #33465e;border-radius:20px;padding:0 18px;font-size:15px;min-height:42px}"
"#page{background:transparent}"
".card{background-image:linear-gradient(180deg,#121d2b,#0f1926);color:#e8edf5;border:1px solid #2a3a4e;border-radius:12px;padding:15px}"
".card-title{color:#f6f8fb;font-size:17px;font-weight:800}"
".muted{color:#abb6c5;font-size:13px}"
".good{color:#28e57b;font-size:13px;font-weight:700}"
".purple{color:#a944ff;font-weight:800}"
"#game-title{color:#f8f9fb;font-size:31px;font-weight:800;margin:0 8px}"
"#meta{color:#bdc7d4;font-size:14px;margin:0 6px}"
".meta-chip{background-image:linear-gradient(180deg,#192434,#131d2b);border:1px solid #34465d;border-radius:16px;padding:5px 13px;color:#f1f4f8;font-size:13px}"
".launch-shell{background-image:linear-gradient(180deg,#111c29,#0d1621);border:1px solid #26384e;border-radius:12px;padding:9px}"
"#play{background-image:linear-gradient(180deg,#ffe23d,#ffc72d);color:#090909;border:1px solid #ffdc36;border-radius:11px;padding:0;box-shadow:0 4px 15px rgba(0,0,0,.45);min-height:88px}"
"#play:hover{background-image:linear-gradient(180deg,#ffe85e,#ffd13b)}"
"#play .launch-icon,#play .launch-title,#play .launch-subtitle{color:#090909}"
".launch-icon{font-size:34px;font-weight:900}"
".launch-title{font-size:23px;font-weight:900}"
".launch-subtitle{font-size:14px;font-weight:500}"
"#normal{background-image:linear-gradient(180deg,#172437,#111c2a);color:#f4f6f9;border:1px solid #35465d;border-radius:11px;padding:0;min-height:88px}"
"#normal:hover{background-image:linear-gradient(180deg,#1c2a3d,#152234)}"
"#normal .launch-icon,#normal .normal-title,#normal .normal-subtitle{color:#f3f6fb}"
".normal-title{font-size:17px;font-weight:800}"
".normal-subtitle{font-size:13px;color:#aeb9c7}"
".info-card{min-height:128px;padding:16px}"
".info-icon{font-size:31px;font-weight:800;color:#eef3f9}"
".info-icon-wand{font-size:38px;font-weight:900;color:#a83cff}"
".action{background-image:linear-gradient(180deg,#19273a,#142132);color:#edf1f6;border:1px solid #34465c;border-radius:8px;padding:5px 10px;font-size:13px;min-height:36px}"
".action:hover{background:#223248}"
".windowctl{background:transparent;color:#dce3ec;border:0;box-shadow:none;padding:5px 9px;font-size:17px}"
".windowctl:hover{background:rgba(255,255,255,.07)}#closectl:hover{background:#b32635}"
"list{background:transparent}row{background:transparent;color:#d8e0ea;border-radius:9px;margin:2px 0}row:selected{background:#27334a;color:white}"
"textview,textview text{background:#080d14;color:#c1ccd9;font-family:Monospace;font-size:12px}"
"#logframe{background:#080d14;border:1px solid #202e3e;border-radius:9px}"
"#section-title{color:#f5f7fb;font-size:25px;font-weight:800}"
"#status-pill{background:#0e4328;color:#3bed8d;border-radius:14px;padding:6px 13px;font-size:13px;font-weight:800}"
"#sidebar-foot{background:#111c2a;border:1px solid #304055;border-radius:11px;padding:16px;min-height:126px}"
"#hero-frame{background:#101923;border:1px solid #26364a;border-radius:11px}"
".status-card{min-height:153px;padding:15px}"
"#footer{color:#78869a;font-size:11px;padding:4px 0}"
".nav-icon{color:#e8edf5}"
".nav-label{color:#e8edf5;font-size:17px;font-weight:600}"
".quick-label{color:#e3e9f1;font-size:13px}"
".quick-chevron{color:#aeb9c7;font-size:14px}"
".game-row-title{font-size:15px;font-weight:800}.game-thumb{background:#0b121c;border:1px solid #2b3b50;border-radius:7px;padding:2px}\n";

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
static int game_is_steam(const Game *g){return !g||!g->provider[0]||!strcmp(g->provider,"steam");}
static const char *game_ce_id(const Game *g){return game_is_steam(g)?g->appid:"0";}
static const char *heroic_provider_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-provider.py",a);else snprintf(p,sizeof p,"gameweld-heroic-provider.py");return p;}
static const char *heroic_launch_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-launch.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-launch.sh");return p;}
static const char *heroic_cheat_table_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-cheat-table.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-cheat-table.sh");return p;}
static const char *heroic_local_trainer_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-local-trainer.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-local-trainer.sh");return p;}
static const char *heroic_session_control_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-session-control.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-session-control.sh");return p;}
static const char *heroic_trainer_runtime_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-heroic-trainer-runtime.sh",a);else snprintf(p,sizeof p,"gameweld-heroic-trainer-runtime.sh");return p;}
static const char *trainer_library_tool(void){static char p[2048];const char*a=getenv("APPDIR");if(a&&*a)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-trainer-library.py",a);else snprintf(p,sizeof p,"gameweld-trainer-library.py");return p;}

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
    G.steam_game_count=parse_games(body); G.game_count=append_heroic_games(G.steam_game_count); G.heroic_game_count=G.game_count-G.steam_game_count; if(G.selected>=G.game_count)G.selected=G.game_count?0:-1; free(body); return 1;
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

enum { TL_GAME=0, TL_CONF, TL_VERSION, TL_HEALTH, TL_REASON, TL_TRAINER, TL_FOLDER, TL_PATH, TL_KEY, TL_STATE, TL_COLS };

static GtkWidget *trainer_tree_new(void){
    GtkListStore *store=gtk_list_store_new(TL_COLS,g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"),g_type_from_name("gchararray"));
    GtkWidget *view=gtk_tree_view_new_with_model((GtkTreeModel*)store);
    g_object_unref(store);
    gtk_tree_view_set_headers_visible((GtkTreeView*)view,TRUE);
    GtkCellRenderer *r=gtk_cell_renderer_text_new();
    gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Status",r,"text",TL_STATE,NULL);
    r=gtk_cell_renderer_text_new();
    gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Game",r,"text",TL_GAME,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Confidence",r,"text",TL_CONF,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Version",r,"text",TL_VERSION,NULL);
    r=gtk_cell_renderer_text_new();gtk_tree_view_insert_column_with_attributes((GtkTreeView*)view,-1,"Health",r,"text",TL_HEALTH,NULL);
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
    if(G.trainer_library_assign_suggested)gtk_widget_set_sensitive(G.trainer_library_assign_suggested,have_pick&&suggested>=0);
    if(G.trainer_library_select_suggested)gtk_widget_set_sensitive(G.trainer_library_select_suggested,suggested>=0);
    if(G.trainer_library_assign_selected){
        int safe=have_pick&&selected_ok;
        if(safe&&trainer_pick_is_strong_target()&&suggested>=0&&!selected_matches)safe=0;
        gtk_widget_set_sensitive(G.trainer_library_assign_selected,safe);
    }
    if(G.trainer_library_open_folder)gtk_widget_set_sensitive(G.trainer_library_open_folder,have_pick);
}

static void trainer_pick_changed(GtkTreeSelection *sel,void*d){
    (void)d;GtkTreeModel*m=NULL;GtkTreeIter it;
    if(!gtk_tree_selection_get_selected(sel,&m,&it))return;
    char *game=NULL,*conf=NULL,*version=NULL,*health=NULL,*reason=NULL,*path=NULL,*key=NULL,*state=NULL,*folder=NULL;
    gtk_tree_model_get(m,&it,TL_GAME,&game,TL_CONF,&conf,TL_VERSION,&version,TL_HEALTH,&health,TL_REASON,&reason,TL_PATH,&path,TL_KEY,&key,TL_STATE,&state,TL_FOLDER,&folder,-1);
    if(path&&*path){
        snprintf(G.trainer_library_pick_path,sizeof G.trainer_library_pick_path,"%s",path);
        snprintf(G.trainer_library_pick_game,sizeof G.trainer_library_pick_game,"%s",game?game:"");
        snprintf(G.trainer_library_pick_key,sizeof G.trainer_library_pick_key,"%s",key?key:"");
        snprintf(G.trainer_library_pick_state,sizeof G.trainer_library_pick_state,"%s",state?state:"");
        if(G.trainer_library_pick){
            char msg[4096];int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);
            snprintf(msg,sizeof msg,"Selected trainer: %s\nStatus: %s • Health: %s • Suggested game: %s%s%s%s%s",path,(state&&*state)?state:"UNMATCHED",(health&&*health)?health:"—",(game&&*game)?game:"unmatched",(conf&&*conf)?" • confidence ":"",(conf&&*conf)?conf:"",(version&&*version)?" • version ":"",(version&&*version)?version:"");
            if(reason&&*reason){strncat(msg,"\nWhy: ",sizeof msg-strlen(msg)-1);strncat(msg,reason,sizeof msg-strlen(msg)-1);}
            if(folder&&*folder){strncat(msg,"\nSource folder: ",sizeof msg-strlen(msg)-1);strncat(msg,folder,sizeof msg-strlen(msg)-1);}
            if(G.selected>=0&&G.selected<G.game_count&&suggested>=0&&strcmp(game_key(&G.games[G.selected]),G.trainer_library_pick_key)){
                strncat(msg,"\nSafety: the currently selected Library game is different. Use Assign to Suggested Game, or choose the intended game first.",sizeof msg-strlen(msg)-1);
            }
            set_label(G.trainer_library_pick,msg);
        }
    }
    update_trainer_library_actions();
    g_free(game);g_free(conf);g_free(version);g_free(health);g_free(reason);g_free(path);g_free(key);g_free(state);g_free(folder);
}

static void trainer_attention_game_changed(GtkTreeSelection*sel,void*d){
    (void)d;GtkTreeModel*m=NULL;GtkTreeIter it;if(!gtk_tree_selection_get_selected(sel,&m,&it))return;char*key=NULL,*game=NULL;gtk_tree_model_get(m,&it,TG_KEY,&key,TG_GAME,&game,-1);int idx=trainer_game_index_by_key(key);if(idx>=0){G.selected=idx;refresh_ui();if(G.trainer_library_selected){char lt[2048]={0},msg[4096];int mapped=load_local_trainer(game_key(&G.games[idx]),lt,sizeof lt);if(mapped&&readable_file(lt))snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Valid",G.games[idx].name,lt);else if(mapped)snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: %s\nHealth: Missing",G.games[idx].name,lt);else snprintf(msg,sizeof msg,"Selected game: %s\nAssigned trainer: none",G.games[idx].name);set_label(G.trainer_library_selected,msg);}update_trainer_library_actions();}g_free(key);g_free(game);
}

static void trainer_store_add(GtkWidget *view,const char *state,const char *game,const char *score,const char *reason,const char *path,const char *source,const char *key,const char *version,const char *health){
    if(!view||!path||!*path)return;GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)view);if(!m)return;GtkListStore*st=(GtkListStore*)m;GtkTreeIter it;const char*base=strrchr(path,'/');base=base?base+1:path;char conf[64];if(score&&atoi(score)>0)snprintf(conf,sizeof conf,"%s%%",score);else snprintf(conf,sizeof conf,"—");const char *shown_state=!strcmp(state?state:"","ASSIGNED")?"Assigned":(!strcmp(state?state:"","MATCH")?"Matched":(!strcmp(state?state:"","ALTERNATE")?"Alternative":(!strcmp(state?state:"","AMBIG")?"Ambiguous":(!strcmp(state?state:"","MISSING")?"Missing":"Unmatched"))));gtk_list_store_append(st,&it);gtk_list_store_set(st,&it,TL_GAME,(game&&*game)?game:"—",TL_CONF,conf,TL_VERSION,(version&&*version)?version:"—",TL_HEALTH,(health&&*health)?health:"—",TL_REASON,reason?reason:"",TL_TRAINER,base,TL_FOLDER,source?source:"",TL_PATH,path,TL_KEY,key?key:"",TL_STATE,shown_state,-1);
}

static void refresh_trainer_library_rows(void){
    GtkWidget*views[5]={G.trainer_library_matched,G.trainer_library_alternates,G.trainer_library_ambiguous,G.trainer_library_unmatched,G.trainer_library_health};for(int i=0;i<5;i++)if(views[i]){GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)views[i]);if(m)gtk_list_store_clear((GtkListStore*)m);}
    if(G.trainer_library_attention_games){GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)G.trainer_library_attention_games);if(m)gtk_list_store_clear((GtkListStore*)m);}
    if(!G.trainer_library_matched&&!G.trainer_library_alternates&&!G.trainer_library_ambiguous&&!G.trainer_library_unmatched&&!G.trainer_library_health&&!G.trainer_library_attention_games)return;
    const char*q=trainer_library_query();const char*sort=trainer_library_sort_id();int attention=trainer_library_attention_only();
    int fd[2];if(pipe(fd)!=0)return;pid_t p=fork();
    if(p==0){close(fd[0]);dup2(fd[1],STDOUT_FILENO);close(fd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}if(attention)execlp("python3","python3",trainer_library_tool(),"rows","--query",q?q:"","--sort",sort,"--attention",(char*)NULL);else execlp("python3","python3",trainer_library_tool(),"rows","--query",q?q:"","--sort",sort,(char*)NULL);_exit(127);}
    close(fd[1]);FILE*f=fdopen(fd[0],"r");char line[8192];int found_pick=0;
    if(f){while(fgets(line,sizeof line,f)){line[strcspn(line,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(line,"\t",&save);char*state=strtok_r(NULL,"\t",&save);char*key=strtok_r(NULL,"\t",&save);char*game=strtok_r(NULL,"\t",&save);char*score=strtok_r(NULL,"\t",&save);char*reason=strtok_r(NULL,"\t",&save);char*path=strtok_r(NULL,"\t",&save);char*source=strtok_r(NULL,"\t",&save);char*version=strtok_r(NULL,"\t",&save);char*health=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"ROW")||!state||!path)continue;GtkWidget*v=(!strcmp(state,"MATCH")||!strcmp(state,"ASSIGNED"))?G.trainer_library_matched:(!strcmp(state,"ALTERNATE")?G.trainer_library_alternates:(!strcmp(state,"AMBIG")?G.trainer_library_ambiguous:(!strcmp(state,"MISSING")?G.trainer_library_health:G.trainer_library_unmatched)));trainer_store_add(v,state,game,score,reason,path,source,key,version,health);if(G.trainer_library_pick_path[0]&&!strcmp(G.trainer_library_pick_path,path))found_pick=1;}fclose(f);}else close(fd[0]);int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}
    if(G.trainer_library_attention_games){int gd[2];if(pipe(gd)==0){pid_t gp=fork();if(gp==0){close(gd[0]);dup2(gd[1],STDOUT_FILENO);close(gd[1]);int dn=open("/dev/null",O_WRONLY);if(dn>=0){dup2(dn,STDERR_FILENO);if(dn>2)close(dn);}const char*gsort=!strcmp(sort,"confidence")?"confidence":"game";execlp("python3","python3",trainer_library_tool(),"game-rows","--query",q?q:"","--sort",gsort,(char*)NULL);_exit(127);}close(gd[1]);FILE*gf=fdopen(gd[0],"r");if(gf){while(fgets(line,sizeof line,gf)){line[strcspn(line,"\r\n")]=0;char*save=NULL;char*kind=strtok_r(line,"\t",&save);char*state=strtok_r(NULL,"\t",&save);char*key=strtok_r(NULL,"\t",&save);char*game=strtok_r(NULL,"\t",&save);char*score=strtok_r(NULL,"\t",&save);char*issue=strtok_r(NULL,"\t",&save);char*detail=strtok_r(NULL,"\t",&save);if(!kind||strcmp(kind,"GAME")||!state||!key||!game)continue;GtkTreeModel*m=gtk_tree_view_get_model((GtkTreeView*)G.trainer_library_attention_games);GtkListStore*ls=(GtkListStore*)m;GtkTreeIter it;char conf[64];if(score&&atoi(score)>0)snprintf(conf,sizeof conf,"%s%%",score);else snprintf(conf,sizeof conf,"—");const char*shown=!strcmp(state,"MISSING")?"Missing":(!strcmp(state,"AMBIG")?"Ambiguous":"No trainer");char why[2048];snprintf(why,sizeof why,"%s%s%s",issue?issue:"",(detail&&*detail&&strcmp(detail,"—"))?" — ":"",(detail&&*detail&&strcmp(detail,"—"))?detail:"");gtk_list_store_append(ls,&it);gtk_list_store_set(ls,&it,TG_STATE,shown,TG_GAME,game,TG_CONF,conf,TG_ISSUE,why,TG_KEY,key,-1);}fclose(gf);}else close(gd[0]);int gst=0;if(gp>0)while(waitpid(gp,&gst,0)<0&&errno==EINTR){}}}
    if(G.trainer_library_pick_path[0]&&!found_pick&&!attention){G.trainer_library_pick_path[0]=0;G.trainer_library_pick_game[0]=0;G.trainer_library_pick_key[0]=0;G.trainer_library_pick_state[0]=0;if(G.trainer_library_pick)set_label(G.trainer_library_pick,"Select a trainer row to review its suggested game/version, assign it safely, reassign an ambiguous/unmatched trainer, or ignore it.");}
    update_trainer_library_actions();
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
        if(G.steam_cleanup_status)gtk_label_set_text((GtkLabel*)G.steam_cleanup_status,"Legacy Wand launch hooks removed. Restart Steam once, then direct Play will be normal.");
    }else{
        log_line("No legacy wand-steam-wrap Launch Options were found in Steam localconfig.vdf files.");
        if(G.steam_cleanup_status)gtk_label_set_text((GtkLabel*)G.steam_cleanup_status,"No legacy wand-steam-wrap Launch Options found.");
    }
}

static const char *local_trainer_launcher(void){static char p[2048];const char *appdir=getenv("APPDIR");if(appdir&&*appdir)snprintf(p,sizeof p,"%s/usr/libexec/gameweld-local-trainer.sh",appdir);else snprintf(p,sizeof p,"gameweld-local-trainer.sh");return p;}
static void spawn_local_trainer(const char *appid,const char *trainer){pid_t p=fork();if(p==0){execl(local_trainer_launcher(),local_trainer_launcher(),appid,trainer,(char*)NULL);_exit(127);}}
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
    set_image_path(G.hero_image,hh?hero:NULL,893,275);set_image_path(G.cover_image,hc?cover:NULL,327,235);
    if(g&&strcmp(G.artwork_appid,game_key(g))){snprintf(G.artwork_appid,sizeof G.artwork_appid,"%s",game_key(g));if(hh||hc)log_line("Artwork loaded for %s%s%s",g->name,hh?" • hero":"",hc?" • cover":"");else log_line("No cached artwork found yet for %s (%s %s).",g->name,game_is_steam(g)?"Steam":"Heroic",g->appid);}
}

static gboolean force_mockup_geometry(void *unused){
    (void)unused;
    /* KWin can restore the old 0.1.41 window size after GTK's default-size hint.
     * Keep the approved mockup geometry after mapping. The window now uses a
     * real GTK client-side titlebar, so KWin should not add a second strip. */
    gtk_window_resize((GtkWindow*)G.window,1536,1024);
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
    if(G.quick_store)gtk_widget_set_visible(G.quick_store,g&&game_is_steam(g));
    if(G.top_steam_status){
        snprintf(b,sizeof b,"<span foreground=\"#f4f6fa\" weight=\"bold\">Game Sources</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Steam %d • Heroic %d</span>",G.steam_game_count,G.heroic_game_count);
        gtk_label_set_markup((GtkLabel*)G.top_steam_status,b);
    }
    if(g){
        const char *src=game_is_steam(g)?"Steam":"Heroic";
        refresh_artwork(g);set_label(G.hero_name,g->name);
        if(game_is_steam(g))snprintf(b,sizeof b,"Steam • App ID: %s",g->appid);
        else snprintf(b,sizeof b,"Heroic • %s • ID: %s",g->runner,g->appid);
        set_label(G.hero_meta,b);
        if(G.game_detected_detail){snprintf(b,sizeof b,"%s\n%s • %s",g->name,src,game_is_steam(g)?g->appid:g->runner);set_label(G.game_detected_detail,b);}
        if(game_is_steam(g)){
            gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Detected</span>\n<span foreground=\"#aeb9c7\">🎮   Game:        </span><span foreground=\"#28e57b\" weight=\"bold\">Installed</span>\n<span foreground=\"#aeb9c7\">⚙   Runner:      Steam Play</span>");
            set_label(G.right_prefix,g->wand_found?"▰   Prefix:      Compatible":"▰   Prefix:      Detected");
        }else{
            if(managed_state==1)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Running (GameWeld managed)\nPID: %ld",g->runner,managed_game_pid);else if(managed_state==2)snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Closed • trainer still running\nTrainer PID: %ld",g->runner,managed_trainer_pid);else snprintf(b,sizeof b,"Heroic: Detected\nRunner: %s\nGame: Installed",g->runner);set_label(G.right_game,b);
            snprintf(b,sizeof b,"▰   Prefix:      %s",g->prefix[0]?g->prefix:"Heroic managed");set_label(G.right_prefix,b);
        }
    } else {
        if(G.game_detected_detail)set_label(G.game_detected_detail,"No game selected");set_image_path(G.hero_image,NULL,893,275);set_image_path(G.cover_image,NULL,327,235);G.artwork_appid[0]=0;set_label(G.hero_name,"Select a game");set_label(G.hero_meta,"Steam / Heroic");gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">Game source:     Not selected\n🎮   Game:        Not detected\n⚙   Runner:      —</span>");set_label(G.right_prefix,"▰   Prefix:      —");
    }
    if(g&&!game_is_steam(g)){
        gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Heroic\n✣   Trainers:    Local / Cheat Engine</span>");
        if(managed_state==1)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#28e57b\" weight=\"bold\">GameWeld managed</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Actual game process running</span>");else if(managed_state==2)snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Session:     </span><span foreground=\"#efb85b\" weight=\"bold\">Trainer remains</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Game process exited</span>");else snprintf(b,sizeof b,"<span foreground=\"#aeb9c7\">⚙   Heroic:      </span><span foreground=\"#28e57b\" weight=\"bold\">%s</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Direct live-prefix ready</span>",g->wine_name[0]?g->wine_name:(g->wine_type[0]?g->wine_type:"Launcher-managed"));gtk_label_set_markup((GtkLabel*)G.right_proton,b);
    } else {
        if(G.wand_installed)gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    </span><span foreground=\"#28e57b\" weight=\"bold\">Steam compatibility</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     </span><span foreground=\"#28e57b\" weight=\"bold\">Available</span>");else gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">◆   Provider:    Steam compatibility not installed\n✣   Trainer:     Unavailable</span>");
        if(G.wand_healthy)gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">GE-Proton-Wand-SHA256</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Ready to Launch</span>");else gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">Needs setup</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Setup required</span>");
    }
    set_label(G.game_ready,g?(managed_state==1?"Running":(managed_state==2?"Trainer active":"Installed")):"Not detected");set_label(G.wand_ready,(g&&!game_is_steam(g))?"Heroic":(G.wand_installed?"Ready":"Needs setup"));set_label(G.compat_ready,(g&&!game_is_steam(g))?(managed_state?"Managed session":"Launcher-managed"):(G.wand_healthy?"Configured":"Needs repair"));
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
    const char *native_available=(g&&game_is_steam(g))?available_native_profile(g->appid):NULL;
    int has_native=g&&native_available&&load_native_profile(game_key(g),np,sizeof np)&&!strcmp(np,native_available);
    if(G.play_title)set_label(G.play_title,managed_state==1?"GAME RUNNING":(managed_state==2?"TRAINER STILL RUNNING":(has_native?"PLAY WITH NATIVE TRAINER":(use_ct?"PLAY WITH CHEAT TABLE":(has_local?"PLAY WITH LOCAL TRAINER":((g&&!game_is_steam(g))?"PLAY THROUGH HEROIC":"PLAY WITH WAND PROVIDER"))))));
    if(G.play_subtitle)set_label(G.play_subtitle,managed_state==1?"GameWeld is tracking the actual Heroic game process • trainer shares the managed UMU session":(managed_state==2?"The game has exited but the trainer is still active • close it or use Stop Stuck Trainer":(has_native?"Built-in Resonance trainer • no Cheat Engine • unlimited local profile":(use_ct?"Launch game + Cheat Engine table (local / unlimited)":(has_local?"Launch game + your local trainer (local / unlimited)":((g&&!game_is_steam(g))?"Launch with Heroic using its configured Wine/Proton runner":"Launch game with the legacy Steam compatibility provider"))))));
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
    if(G.setup_detail){snprintf(b,sizeof b,"%s\nBase Proton: %s\nWand tool: %s",G.verify_message[0]?G.verify_message:"Not checked",G.base_proton[0]?G.base_proton:"Not detected",G.wand_tool[0]?G.wand_tool:"Not installed");set_label(G.setup_detail,b);}
}

static void spawn_heroic_normal(const Game*g){pid_t p=fork();if(p==0){execl(heroic_launch_tool(),heroic_launch_tool(),g->runner,g->appid,(char*)NULL);_exit(127);}}
static void spawn_heroic_table(const Game*g,const char*ce,const char*table){pid_t p=fork();if(p==0){execl(heroic_cheat_table_tool(),heroic_cheat_table_tool(),g->runner,g->appid,g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,ce,table,(char*)NULL);_exit(127);}}
static void spawn_heroic_trainer(const Game*g,const char*trainer){pid_t p=fork();if(p==0){execl(heroic_local_trainer_tool(),heroic_local_trainer_tool(),g->runner,g->appid,g->name,g->install_dir,g->executable,g->prefix,g->wine_type,g->wine_bin,trainer,g->heroic_root,(char*)NULL);_exit(127);}}
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
static void on_play(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}char lt[2048]={0},ct[2048]={0},ce[2048]={0},np[128]={0};Game*g=&G.games[G.selected];if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Game launch is blocked until it finishes or you press Cancel Runtime Repair in Settings.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"Trainer runtime repair is still active. Wait for completion or cancel it before launching the game.");return;}const char*k=game_key(g);const char*native_available=game_is_steam(g)?available_native_profile(g->appid):NULL;if(native_available&&load_native_profile(k,np,sizeof np)&&!strcmp(np,native_available)){log_line("Launching %s through Steam + native trainer profile: %s",g->name,np);spawn_native_profile(g->appid,np);return;}if(load_cheat_table(k,ct,sizeof ct)&&readable_file(ct)){if((load_cheat_engine(ce,sizeof ce)&&readable_file(ce))||detect_managed_cheat_engine(game_ce_id(g),ce,sizeof ce)){log_line("Launching %s through %s + Cheat Engine table: %s",g->name,game_is_steam(g)?"Steam":"Heroic",ct);if(game_is_steam(g))spawn_cheat_table(g->appid,ce,ct);else spawn_heroic_table(g,ce,ct);return;}}if(load_local_trainer(k,lt,sizeof lt)&&readable_file(lt)){log_line("Launching %s through %s + local trainer: %s",g->name,game_is_steam(g)?"Steam":"Heroic",lt);if(game_is_steam(g))spawn_local_trainer(g->appid,lt);else spawn_heroic_trainer(g,lt);return;}if(game_is_steam(g))start_job(JOB_PLAY,g->appid,"Preparing game and launching with the Steam compatibility provider…");else{log_line("No trainer/table configured for %s; launching normally through Heroic.",g->name);spawn_heroic_normal(g);}}
static void on_play_normal(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(!game_is_steam(g)&&heroic_runtime_repair_active_ui(g)){log_line("Trainer runtime repair is still active for %s. Normal Heroic launch is blocked until repair completes or is cancelled.",g->name);if(G.local_trainer_status)set_label(G.local_trainer_status,"FLiNG runtime repair is active; normal Heroic launch is temporarily blocked to protect the prefix.");return;}if(game_is_steam(g)){spawn_detached("steam","-applaunch",g->appid);log_line("Launching normally through Steam…");}else{spawn_heroic_normal(g);log_line("Launching normally through Heroic (%s)…",g->runner);}}
static void on_steam_page(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(game_is_steam(g)){char u[256];snprintf(u,sizeof u,"steam://store/%s",g->appid);spawn_detached("xdg-open",u,NULL);}else log_line("Store-page shortcut is not wired for Heroic %s games yet.",g->runner);}
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
static void on_health(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}Game*g=&G.games[G.selected];if(!game_is_steam(g)){log_line("Heroic launch diagnostics are recorded in ~/.local/state/gameweld/heroic-*.log.");return;}start_job(JOB_HEALTH,g->appid,"Checking trainer health…");}
static void on_refresh(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_REFRESH,NULL,"Refreshing Steam, Heroic and GameWeld status…");}

static void nav_activate(GtkWidget *active,const char *page){GtkWidget *all[]={G.nav_home,G.nav_library,G.nav_trainers,G.nav_setup,G.nav_diag,G.nav_settings,G.nav_about};for(int i=0;i<7;i++)if(all[i])unstyle(all[i],"nav-active");style(active,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,page);}
static void nav_home(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_home,"home");}
static void nav_library(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_library,"library");}
static void nav_trainers(GtkButton*b,void*d){(void)b;(void)d;refresh_trainer_library_view();nav_activate(G.nav_trainers,"trainers");}
static void nav_setup(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_setup,"setup");}
static void nav_diag(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_diag,"diag");}
static void nav_settings(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_settings,"settings");}
static void nav_about(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_about,"about");}

static void on_search(GtkEntry *entry,void*d){(void)d;const char *q=gtk_entry_get_text(entry);for(int i=0;i<G.game_count;i++){int vis=1;if(q&&*q){char a[512],b[512];snprintf(a,sizeof a,"%s",G.games[i].name);snprintf(b,sizeof b,"%s",q);for(char*p=a;*p;p++)*p=(char)tolower((unsigned char)*p);for(char*p=b;*p;p++)*p=(char)tolower((unsigned char)*p);vis=strstr(a,b)!=NULL;}gtk_widget_set_visible(G.game_rows[i],vis);}}
static void on_destroy(GtkWidget*w,void*d){(void)w;(void)d;if(G.backend_pid>0)kill(G.backend_pid,SIGTERM);gtk_main_quit();}

static GtkWidget *card(const char *title,const char *detail,GtkWidget **detail_out){GtkWidget *c=box(GTK_ORIENTATION_VERTICAL,6);style(c,"card");margins(c,4);GtkWidget*t=label(title,"card-title");pack(c,t,0);GtkWidget*x=label(detail,"muted");gtk_label_set_line_wrap((GtkLabel*)x,TRUE);pack(c,x,0);if(detail_out)*detail_out=x;return c;}

static GtkWidget *icon_named(const char *name,int px){GtkWidget*i=gtk_image_new_from_icon_name(name,GTK_ICON_SIZE_BUTTON);if(i)gtk_image_set_pixel_size((GtkImage*)i,px);return i;}
static GtkWidget *make_nav(const char *icon,const char *txt,GCallback cb){GtkWidget*b=gtk_button_new();style(b,"nav");gtk_widget_set_hexpand(b,TRUE);GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,16);margins(r,3);GtkWidget*i=icon_named(icon,22);if(i){style(i,"nav-icon");pack(r,i,0);}GtkWidget*l=label(txt,"nav-label");pack(r,l,1);gtk_container_add(b,r);g_signal_connect_data(b,"clicked",cb,NULL,NULL,0);return b;}
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
static void on_trainer_library_attention_toggled(GtkToggleButton*w,void*d){(void)d;if(G.trainer_library_tabs&&gtk_toggle_button_get_active(w))gtk_notebook_set_current_page((GtkNotebook*)G.trainer_library_tabs,5);refresh_trainer_library_rows();}
static void on_trainer_library_clear_filter(GtkButton*b,void*d){(void)b;(void)d;if(G.trainer_library_filter)gtk_entry_set_text((GtkEntry*)G.trainer_library_filter,"");if(G.trainer_library_attention_toggle)gtk_toggle_button_set_active((GtkToggleButton*)G.trainer_library_attention_toggle,FALSE);if(G.trainer_library_sort)gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_sort,"status");refresh_trainer_library_rows();}

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
    GtkWidget*sub=label(primary?"Launch game with the legacy Steam compatibility provider":"Launch without trainer",primary?"launch-subtitle":"normal-subtitle");
    if(primary){G.play_title=title;G.play_subtitle=sub;}
    pack(t,title,0);pack(t,sub,0);pack(r,t,1);gtk_container_add(b,r);return b;
}

static GtkWidget *build_home(void){
    GtkWidget*page=box(GTK_ORIENTATION_HORIZONTAL,13);gtk_widget_set_name(page,"page");margins(page,12);
    GtkWidget*main=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_hexpand(main,TRUE);pack(page,main,1);

    GtkWidget*hero=box(GTK_ORIENTATION_VERTICAL,7);gtk_widget_set_name(hero,"hero-frame");
    G.hero_image=gtk_image_new();gtk_widget_set_size_request(G.hero_image,893,275);pack(hero,G.hero_image,0);
    G.hero_name=label("Select a game",NULL);gtk_widget_set_name(G.hero_name,"game-title");gtk_widget_set_margin_start(G.hero_name,14);gtk_widget_set_margin_top(G.hero_name,5);pack(hero,G.hero_name,0);
    GtkWidget*meta=box(GTK_ORIENTATION_HORIZONTAL,9);gtk_widget_set_margin_start(meta,14);gtk_widget_set_margin_end(meta,14);gtk_widget_set_margin_bottom(meta,10);
    GtkWidget*steam=label("◉  Steam",NULL);gtk_widget_set_name(steam,"meta");pack(meta,steam,0);
    GtkWidget*sep=label("|",NULL);style(sep,"muted");pack(meta,sep,0);
    G.hero_meta=label("App ID: —",NULL);gtk_widget_set_name(G.hero_meta,"meta");pack(meta,G.hero_meta,0);
    GtkWidget*mgrow=box(GTK_ORIENTATION_HORIZONTAL,0);pack(meta,mgrow,1);
    pack(meta,meta_chip("Action"),0);pack(meta,meta_chip("Adventure"),0);pack(meta,meta_chip("Single Player"),0);
    pack(hero,meta,0);pack(main,hero,0);

    GtkWidget*plays=box(GTK_ORIENTATION_HORIZONTAL,11);style(plays,"launch-shell");
    G.play_button=launch_button(1);gtk_widget_set_size_request(G.play_button,560,88);g_signal_connect_data(G.play_button,"clicked",(GCallback)on_play,NULL,NULL,0);pack(plays,G.play_button,1);
    GtkWidget*normal=launch_button(0);gtk_widget_set_size_request(normal,265,88);g_signal_connect_data(normal,"clicked",(GCallback)on_play_normal,NULL,NULL,0);pack(plays,normal,0);pack(main,plays,0);

    GtkWidget*cards=box(GTK_ORIENTATION_HORIZONTAL,10);
    GtkWidget*c1=box(GTK_ORIENTATION_VERTICAL,8);style(c1,"card");style(c1,"info-card");GtkWidget*c1r=box(GTK_ORIENTATION_HORIZONTAL,13);GtkWidget*c1i=label("◉",NULL);style(c1i,"info-icon");gtk_widget_set_halign(c1i,GTK_ALIGN_CENTER);pack(c1r,c1i,0);GtkWidget*c1txt=box(GTK_ORIENTATION_VERTICAL,3);pack(c1txt,label("Game Detected","card-title"),0);G.game_detected_detail=label("Select a game from your Library","muted");gtk_label_set_line_wrap((GtkLabel*)G.game_detected_detail,TRUE);pack(c1txt,G.game_detected_detail,0);pack(c1r,c1txt,1);pack(c1,c1r,1);G.game_ready=label("Installed","good");gtk_widget_set_name(G.game_ready,"status-pill");gtk_widget_set_halign(G.game_ready,GTK_ALIGN_CENTER);pack(c1,G.game_ready,0);
    GtkWidget*c2=status_card("◆","Trainer Ready","Trainer provider installed and\nconfigured",&G.wand_ready,"Ready");
    GtkWidget*c3=status_card("⚙","Compatibility","GameWeld isolated Steam Proton tool",&G.compat_ready,"Configured");
    pack(cards,c1,1);pack(cards,c2,1);pack(cards,c3,1);pack(main,cards,0);

    GtkWidget*log=box(GTK_ORIENTATION_VERTICAL,6);style(log,"card");GtkWidget*lh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(lh,label("▣  Activity Log","card-title"),1);GtkWidget*clear=button("⌫  Clear Log","action");pack(lh,clear,0);pack(log,lh,0);
    G.activity=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.activity,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.activity,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.activity,TRUE);gtk_widget_set_name(G.activity,"logframe");
    GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(sc,-1,180);gtk_container_add(sc,G.activity);pack(log,sc,1);pack(main,log,1);

    GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_size_request(right,352,-1);
    GtkWidget*cf=box(GTK_ORIENTATION_VERTICAL,0);style(cf,"card");G.cover_image=gtk_image_new();gtk_widget_set_size_request(G.cover_image,327,235);pack(cf,G.cover_image,0);pack(right,cf,0);
    GtkWidget*gs=box(GTK_ORIENTATION_VERTICAL,7);style(gs,"card");style(gs,"status-card");GtkWidget*gh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(gh,label("Game Status","card-title"),1);GtkWidget*gready=label("●  Ready to Play","good");gtk_widget_set_name(gready,"status-pill");pack(gh,gready,0);pack(gs,gh,0);G.right_game=label("◉   Steam:       Online\n🎮   Game:        Installed\n⚙   Proton:      GE-Proton (Game)","muted");pack(gs,G.right_game,0);G.right_prefix=label("▰   Prefix:      Compatible","good");pack(gs,G.right_prefix,0);pack(right,gs,0);
    GtkWidget*ws=box(GTK_ORIENTATION_VERTICAL,7);style(ws,"card");style(ws,"status-card");GtkWidget*wh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(wh,label("Trainer Status","card-title"),1);GtkWidget*wready=label("●  Ready","good");gtk_widget_set_name(wready,"status-pill");pack(wh,wready,0);pack(ws,wh,0);G.right_wand=label("◆   Provider:    Wand (Steam)\n✣   Trainer:     Available","muted");pack(ws,G.right_wand,0);G.right_proton=label("⚙   Proton:      GE-Proton-Wand-SHA256\nⓘ   Status:      Ready to Launch","good");pack(ws,G.right_proton,0);pack(right,ws,0);
    GtkWidget*qa=box(GTK_ORIENTATION_VERTICAL,7);style(qa,"card");pack(qa,label("Quick Actions","card-title"),0);GtkWidget*h=quick_button("utilities-system-monitor-symbolic","Check Trainer Health");GtkWidget*rp=quick_button("applications-engineering-symbolic","Repair Steam Compatibility");GtkWidget*gf=quick_button("folder-open-symbolic","Open Game Folder");GtkWidget*sp=quick_button("external-link-symbolic","Open Steam Page");G.quick_store=sp;g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);g_signal_connect_data(rp,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(gf,"clicked",(GCallback)on_game_folder,NULL,NULL,0);g_signal_connect_data(sp,"clicked",(GCallback)on_steam_page,NULL,NULL,0);pack(qa,h,0);pack(qa,rp,0);pack(qa,gf,0);pack(qa,sp,0);pack(right,qa,0);
    GtkWidget*rgrow=box(GTK_ORIENTATION_VERTICAL,0);pack(right,rgrow,1);GtkWidget*rf=label("GameWeld 0.3.0 Test 9   |   Open Source   |   MIT License",NULL);gtk_widget_set_name(rf,"footer");gtk_widget_set_halign(rf,GTK_ALIGN_CENTER);pack(right,rf,0);pack(page,right,0);
    return page;
}

static GtkWidget *build_library(void){
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,10);margins(p,18);GtkWidget*t=label("Game Library",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);
    GtkWidget*help=label("Every detected game uses its own artwork. GameWeld checks user overrides first, then curated assets, then Steam's local library artwork cache.","muted");gtk_label_set_line_wrap((GtkLabel*)help,TRUE);pack(p,help,0);
    GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_vexpand(sc,TRUE);G.game_list=gtk_list_box_new();g_signal_connect_data(G.game_list,"row-selected",(GCallback)selected_changed,NULL,NULL,0);
    for(int i=0;i<G.game_count;i++){
        GtkWidget*r=gtk_list_box_row_new();G.game_rows[i]=r;GtkWidget*rb=box(GTK_ORIENTATION_HORIZONTAL,12);margins(rb,9);
        GtkWidget*thumb=gtk_image_new();style(thumb,"game-thumb");char art[2048]={0};if(!resolve_game_art(&G.games[i],1,art,sizeof art))resolve_game_art(&G.games[i],0,art,sizeof art);set_image_path(thumb,art[0]?art:NULL,72,96);pack(rb,thumb,0);
        GtkWidget*txt=box(GTK_ORIENTATION_VERTICAL,4);GtkWidget*n=label(G.games[i].name,"game-row-title");pack(txt,n,0);char x[384];if(game_is_steam(&G.games[i]))snprintf(x,sizeof x,"Steam • App ID: %s",G.games[i].appid);else snprintf(x,sizeof x,"Heroic • %s • ID: %s",G.games[i].runner,G.games[i].appid);pack(txt,label(x,"muted"),0);pack(txt,label(art[0]?"Artwork ready":(game_is_steam(&G.games[i])?"Artwork will load from Steam cache when available":"Heroic artwork not cached"),"muted"),0);pack(rb,txt,1);GtkWidget*installed=label("Installed","good");gtk_widget_set_name(installed,"status-pill");pack(rb,installed,0);
        gtk_container_add(r,rb);gtk_list_box_insert((GtkListBox*)G.game_list,r,-1);
    }
    gtk_container_add(sc,G.game_list);pack(p,sc,1);return p;
}


static void on_enable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game from Library first.");return;}Game*g=&G.games[G.selected];if(!game_is_steam(g)){log_line("Native converted-table profiles are currently Steam-only.");return;}const char*p=available_native_profile(g->appid);if(!p){log_line("No native trainer profile is available for %s yet.",g->name);return;}if(save_native_profile(game_key(g),p))log_line("Native trainer profile enabled for %s: %s",g->name,p);else log_line("Could not save native profile configuration.");refresh_ui();}
static void on_disable_native_profile(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;Game*g=&G.games[G.selected];if(save_native_profile(game_key(g),NULL))log_line("Native trainer profile disabled for %s.",g->name);refresh_ui();}

static void on_scan_trainer_library(GtkButton*b,void*d){(void)b;(void)d;start_trainer_library_scan();}
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
static void on_assign_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose the target game in Library first.");return;}if(!G.trainer_library_pick_path[0]||!readable_file(G.trainer_library_pick_path)){log_line("Choose a trainer row in Trainer Library first.");return;}Game*g=&G.games[G.selected];int suggested=trainer_game_index_by_key(G.trainer_library_pick_key);if(trainer_pick_is_strong_target()&&suggested>=0&&strcmp(game_key(g),G.trainer_library_pick_key)){log_line("Assignment blocked for safety: %s is matched to %s, not %s. Use Assign to Suggested Game or select %s first.",G.trainer_library_pick_path,G.games[suggested].name,g->name,G.games[suggested].name);return;}if(save_local_trainer(game_key(g),G.trainer_library_pick_path)){log_line("Trainer Library assignment: %s → %s",g->name,G.trainer_library_pick_path);refresh_ui();refresh_trainer_library_view();start_selected_trainer_scan();}else log_line("Could not save Trainer Library assignment for %s.",g->name);}
static void on_ignore_library_pick(GtkButton*b,void*d){(void)b;(void)d;if(!G.trainer_library_pick_path[0]){log_line("Choose a trainer row in Trainer Library first.");return;}char path[2048];snprintf(path,sizeof path,"%s",G.trainer_library_pick_path);pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"ignore",path,(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer Library will ignore: %s",path);G.trainer_library_pick_path[0]=0;G.trainer_library_pick_game[0]=0;G.trainer_library_pick_key[0]=0;G.trainer_library_pick_state[0]=0;if(G.trainer_library_pick)set_label(G.trainer_library_pick,"Select a trainer row to review its suggested game/version, assign it safely, switch to an alternative version, reassign an ambiguous/unmatched trainer, or ignore it.");refresh_trainer_library_view();}else log_line("Could not add trainer to the ignore list: %s",path);}
static void on_clear_ignored_trainers(GtkButton*b,void*d){(void)b;(void)d;pid_t p=fork();if(p==0){execlp("python3","python3",trainer_library_tool(),"clear-ignored",(char*)NULL);_exit(127);}int st=0;if(p>0)while(waitpid(p,&st,0)<0&&errno==EINTR){}if(p>0&&WIFEXITED(st)&&WEXITSTATUS(st)==0){log_line("Trainer Library ignore list cleared. Rescan to rediscover those trainer executables.");refresh_trainer_library_view();}else log_line("Could not clear the Trainer Library ignore list.");}
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
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,10);margins(p,18);
    GtkWidget*t=label("Trainer Library",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);
    GtkWidget*intro=label("Discover, review and manage standalone Windows trainer executables. GameWeld uses standard XDG/Home locations, folders you add, and install paths reported by Steam/Heroic. Test 9 adds fast search, sorting and a Games Needing Attention view for large libraries. Filters operate on the last scan instantly; they do not rescan disks. GameWeld never deletes trainer EXE files during Library maintenance.","muted");gtk_label_set_line_wrap((GtkLabel*)intro,TRUE);pack(p,intro,0);

    GtkWidget*actions1=box(GTK_ORIENTATION_HORIZONTAL,8);
    GtkWidget*scan=button("Rescan / Auto-Match All Games","action");GtkWidget*rescan=button("Rescan Selected Game","action");GtkWidget*add=button("Add Trainer Folder","action");GtkWidget*refresh=button("Refresh View","action");
    g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(rescan,"clicked",(GCallback)on_rescan_selected_trainer,NULL,NULL,0);g_signal_connect_data(add,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(refresh,"clicked",(GCallback)nav_trainers,NULL,NULL,0);
    pack(actions1,scan,0);pack(actions1,rescan,0);pack(actions1,add,0);pack(actions1,refresh,0);pack(p,actions1,0);

    GtkWidget*filters=box(GTK_ORIENTATION_HORIZONTAL,8);G.trainer_library_filter=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.trainer_library_filter,"Search game, trainer, version, health, folder…");gtk_widget_set_hexpand(G.trainer_library_filter,TRUE);G.trainer_library_sort=gtk_combo_box_text_new();gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"status","Sort: Status / health");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"game","Sort: Game name");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"confidence","Sort: Confidence");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"version","Sort: Version (newest first)");gtk_combo_box_text_append((GtkComboBoxText*)G.trainer_library_sort,"trainer","Sort: Trainer filename");gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_library_sort,"status");G.trainer_library_attention_toggle=gtk_check_button_new_with_label("Needs attention only");GtkWidget*clearfilter=button("Clear Filters","action");g_signal_connect_data(G.trainer_library_filter,"changed",(GCallback)on_trainer_library_filter_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_sort,"changed",(GCallback)on_trainer_library_sort_changed,NULL,NULL,0);g_signal_connect_data(G.trainer_library_attention_toggle,"toggled",(GCallback)on_trainer_library_attention_toggled,NULL,NULL,0);g_signal_connect_data(clearfilter,"clicked",(GCallback)on_trainer_library_clear_filter,NULL,NULL,0);pack(filters,G.trainer_library_filter,1);pack(filters,G.trainer_library_sort,0);pack(filters,G.trainer_library_attention_toggle,0);pack(filters,clearfilter,0);pack(p,filters,0);

    GtkWidget*actions2=box(GTK_ORIENTATION_HORIZONTAL,8);
    G.trainer_library_assign_suggested=button("Assign to Suggested Game","action");G.trainer_library_select_suggested=button("Select Suggested Game","action");G.trainer_library_assign_selected=button("Assign to Selected Game","action");G.trainer_library_open_folder=button("Open Trainer Folder","action");
    g_signal_connect_data(G.trainer_library_assign_suggested,"clicked",(GCallback)on_assign_suggested_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_select_suggested,"clicked",(GCallback)on_select_suggested_library_game,NULL,NULL,0);g_signal_connect_data(G.trainer_library_assign_selected,"clicked",(GCallback)on_assign_library_pick,NULL,NULL,0);g_signal_connect_data(G.trainer_library_open_folder,"clicked",(GCallback)on_open_selected_trainer_folder,NULL,NULL,0);
    gtk_widget_set_sensitive(G.trainer_library_assign_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_select_suggested,FALSE);gtk_widget_set_sensitive(G.trainer_library_assign_selected,FALSE);gtk_widget_set_sensitive(G.trainer_library_open_folder,FALSE);
    pack(actions2,G.trainer_library_assign_suggested,0);pack(actions2,G.trainer_library_select_suggested,0);pack(actions2,G.trainer_library_assign_selected,0);pack(actions2,G.trainer_library_open_folder,0);pack(p,actions2,0);

    GtkWidget*actions3=box(GTK_ORIENTATION_HORIZONTAL,8);
    GtkWidget*manual=button("Choose Trainer EXE…","action");GtkWidget*clear=button("Clear Selected Game Assignment","action");GtkWidget*ignore=button("Ignore Selected Trainer","action");GtkWidget*clearignore=button("Clear Ignored Trainers","action");GtkWidget*prune=button("Remove Missing Mappings","action");
    g_signal_connect_data(manual,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);g_signal_connect_data(ignore,"clicked",(GCallback)on_ignore_library_pick,NULL,NULL,0);g_signal_connect_data(clearignore,"clicked",(GCallback)on_clear_ignored_trainers,NULL,NULL,0);g_signal_connect_data(prune,"clicked",(GCallback)on_prune_missing_trainers,NULL,NULL,0);
    pack(actions3,manual,0);pack(actions3,clear,0);pack(actions3,ignore,0);pack(actions3,clearignore,0);pack(actions3,prune,0);pack(p,actions3,0);

    GtkWidget*policy=box(GTK_ORIENTATION_HORIZONTAL,8);G.trainer_library_policy=label("Duplicate-version policy: ask (safe default)","muted");GtkWidget*pask=button("Ask me","action");GtkWidget*pkeep=button("Keep current","action");GtkWidget*pnew=button("Prefer newest","action");g_signal_connect_data(pask,"clicked",(GCallback)on_policy_ask,NULL,NULL,0);g_signal_connect_data(pkeep,"clicked",(GCallback)on_policy_keep,NULL,NULL,0);g_signal_connect_data(pnew,"clicked",(GCallback)on_policy_newest,NULL,NULL,0);pack(policy,G.trainer_library_policy,1);pack(policy,pask,0);pack(policy,pkeep,0);pack(policy,pnew,0);pack(p,policy,0);

    GtkWidget*sel=box(GTK_ORIENTATION_VERTICAL,6);style(sel,"card");pack(sel,label("Assignment Target","card-title"),0);G.trainer_library_selected=label("Select a game in Library to assign or clear its trainer.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_selected,TRUE);pack(sel,G.trainer_library_selected,0);G.trainer_library_pick=label("Select a trainer row to review its suggested game/version, assign it safely, switch to an alternative version, reassign an ambiguous/unmatched trainer, or ignore it.","muted");gtk_label_set_line_wrap((GtkLabel*)G.trainer_library_pick,TRUE);pack(sel,G.trainer_library_pick,0);pack(p,sel,0);

    GtkWidget*library=box(GTK_ORIENTATION_VERTICAL,6);style(library,"card");pack(library,label("Trainer & Game Results","card-title"),0);
    GtkWidget*nb=gtk_notebook_new();G.trainer_library_tabs=nb;gtk_widget_set_vexpand(nb,TRUE);gtk_widget_set_size_request(nb,-1,370);
    G.trainer_library_matched=trainer_tree_new();G.trainer_library_alternates=trainer_tree_new();G.trainer_library_ambiguous=trainer_tree_new();G.trainer_library_unmatched=trainer_tree_new();G.trainer_library_health=trainer_tree_new();
    GtkWidget*views[5]={G.trainer_library_matched,G.trainer_library_alternates,G.trainer_library_ambiguous,G.trainer_library_unmatched,G.trainer_library_health};const char*tabs[5]={"Assigned / Matched","Alternatives","Ambiguous","Unmatched Trainers","Health Issues"};
    for(int i=0;i<5;i++){GtkTreeSelection*seln=gtk_tree_view_get_selection((GtkTreeView*)views[i]);gtk_tree_selection_set_mode(seln,GTK_SELECTION_SINGLE);g_signal_connect_data(seln,"changed",(GCallback)trainer_pick_changed,NULL,NULL,0);GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)sc,GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);gtk_container_add(sc,views[i]);gtk_notebook_append_page((GtkNotebook*)nb,sc,label(tabs[i],NULL));}
    G.trainer_library_attention_games=trainer_attention_tree_new();GtkTreeSelection*ags=gtk_tree_view_get_selection((GtkTreeView*)G.trainer_library_attention_games);gtk_tree_selection_set_mode(ags,GTK_SELECTION_SINGLE);g_signal_connect_data(ags,"changed",(GCallback)trainer_attention_game_changed,NULL,NULL,0);GtkWidget*agsc=gtk_scrolled_window_new(NULL,NULL);gtk_scrolled_window_set_policy((GtkScrolledWindow*)agsc,GTK_POLICY_AUTOMATIC,GTK_POLICY_AUTOMATIC);gtk_container_add(agsc,G.trainer_library_attention_games);gtk_notebook_append_page((GtkNotebook*)nb,agsc,label("Games Needing Attention",NULL));
    pack(library,nb,1);pack(p,library,1);

    GtkWidget*summary=box(GTK_ORIENTATION_VERTICAL,6);style(summary,"card");pack(summary,label("Last Scan Summary","card-title"),0);G.trainer_library_view=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.trainer_library_view,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.trainer_library_view,TRUE);gtk_text_buffer_set_text(gtk_text_view_get_buffer((GtkTextView*)G.trainer_library_view),"No Trainer Library scan has completed yet.",-1);GtkWidget*scsum=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(scsum,-1,180);gtk_container_add(scsum,G.trainer_library_view);pack(summary,scsum,1);pack(p,summary,0);
    return p;
}

static GtkWidget *build_setup(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Setup & Compatibility",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);pack(p,label("GameWeld keeps a separate Proton-GE tool so your normal Proton installations remain untouched.","muted"),0);GtkWidget*c=card("Compatibility status","Checking…",&G.setup_detail);G.setup_status=label("Checking…","good");pack(c,G.setup_status,0);pack(p,c,0);GtkWidget*row=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*i=button("Install / Repair","action");GtkWidget*v=button("Verify","action");g_signal_connect_data(i,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(v,"clicked",(GCallback)on_verify,NULL,NULL,0);pack(row,i,0);pack(row,v,0);pack(p,row,0);GtkWidget*note=card("What setup does","Detects Steam and Proton-GE, maintains GameWeld's isolated Steam compatibility tool, applies the proven crypt32 compatibility payload, and leaves normal Proton-GE unchanged.",NULL);pack(p,note,0);return p;}
static GtkWidget *build_diag(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Diagnostics",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);GtkWidget*h=button("Check Trainer Health","action");g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);pack(p,h,0);G.health_detail=label("Launch a game with its configured trainer provider, then check TrainerLib/signature/command health here.","muted");gtk_label_set_line_wrap((GtkLabel*)G.health_detail,TRUE);pack(p,G.health_detail,0);return p;}
static GtkWidget *build_settings(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Settings",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);
    GtkWidget*nc=box(GTK_ORIENTATION_VERTICAL,8);style(nc,"card");pack(nc,label("Native CT Profile (No Cheat Engine)","card-title"),0);GtkWidget*nd=label("GameWeld can directly run converted table logic for supported games without Cheat Engine. Resonance: A Plague Tale Legacy has a built-in conversion of Paul44's v1.1 table with God Mode, Invisible, Resonance Points, FOV and Console controls. The original .CT is not redistributed.","muted");gtk_label_set_line_wrap((GtkLabel*)nd,TRUE);pack(nc,nd,0);GtkWidget*nr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*nen=button("Enable Native Profile","action");GtkWidget*ndis=button("Disable Native Profile","action");g_signal_connect_data(nen,"clicked",(GCallback)on_enable_native_profile,NULL,NULL,0);g_signal_connect_data(ndis,"clicked",(GCallback)on_disable_native_profile,NULL,NULL,0);pack(nr,nen,0);pack(nr,ndis,0);pack(nc,nr,0);G.native_profile_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.native_profile_status,TRUE);pack(nc,G.native_profile_status,0);pack(p,nc,0);
    GtkWidget*lc=box(GTK_ORIENTATION_VERTICAL,8);style(lc,"card");pack(lc,label("Local Trainer Provider (Unlimited)","card-title"),0);GtkWidget*desc=label("GameWeld can discover standalone Windows trainer EXEs automatically or you can choose one manually. Discovery uses standard XDG/Home folders, folders you add, and the install paths reported by Steam/Heroic; it never assumes a specific username, /mnt/games, drive layout or distro. Steam uses the proven live Proton-session handoff. Heroic games from Epic, GOG and Amazon stay launcher-native: GameWeld launches through the detected Heroic runner. For local trainers on affected Wine/Proton 11+ builds, GameWeld uses its pinned GE-Proton10-34 + Wine-Wayland compatibility session. Epic/Legendary launches through Heroic's authenticated Legendary backend with an explicit UMU environment; the trainer joins it with UMU runinprefix. GOG/Amazon retain the verified temporary Heroic handshake.","muted");gtk_label_set_line_wrap((GtkLabel*)desc,TRUE);pack(lc,desc,0);G.local_trainer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.local_trainer_entry,"No local trainer configured");pack(lc,G.local_trainer_entry,0);GtkWidget*lr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*choose=button("Choose Trainer EXE","action");GtkWidget*scan=button("Scan / Auto-Match Trainers","action");GtkWidget*addfolder=button("Add Trainer Folder","action");GtkWidget*clear=button("Clear Trainer","action");g_signal_connect_data(choose,"clicked",(GCallback)on_choose_local_trainer,NULL,NULL,0);g_signal_connect_data(scan,"clicked",(GCallback)on_scan_trainer_library,NULL,NULL,0);g_signal_connect_data(addfolder,"clicked",(GCallback)on_add_trainer_folder,NULL,NULL,0);g_signal_connect_data(clear,"clicked",(GCallback)on_clear_local_trainer,NULL,NULL,0);pack(lr,choose,0);pack(lr,scan,0);pack(lr,addfolder,0);pack(lr,clear,0);pack(lc,lr,0);GtkWidget*hr=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*stop=button("Stop Stuck Trainer","action");GtkWidget*reset=button("Reset Heroic Prefix (Closes Game)","action");g_signal_connect_data(stop,"clicked",(GCallback)on_stop_heroic_trainer,NULL,NULL,0);g_signal_connect_data(reset,"clicked",(GCallback)on_reset_heroic_prefix,NULL,NULL,0);pack(hr,stop,0);pack(hr,reset,0);pack(lc,hr,0);GtkWidget*compat=label("Heroic FLiNG compatibility engine: normal desktop windows are used. The engine is game-agnostic and scoped to the exact Heroic installation discovered for the selected title. On affected Wine/Proton 11+ builds, game and trainer share pinned GE-Proton10-34 with Wine-Wayland. Epic/Legendary uses matching UMU runinprefix instead of host Wine, so a trainer cannot be deferred until after game exit.","muted");gtk_label_set_line_wrap((GtkLabel*)compat,TRUE);pack(lc,compat,0);G.local_trainer_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.local_trainer_status,TRUE);pack(lc,G.local_trainer_status,0);pack(p,lc,0);
    GtkWidget*cc=box(GTK_ORIENTATION_VERTICAL,8);style(cc,"card");pack(cc,label("Managed Cheat Engine Provider (.CT)","card-title"),0);GtkWidget*cd=label("GameWeld uses the official Cheat Engine Linux package as the native bridge and a shared Windows CE companion in windowsbin. Steam handoff joins the verified Proton session; Heroic handoff waits for the real game process and asks Heroic to launch Windows CE as an alternate executable using that game's configured Wine/Proton runner. Install the bridge and Windows companion once. Cheat Engine itself is not bundled inside GameWeld.","muted");gtk_label_set_line_wrap((GtkLabel*)cd,TRUE);pack(cc,cd,0);G.cheat_engine_installer_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_installer_entry,"Official CheatEngineLinux771.zip or Windows CE installer/ZIP");pack(cc,G.cheat_engine_installer_entry,0);G.cheat_engine_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_engine_entry,"Managed native Linux CE appears here after install");pack(cc,G.cheat_engine_entry,0);G.cheat_table_entry=gtk_entry_new();gtk_entry_set_placeholder_text((GtkEntry*)G.cheat_table_entry,"No .CT table configured for selected game");pack(cc,G.cheat_table_entry,0);GtkWidget*cr0=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceauto=button("Download + Install Linux CE","action");GtkWidget*cedl=button("Open Official Linux ZIP","action");GtkWidget*cewin=button("Open Official Windows CE","action");GtkWidget*cei=button("Choose CE Package","action");g_signal_connect_data(ceauto,"clicked",(GCallback)on_download_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cedl,"clicked",(GCallback)on_open_cheat_engine_download,NULL,NULL,0);g_signal_connect_data(cewin,"clicked",(GCallback)on_open_cheat_engine_windows_download,NULL,NULL,0);g_signal_connect_data(cei,"clicked",(GCallback)on_choose_cheat_engine_installer,NULL,NULL,0);pack(cr0,ceauto,0);pack(cr0,cedl,0);pack(cr0,cewin,0);pack(cr0,cei,0);pack(cc,cr0,0);GtkWidget*cr1=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*ceinstall=button("Install Selected Package","action");GtkWidget*ced=button("Detect / Refresh CE","action");GtkWidget*cce=button("Choose Existing CE","action");GtkWidget*cct=button("Choose .CT Table","action");g_signal_connect_data(ceinstall,"clicked",(GCallback)on_install_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(ced,"clicked",(GCallback)on_detect_managed_cheat_engine,NULL,NULL,0);g_signal_connect_data(cce,"clicked",(GCallback)on_choose_cheat_engine,NULL,NULL,0);g_signal_connect_data(cct,"clicked",(GCallback)on_choose_cheat_table,NULL,NULL,0);pack(cr1,ceinstall,0);pack(cr1,ced,0);pack(cr1,cce,0);pack(cr1,cct,0);pack(cc,cr1,0);GtkWidget*cr2=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*cte=button("Clear External CE","action");GtkWidget*ctt=button("Clear Table","action");g_signal_connect_data(cte,"clicked",(GCallback)on_clear_cheat_engine,NULL,NULL,0);g_signal_connect_data(ctt,"clicked",(GCallback)on_clear_cheat_table,NULL,NULL,0);pack(cr2,cte,0);pack(cr2,ctt,0);pack(cc,cr2,0);G.cheat_table_status=label("Select a game first.","good");gtk_label_set_line_wrap((GtkLabel*)G.cheat_table_status,TRUE);pack(cc,G.cheat_table_status,0);pack(p,cc,0);
    GtkWidget*scard=box(GTK_ORIENTATION_VERTICAL,8);style(scard,"card");pack(scard,label("Steam Direct Launch Cleanup","card-title"),0);GtkWidget*sd=label("Older Wand Native builds could leave wand-steam-wrap in a game's Steam Launch Options. A pass-through wrapper stops Wand from opening, but Steam can still invoke that old hook and leave a terminal window attached to the game. This cleanup removes only LaunchOptions entries that still reference wand-steam-wrap and creates a timestamped localconfig.vdf backup first.","muted");gtk_label_set_line_wrap((GtkLabel*)sd,TRUE);pack(scard,sd,0);GtkWidget*sbtn=button("Remove Legacy Steam Hooks","action");g_signal_connect_data(sbtn,"clicked",(GCallback)on_clean_legacy_hooks,NULL,NULL,0);pack(scard,sbtn,0);G.steam_cleanup_status=label("After cleanup, restart Steam once before testing direct Play.","good");gtk_label_set_line_wrap((GtkLabel*)G.steam_cleanup_status,TRUE);pack(scard,G.steam_cleanup_status,0);pack(p,scard,0);pack(p,card("Safety","Use native profiles, local trainers and Cheat Engine tables for single-player/offline games. Do not use them in anti-cheat protected or competitive multiplayer modes. No provider bypasses anti-cheat systems.",NULL),0);return p;}
static GtkWidget *build_about(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("GameWeld",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);pack(p,label("0.3.0 Test 9\nTrainer Library UX • instant search/filter • sorting • games-needing-attention view • bulk rescan • 0.2.2 launch core frozen.","muted"),0);pack(p,label("Legacy Steam provider: proven compatibility runtime\nNative CT profile: converted supported Steam tables without Cheat Engine\nLocal provider: standalone trainer EXE through Steam or Heroic\nTrainer Library: search/filter + sorting + games-needing-attention + health/recovery + duplicate-version policy + safe assignment + ignore\nManaged CE provider: Linux CE bridge + Windows CE direct live-prefix handoff\nCheat Table provider: per-game .CT table with managed or external CE\nHeroic provider: Epic / GOG / Amazon discovery + live UMU-container trainer injection + CE handoff\nSteam direct launch: no automatic legacy-provider startup","muted"),0);return p;}

static void build_ui(void){
    G.window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title((GtkWindow*)G.window,"GameWeld");
    gtk_window_set_default_size((GtkWindow*)G.window,1536,1024);
    gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    gtk_window_set_decorated((GtkWindow*)G.window,TRUE);
    g_signal_connect_data(G.window,"destroy",(GCallback)on_destroy,NULL,NULL,0);

    /* Test 12: keep our own full-width GTK titlebar. This is the supported GTK3
     * path for client-side decorations and prevents KWin from adding its own
     * extra title strip above the mockup chrome. The left brand block and the
     * right search/status/window-controls block remain visually identical to
     * the approved mockup, but now jointly own the window chrome. */
    GtkWidget*titlebar=box(GTK_ORIENTATION_HORIZONTAL,0);
    gtk_widget_set_name(titlebar,"app-titlebar");
    gtk_widget_set_size_request(titlebar,-1,78);

    GtkWidget*titlebrand=box(GTK_ORIENTATION_HORIZONTAL,12);
    gtk_widget_set_name(titlebrand,"title-brand");
    gtk_widget_set_size_request(titlebrand,268,78);
    gtk_widget_set_margin_start(titlebrand,18);
    gtk_widget_set_margin_end(titlebrand,18);
    GtkWidget*wm=label("GF",NULL);gtk_widget_set_name(wm,"wandmark");
    pack(titlebrand,wm,0);
    GtkWidget*bt=box(GTK_ORIENTATION_VERTICAL,0);
    GtkWidget*brand=label("GameWeld",NULL);gtk_widget_set_name(brand,"brand");pack(bt,brand,0);
    GtkWidget*ver=label("v0.3.0-test9",NULL);gtk_widget_set_name(ver,"brandver");pack(bt,ver,0);
    pack(titlebrand,bt,1);
    pack(titlebar,titlebrand,0);

    GtkWidget*top=box(GTK_ORIENTATION_HORIZONTAL,14);
    gtk_widget_set_name(top,"topbar");
    gtk_widget_set_size_request(top,-1,78);
    gtk_widget_set_margin_start(top,18);
    gtk_widget_set_margin_end(top,18);
    G.search=gtk_entry_new();
    gtk_entry_set_placeholder_text((GtkEntry*)G.search,"Search your games...");
    gtk_entry_set_icon_from_icon_name((GtkEntry*)G.search,GTK_ENTRY_ICON_PRIMARY,"system-search-symbolic");
    gtk_widget_set_size_request(G.search,470,44);
    g_signal_connect_data(G.search,"changed",(GCallback)on_search,NULL,NULL,0);
    pack(top,G.search,0);
    GtkWidget*tg=box(GTK_ORIENTATION_HORIZONTAL,0);pack(top,tg,1);
    GtkWidget*steamtop=box(GTK_ORIENTATION_HORIZONTAL,9);
    GtkWidget*sticon=icon_named("applications-games-symbolic",24);if(sticon)pack(steamtop,sticon,0);
    G.top_steam_status=label("",NULL);
    gtk_label_set_markup((GtkLabel*)G.top_steam_status,"<span foreground=\"#f4f6fa\" weight=\"bold\">Game Sources</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Detecting…</span>");
    pack(steamtop,G.top_steam_status,0);pack(top,steamtop,0);
    GtkWidget*gear=button("⚙","windowctl");pack(top,gear,0);
    pack(top,gtk_separator_new(GTK_ORIENTATION_VERTICAL),0);
    GtkWidget*mi=button("—","windowctl");GtkWidget*ma=button("□","windowctl");GtkWidget*cl=button("×","windowctl");gtk_widget_set_name(cl,"closectl");
    g_signal_connect_data(mi,"clicked",(GCallback)on_minimize,NULL,NULL,0);
    g_signal_connect_data(ma,"clicked",(GCallback)on_maximize,NULL,NULL,0);
    g_signal_connect_data(cl,"clicked",(GCallback)on_close_btn,NULL,NULL,0);
    pack(top,mi,0);pack(top,ma,0);pack(top,cl,0);
    pack(titlebar,top,1);
    gtk_window_set_titlebar((GtkWindow*)G.window,titlebar);

    GtkWidget*root=box(GTK_ORIENTATION_HORIZONTAL,0);gtk_widget_set_name(root,"root");gtk_container_add(G.window,root);

    /* Content sidebar starts directly below the titlebar brand block. */
    GtkWidget*side=box(GTK_ORIENTATION_VERTICAL,9);gtk_widget_set_name(side,"sidebar");gtk_widget_set_size_request(side,268,-1);margins(side,18);
    G.nav_home=make_nav("applications-games-symbolic","Home",(GCallback)nav_home);
    G.nav_library=make_nav("view-grid-symbolic","Library",(GCallback)nav_library);
    G.nav_trainers=make_nav("system-search-symbolic","Trainer Library",(GCallback)nav_trainers);
    G.nav_setup=make_nav("applications-engineering-symbolic","Setup",(GCallback)nav_setup);
    GtkWidget*compat=make_nav("emblem-ok-symbolic","Compatibility",(GCallback)nav_setup);
    G.nav_diag=make_nav("utilities-system-monitor-symbolic","Diagnostics",(GCallback)nav_diag);
    G.nav_settings=make_nav("preferences-system-symbolic","Settings",(GCallback)nav_settings);
    G.nav_about=make_nav("dialog-information-symbolic","About",(GCallback)nav_about);
    pack(side,G.nav_home,0);pack(side,G.nav_library,0);pack(side,G.nav_trainers,0);pack(side,G.nav_setup,0);pack(side,compat,0);pack(side,G.nav_diag,0);pack(side,G.nav_settings,0);pack(side,G.nav_about,0);
    GtkWidget*grow=box(GTK_ORIENTATION_VERTICAL,0);pack(side,grow,1);
    GtkWidget*sf=box(GTK_ORIENTATION_VERTICAL,4);gtk_widget_set_name(sf,"sidebar-foot");pack(sf,label("●   GameWeld","good"),0);pack(sf,label("      v0.3.0-test9\n\nSteam + Heroic • Proton/Wine • Native GUI\n\nPlay More. Your Way.","muted"),0);pack(side,sf,0);pack(root,side,0);

    GtkWidget*main=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_hexpand(main,TRUE);pack(root,main,1);
    G.stack=gtk_stack_new();gtk_widget_set_hexpand(G.stack,TRUE);gtk_widget_set_vexpand(G.stack,TRUE);
    gtk_stack_add_named((GtkStack*)G.stack,build_home(),"home");
    gtk_stack_add_named((GtkStack*)G.stack,build_library(),"library");
    gtk_stack_add_named((GtkStack*)G.stack,build_trainer_library(),"trainers");
    gtk_stack_add_named((GtkStack*)G.stack,build_setup(),"setup");
    gtk_stack_add_named((GtkStack*)G.stack,build_diag(),"diag");
    gtk_stack_add_named((GtkStack*)G.stack,build_settings(),"settings");
    gtk_stack_add_named((GtkStack*)G.stack,build_about(),"about");
    pack(main,G.stack,1);

    {const char*start=getenv("WAND_NATIVE_START_PAGE");if(start&&!*start)start=NULL;if(start&&!strcmp(start,"settings")){style(G.nav_settings,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,"settings");}else{style(G.nav_home,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,"home");}}
    if(G.game_count>0){G.selected=0;gtk_list_box_select_row((GtkListBox*)G.game_list,(GtkListBoxRow*)G.game_rows[0]);}
    refresh_ui();
    log_line("Refreshing installed game sources...");log_line("Steam games detected: %d",G.steam_game_count);log_line("Heroic games detected: %d",G.heroic_game_count);if(G.wand_installed)log_line("Legacy Wand Steam trainer provider ready");if(G.wand_healthy)log_line("Steam Proton tool ready: GE-Proton-Wand-SHA256");log_line("GameWeld providers ready.");if(G.legacy_wrapper_neutralized)log_line("Legacy Steam wand-steam-wrap neutralized; direct Steam Play will no longer auto-start Wand. Backup: %s",G.legacy_wrapper_backup);
    GtkCssProvider*prov=gtk_css_provider_new();gtk_css_provider_load_from_data(prov,CSS,-1,NULL);gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),prov,GTK_STYLE_PROVIDER_PRIORITY_USER);g_object_unref(prov);
    gtk_widget_show_all(G.window);
    start_trainer_library_scan();
    gtk_window_resize((GtkWindow*)G.window,1536,1024);gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    g_idle_add(force_mockup_geometry,NULL);g_timeout_add(180,force_mockup_geometry,NULL);g_timeout_add(1000,heroic_session_status_tick,NULL);
}

int main(int argc,char**argv){memset(&G,0,sizeof G);G.selected=-1;clear_desktop_activation_env();if(argc>1&&!strcmp(argv[1],"--cleanup-steam-hooks")){char backup[2048]={0};int files=0;int n=cleanup_legacy_steam_hooks(backup,sizeof backup,&files);if(n>0){printf("Removed legacy wand-steam-wrap Launch Options from %d Steam config file(s).\n",files);if(backup[0])printf("Last backup: %s\n",backup);printf("Restart Steam once before testing direct Play.\n");return 0;}printf("No legacy wand-steam-wrap Launch Options found.\n");return 0;}G.legacy_wrapper_neutralized=neutralize_legacy_wrapper();gtk_init(&argc,&argv);if(!start_backend()){fprintf(stderr,"Could not start GameWeld backend.\n");return 2;}char *e=NULL;if(!refresh_model(&e)){fprintf(stderr,"Backend status failed: %s\n",e?e:"unknown");free(e);}build_ui();gtk_main();if(G.backend_pid>0){kill(G.backend_pid,SIGTERM);waitpid(G.backend_pid,NULL,WNOHANG);}return 0;}
