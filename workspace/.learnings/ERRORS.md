# Errors

Command failures, exceptions, and unexpected behavior.

**Statuses**: pending | in_progress | resolved | wont_fix

---

## [ERR-20260305-001] openclaw_update_timeout

**Logged**: 2026-03-05T08:28:00Z
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
daily-maintenance Cron-Job lief in Timeout (300s) — `openclaw update` braucht 3-4 Minuten.

### Error
```
Error: cron: job execution timed out (durationMs: 744522)
```

### Context
- Cron-Job Timeout war 300s, Build brauchte 744s
- Server: Hetzner CAX11, 2 ARM-Cores, 3.7 GB RAM, kein Swap

### Resolution
- **Resolved**: 2026-03-05T08:52:00Z
- **Notes**: Maintenance von Cron auf systemd-Timer umgestellt. 4 GB Swap angelegt. Gateway wird vor Update gestoppt.

---
