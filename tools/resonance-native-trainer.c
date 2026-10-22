/*
 * Wand Native - Resonance: A Plague Tale Legacy native trainer helper
 * Direct conversion of the core behavior in Paul44's Resonance v1.1 Cheat Engine table.
 *
 * This helper intentionally has no Cheat Engine dependency and no PE imports. It resolves
 * Win32 APIs at runtime so it can be cross-built in a minimal environment.
 *
 * Supported converted features:
 *   - God Mode
 *   - Invisible
 *   - Resonance Points
 *   - FOV
 *   - Console show/hide
 *
 * Single-player/offline use only. No anti-cheat bypasses.
 */

int _fltused = 0;

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef signed int i32;
typedef signed long long i64;
typedef unsigned long long usize;
typedef long long isize;
typedef void *HANDLE;
typedef void *HMODULE;
typedef void *HWND;
typedef void *HINSTANCE;
typedef void *HCURSOR;
typedef void *HBRUSH;
typedef void *HICON;
typedef void *HMENU;
typedef u64 WPARAM;
typedef i64 LPARAM;
typedef i64 LRESULT;
typedef u32 DWORD;
typedef int BOOL;
typedef u16 WCHAR;
typedef const char *LPCSTR;
typedef char *LPSTR;
typedef const WCHAR *LPCWSTR;
typedef void *LPVOID;
typedef const void *LPCVOID;
typedef usize SIZE_T;
typedef u64 ULONG_PTR;
typedef unsigned short ATOM;
typedef LRESULT (*WNDPROC)(HWND,u32,WPARAM,LPARAM);

#define NULL ((void*)0)
#define TRUE 1
#define FALSE 0
#define INVALID_HANDLE_VALUE ((HANDLE)(isize)-1)

#define TH32CS_SNAPPROCESS 0x00000002u
#define TH32CS_SNAPMODULE  0x00000008u
#define TH32CS_SNAPMODULE32 0x00000010u
#define PROCESS_VM_OPERATION 0x0008u
#define PROCESS_VM_READ      0x0010u
#define PROCESS_VM_WRITE     0x0020u
#define PROCESS_QUERY_INFORMATION 0x0400u
#define MEM_COMMIT  0x1000u
#define MEM_RESERVE 0x2000u
#define MEM_RELEASE 0x8000u
#define PAGE_NOACCESS 0x01u
#define PAGE_GUARD 0x100u
#define PAGE_EXECUTE_READWRITE 0x40u
#define STILL_ACTIVE 259u

#define WS_OVERLAPPEDWINDOW 0x00CF0000u
#define WS_VISIBLE 0x10000000u
#define WS_CHILD 0x40000000u
#define WS_TABSTOP 0x00010000u
#define WS_BORDER 0x00800000u
#define BS_AUTOCHECKBOX 0x00000003u
#define BM_GETCHECK 0x00F0u
#define BST_CHECKED 1u
#define SW_SHOW 5
#define SW_HIDE 0
#define CW_USEDEFAULT ((i32)0x80000000u)
#define COLOR_WINDOW 5
#define IDC_ARROW ((LPCSTR)(usize)32512)
#define DEFAULT_GUI_FONT 17
#define WM_CREATE 0x0001u
#define WM_DESTROY 0x0002u
#define WM_CLOSE 0x0010u
#define WM_COMMAND 0x0111u
#define WM_TIMER 0x0113u
#define WM_SETFONT 0x0030u
#define MB_OK 0x00000000u
#define MB_ICONERROR 0x00000010u

#define ID_ATTACH 1001
#define ID_GOD 1002
#define ID_INVIS 1003
#define ID_POINTS_EDIT 1004
#define ID_POINTS_SET 1005
#define ID_FOV_EDIT 1006
#define ID_FOV_SET 1007
#define ID_FOV_RESET 1008
#define ID_CONSOLE 1009
#define ID_STATUS 1010
#define TIMER_ATTACH 1

#define SCAN_BUF_SIZE (1024u*1024u)

#pragma pack(push, 8)
typedef struct {
    DWORD dwSize;
    DWORD cntUsage;
    DWORD th32ProcessID;
    ULONG_PTR th32DefaultHeapID;
    DWORD th32ModuleID;
    DWORD cntThreads;
    DWORD th32ParentProcessID;
    i32 pcPriClassBase;
    DWORD dwFlags;
    WCHAR szExeFile[260];
} PROCESSENTRY32W;

typedef struct {
    DWORD dwSize;
    DWORD th32ModuleID;
    DWORD th32ProcessID;
    DWORD GlblcntUsage;
    DWORD ProccntUsage;
    u8 *modBaseAddr;
    DWORD modBaseSize;
    HMODULE hModule;
    WCHAR szModule[256];
    WCHAR szExePath[260];
} MODULEENTRY32W;

