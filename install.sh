#!/usr/bin/env bash
# Instala (o desinstala con --uninstall) agy-bridge para el usuario actual:
#   ~/.local/bin/agy-task            → bin/agy-task
#   ~/.claude/skills/agy-bridge      → claude/skills/agy-bridge
# Solo crea enlaces simbólicos; no modifica la configuración de Claude Code ni la de agy.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/agy-task"
SKILL="$HOME/.claude/skills/agy-bridge"

remove_link() { # solo borra si es un enlace nuestro
  if [ -L "$1" ] && [[ "$(readlink "$1")" == "$HERE"/* ]]; then rm "$1"; echo "eliminado $1"; fi
}

if [ "${1:-}" = "--uninstall" ]; then
  remove_link "$BIN"; remove_link "$SKILL"; exit 0
fi

link() { # destino origen
  if [ -e "$1" ] && [ ! -L "$1" ]; then echo "ya existe $1 y no es un enlace: no se toca" >&2; exit 1; fi
  mkdir -p "$(dirname "$1")"; ln -sfn "$2" "$1"; echo "$1 → $2"
}
chmod +x "$HERE/bin/agy-task"
link "$BIN" "$HERE/bin/agy-task"
link "$SKILL" "$HERE/claude/skills/agy-bridge"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "aviso: añade ~/.local/bin a tu PATH" ;; esac
"$BIN" doctor
