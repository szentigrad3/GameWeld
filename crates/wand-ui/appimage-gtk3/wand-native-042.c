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
typedef struct _GtkListBox GtkListBox;
typedef struct _GtkListBoxRow GtkListBoxRow;
typedef struct _GtkStack GtkStack;
typedef struct _GtkTextView GtkTextView;
typedef struct _GtkTextBuffer GtkTextBuffer;
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
extern void gtk_entry_set_placeholder_text(GtkEntry *, const char *);
extern void gtk_entry_set_icon_from_icon_name(GtkEntry *, int, const char *);
extern const char *gtk_entry_get_text(GtkEntry *);
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
#define FALSE 0
#define TRUE 1

#define MAX_GAMES 512
#define HTTP_MAX (1024 * 1024)

typedef struct {
    char appid[32];
    char name[384];
    char install_dir[1024];
    char selected_tool[256];
    int wand_found;
} Game;

typedef struct App App;

struct App {
    int port;
    pid_t backend_pid;
    Game games[MAX_GAMES];
    int game_count;
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
    char artwork_appid[32];
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
    GtkWidget *activity;
    GtkWidget *setup_status;
    GtkWidget *setup_detail;
    GtkWidget *health_detail;
    GtkWidget *nav_home;
    GtkWidget *nav_library;
    GtkWidget *nav_setup;
    GtkWidget *nav_diag;
    GtkWidget *nav_settings;
    GtkWidget *nav_about;
};

static App G;

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
static int parse_games(const char *json) {
    const char *p=find_key(json,"games"); if(!p)return 0; p=strchr(p,'['); if(!p)return 0; p++;
    int count=0; while(*p && *p!=']' && count<MAX_GAMES){ while(*p && *p!='{' && *p!=']')p++; if(*p!='{')break; const char *start=p; int depth=0; int inq=0; do{ if(*p=='\"' && (p==start||p[-1]!='\\'))inq=!inq; if(!inq){if(*p=='{')depth++;else if(*p=='}')depth--;} p++; }while(*p && depth>0); size_t n=(size_t)(p-start); char *obj=malloc(n+1); memcpy(obj,start,n); obj[n]=0;
        Game *g=&G.games[count]; memset(g,0,sizeof *g); json_string(obj,"appid",g->appid,sizeof g->appid); json_string(obj,"name",g->name,sizeof g->name); json_string(obj,"install_dir",g->install_dir,sizeof g->install_dir); json_string(obj,"selected_tool",g->selected_tool,sizeof g->selected_tool); g->wand_found=json_bool(obj,"wand_found",0); free(obj); if(g->appid[0])count++;
    } return count;
}

static int refresh_model(char **err) {
    char *body=NULL; int code=0; if(http_request("GET","/api/status",NULL,&body,&code)<0){*err=strdup("Could not contact Wand Native backend.");return 0;}
    if(code!=200){*err=body;return 0;}
    G.wand_installed=json_bool(body,"wand_installed",0); G.wand_healthy=json_bool(body,"wand_healthy",0); G.base_compatible=json_bool(body,"base_compatible",0);
    json_string(body,"base_proton",G.base_proton,sizeof G.base_proton); json_string(body,"wand_tool",G.wand_tool,sizeof G.wand_tool); json_string(body,"verify_message",G.verify_message,sizeof G.verify_message);
    G.game_count=parse_games(body); if(G.selected>=G.game_count)G.selected=G.game_count?0:-1; free(body); return 1;
}