typedef struct {
    LPVOID BaseAddress;
    LPVOID AllocationBase;
    DWORD AllocationProtect;
    DWORD _align1;
    SIZE_T RegionSize;
    DWORD State;
    DWORD Protect;
    DWORD Type;
    DWORD _align2;
} MEMORY_BASIC_INFORMATION;

typedef struct { i32 left, top, right, bottom; } RECT;
typedef struct { i32 x,y; } POINT;
typedef struct {
    HWND hwnd;
    u32 message;
    WPARAM wParam;
    LPARAM lParam;
    DWORD time;
    POINT pt;
    DWORD lPrivate;
} MSG;
typedef struct {
    u32 cbSize;
    u32 style;
    WNDPROC lpfnWndProc;
    i32 cbClsExtra;
    i32 cbWndExtra;
    HINSTANCE hInstance;
    HICON hIcon;
    HCURSOR hCursor;
    HBRUSH hbrBackground;
    LPCSTR lpszMenuName;
    LPCSTR lpszClassName;
    HICON hIconSm;
} WNDCLASSEXA;
#pragma pack(pop)

/* kernel32 */
typedef HMODULE (*LoadLibraryA_t)(LPCSTR);
typedef HMODULE (*GetModuleHandleA_t)(LPCSTR);
typedef HANDLE (*CreateToolhelp32Snapshot_t)(DWORD,DWORD);
typedef BOOL (*Process32FirstW_t)(HANDLE,PROCESSENTRY32W*);
typedef BOOL (*Process32NextW_t)(HANDLE,PROCESSENTRY32W*);
typedef BOOL (*Module32FirstW_t)(HANDLE,MODULEENTRY32W*);
typedef BOOL (*Module32NextW_t)(HANDLE,MODULEENTRY32W*);
typedef HANDLE (*OpenProcess_t)(DWORD,BOOL,DWORD);
typedef BOOL (*ReadProcessMemory_t)(HANDLE,LPCVOID,LPVOID,SIZE_T,SIZE_T*);
typedef BOOL (*WriteProcessMemory_t)(HANDLE,LPVOID,LPCVOID,SIZE_T,SIZE_T*);
typedef LPVOID (*VirtualAllocEx_t)(HANDLE,LPVOID,SIZE_T,DWORD,DWORD);
typedef BOOL (*VirtualFreeEx_t)(HANDLE,LPVOID,SIZE_T,DWORD);
typedef BOOL (*VirtualProtectEx_t)(HANDLE,LPVOID,SIZE_T,DWORD,DWORD*);
typedef SIZE_T (*VirtualQueryEx_t)(HANDLE,LPCVOID,MEMORY_BASIC_INFORMATION*,SIZE_T);
typedef BOOL (*FlushInstructionCache_t)(HANDLE,LPCVOID,SIZE_T);
typedef BOOL (*CloseHandle_t)(HANDLE);
typedef void (*Sleep_t)(DWORD);
typedef DWORD (*GetLastError_t)(void);
typedef void (*ExitProcess_t)(DWORD);
typedef BOOL (*GetExitCodeProcess_t)(HANDLE,DWORD*);
/* user32 */
typedef ATOM (*RegisterClassExA_t)(const WNDCLASSEXA*);
typedef HWND (*CreateWindowExA_t)(DWORD,LPCSTR,LPCSTR,DWORD,i32,i32,i32,i32,HWND,HMENU,HINSTANCE,LPVOID);
typedef LRESULT (*DefWindowProcA_t)(HWND,u32,WPARAM,LPARAM);
typedef BOOL (*ShowWindow_t)(HWND,i32);
typedef BOOL (*UpdateWindow_t)(HWND);
typedef i32 (*GetMessageA_t)(MSG*,HWND,u32,u32);
typedef BOOL (*TranslateMessage_t)(const MSG*);
typedef LRESULT (*DispatchMessageA_t)(const MSG*);
typedef void (*PostQuitMessage_t)(i32);
typedef BOOL (*SetWindowTextA_t)(HWND,LPCSTR);
typedef i32 (*GetWindowTextA_t)(HWND,LPSTR,i32);
typedef LRESULT (*SendMessageA_t)(HWND,u32,WPARAM,LPARAM);
typedef i32 (*MessageBoxA_t)(HWND,LPCSTR,LPCSTR,u32);
typedef HWND (*FindWindowA_t)(LPCSTR,LPCSTR);
typedef HCURSOR (*LoadCursorA_t)(HINSTANCE,LPCSTR);
typedef usize (*SetTimer_t)(HWND,usize,u32,void*);
typedef BOOL (*KillTimer_t)(HWND,usize);
/* gdi32 */
typedef void *(*GetStockObject_t)(i32);

