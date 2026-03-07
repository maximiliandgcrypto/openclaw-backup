# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice
**Areas**: frontend | backend | infra | tests | docs | config
**Statuses**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill

---

## [LRN-20260305-001] best_practice

**Logged**: 2026-03-05T08:50:00Z
**Priority**: critical
**Status**: resolved
**Area**: infra

### Summary
`openclaw update` darf nicht aus dem Gateway-Prozess heraus laufen — killt sich selbst.

### Details
Cron-Jobs laufen als Child-Prozess des Gateways. `openclaw update` führt `pnpm build` aus (~2.4 GB RAM). Auf einem 4 GB Server überlastet das den RAM. Wenn der Gateway restartet (Teil des Updates), werden Cron-Jobs gekillt → Endlosschleife.

### Suggested Action
Update immer als systemd-Timer außerhalb des Gateways ausführen: Gateway stop → Update → Gateway start.

### Metadata
- Source: error + user_feedback
- Tags: openclaw, cron, gateway, memory, systemd

---

## [LRN-20260305-002] correction

**Logged**: 2026-03-05T08:44:00Z
**Priority**: medium
**Status**: promoted
**Area**: config

### Summary
`openclaw cron jobs.json` direkt bearbeiten reicht — kein Gateway-Restart nötig.

### Details
Der Gateway liest die jobs.json bei jedem Cron-Run neu. Änderungen werden automatisch übernommen. Gateway-Restart ist überflüssig und riskant.

### Metadata
- Source: user_feedback
- Tags: openclaw, cron, config
- Promoted: TOOLS.md

---

## [LRN-20260305-003] correction

**Logged**: 2026-03-05T09:02:00Z
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
`openclaw message send` nutzt `--target`, nicht `--to`.

### Details
CLI-Flag für Empfänger ist `--target <dest>`, nicht `--to`. Fehler verursachte Discord-Delivery-Fehler im Maintenance-Script.

### Metadata
- Source: error
- Tags: openclaw, cli, discord

---

### 2026-03-06: Sub-Agent Status vergessen zu updaten
- **Category**: correction
- **Area**: backend
- **What happened**: Task-Creator UI Sub-Agent war fertig, aber ich hab vergessen den Agent-Status UND Todo-Status in live-status.json auf "done" zu setzen
- **Root cause**: Kein automatischer Prozess dafür, nur manuelle Updates
- **Fix**: In SOUL.md als PFLICHT-Regel eingetragen — nach JEDEM Sub-Agent sofort beides updaten
- **Status**: resolved
