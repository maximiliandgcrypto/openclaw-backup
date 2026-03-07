#!/usr/bin/env bash
# nordvpn-wrap.sh — Run a command through NordVPN without breaking Tailscale
#
# Usage:  nordvpn-wrap.sh <command> [args...]
# Env:    NORDVPN_COUNTRY  — NordVPN country to connect to (default: Finland)
#         NORDVPN_TIMEOUT  — Connection timeout in seconds (default: 300)
#
# Why:    NordVPN hijacks routing table 205 and breaks Tailscale.
#         This wrapper connects → runs → disconnects on-demand so Tailscale
#         only loses connectivity for the duration of the wrapped command.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
COUNTRY="${NORDVPN_COUNTRY:-Finland}"
TIMEOUT="${NORDVPN_TIMEOUT:-300}"   # seconds

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[nordvpn-wrap] $*" >&2; }
err()  { echo "[nordvpn-wrap] ERROR: $*" >&2; }
die()  { err "$*"; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
[[ $# -eq 0 ]] && {
  echo "Usage: $(basename "$0") <command> [args...]" >&2
  echo "  Env: NORDVPN_COUNTRY (default: Finland)" >&2
  echo "       NORDVPN_TIMEOUT (default: 300 seconds)" >&2
  exit 1
}

command -v nordvpn &>/dev/null || die "nordvpn not found. Install NordVPN first."

# ── Tailscale state ───────────────────────────────────────────────────────────
tailscale_was_up=false
if command -v tailscale &>/dev/null; then
  if tailscale status &>/dev/null 2>&1; then
    tailscale_was_up=true
    log "Tailscale is currently online (will restore after disconnect)"
  fi
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────
_cmd_exit=0
_cleanup_done=false

cleanup() {
  [[ "$_cleanup_done" == "true" ]] && return
  _cleanup_done=true

  log "Disconnecting NordVPN..."
  nordvpn disconnect &>/dev/null || true

  if [[ "$tailscale_was_up" == "true" ]]; then
    log "Waiting for Tailscale to come back online..."
    local ts_timeout=60
    local ts_elapsed=0
    local ts_interval=2
    while ! tailscale status &>/dev/null 2>&1; do
      if [[ $ts_elapsed -ge $ts_timeout ]]; then
        err "Tailscale did not recover within ${ts_timeout}s — check manually"
        break
      fi
      sleep "$ts_interval"
      ts_elapsed=$(( ts_elapsed + ts_interval ))
    done
    if tailscale status &>/dev/null 2>&1; then
      log "Tailscale is back online"
    fi
  fi
}

# Trap SIGINT (Ctrl-C), SIGTERM, and EXIT so we always disconnect
trap 'cleanup' EXIT
trap 'log "Caught SIGINT"; cleanup; exit 130' INT
trap 'log "Caught SIGTERM"; cleanup; exit 143' TERM

# ── Connect to NordVPN ────────────────────────────────────────────────────────
log "Connecting to NordVPN ($COUNTRY)..."

nordvpn connect "$COUNTRY" &>/dev/null &
connect_pid=$!

elapsed=0
interval=3
connected=false

while [[ $elapsed -lt $TIMEOUT ]]; do
  # Check if nordvpn connect process finished
  if ! kill -0 "$connect_pid" 2>/dev/null; then
    # Process ended; verify connection status
    if nordvpn status 2>/dev/null | grep -qi "connected"; then
      connected=true
      break
    else
      die "nordvpn connect exited but status shows not connected"
    fi
  fi
  # Also poll status independently in case connect blocks
  if nordvpn status 2>/dev/null | grep -qi "connected"; then
    connected=true
    kill "$connect_pid" 2>/dev/null || true
    wait "$connect_pid" 2>/dev/null || true
    break
  fi
  sleep "$interval"
  elapsed=$(( elapsed + interval ))
done

if [[ "$connected" != "true" ]]; then
  kill "$connect_pid" 2>/dev/null || true
  wait "$connect_pid" 2>/dev/null || true
  die "NordVPN did not connect within ${TIMEOUT}s (country: $COUNTRY)"
fi

log "NordVPN connected ($(nordvpn status 2>/dev/null | grep -i 'ip\|server' | head -2 | tr '\n' ' ' | sed 's/[[:space:]]*$//'))"

# ── Run the wrapped command ───────────────────────────────────────────────────
log "Running: $*"
"$@" || _cmd_exit=$?

# cleanup() fires via EXIT trap automatically; pass exit code through
exit $_cmd_exit
