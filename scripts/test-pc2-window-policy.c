/* Pure C regression cases for PC2 WINDOWED monitor sizing.
 * No GUI, Steam, Proton, game or updater is launched by these tests.
 */
#include <assert.h>
#include <stdio.h>
#include "../crates/wand-ui/appimage-gtk3/gameweld-pc2-window-policy.h"

static void case_window(const char *name,int lw,int lh,int pw,int ph,int expected_w,int expected_h){
    GameWeldPC2WindowPolicy p=gameweld_pc2_window_policy(lw,lh,pw,ph);
    assert(p.maximize==0); /* Never auto-maximize even on 4K/5K. */
    assert(p.width==expected_w);
    assert(p.height==expected_h);
    assert(p.width>0 && p.height>0);
    assert(p.width<lw && p.height<lh);
    printf("PASS %-23s monitor=%dx%d restored=%dx%d windowed=yes\n",
        name,pw,ph,p.width,p.height);
}
int main(void){
    case_window("720p compact",1280,700,1280,720,1152,616);
    case_window("1080p",1920,1040,1920,1080,1632,884);
    case_window("1440p",2560,1380,2560,1440,1850,1100);
    case_window("3440 ultrawide",3440,1380,3440,1440,1850,1100);
    case_window("4K unscaled",3840,2100,3840,2160,2200,1280);
    case_window("4K HiDPI 2x",1920,1040,3840,2160,1497,863);
    case_window("5K HiDPI 2x",2560,1400,5120,2880,1996,1162);
    case_window("1440p scaled",1280,690,2560,1440,1024,600);
    printf("Result: PASS (8 resolutions, all windowed with exact dimensions)\n");
    return 0;
}
