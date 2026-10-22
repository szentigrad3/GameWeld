# Per-game artwork

Wand Native resolves artwork by Steam App ID.

Bundled/curated layout:

```
assets/games/<appid>/hero.png
assets/games/<appid>/cover.png
```

User overrides use the same filenames under:

```
$WAND_NATIVE_ARTWORK_DIR/<appid>/
$XDG_DATA_HOME/wand-native/artwork/<appid>/
~/.local/share/wand-native/artwork/<appid>/
```

If no override or bundled set exists, Wand Native reads Steam's own local
`appcache/librarycache` assets. Both Steam's legacy flat filenames and its
newer `<appid>/<hash>/...` cache layout are supported. Blurred backgrounds,
logos, and icons are deliberately rejected as full hero/cover artwork.
