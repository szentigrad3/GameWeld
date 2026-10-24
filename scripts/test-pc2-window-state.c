/* Native I/O roundtrip test for GameWeld PC2's actual window size state
 * helpers. No GTK process, game, Steam, updater or Wine prefix involved.
 * Run: gcc -std=gnu11 -Wall -Wextra -Werror scripts/test-pc2-window-state.c
 *      -o /tmp/test-pc2-window-state && /tmp/test-pc2-window-state
 */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../crates/wand-ui/appimage-gtk3/gameweld-pc2-window-state.h"

int main(void){
    char dirname[]="/tmp/gameweld-window-state-test-XXXXXX";
    char *dir=mkdtemp(dirname);
    assert(dir);
    char file[1024],symlink_path[1024];
    assert(snprintf(file,sizeof file,"%s/pc2-window-size.txt",dir)>0);
    assert(snprintf(symlink_path,sizeof symlink_path,"%s/other.txt",dir)>0);
    int w=0,h=0;

    assert(!gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(gameweld_pc2_state_write(file,1240,860));
    assert(gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(w==1240&&h==860);
    puts("PASS first-run save and next-process read");

    /* A manual resize is saved again and wins over the earlier dimensions. */
    assert(gameweld_pc2_state_write(file,1750,1020));
    w=h=0;
    assert(gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(w==1750&&h==1020);
    puts("PASS manually resized dimensions replace previous session");

    w=h=0;
    assert(gameweld_pc2_state_read(file,&w,&h,1100,740));
    assert(w==1100&&h==740);
    puts("PASS saved size clamps to a smaller monitor workarea");

    assert(!gameweld_pc2_state_write(file,0,700));
    assert(!gameweld_pc2_state_write(file,9000,700));
    assert(gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(w==1750&&h==1020);
    puts("PASS invalid dimensions cannot overwrite user preference");

    FILE *f=fopen(file,"w");assert(f);
    assert(fputs("bad window size\n",f)>=0);assert(fclose(f)==0);
    w=h=0;
    assert(!gameweld_pc2_state_read(file,&w,&h,3000,2000));
    puts("PASS malformed preference rejected; default can be used");

    /* Reset removes only its state file, then normal default can be recorded. */
    assert(unlink(file)==0);
    assert(!gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(gameweld_pc2_state_write(file,1550,900));
    assert(gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(w==1550&&h==900);
    puts("PASS reset/close/reopen roundtrip");

    /* The read path must not follow untrusted symbolic links. */
    assert(unlink(file)==0);
    assert(gameweld_pc2_state_write(symlink_path,1530,880));
    assert(symlink(symlink_path,file)==0);
    assert(!gameweld_pc2_state_read(file,&w,&h,3000,2000));
    assert(unlink(file)==0);
    assert(unlink(symlink_path)==0);
    assert(rmdir(dir)==0);
    puts("PASS symlink refusal and test directory cleanup");

    puts("Result: PASS (native window preference persistence roundtrip)");
    return 0;
}
