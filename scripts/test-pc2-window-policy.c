/* Pure C regression cases for PC2 GTK-independent monitor sizing.
 * Compile/run offline: no GTK, display server, Steam, Proton or game required.
 */
#include <assert.h>
#include <stdio.h>
#include "../crates/wand-ui/appimage-gtk3/gameweld-pc2-window-policy.h"

static void case_window(
    const char *label, int lw, int lh, int pw, int ph, int maximize)
{
    GameWeldPC2WindowPolicy p=gameweld_pc2_window_policy(lw,lh,pw,ph);
    assert(p.maximize==maximize);
    assert(p.width>0 && p.height>0);
    assert(p.width<=lw && p.height<=lh);
    assert(p.width>=lw/2 && p.height>=lh/2);
    printf("PASS %-28s logical=%dx%d physical=%dx%d restored=%dx%d maximized=%s\n",
        label,lw,lh,pw,ph,p.width,p.height,p.maximize?"yes":"no");
}

int main(void)
{
    case_window("720p compact",1280,700,1280,720,0);
    case_window("1080p",1920,1040,1920,1080,0);
    case_window("1440p",2560,1380,2560,1440,0);
    case_window("3440 ultrawide",3440,1380,3440,1440,0);
    case_window("4K 1x",3840,2100,3840,2160,1);
    case_window("4K 2x HiDPI",1920,1040,3840,2160,1);
    case_window("5K 2x HiDPI",2560,1400,5120,2880,1);
    case_window("1440p high scaling",1280,690,2560,1440,0);
    GameWeldPC2WindowPolicy a=gameweld_pc2_window_policy(1920,1040,1920,1080);
    assert(a.width==1728 && a.height==915);
    GameWeldPC2WindowPolicy b=gameweld_pc2_window_policy(2560,1380,2560,1440);
    assert(b.width==2355 && b.height==1242);
    GameWeldPC2WindowPolicy c=gameweld_pc2_window_policy(1920,1040,3840,2160);
    assert(c.width==1766 && c.height==936);
    printf("Result: PASS (8 resolutions, 3 exact restored-size checks)\n");
    return 0;
}
