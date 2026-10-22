Wand Auxiliary Diagnostics

Basic:
  ./scripts/enable-aux-diagnostics.sh basic

Deep (adds Wine +server; much noisier):
  ./scripts/enable-aux-diagnostics.sh deep

After reproducing the Wand "trouble running mods" popup once:
  ./scripts/collect-aux-diagnostics.sh 2713000

Return to normal mode:
  ./scripts/disable-aux-diagnostics.sh

The collector writes a single text report to ~/Desktop when that directory
exists. It does not dump passwords, tokens, browser storage, or the whole
process environment.
