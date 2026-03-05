#!/bin/bash
# Daily Backup — pushes critical OpenClaw config to GitHub
# Secrets are replaced with placeholders before commit

set -uo pipefail

REPO="maximiliandgcrypto/openclaw-backup"
BACKUP_DIR="/tmp/openclaw-backup"
WORKSPACE="$HOME/.openclaw/workspace"
OPENCLAW_DIR="$HOME/.openclaw"
DATE=$(date +"%Y-%m-%d")
ERRORS=""

log() { echo "[$(date +%H:%M:%S)] $*"; }

# --- Setup ---
rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"
git init -q
git remote add origin "https://github.com/$REPO.git" 2>/dev/null || true

# Pull existing if any
git fetch origin main 2>/dev/null && git checkout -q main 2>/dev/null || git checkout -q -b main

# --- Collect files ---
log "Collecting files..."

# 1. Workspace files (SOUL, MEMORY, AGENTS, USER, IDENTITY, TOOLS, HEARTBEAT, etc.)
mkdir -p workspace
for f in SOUL.md MEMORY.md AGENTS.md USER.md IDENTITY.md TOOLS.md HEARTBEAT.md BOOTSTRAP.md; do
    [ -f "$WORKSPACE/$f" ] && cp "$WORKSPACE/$f" "workspace/$f"
done

# 2. Memory files
if [ -d "$WORKSPACE/memory" ]; then
    mkdir -p workspace/memory
    cp -r "$WORKSPACE/memory/"*.md workspace/memory/ 2>/dev/null || true
fi

# 3. Learnings
if [ -d "$WORKSPACE/.learnings" ]; then
    mkdir -p workspace/.learnings
    cp -r "$WORKSPACE/.learnings/"*.md workspace/.learnings/ 2>/dev/null || true
fi

# 4. Scripts
if [ -d "$WORKSPACE/scripts" ]; then
    mkdir -p workspace/scripts
    cp -r "$WORKSPACE/scripts/"* workspace/scripts/ 2>/dev/null || true
fi

# 5. Gateway config
mkdir -p config
[ -f "$OPENCLAW_DIR/openclaw.json" ] && cp "$OPENCLAW_DIR/openclaw.json" "config/openclaw.json"

# 6. Cron jobs
[ -f "$OPENCLAW_DIR/cron/jobs.json" ] && cp "$OPENCLAW_DIR/cron/jobs.json" "config/cron-jobs.json"

# 7. Systemd units
mkdir -p systemd
for f in /etc/systemd/system/openclaw-*.service /etc/systemd/system/openclaw-*.timer; do
    [ -f "$f" ] && cp "$f" "systemd/" 2>/dev/null || true
done

# 8. Skills list (just names, not full content)
ls "$HOME/openclaw/skills/" 2>/dev/null > config/installed-skills.txt || true

# --- Scrub secrets ---
log "Scrubbing secrets..."

scrub_file() {
    local file="$1"
    [ ! -f "$file" ] && return

    # API keys (generic patterns)
    sed -i -E 's/(sk-[a-zA-Z0-9_-]{20,})/[OPENAI_API_KEY]/g' "$file"
    sed -i -E 's/(sk-proj-[a-zA-Z0-9_-]{20,})/[OPENAI_API_KEY]/g' "$file"
    sed -i -E 's/(github_pat_[a-zA-Z0-9_]{20,})/[GITHUB_PAT]/g' "$file"
    sed -i -E 's/(AIza[a-zA-Z0-9_-]{30,})/[GOOGLE_API_KEY]/g' "$file"
    sed -i -E 's/(gsk_[a-zA-Z0-9]{20,})/[GROQ_API_KEY]/g' "$file"
    
    # Telegram bot token
    sed -i -E 's/[0-9]{8,}:[A-Za-z0-9_-]{30,}/[TELEGRAM_BOT_TOKEN]/g' "$file"
    
    # Discord bot token
    sed -i -E 's/[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}/[DISCORD_BOT_TOKEN]/g' "$file"
    
    # Generic long hex tokens (gateway auth etc)
    sed -i -E 's/"token": "[a-f0-9]{32,}"/"token": "[AUTH_TOKEN]"/g' "$file"
    
    # DeepSeek API key
    sed -i -E 's/sk-[a-f0-9]{20,}/[DEEPSEEK_API_KEY]/g' "$file"
    
    # Generic apiKey fields
    sed -i -E 's/"apiKey": "[^"]{10,}"/"apiKey": "[API_KEY_REDACTED]"/g' "$file"
    
    # botToken fields
    sed -i -E 's/"botToken": "[TELEGRAM_BOT_TOKEN]"]+"/"botToken": "[TELEGRAM_BOT_TOKEN]"/g' "$file"
    
    # Webhook URLs
    sed -i -E 's|https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+|[DISCORD_WEBHOOK_URL]|g' "$file"
}

find "$BACKUP_DIR" -name "*.json" -o -name "*.md" -o -name "*.sh" -o -name "*.txt" | while read f; do
    scrub_file "$f"
done

# --- Double-check: scan for remaining secrets ---
LEAKED=$(grep -rEn '(sk-proj-[a-zA-Z0-9]{20}|sk-[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9]{30}|github_pat_[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]{20}|"botToken": "[TELEGRAM_BOT_TOKEN]"$BACKUP_DIR" --include="*.json" --include="*.md" --include="*.sh" 2>/dev/null | grep -v '\[.*_KEY\]\|\[.*_TOKEN\]\|\[.*REDACTED\]' || true)
if [ -n "$LEAKED" ]; then
    log "WARNING: Possible remaining secrets detected!"
    ERRORS+="Possible leaked secrets found after scrubbing. "
fi

# --- Git commit + push ---
log "Committing..."
git add -A

# Check if anything changed
if git diff --cached --quiet 2>/dev/null; then
    SUMMARY="No changes since last backup"
    log "$SUMMARY"
else
    CHANGED=$(git diff --cached --stat | tail -1)
    SUMMARY="Backup $DATE — $CHANGED"
    git -c user.name="OpenClaw Backup" -c user.email="backup@openclaw.local" commit -q -m "$SUMMARY"
    
    log "Pushing..."
    git push -u origin main -q 2>&1 || { ERRORS+="Git push failed. "; log "Push failed!"; }
fi

# --- Report to Discord ---
if [ -n "$ERRORS" ]; then
    REPORT="❌ **Backup $DATE** — Fehler: $ERRORS"
else
    REPORT="✅ **Backup $DATE** — $SUMMARY"
fi

openclaw message send --channel discord --target 1478855159474950377 -m "$REPORT" 2>/dev/null || log "Discord delivery failed"

# Cleanup
rm -rf "$BACKUP_DIR"
log "Done."