static LoadLibraryA_t pLoadLibraryA;
static GetModuleHandleA_t pGetModuleHandleA;
static CreateToolhelp32Snapshot_t pCreateToolhelp32Snapshot;
static Process32FirstW_t pProcess32FirstW;
static Process32NextW_t pProcess32NextW;
static Module32FirstW_t pModule32FirstW;
static Module32NextW_t pModule32NextW;
static OpenProcess_t pOpenProcess;
static ReadProcessMemory_t pReadProcessMemory;
static WriteProcessMemory_t pWriteProcessMemory;
static VirtualAllocEx_t pVirtualAllocEx;
static VirtualFreeEx_t pVirtualFreeEx;
static VirtualProtectEx_t pVirtualProtectEx;
static VirtualQueryEx_t pVirtualQueryEx;
static FlushInstructionCache_t pFlushInstructionCache;
static CloseHandle_t pCloseHandle;
static Sleep_t pSleep;
static GetLastError_t pGetLastError;
static ExitProcess_t pExitProcess;
static GetExitCodeProcess_t pGetExitCodeProcess;
static RegisterClassExA_t pRegisterClassExA;
static CreateWindowExA_t pCreateWindowExA;
static DefWindowProcA_t pDefWindowProcA;
static ShowWindow_t pShowWindow;
static UpdateWindow_t pUpdateWindow;
static GetMessageA_t pGetMessageA;
static TranslateMessage_t pTranslateMessage;
static DispatchMessageA_t pDispatchMessageA;
static PostQuitMessage_t pPostQuitMessage;
static SetWindowTextA_t pSetWindowTextA;
static GetWindowTextA_t pGetWindowTextA;
static SendMessageA_t pSendMessageA;
static MessageBoxA_t pMessageBoxA;
static FindWindowA_t pFindWindowA;
static LoadCursorA_t pLoadCursorA;
static SetTimer_t pSetTimer;
static KillTimer_t pKillTimer;
static GetStockObject_t pGetStockObject;

static HANDLE g_proc;
static DWORD g_pid;
static u64 g_module_base;
static u64 g_module_size;
static u64 g_cheat_flags;
static u64 g_fov_global;
static u64 g_skill_addr;
static u64 g_remote_block;
static u64 g_pskill;
static int g_skill_injected;
static int g_console_shown;
static int g_ready_god;
static int g_ready_fov;
static int g_ready_points;

static HWND g_main;
static HWND g_status;
static HWND g_god;
static HWND g_invis;
static HWND g_points;
static HWND g_fov;
static HWND g_feature;

static u8 g_scanbuf[SCAN_BUF_SIZE];

static usize cstrlen(const char *s){ usize n=0; if(!s)return 0; while(s[n])n++; return n; }
static int lowerc(int c){ return (c>='A'&&c<='Z')?c+32:c; }
static int streqi(const char *a,const char*b){ if(!a||!b)return 0; while(*a&&*b){if(lowerc((u8)*a)!=lowerc((u8)*b))return 0;a++;b++;}return *a==0&&*b==0; }
static int wstreqi_ascii(const WCHAR*w,const char*s){ usize i=0; if(!w||!s)return 0; while(w[i]&&s[i]){if(lowerc((int)w[i])!=lowerc((u8)s[i]))return 0;i++;}return w[i]==0&&s[i]==0; }
static void memcopy(void*d,const void*s,usize n){u8*D=(u8*)d;const u8*S=(const u8*)s;while(n--)*D++=*S++;}
static void memzero(void*d,usize n){u8*D=(u8*)d;while(n--)*D++=0;}
static i32 read_i32(const u8*p){i32 v;memcopy(&v,p,4);return v;}
static void put_u64(u8*p,u64 v){memcopy(p,&v,8);} static void put_i32(u8*p,i32 v){memcopy(p,&v,4);}

static void* peb_ptr(void){void*p;__asm__("movq %%gs:0x60,%0":"=r"(p));return p;}

