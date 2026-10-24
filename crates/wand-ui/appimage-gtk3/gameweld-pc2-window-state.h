/* PC2 width/height preference round-trip. No GTK, game or trainer access.
 * Linux-only host APIs already used by GameWeld's GTK3 frontend.
 * File contents are "WIDTH HEIGHT\n"; maximized state is never recorded.
 */
#ifndef GAMEWELD_PC2_WINDOW_STATE_H
#define GAMEWELD_PC2_WINDOW_STATE_H
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static int gameweld_pc2_state_read(
    const char *path,int *out_w,int *out_h,int max_w,int max_h)
{
    if(!path||!out_w||!out_h||max_w<1||max_h<1)return 0;
    int fd=open(path,O_RDONLY|O_NOFOLLOW);
    if(fd<0)return 0;
    FILE *f=fdopen(fd,"r");
    if(!f){close(fd);return 0;}
    int w=0,h=0;
    int parsed=fscanf(f,"%d %d",&w,&h)==2;
    fclose(f);
    if(!parsed||w<640||h<480||w>8192||h>8192)return 0;
    if(w>max_w)w=max_w;
    if(h>max_h)h=max_h;
    if(w<1||h<1)return 0;
    *out_w=w;*out_h=h;
    return 1;
}

static int gameweld_pc2_state_write(const char *path,int w,int h)
{
    if(!path||w<640||h<480||w>8192||h>8192)return 0;
    char temp[4096]={0};
    int n=snprintf(temp,sizeof temp,"%s.tmp-%ld",path,(long)getpid());
    if(n<=0||n>=(int)sizeof temp)return 0;
    int fd=open(temp,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);
    if(fd<0)return 0;
    char value[64];
    int len=snprintf(value,sizeof value,"%d %d\n",w,h);
    ssize_t actual=write(fd,value,(size_t)len);
    int close_result=close(fd);
    if(actual!=len||close_result!=0){unlink(temp);return 0;}
    if(rename(temp,path)!=0){unlink(temp);return 0;}
    return 1;
}
#endif
