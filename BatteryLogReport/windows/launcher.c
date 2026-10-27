/* Minimal Windows 7 ABI: no CRT, .NET, or modern Windows API dependencies. */
typedef __WCHAR_TYPE__ WCHAR;
typedef const WCHAR *LPCWSTR;
typedef unsigned long DWORD;
typedef int BOOL;
typedef void *HANDLE;
/* LLD's MinGW target roots this symbol even when no TLS or CRT is used. */
DWORD _tls_index;
#define NULL ((void*)0)
#define FALSE 0
#define TRUE 1
#define INFINITE 0xffffffffUL
#define INVALID_FILE_ATTRIBUTES 0xffffffffUL
#define MB_OK 0
#define MB_ICONERROR 0x10
#define API __declspec(dllimport)
typedef struct {
    DWORD cb; WCHAR *lpReserved,*lpDesktop,*lpTitle;
    DWORD dwX,dwY,dwXSize,dwYSize,dwXCountChars,dwYCountChars,dwFillAttribute,dwFlags;
    unsigned short wShowWindow,cbReserved2;unsigned char *lpReserved2;
    HANDLE hStdInput,hStdOutput,hStdError;
} STARTUPINFOW;
typedef struct { HANDLE hProcess,hThread;DWORD dwProcessId,dwThreadId; } PROCESS_INFORMATION;
API DWORD GetModuleFileNameW(HANDLE,WCHAR*,DWORD);
API DWORD GetFileAttributesW(LPCWSTR);
API LPCWSTR GetCommandLineW(void);
API BOOL CreateProcessW(LPCWSTR,WCHAR*,void*,void*,BOOL,DWORD,void*,LPCWSTR,STARTUPINFOW*,PROCESS_INFORMATION*);
API BOOL CloseHandle(HANDLE);
API DWORD WaitForSingleObject(HANDLE,DWORD);
API BOOL GetExitCodeProcess(HANDLE,DWORD*);
API int MessageBoxW(HANDLE,LPCWSTR,LPCWSTR,unsigned int);
API __declspec(noreturn) void ExitProcess(unsigned int);
void *memset(void *dest,int value,__SIZE_TYPE__ n){volatile unsigned char *p=(volatile unsigned char*)dest;while(n--)*p++=(unsigned char)value;return dest;}

static WCHAR directory[32768], javaPath[32768], command[32768];
static BOOL append(WCHAR *dest, DWORD capacity, LPCWSTR value) {
    DWORD n=0,m=0;while(dest[n])n++;while(value[m])m++;
    if(n+m>=capacity)return FALSE;for(DWORD i=0;i<=m;i++)dest[n+i]=value[i];return TRUE;
}
void entry(void) {
    DWORD n=GetModuleFileNameW(NULL,directory,32768);
    if(!n||n>=32768)ExitProcess(1);
    while(n&&directory[n-1]!=L'\\')n--;
    if(!n)ExitProcess(1);directory[n-1]=0;
    if(!append(javaPath,32768,directory)||!append(javaPath,32768,L"\\runtime\\bin\\javaw.exe"))ExitProcess(1);
    if(GetFileAttributesW(javaPath)==INVALID_FILE_ATTRIBUTES){MessageBoxW(NULL,L"runtime 폴더를 찾을 수 없습니다. ZIP 전체를 압축 해제한 뒤 실행해 주세요.",L"축전지 로그 보고서",MB_OK|MB_ICONERROR);ExitProcess(1);}
    if(!append(command,32768,L"\"")||!append(command,32768,javaPath)||!append(command,32768,L"\" -Xmx1024m -Dfile.encoding=UTF-8 -jar \"")||!append(command,32768,directory)||!append(command,32768,L"\\BatteryLogReport.jar\""))ExitProcess(1);
    LPCWSTR args=GetCommandLineW();
    if(*args==L'"'){args++;while(*args&&*args!=L'"')args++;if(*args)args++;}else while(*args&&*args!=L' '&&*args!=L'\t')args++;
    if(!append(command,32768,args))ExitProcess(1);
    STARTUPINFOW si={0};PROCESS_INFORMATION pi={0};si.cb=sizeof(si);
    if(!CreateProcessW(javaPath,command,NULL,NULL,FALSE,0,NULL,directory,&si,&pi)){
        MessageBoxW(NULL,L"실행 환경을 시작하지 못했습니다. Windows 7 SP1 이상 64비트 환경인지 확인해 주세요.",L"축전지 로그 보고서",MB_OK|MB_ICONERROR);ExitProcess(1);
    }
    CloseHandle(pi.hThread);WaitForSingleObject(pi.hProcess,INFINITE);DWORD code=1;GetExitCodeProcess(pi.hProcess,&code);CloseHandle(pi.hProcess);ExitProcess(code);
}