static void* find_module(const char*name){
    u8*peb=(u8*)peb_ptr(); if(!peb)return 0; u8*ldr=*(u8**)(peb+0x18); if(!ldr)return 0;
    u8*head=ldr+0x20; u8*link=*(u8**)head; u32 guard=0;
    while(link&&link!=head&&guard++<256){u8*ent=link-0x10;void*base=*(void**)(ent+0x30);u16 len=*(u16*)(ent+0x58);WCHAR*buf=*(WCHAR**)(ent+0x60);if(buf){usize chars=len/2;usize i=0;int ok=1;for(;name[i]&&i<chars;i++)if(lowerc((int)buf[i])!=lowerc((u8)name[i])){ok=0;break;}if(ok&&!name[i]&&i==chars)return base;}link=*(u8**)link;}
    return 0;
}
static int streq(const char*a,const char*b){while(a&&b&&*a&&*b){if(*a!=*b)return 0;a++;b++;}return a&&b&&*a==*b;}
static void* resolve_export(void*mb,const char*name){
    if(!mb||!name)return 0;u8*b=(u8*)mb;u32 pe=*(u32*)(b+0x3c);u8*opt=b+pe+24;u32 erva=*(u32*)(opt+0x70),esz=*(u32*)(opt+0x74);if(!erva)return 0;u8*e=b+erva;u32 n=*(u32*)(e+0x18),funcs=*(u32*)(e+0x1c),names=*(u32*)(e+0x20),ords=*(u32*)(e+0x24);
    for(u32 i=0;i<n;i++){char*s=(char*)(b+*(u32*)(b+names+i*4));if(streq(s,name)){u16 o=*(u16*)(b+ords+i*2);u32 r=*(u32*)(b+funcs+o*4);if(r>=erva&&r<erva+esz){char*f=(char*)(b+r),mod[80],fn[128],dll[88];u32 a=0,c=0;while(f[a]&&f[a]!='.'&&a<72){mod[a]=f[a];a++;}mod[a]=0;if(f[a]=='.')a++;while(f[a]&&c<120)fn[c++]=f[a++];fn[c]=0;c=0;while(mod[c]&&c<72){dll[c]=mod[c];c++;}dll[c++]='.';dll[c++]='d';dll[c++]='l';dll[c++]='l';dll[c]=0;void*m=find_module(dll);if(!m)return 0;return resolve_export(m,fn);}return b+r;}}
    return 0;
}

static int init_api(void){
    void*k=find_module("kernel32.dll");if(!k)return 0;
#define RESOLVE_K(name) p##name=(name##_t)resolve_export(k,#name); if(!p##name)return 0
    RESOLVE_K(LoadLibraryA); RESOLVE_K(GetModuleHandleA); RESOLVE_K(CreateToolhelp32Snapshot); RESOLVE_K(Process32FirstW); RESOLVE_K(Process32NextW); RESOLVE_K(Module32FirstW); RESOLVE_K(Module32NextW); RESOLVE_K(OpenProcess); RESOLVE_K(ReadProcessMemory); RESOLVE_K(WriteProcessMemory); RESOLVE_K(VirtualAllocEx); RESOLVE_K(VirtualFreeEx); RESOLVE_K(VirtualProtectEx); RESOLVE_K(VirtualQueryEx); RESOLVE_K(FlushInstructionCache); RESOLVE_K(CloseHandle); RESOLVE_K(Sleep); RESOLVE_K(GetLastError); RESOLVE_K(ExitProcess); RESOLVE_K(GetExitCodeProcess);
#undef RESOLVE_K
    void*u=pLoadLibraryA("user32.dll");if(!u)return 0;
#define RESOLVE_U(name) p##name=(name##_t)resolve_export(u,#name); if(!p##name)return 0
    RESOLVE_U(RegisterClassExA); RESOLVE_U(CreateWindowExA); RESOLVE_U(DefWindowProcA); RESOLVE_U(ShowWindow); RESOLVE_U(UpdateWindow); RESOLVE_U(GetMessageA); RESOLVE_U(TranslateMessage); RESOLVE_U(DispatchMessageA); RESOLVE_U(PostQuitMessage); RESOLVE_U(SetWindowTextA); RESOLVE_U(GetWindowTextA); RESOLVE_U(SendMessageA); RESOLVE_U(MessageBoxA); RESOLVE_U(FindWindowA); RESOLVE_U(LoadCursorA); RESOLVE_U(SetTimer); RESOLVE_U(KillTimer);
#undef RESOLVE_U
    void*g=pLoadLibraryA("gdi32.dll"); if(g)pGetStockObject=(GetStockObject_t)resolve_export(g,"GetStockObject");
    return 1;
}

