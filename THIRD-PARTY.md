# Third-party runtime components

## Wine crypt32 (modified compatibility build)

GameWeld public binary releases may include x86_64 and i386 `crypt32.dll`
files built from the Valve/Proton Wine source baseline at commit
`46b29104e3741fe23bf5e2547196a253aab88c89`, with the source change in:

`patches/wine-crypt32-cert-sha256-prop.patch`

Wine is licensed under the GNU Lesser General Public License (LGPL), version
2.1 or later. The exact upstream source can be obtained from the ValveSoftware
Wine repository at the commit above; the complete local modification is shipped
as a patch in this source/release tree so the distributed binary can be
reconstructed.

The modification implements `CERT_SHA256_HASH_PROP_ID` certificate-property
behavior; it does not bypass Tophat signature verification.

## GE-Proton

GameWeld can reuse an installed compatible GE-Proton or download the official
GE-Proton11-7 x86_64 release from GloriousEggroll's proton-ge-custom project.
The GE-Proton archive is not republished inside GameWeld; the installer
verifies the official release's published SHA-512 checksum before use.

## Microsoft DWriteCore

GameWeld can download Microsoft.WindowsAppSDK.DWrite 2.1.0 from the official
NuGet service and extract DWriteCore.dll for Wand/WeMod compatibility.

The Microsoft binary is not bundled in GameWeld. See the package's own
license information on NuGet for its terms.


## Cheat Engine

GameWeld can download the official native Linux Cheat Engine 7.7.1 archive directly from `https://cheatengine.org/download/CheatEngineLinux771.zip` when the user explicitly requests installation. Cheat Engine binaries are not bundled or redistributed inside GameWeld. The optional older Windows/Proton CE path is also retained for user-supplied installers. Cheat Engine's own license/terms apply.


## Heroic Games Launcher

GameWeld does not bundle Heroic. When Heroic is installed by the user, GameWeld can read Heroic's local installed-game metadata and send launch requests through Heroic's registered `heroic://` protocol. Heroic, Legendary, gogdl and Nile remain separate projects under their own licenses.

## Cheat Happens Aurora and Cheat Evolution validation samples

GameWeld can recognize and explicitly launch user-supplied Cheat Happens Aurora and Cheat Evolution manager packages using package-level fingerprints. Their binaries are not bundled, copied into, or redistributed with GameWeld. Test fixtures and release packages contain only GameWeld code; the original manager files remain under their vendors' own terms.

## Optional Wand-Enhancer (external software, not bundled)
GameWeld 0.6.0 Test 5 can launch a locally built `WandEnhancer.exe` through Wine as an experimental convenience. Source: https://github.com/k1tbyte/Wand-Enhancer, license Apache-2.0, maintained by k1tbyte and contributors. No upstream Wand-Enhancer source, binaries, modified Wand files, or embedded patch recipes are included in the GameWeld AppImage. Users choose and build the third-party executable themselves. Current upstream is Windows WPF/.NET Framework 4.8 and execution under Wine may fail.
