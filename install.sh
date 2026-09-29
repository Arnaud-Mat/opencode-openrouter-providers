#!/usr/bin/env bash
# Install a daily refresh of OpenRouter provider variants into your opencode config.
#
#   macOS  -> launchd LaunchAgent (runs at login + daily at 08:00)
#   Linux  -> crontab entry      (daily at 08:00)
#
# Usage: ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="$SCRIPT_DIR/gen-providers.py"
PY="$(command -v python3 || true)"
LABEL="ai.opencode.genproviders"
LOG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
LOG="$LOG_DIR/gen-providers.log"

if [[ -z "$PY" ]]; then
  echo "python3 not found in PATH." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

run_once() {
  echo "Running once to populate the config..."
  "$PY" "$GEN" || true
}

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$GEN</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/gen-providers.err.log</string>
</dict>
</plist>
PLIST_EOF
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "Installed launchd agent: $PLIST"
    ;;

  Linux)
    CRON_LINE="0 8 * * * $PY $GEN >> $LOG 2>&1"
    ( crontab -l 2>/dev/null | grep -vF "$GEN" ; echo "$CRON_LINE" ) | crontab -
    echo "Installed crontab entry:"
    echo "  $CRON_LINE"
    ;;

  *)
    echo "Unsupported OS: $(uname -s). Run the script manually:" >&2
    echo "  $PY $GEN" >&2
    exit 1
    ;;
esac

run_once
echo
echo "Done. Restart OpenCode to see the provider choices."
echo "Refresh manually any time:  $PY $GEN"