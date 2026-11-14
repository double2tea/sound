#!/usr/bin/env bash
set -euo pipefail

REPO="${SOUND_SKILL_REPO:-https://github.com/double2tea/sound.git}"

case "${1:-}" in
  --claude) DEST="$HOME/.claude/skills/sound" ;;
  --codex)  DEST="$HOME/.codex/skills/sound" ;;
  --qoder)  DEST="$HOME/.qoder/skills/sound" ;;
  "")       DEST="$HOME/.agents/skills/sound" ;;
  *)        DEST="$1" ;;
esac

if [ -e "$DEST" ]; then
  echo "already exists: $DEST" >&2
  echo "remove it first or pass another path" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
git clone --depth 1 "$REPO" "$DEST"

echo "installed: $DEST"
echo
echo "usage:"
echo "  cd \"$DEST\" && python3 scripts/sfx.py freesound \"whoosh\" --license cc0"
echo "  cd \"$DEST\" && python3 scripts/sfxlib.py search \"whoosh\" --source all"
echo "  cd \"$DEST\" && python3 scripts/fs_api.py status"
