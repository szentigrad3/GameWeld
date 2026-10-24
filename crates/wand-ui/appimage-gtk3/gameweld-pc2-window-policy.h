/* GameWeld PC2 monitor-aware startup policy, independent of GTK runtime.
 * Inputs: logical monitor workarea and physical monitor geometry in pixels.
 * UHD/4K fills available desktop via GTK maximize; smaller screens open as
 * proportionally sized windows. Never choose physical pixel counts as GTK
 * logical window dimensions on scaled monitors.
 */
#ifndef GAMEWELD_PC2_WINDOW_POLICY_H
#define GAMEWELD_PC2_WINDOW_POLICY_H

typedef struct {
    int width;
    int height;
    int maximize;
} GameWeldPC2WindowPolicy;

static GameWeldPC2WindowPolicy gameweld_pc2_window_policy(
    int logical_w, int logical_h, int physical_w, int physical_h)
{
    if (logical_w <= 0) logical_w = 1280;
    if (logical_h <= 0) logical_h = 720;
    /* If backend physical dimensions are unavailable, use logical values
     * rather than guessing a HiDPI scale or forcing a 4K fullscreen. */
    if (physical_w <= 0) physical_w = logical_w;
    if (physical_h <= 0) physical_h = logical_h;

    int width_pct = 90, height_pct = 88;
    if (physical_w <= 1600 || physical_h <= 900) {
        width_pct = 95; height_pct = 93;
    } else if (physical_w >= 2560 && physical_h >= 1440) {
        width_pct = 92; height_pct = 90;
    }

    int maxw = logical_w > 40 ? logical_w - 24 : logical_w;
    int maxh = logical_h > 60 ? logical_h - 32 : logical_h;
    int w = (logical_w * width_pct) / 100;
    int h = (logical_h * height_pct) / 100;
    if (w < 900 && maxw >= 900) w = 900;
    if (h < 600 && maxh >= 600) h = 600;
    if (w > maxw) w = maxw;
    if (h > maxh) h = maxh;
    if (w < 1) w = 1;
    if (h < 1) h = 1;

    GameWeldPC2WindowPolicy result = {
        w, h, physical_w >= 3840 && physical_h >= 2160
    };
    return result;
}

#endif /* GAMEWELD_PC2_WINDOW_POLICY_H */