static DWORD find_process(void){HANDLE s=pCreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);if(s==INVALID_HANDLE_VALUE)return 0;PROCESSENTRY32W pe;memzero(&pe,sizeof pe);pe.dwSize=sizeof pe;DWORD pid=0;if(pProcess32FirstW(s,&pe)){do{if(wstreqi_ascii(pe.szExeFile,"Resonance.exe")){pid=pe.th32ProcessID;break;}}while(pProcess32NextW(s,&pe));}pCloseHandle(s);return pid;}
static int find_main_module(DWORD pid,u64*base,u64*size){HANDLE s=pCreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);if(s==INVALID_HANDLE_VALUE)return 0;MODULEENTRY32W me;memzero(&me,sizeof me);me.dwSize=sizeof me;int ok=0;if(pModule32FirstW(s,&me)){do{if(wstreqi_ascii(me.szModule,"Resonance.exe")){*base=(u64)(usize)me.modBaseAddr;*size=me.modBaseSize;ok=1;break;}}while(pModule32NextW(s,&me));}pCloseHandle(s);return ok;}

static int rpm(u64 addr,void*out,usize n){SIZE_T got=0;return g_proc&&pReadProcessMemory(g_proc,(void*)(usize)addr,out,n,&got)&&got==n;}
static int wpm(u64 addr,const void*src,usize n){SIZE_T put=0;return g_proc&&pWriteProcessMemory(g_proc,(void*)(usize)addr,src,n,&put)&&put==n;}
static int read_u64_remote(u64 addr,u64*out){return rpm(addr,out,8);} static int write_u8_remote(u64 a,u8 v){return wpm(a,&v,1);} static int write_u32_remote(u64 a,u32 v){return wpm(a,&v,4);} static int write_float_remote(u64 a,float v){return wpm(a,&v,4);} static int read_float_remote(u64 a,float*v){return rpm(a,v,4);}