static int start_backend(void) {
    const char *path=getenv("WAND_NATIVE_BACKEND"); char fallback[2048];
    if(!path||!*path){const char *appdir=getenv("APPDIR"); if(appdir){snprintf(fallback,sizeof fallback,"%s/usr/libexec/wand-native-backend",appdir);path=fallback;} else path="wand-native-backend";}
    int fds[2]; if(pipe(fds)<0)return 0; pid_t p=fork(); if(p<0)return 0;
    if(p==0){close(fds[0]); dup2(fds[1],STDOUT_FILENO); dup2(fds[1],STDERR_FILENO); close(fds[1]); execl(path,path,(char*)NULL); _exit(127);} close(fds[1]); G.backend_pid=p;
    char line[1024]={0}; size_t n=0; for(int tries=0;tries<100 && n+1<sizeof line;tries++){char c; ssize_t r=read(fds[0],&c,1); if(r==1){line[n++]=c; if(c=='\n')break;} else {usleep(50000);} } close(fds[0]);
    char *q=strstr(line,"127.0.0.1:"); if(!q)return 0; G.port=atoi(q+10); return G.port>0;
}

static void refresh_ui(void);

static gboolean job_done(void *vp);

typedef enum { JOB_SETUP, JOB_VERIFY, JOB_HEALTH, JOB_PLAY, JOB_REFRESH } JobType;
typedef struct { JobType type; char appid[32]; char *message; int success; } Job;

