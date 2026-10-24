/* GameWeld PC2 adaptive WINDOWED startup policy, independent of GTK.
 * Inputs are the GTK logical monitor workarea and physical monitor geometry.
 * Every display starts in a normal, resizable window, never fullscreen or
 * automatically maximized. A 4K display gets a larger but bounded window,
 * while compact screens fit their usable workarea. Physical dimensions are
 * used to classify display density, not passed as GTK logical dimensions.
 */
#ifndef GAMEWELD_PC2_WINDOW_POLICY_H
#define GAMEWELD_PC2_WINDOW_POLICY_H

typedef struct {
    int width;
    int height;
    int maximize; /* Always false for startup; users can maximize manually. */
} GameWeldPC2WindowPolicy;

static GameWeldPC2WindowPolicy gameweld_pc2_window_policy(
    int logical_w, int logical_h, int physical_w, int physical_h)
{
    if(logical_w <= 0) logical_w = 1280;
    if(logical_h <= 0) logical_h = 720;
    if(physical_w <= 0) physical_w = logical_w;
    if(physical_h <= 0) physical_h = logical_h;

    int width_pct = 85, height_pct = 85;
    int soft_max_w = 1720, soft_max_h = 1020;
    if(physical_w <= 1600 || physical_h <= 900){
        width_pct = 90; height_pct = 88;
        soft_max_w = 1350; soft_max_h = 820;
    }else if(physical_w >= 3840 && physical_h >= 2160){
        width_pct = 78; height_pct = 83;
        soft_max_w = 2200; soft_max_h = 1280;
    }else if(physical_w >= 2560 && physical_h >= 1440){
        width_pct = 80; height_pct = 83;
        soft_max_w = 1850; soft_max_h = 1100;
    }

    int maxw = logical_w > 40 ? logical_w - 24 : logical_w;
    int maxh = logical_h > 60 ? logical_h - 32 : logical_h;
    int w = (logical_w * width_pct) / 100;
    int h = (logical_h * height_pct) / 100;
    if(w > soft_max_w) w = soft_max_w;
    if(h > soft_max_h) h = soft_max_h;
    if(w < 900 && maxw >= 900) w = 900;
    if(h < 600 && maxh >= 600) h = 600;
    if(w > maxw) w = maxw;
    if(h > maxh) h = maxh;
    if(w < 1) w = 1;
    if(h < 1) h = 1;

    GameWeldPC2WindowPolicy result = {w, h, 0};
    return result;
}
#endif