static int memeq(const u8*a,const u8*b,usize n){for(usize i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static u64 scan_exact(const u8*pat,usize plen){
    if(!g_proc||!g_module_base||!g_module_size||!pat||!plen)return 0;u64 cur=g_module_base,end=g_module_base+g_module_size;
    while(cur<end){MEMORY_BASIC_INFORMATION mbi;memzero(&mbi,sizeof mbi);SIZE_T q=pVirtualQueryEx(g_proc,(void*)(usize)cur,&mbi,sizeof mbi);if(!q||!mbi.RegionSize){cur+=0x1000;continue;}u64 rs=(u64)(usize)mbi.BaseAddress,re=rs+(u64)mbi.RegionSize;if(re<=cur){cur+=0x1000;continue;}u64 s=rs<g_module_base?g_module_base:rs,uend=re>end?end:re;
        if(mbi.State==MEM_COMMIT && !(mbi.Protect&PAGE_GUARD) && (mbi.Protect&0xff)!=PAGE_NOACCESS){u64 pos=s;while(pos<uend){usize want=(usize)(uend-pos);if(want>SCAN_BUF_SIZE)want=SCAN_BUF_SIZE;SIZE_T got=0;if(pReadProcessMemory(g_proc,(void*)(usize)pos,g_scanbuf,want,&got)&&got>=plen){for(usize i=0;i+plen<=got;i++)if(memeq(g_scanbuf+i,pat,plen))return pos+i;}if(want<=plen)break;pos+=want-(plen-1);}}
        cur=re;
    }return 0;
}

static int decode_rip_target(u64 a,u64*out){u8 b[20];if(!rpm(a,b,sizeof b))return 0;u32 i=0;while(i<4&&(b[i]==0x66||b[i]==0x67||b[i]==0xF2||b[i]==0xF3))i++;if((b[i]&0xF0)==0x40)i++;u8 op=b[i++];int imm=0;if(op==0x0F){u8 op2=b[i++];if(!(op2==0xB6||op2==0xB7||op2==0xBE||op2==0xBF))return 0;}else{if(op==0x80||op==0x83||op==0xC6)imm=1;else if(op==0x81||op==0xC7)imm=4;else if(!(op==0x8B||op==0x8D||op==0x89||op==0x8A||op==0x39||op==0x3B||op==0xFF))return 0;}u8 modrm=b[i++];if((modrm&0xC7)!=0x05)return 0;i32 disp=read_i32(b+i);i+=4;i+=(u32)imm;*out=a+(u64)i+(i64)disp;return 1;}

static u64 alloc_near(u64 around){u64 base=around&~0xffffULL;for(u32 step=1;step<8192;step++){u64 d=(u64)step*0x10000ULL;u64 cand1=base>d?base-d:0;if(cand1>0x10000){void*p=pVirtualAllocEx(g_proc,(void*)(usize)cand1,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);if(p){u64 x=(u64)(usize)p;i64 rel=(i64)x-(i64)(around+5);if(rel>=-0x7fffffffLL&&rel<=0x7fffffffLL)return x;pVirtualFreeEx(g_proc,p,0,MEM_RELEASE);}}u64 cand2=base+d;void*p2=pVirtualAllocEx(g_proc,(void*)(usize)cand2,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);if(p2){u64 x=(u64)(usize)p2;i64 rel=(i64)x-(i64)(around+5);if(rel>=-0x7fffffffLL&&rel<=0x7fffffffLL)return x;pVirtualFreeEx(g_proc,p2,0,MEM_RELEASE);}}
    return 0;
}

static int inject_skill_capture(void){
    static const u8 sig[]={0x8B,0x41,0x40,0x48,0x8B,0x5C,0x24,0x30};g_skill_addr=scan_exact(sig,sizeof sig);if(!g_skill_addr)return 0;u64 mem=alloc_near(g_skill_addr);if(!mem)return 0;g_remote_block=mem;g_pskill=mem+0x100;u64 zero=0;if(!wpm(g_pskill,&zero,8))return 0;
    u8 code[64];memzero(code,sizeof code);u32 n=0;code[n++]=0x41;code[n++]=0x57;code[n++]=0x49;code[n++]=0xBF;put_u64(code+n,g_pskill);n+=8;code[n++]=0x49;code[n++]=0x89;code[n++]=0x0F;code[n++]=0x41;code[n++]=0x5F;code[n++]=0x8B;code[n++]=0x41;code[n++]=0x40;code[n++]=0x48;code[n++]=0x8B;code[n++]=0x5C;code[n++]=0x24;code[n++]=0x30;code[n++]=0xE9;i64 back=(i64)(g_skill_addr+8)-(i64)(mem+n+4);if(back<-0x80000000LL||back>0x7fffffffLL)return 0;put_i32(code+n,(i32)back);n+=4;if(!wpm(mem,code,n))return 0;
    u8 patch[8];patch[0]=0xE9;i64 rel=(i64)mem-(i64)(g_skill_addr+5);if(rel<-0x80000000LL||rel>0x7fffffffLL)return 0;put_i32(patch+1,(i32)rel);patch[5]=patch[6]=patch[7]=0x90;DWORD old=0,tmp=0;if(!pVirtualProtectEx(g_proc,(void*)(usize)g_skill_addr,8,PAGE_EXECUTE_READWRITE,&old))return 0;if(!wpm(g_skill_addr,patch,8)){pVirtualProtectEx(g_proc,(void*)(usize)g_skill_addr,8,old,&tmp);return 0;}pVirtualProtectEx(g_proc,(void*)(usize)g_skill_addr,8,old,&tmp);pFlushInstructionCache(g_proc,(void*)(usize)g_skill_addr,8);g_skill_injected=1;return 1;
}

static void restore_skill(void){if(g_proc&&g_skill_injected&&g_skill_addr){static const u8 sig[]={0x8B,0x41,0x40,0x48,0x8B,0x5C,0x24,0x30};DWORD old=0,tmp=0;if(pVirtualProtectEx(g_proc,(void*)(usize)g_skill_addr,8,PAGE_EXECUTE_READWRITE,&old)){wpm(g_skill_addr,sig,8);pVirtualProtectEx(g_proc,(void*)(usize)g_skill_addr,8,old,&tmp);pFlushInstructionCache(g_proc,(void*)(usize)g_skill_addr,8);}}if(g_proc&&g_remote_block)pVirtualFreeEx(g_proc,(void*)(usize)g_remote_block,0,MEM_RELEASE);g_skill_injected=0;g_skill_addr=0;g_remote_block=0;g_pskill=0;}

static void set_status(const char*s){if(g_status&&pSetWindowTextA)pSetWindowTextA(g_status,s);} static void set_feature(const char*s){if(g_feature&&pSetWindowTextA)pSetWindowTextA(g_feature,s);}

static void detach_game(void){if(g_proc){if(g_cheat_flags){write_u8_remote(g_cheat_flags,0);write_u8_remote(g_cheat_flags+1,0);}restore_skill();pCloseHandle(g_proc);}g_proc=0;g_pid=0;g_module_base=0;g_module_size=0;g_cheat_flags=0;g_fov_global=0;g_ready_god=g_ready_fov=g_ready_points=0;set_status("Waiting for Resonance.exe...");set_feature("Native profile loaded. Start/load a save in Resonance.");}

static int attach_game(void){
    if(g_proc)return 1;DWORD pid=find_process();if(!pid){set_status("Waiting for Resonance.exe...");return 0;}HANDLE h=pOpenProcess(PROCESS_VM_OPERATION|PROCESS_VM_READ|PROCESS_VM_WRITE|PROCESS_QUERY_INFORMATION,FALSE,pid);if(!h){set_status("Found Resonance.exe but could not open it.");return 0;}g_proc=h;g_pid=pid;if(!find_main_module(pid,&g_module_base,&g_module_size)){detach_game();set_status("Attached, but Resonance.exe module was not found.");return 0;}
    static const u8 gods[]={0x48,0x8D,0xB9,0xC0,0x01,0x00,0x00,0x48};u64 gs=scan_exact(gods,sizeof gods);if(gs&&gs>=0x12&&decode_rip_target(gs-0x12,&g_cheat_flags))g_ready_god=1;
    static const u8 fovs[]={0x48,0x03,0xC0,0x3B,0x4C,0xC2,0x04};u64 fs=scan_exact(fovs,sizeof fovs);if(fs&&fs>=7&&decode_rip_target(fs-7,&g_fov_global))g_ready_fov=1;
    g_ready_points=inject_skill_capture();
    set_status("Attached to Resonance.exe — native trainer active.");
    if(g_ready_god&&g_ready_fov&&g_ready_points)set_feature("Ready: God Mode • Invisible • Resonance Points • FOV • Console");
    else if(g_ready_god&&g_ready_points)set_feature("Partial profile: God/Invisible + Resonance Points ready. FOV signature not found.");
    else if(g_ready_god)set_feature("Partial profile: God/Invisible ready. Points/FOV signatures need an updated profile.");
    else set_feature("Profile signatures did not match this game build. No memory changes were applied.");
    return 1;
}

static u64 resolve_fov_addr(void){if(!g_ready_fov||!g_fov_global)return 0;u64 p=0;float v=0.0f;if(read_u64_remote(g_fov_global+0x18,&p)&&p&&read_float_remote(p+0x1048,&v)&&v>1.0f&&v<200.0f)return p+0x1048;u64 a=0,b=0;if(read_u64_remote(g_fov_global,&a)&&a&&read_u64_remote(a+0x18,&b)&&b&&read_float_remote(b+0x1048,&v)&&v>1.0f&&v<200.0f)return b+0x1048;return 0;}

static u32 parse_u32(const char*s){u64 v=0;while(s&&*s==' ')s++;while(s&&*s>='0'&&*s<='9'){v=v*10+(u32)(*s-'0');if(v>0xffffffffULL)v=0xffffffffULL;s++;}return (u32)v;}
static float parse_float_simple(const char*s){int sign=1;if(!s)return 0.0f;while(*s==' ')s++;if(*s=='-'){sign=-1;s++;}double v=0.0;while(*s>='0'&&*s<='9'){v=v*10.0+(*s-'0');s++;}if(*s=='.'){double p=0.1;s++;while(*s>='0'&&*s<='9'){v+=(*s-'0')*p;p*=0.1;s++;}}return (float)(v*sign);}

static void apply_font(HWND h){if(h&&pGetStockObject&&pSendMessageA){void*f=pGetStockObject(DEFAULT_GUI_FONT);if(f)pSendMessageA(h,WM_SETFONT,(WPARAM)(usize)f,TRUE);}}
static HWND mkctl(LPCSTR cls,LPCSTR text,DWORD style,int x,int y,int w,int h,int id){HWND z=pCreateWindowExA(0,cls,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,g_main,(HMENU)(usize)id,pGetModuleHandleA(0),0);apply_font(z);return z;}

static LRESULT wndproc(HWND hwnd,u32 msg,WPARAM wp,LPARAM lp){(void)lp;
    if(msg==WM_CREATE){g_main=hwnd;mkctl("STATIC","Resonance: A Plague Tale Legacy — Native Trainer",0,18,14,500,24,0);g_status=mkctl("STATIC","Waiting for Resonance.exe...",0,18,44,500,22,ID_STATUS);g_feature=mkctl("STATIC","Native conversion of Paul44 Resonance v1.1 CT. No Cheat Engine required.",0,18,68,550,22,0);mkctl("BUTTON","Attach / Rescan",BS_AUTOCHECKBOX&0,18,100,120,28,ID_ATTACH);g_god=mkctl("BUTTON","God Mode",BS_AUTOCHECKBOX|WS_TABSTOP,18,145,150,26,ID_GOD);g_invis=mkctl("BUTTON","Invisible",BS_AUTOCHECKBOX|WS_TABSTOP,190,145,150,26,ID_INVIS);mkctl("STATIC","Resonance Points:",0,18,192,135,22,0);g_points=mkctl("EDIT","999",WS_BORDER|WS_TABSTOP,155,188,90,26,ID_POINTS_EDIT);mkctl("BUTTON","Set Points",WS_TABSTOP,255,188,105,27,ID_POINTS_SET);mkctl("STATIC","FOV:",0,18,232,135,22,0);g_fov=mkctl("EDIT","70",WS_BORDER|WS_TABSTOP,155,228,90,26,ID_FOV_EDIT);mkctl("BUTTON","Set FOV",WS_TABSTOP,255,228,105,27,ID_FOV_SET);mkctl("BUTTON","Reset 50",WS_TABSTOP,370,228,95,27,ID_FOV_RESET);mkctl("BUTTON","Toggle Console",WS_TABSTOP,18,274,140,29,ID_CONSOLE);mkctl("STATIC","Single-player/offline only. This helper does not bypass anti-cheat systems.",0,18,322,520,22,0);pSetTimer(hwnd,TIMER_ATTACH,1000,0);return 0;}
    if(msg==WM_TIMER&&wp==TIMER_ATTACH){if(!g_proc)attach_game();else{DWORD c=0;if(!pGetExitCodeProcess(g_proc,&c)||c!=STILL_ACTIVE)detach_game();}return 0;}
    if(msg==WM_COMMAND){u32 id=(u32)(wp&0xffffu);if(id==ID_ATTACH){if(g_proc)detach_game();attach_game();return 0;}if(!g_proc){set_status("Start Resonance first, then try again.");return 0;}
        if(id==ID_GOD||id==ID_INVIS){if(!g_ready_god){set_status("God/Invisible signature unavailable on this game build.");return 0;}HWND cb=id==ID_GOD?g_god:g_invis;u8 on=(pSendMessageA(cb,BM_GETCHECK,0,0)==BST_CHECKED)?1:0;if(write_u8_remote(g_cheat_flags+(id==ID_INVIS?1:0),on))set_status(on?(id==ID_GOD?"God Mode enabled.":"Invisible enabled."):(id==ID_GOD?"God Mode disabled.":"Invisible disabled."));else set_status("Memory write failed.");return 0;}
        if(id==ID_POINTS_SET){if(!g_ready_points||!g_pskill){set_status("Resonance Points capture is unavailable.");return 0;}u64 obj=0;if(!read_u64_remote(g_pskill,&obj)||!obj){set_status("Points object not captured yet. Load/move in-game and try again.");return 0;}char t[64];pGetWindowTextA(g_points,t,63);u32 v=parse_u32(t);if(write_u32_remote(obj+0x40,v))set_status("Resonance Points updated.");else set_status("Could not write Resonance Points.");return 0;}
        if(id==ID_FOV_SET||id==ID_FOV_RESET){u64 a=resolve_fov_addr();if(!a){set_status("FOV pointer is not ready. Load into gameplay and try again.");return 0;}float v=50.0f;if(id==ID_FOV_SET){char t[64];pGetWindowTextA(g_fov,t,63);v=parse_float_simple(t);if(v<20.0f)v=20.0f;if(v>150.0f)v=150.0f;}if(write_float_remote(a,v))set_status(id==ID_FOV_RESET?"FOV reset to 50.":"FOV updated.");else set_status("Could not write FOV.");return 0;}
        if(id==ID_CONSOLE){HWND c=pFindWindowA("Console",0);if(!c){set_status("Game Console window was not found on this build/state.");return 0;}g_console_shown=!g_console_shown;pShowWindow(c,g_console_shown?SW_SHOW:SW_HIDE);set_status(g_console_shown?"Console shown.":"Console hidden.");return 0;}
    }
    if(msg==WM_CLOSE){detach_game();pKillTimer(hwnd,TIMER_ATTACH);pPostQuitMessage(0);return 0;}if(msg==WM_DESTROY){detach_game();pPostQuitMessage(0);return 0;}return pDefWindowProcA(hwnd,msg,wp,lp);
}

void entry(void){if(!init_api())return;HINSTANCE hi=pGetModuleHandleA(0);WNDCLASSEXA wc;memzero(&wc,sizeof wc);wc.cbSize=sizeof wc;wc.lpfnWndProc=wndproc;wc.hInstance=hi;wc.hCursor=pLoadCursorA(0,IDC_ARROW);wc.hbrBackground=(HBRUSH)(usize)(COLOR_WINDOW+1);wc.lpszClassName="WandNativeResonanceTrainer";if(!pRegisterClassExA(&wc)){pMessageBoxA(0,"Could not register native trainer window.","Wand Native",MB_OK|MB_ICONERROR);pExitProcess(2);}g_main=pCreateWindowExA(0,wc.lpszClassName,"Wand Native - Resonance Native Trainer",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,590,410,0,0,hi,0);if(!g_main){pMessageBoxA(0,"Could not create native trainer window.","Wand Native",MB_OK|MB_ICONERROR);pExitProcess(3);}pShowWindow(g_main,SW_SHOW);pUpdateWindow(g_main);MSG m;while(pGetMessageA(&m,0,0,0)>0){pTranslateMessage(&m);pDispatchMessageA(&m);}detach_game();pExitProcess(0);}
