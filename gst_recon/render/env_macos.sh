# source this on macOS (nix) so WeasyPrint finds pango: `source gst_recon/render/env_macos.sh`
L=""
for p in $(nix build nixpkgs#pango.out nixpkgs#glib.out nixpkgs#harfbuzz.out nixpkgs#fontconfig.lib nixpkgs#fribidi nixpkgs#cairo --no-link --print-out-paths 2>/dev/null | grep -v -E "man|doc|dev$"); do
  [ -d "$p/lib" ] && L="$L:$p/lib"
done
export DYLD_FALLBACK_LIBRARY_PATH="${L#:}"
