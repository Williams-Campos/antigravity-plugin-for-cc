#!/usr/bin/env bash
# Installs (or, with --uninstall, removes) agy-bridge for the current user:
#   ~/.local/bin/agy-task            → bin/agy-task
#   ~/.claude/skills/agy-bridge      → skill/
# It only creates symlinks; it does not modify the Claude Code or agy configuration.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/agy-task"
SKILL="$HOME/.claude/skills/agy-bridge"

remove_link() { # only removes the path if it is one of our symlinks
  if [ -L "$1" ] && [[ "$(readlink "$1")" == "$HERE"/* ]]; then rm "$1"; echo "removed $1"; fi
}

if [ "${1:-}" = "--uninstall" ]; then
  remove_link "$BIN"; remove_link "$SKILL"; exit 0
fi

link() { # destination source
  if [ -e "$1" ] && [ ! -L "$1" ]; then echo "$1 already exists and is not a symlink: leaving it alone" >&2; exit 1; fi
  mkdir -p "$(dirname "$1")"; ln -sfn "$2" "$1"; echo "$1 → $2"
}
chmod +x "$HERE/bin/agy-task"
link "$BIN" "$HERE/bin/agy-task"
link "$SKILL" "$HERE/skill"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "note: add ~/.local/bin to your PATH" ;; esac
"$BIN" doctor
