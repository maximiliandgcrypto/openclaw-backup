# MEMORY.md - Long-Term Memory

_Kuratierte Erinnerungen — das Wichtigste, das ich über Maximilian und unsere Arbeit weiß._

## Wer ist Maximilian?

- Telegram: @maximiliandg
- Schreibt Deutsch (manchmal Englisch gemischt)
- Direkt, kein Blabla
- Versteht Tech gut — weiß wie der Agent funktioniert
- Hat OpenClaw im März 2026 frisch aufgesetzt
- Name: Maximilian (nicht Max)
- Timezone: Europe/Berlin
- Interessiert sich für AlexFinn OpenClaw Guide (11 Hacks)
- Findet Reverse Prompting gut

## Setup-Status (Stand 2026-03-05)

- Twitter/X cookies.json vorhanden → xurl noch nicht verbunden (braucht OAuth)
- Twitter Browser-Login funktioniert (Cookies in Chromium importiert)
- gh eingeloggt ✅ (Account: maximiliandgcrypto)
- Gemini API Key gesetzt ✅
- Brave Search Key fehlt
- gog (Google Workspace) nicht konfiguriert
- eightctl nicht konfiguriert
- OpenAI Key gesetzt ✅ (aber Quota aufgebraucht!)
- Browser (Chromium headless) läuft ✅

## Aktive Provider (Stand 2026-03-05)

- Anthropic Claude Opus 4.6 → **neues Default-Modell** (umgestellt am 05.03.) ✅
- Google Gemini (Flash Lite für Heartbeats, Flash für Crons) ✅
- DeepSeek (V3 + R1 konfiguriert, aber kein Guthaben!) ⚠️

## Server

- Hetzner CAX11: 2 ARM-Cores (Neoverse-N1), 3.7 GB RAM, 38 GB Disk
- 4 GB Swap aktiv (/swapfile, persistent in fstab) ✅
- sudo NOPASSWD für openclaw User eingerichtet ✅
- OS: Ubuntu, Linux 6.8.0-101-generic (arm64)

## Security

- Server komplett gehärtet (SSH, Fail2ban, UFW, OpenClaw Guide)
- Audit: 0 critical · 1 warn (kosmetisch) · 2 info
- Discord dmPolicy: allowlist (nur Maximilian)
- Credentials chmod 700, mDNS minimal, fs.workspaceOnly

## Memory System

- memory-core Plugin aktiv ✅
- Gemini Embeddings (Vector Search) ✅
- Hybrid-Modus (BM25 + Vektoren)
- Memory Flush vor Compaction aktiviert

## Self-Improvement

- self-improving-agent Skill installiert ✅
- .learnings/ Ordner mit LEARNINGS.md, ERRORS.md, FEATURE_REQUESTS.md
- Logge Fehler, Korrekturen, Feature Requests automatisch

## Cron Jobs

- daily-reverse-prompt: 7:00 Berlin → Discord #new-ideas
  - Gemini Flash als Trigger → spawnt Opus Sub-Agent für Research
  - ID: c620881a-e077-49dd-9767-5ff42c68e61a

## Systemd Timer

- openclaw-maintenance: 4:00 Berlin → Gateway stop → openclaw update → Gateway start → Report nach Discord #monitoring
- Getestet und funktioniert ✅ (05.03.2026)
- Script: ~/.openclaw/workspace/scripts/daily-maintenance.sh

## Discord

- Bot "OpenClawMDG" auf Maximilians Server
- Channels: #new-ideas (1478779021280940092), #monitoring (1478855159474950377), #shardib2 (1478757600848773152)
- Maximilian Discord ID: 690605911856644236

## Twitter/X Monitoring

- ShardiB2 Monitor Cron (alle 5 Min) — hat Rate-Limit-Fehler, evtl. instabil
- Browser-Cookies Ansatz funktioniert grundsätzlich

## Lessons Learned

- `openclaw update` NIE aus dem Gateway heraus laufen lassen (killt sich selbst, RAM-Überlastung)
- Cron jobs.json direkt bearbeiten reicht — kein Gateway-Restart nötig
- `openclaw message send` nutzt `--target`, nicht `--to`
- Gateway-Restart killt laufende Agent-Sessions (Henne-Ei-Problem beim Testen)
- OpenAI Embeddings Quota aufgebraucht → auf Gemini gewechselt

## Offene Punkte

- DeepSeek Guthaben aufladen
- Gemini Pro braucht Billing für Nutzung
- Brave API Key fehlt (web_search geht nicht)
- xurl nicht via OAuth verbunden (nur Browser-Cookies)
- OpenAI Guthaben aufladen (Embeddings + Whisper)
- Mission Control bauen? (AlexFinn Hack #6)
- ShardiB2 Monitor stabilisieren