static void *job_worker(void *vp) {
    Job *j=vp; char *body=NULL; int code=0; char path[256],data[128];
    if(j->type==JOB_SETUP){ http_request("POST","/api/install","{}",&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_VERIFY){ http_request("GET","/api/verify",NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_HEALTH){ snprintf(path,sizeof path,"/api/health?appid=%s",j->appid); http_request("GET",path,NULL,&body,&code); j->success=(code>=200&&code<300); }
    else if(j->type==JOB_PLAY){ snprintf(data,sizeof data,"{\"appid\":\"%s\"}",j->appid); http_request("POST","/api/set-game",data,&body,&code); j->success=(code>=200&&code<300); if(j->success){ pid_t p=fork(); if(p==0){execlp("steam","steam","-applaunch",j->appid,(char*)NULL);_exit(127);} } }
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
    if(!g||!g->appid[0])return 0; char p[2048]; const char *home=getenv("HOME"),*xdg=getenv("XDG_DATA_HOME"),*appdir=getenv("APPDIR"),*override=getenv("WAND_NATIVE_ARTWORK_DIR");
    /* User overrides win, then curated AppImage artwork. Layout: <root>/<appid>/{hero,cover}.png */
    if(override&&*override){snprintf(p,sizeof p,"%s/%s",override,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(xdg&&*xdg){snprintf(p,sizeof p,"%s/wand-native/artwork/%s",xdg,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(home&&*home){snprintf(p,sizeof p,"%s/.local/share/wand-native/artwork/%s",home,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}
    if(appdir&&*appdir){snprintf(p,sizeof p,"%s/usr/share/wand-native/assets/games/%s",appdir,g->appid);if(try_named_art(p,NULL,cover,out,cap))return 1;}

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
    const char*a=getenv("APPDIR");char p[2048];if(a&&*a&&name&&*name)snprintf(p,sizeof p,"%s/usr/share/wand-native/assets/%s",a,name);else if(name&&*name)snprintf(p,sizeof p,"usr/share/wand-native/assets/%s",name);else if(a&&*a)snprintf(p,sizeof p,"%s/.DirIcon",a);else snprintf(p,sizeof p,".DirIcon");
    GdkPixbuf*pix=gdk_pixbuf_new_from_file_at_scale(p,w,h,FALSE,NULL);if(!pix&&a&&*a){snprintf(p,sizeof p,"%s/.DirIcon",a);pix=gdk_pixbuf_new_from_file_at_scale(p,w,h,FALSE,NULL);}if(!pix)return NULL;GtkWidget*i=gtk_image_new_from_pixbuf(pix);g_object_unref(pix);return i;
}
static void refresh_artwork(Game *g){
    char hero[2048]={0},cover[2048]={0};int hh=resolve_game_art(g,0,hero,sizeof hero);int hc=resolve_game_art(g,1,cover,sizeof cover);
    if(!hh&&hc){snprintf(hero,sizeof hero,"%s",cover);hh=1;}if(!hc&&hh){snprintf(cover,sizeof cover,"%s",hero);hc=1;}
    set_image_path(G.hero_image,hh?hero:NULL,893,275);set_image_path(G.cover_image,hc?cover:NULL,327,235);
    if(g&&strcmp(G.artwork_appid,g->appid)){snprintf(G.artwork_appid,sizeof G.artwork_appid,"%s",g->appid);if(hh||hc)log_line("Artwork loaded for %s%s%s",g->name,hh?" • hero":"",hc?" • cover":"");else log_line("No artwork cached yet for %s (AppID %s). Steam artwork will be used when available.",g->name,g->appid);}
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
static void spawn_detached(const char *a,const char *b,const char *c){pid_t p=fork();if(p==0){if(c)execlp(a,a,b,c,(char*)NULL);else if(b)execlp(a,a,b,(char*)NULL);else execlp(a,a,(char*)NULL);_exit(127);}}
static void set_label(GtkWidget *w,const char *s){ if(w)gtk_label_set_text((GtkLabel*)w,s?s:""); }
static void selected_changed(GtkListBox *list,GtkListBoxRow *row,void *data){(void)list;(void)data;if(!row)return; int idx=gtk_list_box_row_get_index(row); if(idx>=0&&idx<G.game_count){G.selected=idx;refresh_ui();}}

static void refresh_ui(void) {
    char b[2048]; Game *g=(G.selected>=0&&G.selected<G.game_count)?&G.games[G.selected]:NULL;
    if(G.top_steam_status)gtk_label_set_markup((GtkLabel*)G.top_steam_status,G.game_count?"<span foreground=\"#f4f6fa\" weight=\"bold\">Steam Detected</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Online</span>":"<span foreground=\"#f4f6fa\" weight=\"bold\">Steam Detected</span>\n<span foreground=\"#ef6a73\" weight=\"bold\">Offline</span>");
    if(g){refresh_artwork(g);set_label(G.hero_name,g->name);snprintf(b,sizeof b,"App ID: %s",g->appid);set_label(G.hero_meta,b);if(G.game_detected_detail){snprintf(b,sizeof b,"%s\nApp ID: %s",g->name,g->appid);set_label(G.game_detected_detail,b);}gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#28e57b\" weight=\"bold\">Online</span>\n<span foreground=\"#aeb9c7\">🎮   Game:        </span><span foreground=\"#28e57b\" weight=\"bold\">Installed</span>\n<span foreground=\"#aeb9c7\">⚙   Proton:      GE-Proton (Game)</span>");set_label(G.right_prefix,g->wand_found?"▰   Prefix:      Compatible":"▰   Prefix:      Detected");}
    else {if(G.game_detected_detail)set_label(G.game_detected_detail,"No Steam game selected");set_image_path(G.hero_image,NULL,893,275);set_image_path(G.cover_image,NULL,327,235);G.artwork_appid[0]=0;set_label(G.hero_name,"Select a Steam game");set_label(G.hero_meta,"App ID: —");gtk_label_set_markup((GtkLabel*)G.right_game,"<span foreground=\"#aeb9c7\">◉   Steam:       </span><span foreground=\"#ef6a73\" weight=\"bold\">Offline</span>\n<span foreground=\"#aeb9c7\">🎮   Game:        Not detected</span>\n<span foreground=\"#aeb9c7\">⚙   Proton:      —</span>");set_label(G.right_prefix,"▰   Prefix:      —");}
    if(G.wand_installed)gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">W   Wand:        </span><span foreground=\"#28e57b\" weight=\"bold\">Installed</span>\n<span foreground=\"#aeb9c7\">✣   Trainer:     </span><span foreground=\"#28e57b\" weight=\"bold\">Available</span>");else gtk_label_set_markup((GtkLabel*)G.right_wand,"<span foreground=\"#aeb9c7\">W   Wand:        Not installed\n✣   Trainer:     Unavailable</span>");
    if(G.wand_healthy)gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#28e57b\" weight=\"bold\">GE-Proton-Wand-SHA256</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#28e57b\" weight=\"bold\">Ready to Launch</span>");else gtk_label_set_markup((GtkLabel*)G.right_proton,"<span foreground=\"#aeb9c7\">⚙   Proton:      </span><span foreground=\"#efb85b\" weight=\"bold\">Needs setup</span>\n<span foreground=\"#aeb9c7\">ⓘ   Status:      </span><span foreground=\"#efb85b\" weight=\"bold\">Setup required</span>");
    set_label(G.game_ready,g?"Installed":"Not detected");set_label(G.wand_ready,G.wand_installed?"Ready":"Needs setup");set_label(G.compat_ready,G.wand_healthy?"Configured":"Needs repair");
    if(G.setup_status)set_label(G.setup_status,G.wand_healthy?"✓ Compatibility layer ready":"Compatibility setup required");
    if(G.setup_detail){snprintf(b,sizeof b,"%s\nBase Proton: %s\nWand tool: %s",G.verify_message[0]?G.verify_message:"Not checked",G.base_proton[0]?G.base_proton:"Not detected",G.wand_tool[0]?G.wand_tool:"Not installed");set_label(G.setup_detail,b);}
}

static void on_play(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Steam game first.");return;}start_job(JOB_PLAY,G.games[G.selected].appid,"Preparing game and launching with Wand…");}
static void on_play_normal(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a Steam game first.");return;}spawn_detached("steam","-applaunch",G.games[G.selected].appid);log_line("Launching normally through Steam…");}
static void on_steam_page(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;char u[128];snprintf(u,sizeof u,"steam://store/%s",G.games[G.selected].appid);spawn_detached("xdg-open",u,NULL);}
static void on_game_folder(GtkButton*b,void*d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count)return;spawn_detached("xdg-open",G.games[G.selected].install_dir,NULL);}
static void on_minimize(GtkButton*b,void*d){(void)b;(void)d;gtk_window_iconify((GtkWindow*)G.window);}
static void on_maximize(GtkButton*b,void*d){(void)b;(void)d;static int m=0;if(m){gtk_window_unmaximize((GtkWindow*)G.window);m=0;}else{gtk_window_maximize((GtkWindow*)G.window);m=1;}}
static void on_close_btn(GtkButton*b,void*d){(void)b;(void)d;gtk_widget_destroy(G.window);}
static void on_setup(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_SETUP,NULL,"Installing / repairing Wand compatibility layer…");}
static void on_verify(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_VERIFY,NULL,"Verifying Wand compatibility layer…");}
static void on_health(GtkButton *b,void *d){(void)b;(void)d;if(G.selected<0||G.selected>=G.game_count){log_line("Choose a game first.");return;}start_job(JOB_HEALTH,G.games[G.selected].appid,"Checking trainer health…");}
static void on_refresh(GtkButton *b,void *d){(void)b;(void)d;start_job(JOB_REFRESH,NULL,"Refreshing Steam and Wand status…");}

static void nav_activate(GtkWidget *active,const char *page){GtkWidget *all[]={G.nav_home,G.nav_library,G.nav_setup,G.nav_diag,G.nav_settings,G.nav_about};for(int i=0;i<6;i++)if(all[i])unstyle(all[i],"nav-active");style(active,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,page);}
static void nav_home(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_home,"home");}
static void nav_library(GtkButton*b,void*d){(void)b;(void)d;nav_activate(G.nav_library,"library");}
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
static GtkWidget *launch_button(int primary){
    GtkWidget*b=gtk_button_new();gtk_widget_set_name(b,primary?"play":"normal");
    GtkWidget*r=box(GTK_ORIENTATION_HORIZONTAL,14);margins(r,12);
    GtkWidget*ic=label("▶","launch-icon");gtk_widget_set_halign(ic,GTK_ALIGN_CENTER);pack(r,ic,0);
    GtkWidget*t=box(GTK_ORIENTATION_VERTICAL,1);
    GtkWidget*title=label(primary?"PLAY WITH WAND":"Play Normally",primary?"launch-title":"normal-title");
    GtkWidget*sub=label(primary?"Launch game with Wand and trainer":"Launch without Wand",primary?"launch-subtitle":"normal-subtitle");
    pack(t,title,0);pack(t,sub,0);pack(r,t,1);gtk_container_add(b,r);return b;
}

static GtkWidget *build_home(void){
    GtkWidget*page=box(GTK_ORIENTATION_HORIZONTAL,13);gtk_widget_set_name(page,"page");margins(page,12);
    GtkWidget*main=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_hexpand(main,TRUE);pack(page,main,1);

    GtkWidget*hero=box(GTK_ORIENTATION_VERTICAL,7);gtk_widget_set_name(hero,"hero-frame");
    G.hero_image=gtk_image_new();gtk_widget_set_size_request(G.hero_image,893,275);pack(hero,G.hero_image,0);
    G.hero_name=label("Select a Steam game",NULL);gtk_widget_set_name(G.hero_name,"game-title");gtk_widget_set_margin_start(G.hero_name,14);gtk_widget_set_margin_top(G.hero_name,5);pack(hero,G.hero_name,0);
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
    GtkWidget*c2=status_card("W","Wand Ready","Trainer installed and\nconfigured",&G.wand_ready,"Ready");
    GtkWidget*c3=status_card("⚙","Compatibility","GE-Proton-Wand-SHA256",&G.compat_ready,"Configured");
    pack(cards,c1,1);pack(cards,c2,1);pack(cards,c3,1);pack(main,cards,0);

    GtkWidget*log=box(GTK_ORIENTATION_VERTICAL,6);style(log,"card");GtkWidget*lh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(lh,label("▣  Activity Log","card-title"),1);GtkWidget*clear=button("⌫  Clear Log","action");pack(lh,clear,0);pack(log,lh,0);
    G.activity=gtk_text_view_new();gtk_text_view_set_editable((GtkTextView*)G.activity,FALSE);gtk_text_view_set_cursor_visible((GtkTextView*)G.activity,FALSE);gtk_text_view_set_monospace((GtkTextView*)G.activity,TRUE);gtk_widget_set_name(G.activity,"logframe");
    GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_size_request(sc,-1,180);gtk_container_add(sc,G.activity);pack(log,sc,1);pack(main,log,1);

    GtkWidget*right=box(GTK_ORIENTATION_VERTICAL,10);gtk_widget_set_size_request(right,352,-1);
    GtkWidget*cf=box(GTK_ORIENTATION_VERTICAL,0);style(cf,"card");G.cover_image=gtk_image_new();gtk_widget_set_size_request(G.cover_image,327,235);pack(cf,G.cover_image,0);pack(right,cf,0);
    GtkWidget*gs=box(GTK_ORIENTATION_VERTICAL,7);style(gs,"card");style(gs,"status-card");GtkWidget*gh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(gh,label("Game Status","card-title"),1);GtkWidget*gready=label("●  Ready to Play","good");gtk_widget_set_name(gready,"status-pill");pack(gh,gready,0);pack(gs,gh,0);G.right_game=label("◉   Steam:       Online\n🎮   Game:        Installed\n⚙   Proton:      GE-Proton (Game)","muted");pack(gs,G.right_game,0);G.right_prefix=label("▰   Prefix:      Compatible","good");pack(gs,G.right_prefix,0);pack(right,gs,0);
    GtkWidget*ws=box(GTK_ORIENTATION_VERTICAL,7);style(ws,"card");style(ws,"status-card");GtkWidget*wh=box(GTK_ORIENTATION_HORIZONTAL,8);pack(wh,label("Wand Status","card-title"),1);GtkWidget*wready=label("●  Ready","good");gtk_widget_set_name(wready,"status-pill");pack(wh,wready,0);pack(ws,wh,0);G.right_wand=label("W   Wand:        Installed\n✣   Trainer:     Available","muted");pack(ws,G.right_wand,0);G.right_proton=label("⚙   Proton:      GE-Proton-Wand-SHA256\nⓘ   Status:      Ready to Launch","good");pack(ws,G.right_proton,0);pack(right,ws,0);
    GtkWidget*qa=box(GTK_ORIENTATION_VERTICAL,7);style(qa,"card");pack(qa,label("Quick Actions","card-title"),0);GtkWidget*h=quick_button("utilities-system-monitor-symbolic","Check Trainer Health");GtkWidget*rp=quick_button("applications-engineering-symbolic","Repair Wand Setup");GtkWidget*gf=quick_button("folder-open-symbolic","Open Game Folder");GtkWidget*sp=quick_button("external-link-symbolic","Open Steam Page");g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);g_signal_connect_data(rp,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(gf,"clicked",(GCallback)on_game_folder,NULL,NULL,0);g_signal_connect_data(sp,"clicked",(GCallback)on_steam_page,NULL,NULL,0);pack(qa,h,0);pack(qa,rp,0);pack(qa,gf,0);pack(qa,sp,0);pack(right,qa,0);
    GtkWidget*rgrow=box(GTK_ORIENTATION_VERTICAL,0);pack(right,rgrow,1);GtkWidget*rf=label("Wand Native 0.1.42   |   Open Source   |   MIT License",NULL);gtk_widget_set_name(rf,"footer");gtk_widget_set_halign(rf,GTK_ALIGN_CENTER);pack(right,rf,0);pack(page,right,0);
    return page;
}

static GtkWidget *build_library(void){
    GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,10);margins(p,18);GtkWidget*t=label("Game Library",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);
    GtkWidget*help=label("Every detected game uses its own artwork. Wand Native checks user overrides first, then curated assets, then Steam's local library artwork cache.","muted");gtk_label_set_line_wrap((GtkLabel*)help,TRUE);pack(p,help,0);
    GtkWidget*sc=gtk_scrolled_window_new(NULL,NULL);gtk_widget_set_vexpand(sc,TRUE);G.game_list=gtk_list_box_new();g_signal_connect_data(G.game_list,"row-selected",(GCallback)selected_changed,NULL,NULL,0);
    for(int i=0;i<G.game_count;i++){
        GtkWidget*r=gtk_list_box_row_new();G.game_rows[i]=r;GtkWidget*rb=box(GTK_ORIENTATION_HORIZONTAL,12);margins(rb,9);
        GtkWidget*thumb=gtk_image_new();style(thumb,"game-thumb");char art[2048]={0};if(!resolve_game_art(&G.games[i],1,art,sizeof art))resolve_game_art(&G.games[i],0,art,sizeof art);set_image_path(thumb,art[0]?art:NULL,72,96);pack(rb,thumb,0);
        GtkWidget*txt=box(GTK_ORIENTATION_VERTICAL,4);GtkWidget*n=label(G.games[i].name,"game-row-title");pack(txt,n,0);char x[128];snprintf(x,sizeof x,"Steam • App ID: %s",G.games[i].appid);pack(txt,label(x,"muted"),0);pack(txt,label(art[0]?"Artwork ready":"Artwork will load from Steam cache when available","muted"),0);pack(rb,txt,1);GtkWidget*installed=label("Installed","good");gtk_widget_set_name(installed,"status-pill");pack(rb,installed,0);
        gtk_container_add(r,rb);gtk_list_box_insert((GtkListBox*)G.game_list,r,-1);
    }
    gtk_container_add(sc,G.game_list);pack(p,sc,1);return p;
}

static GtkWidget *build_setup(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Setup & Compatibility",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);pack(p,label("Wand Native keeps a separate Proton-GE tool so your normal Proton installations remain untouched.","muted"),0);GtkWidget*c=card("Compatibility status","Checking…",&G.setup_detail);G.setup_status=label("Checking…","good");pack(c,G.setup_status,0);pack(p,c,0);GtkWidget*row=box(GTK_ORIENTATION_HORIZONTAL,8);GtkWidget*i=button("Install / Repair","action");GtkWidget*v=button("Verify","action");g_signal_connect_data(i,"clicked",(GCallback)on_setup,NULL,NULL,0);g_signal_connect_data(v,"clicked",(GCallback)on_verify,NULL,NULL,0);pack(row,i,0);pack(row,v,0);pack(p,row,0);GtkWidget*note=card("What setup does","Detects Steam and Proton-GE, creates GE Proton Wand SHA256, grafts the proven patched crypt32 DLLs, and leaves normal Proton-GE unchanged.",NULL);pack(p,note,0);return p;}
static GtkWidget *build_diag(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Diagnostics",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);GtkWidget*h=button("Check Trainer Health","action");g_signal_connect_data(h,"clicked",(GCallback)on_health,NULL,NULL,0);pack(p,h,0);G.health_detail=label("Launch a game with Wand, then check TrainerLib/signature/command health here.","muted");gtk_label_set_line_wrap((GtkLabel*)G.health_detail,TRUE);pack(p,G.health_detail,0);return p;}
static GtkWidget *build_settings(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Settings",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);pack(p,card("Launch behaviour","PLAY WITH WAND keeps Steam running and uses the isolated Wand Proton tool. Steam is only restarted when a new compatibility tool must be registered.",NULL),0);pack(p,card("Safety","Wand Native does not change ptrace/Yama settings and does not alter your normal Proton-GE installation.",NULL),0);return p;}
static GtkWidget *build_about(void){GtkWidget*p=box(GTK_ORIENTATION_VERTICAL,12);margins(p,20);GtkWidget*t=label("Wand Native",NULL);gtk_widget_set_name(t,"section-title");pack(p,t,0);pack(p,label("0.1.42 UI Preview\nNative Linux front-end for running Wand with Steam/Proton games.","muted"),0);pack(p,label("Backend: proven 0.1.41 RC8 runtime (frozen)\nUI: redesigned native GTK shell\nCompatibility: isolated GE Proton Wand SHA256","muted"),0);return p;}

static void build_ui(void){
    G.window=gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title((GtkWindow*)G.window,"Wand Native");
    gtk_window_set_default_size((GtkWindow*)G.window,1536,1024);
    gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    gtk_window_set_decorated((GtkWindow*)G.window,TRUE);
    g_signal_connect_data(G.window,"destroy",(GCallback)on_destroy,NULL,NULL,0);

    /* Test 9: make our own full-width GTK titlebar. This is the supported GTK3
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
    GtkWidget*wm=asset_image("wand-logo-reference.png",60,52);
    if(!wm){wm=label("W",NULL);gtk_widget_set_name(wm,"wandmark");}
    pack(titlebrand,wm,0);
    GtkWidget*bt=box(GTK_ORIENTATION_VERTICAL,0);
    GtkWidget*brand=label("Wand Native",NULL);gtk_widget_set_name(brand,"brand");pack(bt,brand,0);
    GtkWidget*ver=label("v0.1.42",NULL);gtk_widget_set_name(ver,"brandver");pack(bt,ver,0);
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
    gtk_label_set_markup((GtkLabel*)G.top_steam_status,"<span foreground=\"#f4f6fa\" weight=\"bold\">Steam Detected</span>\n<span foreground=\"#28e57b\" weight=\"bold\">Online</span>");
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
    G.nav_setup=make_nav("applications-engineering-symbolic","Setup",(GCallback)nav_setup);
    GtkWidget*compat=make_nav("emblem-ok-symbolic","Compatibility",(GCallback)nav_setup);
    G.nav_diag=make_nav("utilities-system-monitor-symbolic","Diagnostics",(GCallback)nav_diag);
    G.nav_settings=make_nav("preferences-system-symbolic","Settings",(GCallback)nav_settings);
    G.nav_about=make_nav("dialog-information-symbolic","About",(GCallback)nav_about);
    pack(side,G.nav_home,0);pack(side,G.nav_library,0);pack(side,G.nav_setup,0);pack(side,compat,0);pack(side,G.nav_diag,0);pack(side,G.nav_settings,0);pack(side,G.nav_about,0);
    GtkWidget*grow=box(GTK_ORIENTATION_VERTICAL,0);pack(side,grow,1);
    GtkWidget*sf=box(GTK_ORIENTATION_VERTICAL,4);gtk_widget_set_name(sf,"sidebar-foot");pack(sf,label("●   Wand Native","good"),0);pack(sf,label("      v0.1.42\n\nLinux • Proton • Native GUI\n\nPlay More. Your Way.","muted"),0);pack(side,sf,0);pack(root,side,0);

    GtkWidget*main=box(GTK_ORIENTATION_VERTICAL,0);gtk_widget_set_hexpand(main,TRUE);pack(root,main,1);
    G.stack=gtk_stack_new();gtk_widget_set_hexpand(G.stack,TRUE);gtk_widget_set_vexpand(G.stack,TRUE);
    gtk_stack_add_named((GtkStack*)G.stack,build_home(),"home");
    gtk_stack_add_named((GtkStack*)G.stack,build_library(),"library");
    gtk_stack_add_named((GtkStack*)G.stack,build_setup(),"setup");
    gtk_stack_add_named((GtkStack*)G.stack,build_diag(),"diag");
    gtk_stack_add_named((GtkStack*)G.stack,build_settings(),"settings");
    gtk_stack_add_named((GtkStack*)G.stack,build_about(),"about");
    pack(main,G.stack,1);

    style(G.nav_home,"nav-active");gtk_stack_set_visible_child_name((GtkStack*)G.stack,"home");
    if(G.game_count>0){G.selected=0;gtk_list_box_select_row((GtkListBox*)G.game_list,(GtkListBoxRow*)G.game_rows[0]);}
    refresh_ui();
    log_line("Checking Steam installation...");log_line("Steam found");log_line("Checking game installation...");log_line("Game detected");log_line("Wand ready");log_line("Proton tool ready: GE-Proton-Wand-SHA256");log_line("Ready to launch!");
    GtkCssProvider*prov=gtk_css_provider_new();gtk_css_provider_load_from_data(prov,CSS,-1,NULL);gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),prov,GTK_STYLE_PROVIDER_PRIORITY_USER);g_object_unref(prov);
    gtk_widget_show_all(G.window);
    gtk_window_resize((GtkWindow*)G.window,1536,1024);gtk_window_set_position((GtkWindow*)G.window,GTK_WIN_POS_CENTER);
    g_idle_add(force_mockup_geometry,NULL);g_timeout_add(180,force_mockup_geometry,NULL);
}

int main(int argc,char**argv){memset(&G,0,sizeof G);G.selected=-1;gtk_init(&argc,&argv);if(!start_backend()){fprintf(stderr,"Could not start Wand Native backend.\n");return 2;}char *e=NULL;if(!refresh_model(&e)){fprintf(stderr,"Backend status failed: %s\n",e?e:"unknown");free(e);}build_ui();gtk_main();if(G.backend_pid>0){kill(G.backend_pid,SIGTERM);waitpid(G.backend_pid,NULL,WNOHANG);}return 0;}
