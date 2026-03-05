#!/bin/bash
# Daily Maintenance for OpenClaw
# Runs OUTSIDE the gateway (via systemd timer)
# Flow: stop gateway → update → start gateway → report to Discord

set -uo pipefail

DATE=$(date +"%Y-%m-%d %H:%M %Z")
LOG="/tmp/openclaw-maintenance-$(date +%Y-%m-%d).log"
VERSION_BEFORE=$(openclaw --version 2>&1 || echo "unknown")
UPDATE_EXIT=0
ERRORS=""

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "=== Daily Maintenance Start — $DATE ==="
log "Version before: $VERSION_BEFORE"

# 1. Stop Gateway
log "Stopping gateway..."
openclaw gateway stop >> "$LOG" 2>&1 || true
sleep 3
if pgrep -f openclaw-gateway > /dev/null 2>&1; then
    log "Force killing gateway..."
    pkill -9 -f openclaw-gateway || true
    sleep 2
fi
log "Gateway stopped."

# 2. Update
log "Running update..."
UPDATE_OUTPUT=$(openclaw update --yes --no-restart 2>&1)
UPDATE_EXIT=$?
echo "$UPDATE_OUTPUT" >> "$LOG"
[ $UPDATE_EXIT -eq 0 ] && log "Update: OK" || { log "Update: FAILED (exit $UPDATE_EXIT)"; ERRORS+="Update failed (exit $UPDATE_EXIT). "; }

VERSION_AFTER=$(openclaw --version 2>&1 || echo "unknown")
log "Version after: $VERSION_AFTER"

# 3. Start Gateway
log "Starting gateway..."
openclaw gateway start >> "$LOG" 2>&1
sleep 8
if pgrep -f openclaw-gateway > /dev/null 2>&1; then
    log "Gateway started."
else
    log "Gateway FAILED to start!"
    ERRORS+="Gateway start failed. "
fi

# 4. Security
AUDIT=$(openclaw security audit 2>&1 | grep -E "(Summary|Critical|High|clean|OK|✓)" | head -2 || echo "n/a")
log "Security: $AUDIT"

# 5. Build report
REPORT="🔧 **Daily Maintenance — $DATE**"$'\n\n'
[ $UPDATE_EXIT -eq 0 ] && REPORT+="✅ **Update:** Erfolgreich"$'\n' || REPORT+="❌ **Update:** Fehlgeschlagen (exit $UPDATE_EXIT)"$'\n'
[ "$VERSION_BEFORE" != "$VERSION_AFTER" ] && REPORT+="📦 **Version:** $VERSION_BEFORE → **$VERSION_AFTER**"$'\n' || REPORT+="📦 **Version:** $VERSION_AFTER (keine Änderung)"$'\n'
REPORT+="⚙️ **Gateway:** PID $(pgrep -f openclaw-gateway || echo 'NOT RUNNING')"$'\n'
REPORT+="🔒 **Security:** $AUDIT"$'\n'
[ -n "$ERRORS" ] && REPORT+=$'\n'"⚠️ **Fehler:** $ERRORS" || REPORT+=$'\n'"✅ Alles sauber."

# 6. Send to Discord
sleep 5
openclaw message send --channel discord --target 1478855159474950377 -m "$REPORT" 2>> "$LOG" || log "Discord delivery failed"

log "=== Maintenance complete ==="
