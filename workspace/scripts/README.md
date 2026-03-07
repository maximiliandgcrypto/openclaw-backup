# scripts/

Utility scripts for the OpenClaw workspace.

---

## nordvpn-wrap.sh

Run any command through NordVPN without permanently breaking Tailscale.

### The Problem

NordVPN hijacks **routing table 205** when connected, which completely blocks
Tailscale traffic. Split-tunneling and subnet whitelisting don't reliably fix
this. The only clean solution is: connect → run → disconnect.

### Usage

```bash
nordvpn-wrap.sh <command> [args...]
```

**Examples:**

```bash
# Fetch your current IP through a Finnish NordVPN exit node
./nordvpn-wrap.sh curl https://ifconfig.me

# Run a script that needs a Finnish IP
./nordvpn-wrap.sh python3 scraper.py

# Use a different country
NORDVPN_COUNTRY=Germany ./nordvpn-wrap.sh curl https://ifconfig.me

# Custom timeout (e.g. 60 seconds)
NORDVPN_TIMEOUT=60 ./nordvpn-wrap.sh my-fast-command
```

### Environment Variables

| Variable           | Default   | Description                            |
|--------------------|-----------|----------------------------------------|
| `NORDVPN_COUNTRY`  | `Finland` | NordVPN country/server group to use    |
| `NORDVPN_TIMEOUT`  | `300`     | Max seconds to wait for connection     |

### Behaviour

1. **Pre-flight:** Checks that `nordvpn` is installed; exits with an error if not.
2. **Tailscale detection:** If Tailscale is online before the call, the script
   waits after NordVPN disconnects until Tailscale is back (up to 60 s).
3. **Connection timeout:** If NordVPN doesn't connect within `NORDVPN_TIMEOUT`
   seconds, the script aborts and exits with an error — NordVPN is disconnected
   before exiting.
4. **Cleanup on signals:** `SIGINT` (Ctrl-C) and `SIGTERM` both trigger an
   orderly NordVPN disconnect before exiting, so you can safely cancel at any
   time.
5. **Exit code passthrough:** The wrapped command's exit code is returned
   verbatim, so you can use `nordvpn-wrap.sh` in pipelines and `&&`/`||` chains.

### Requirements

- `nordvpn` CLI (NordVPN Linux client)
- Optional: `tailscale` CLI (auto-detected; Tailscale recovery is skipped if
  not present)

### Notes

- All status messages go to **stderr** so stdout stays clean for piping.
- NordVPN must be logged in (`nordvpn login`) before using this script.
- If your command runs for a very long time, consider whether an always-on VPN
  profile would be better — this wrapper is designed for short, ad-hoc tasks.
