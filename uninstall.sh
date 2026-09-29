#!/usr/bin/env bash
# Remove the scheduled refresh installed by install.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="$SCRIPT_DIR/gen-providers.py"
LABEL="ai.opencode.genproviders"

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed launchd agent."
    ;;
  Linux)
    if crontab -l 2>/dev/null | grep -qF "$GEN"; then
      ( crontab -l 2>/dev/null | grep -vF "$GEN" ) | crontab -
      echo "Removed crontab entry."
    else
      echo "No crontab entry found."
    fi
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    ;;
esac