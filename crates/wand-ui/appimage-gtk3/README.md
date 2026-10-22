# GTK3 AppImage frontend

This small C frontend is the AppImage UI shell used for the 0.1.42 redesign test builds. It is built directly against the stable GTK3 ABI so the frozen 0.1.41 runtime/backend can remain unchanged.

The Home page mirrors the approved Wand Native mockup: sidebar navigation, top search/status bar, game hero, dual launch actions, three readiness cards, Activity Log, and the right-side status/quick-actions column.

## Per-game artwork

Artwork is selected by Steam App ID; Resonance is not hard-coded as the global skin.

Resolution order:

1. `$WAND_NATIVE_ARTWORK_DIR/<appid>/`
2. `$XDG_DATA_HOME/wand-native/artwork/<appid>/`
3. `~/.local/share/wand-native/artwork/<appid>/`
4. bundled `assets/games/<appid>/`
5. Steam `appcache/librarycache`

Preferred custom names are `hero.png` and `cover.png` (JPG/JPEG/WebP also work). Steam-style names such as `library_hero`, `header`, and `library_600x900` are recognized. If only one game-specific image is available, it is used in both positions rather than displaying another game's artwork.
