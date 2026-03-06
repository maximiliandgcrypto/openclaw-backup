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

## Twitter/X Monitoring — ShardiB2

- **Cron-Job `shardib2-monitor`** (ID: 26813f30-005f-4d25-8a25-a93db3c20b0f)
- Alle 5 Min, Claude Sonnet 4.6, isoliert
- Scrapt BEIDE Tabs: reguläre Posts + Subscriber-Tab (`/superfollows`)
- Posts → Discord `#twitter-posts` (1478757600848773152)
- Login-Fehler → Telegram-Alert an Maximilian
- Cookies: `/workspace/twitter/cookies.json`
- State: `/workspace/twitter/shardib-state.json`
- Scripts: `/workspace/twitter/shardib-monitor.py` (+ fetch-date, fetch-subscriber)
- "Show more"-Fix eingebaut (lange Posts werden aufgeklappt)
- xurl wird NICHT genutzt — X API kostet, Maximilian will das nicht
- Bulk-Import 02.-05.03.2026 erledigt (regulär + subscriber)

## Lessons Learned

- `openclaw update` NIE aus dem Gateway heraus laufen lassen (killt sich selbst, RAM-Überlastung)
- Cron jobs.json direkt bearbeiten reicht — kein Gateway-Restart nötig
- `openclaw message send` nutzt `--target`, nicht `--to`
- Gateway-Restart killt laufende Agent-Sessions (Henne-Ei-Problem beim Testen)
- OpenAI Embeddings Quota aufgebraucht → auf Gemini gewechselt

## NordVPN

- NordVPN CLI installiert auf Server ✅
- Analytics deaktiviert ✅
- Login ausstehend — braucht Access Token von my.nordaccount.com (nicht Username/Password!)
- Account: maximilian.graetz@outlook.con
- Zweck: YouTube und andere Services die Cloud-IPs blocken

## Bekannte ARM-Inkompatibilitäten

- `summarize` CLI (Homebrew) → x86 only, Exec Format Error auf aarch64
- Lesson: Homebrew Binaries auf ARM immer prüfen

## Maximilian als Trader

- Aktiver Trader, Ziel: Geld verdienen
- "Saraton Investments" = geplantes Trading-Business
- Hat Pine Script Algorithmus (reverse-engineered) — **Code noch ausstehend**
- TradingView Premium + TradingAlpha.io
- Fokus: Technische Analyse > News > Fundamentals > Sentiment
- Will Backtesting in Python (Parameter-Sweep)
- Interessiert an Polymarket / Prediction Markets
- **Pine Script erhalten** → `data/pinescript/trend-suite-graetz.pine` (399 Zeilen)
- Algo funktioniert auf 5min, 1h, 4h, Daily — höherer Timeframe = besser
- Day + Swing Trading, alle Assets (Aktien, Options, Crypto, Futures), mit Leverage
- Risk Management dynamisch (A-Setup = mehr Kapital, B-Setup = weniger)
- Dynamischer Stop Loss gewünscht (z.B. bei Trendlinie)
- Größtes Problem: FOMO-Trades die nicht vom Algo kamen
- Ziel: Multi-Millionär
- **Meine Prioritäten**: 1) Algo backtesten 2) Research 3) Signale finden

## Mission Control Dashboard

- Live: http://ubuntu-4gb-hel1-1.tail463d20.ts.net:8080
- Systemd Service `mission-control` (Port 8080, auto-restart)
- Tabs: Dashboard, Signals, Research, Cron Jobs, Memory, Automation, System
- Update-Script: `scripts/update-mission-control.py`

## Nacht-Research

- Cron `nightly-research` (ID: 3daccc8b-d4a6-406f-8bb4-cd3ec1c16404)
- 03:00 Berlin, Opus
- REGEL: Nur fertige umgesetzte Arbeit — KEINE Ideen/Vorschläge
- Ergebnisse: `memory/nightly-research/` + Telegram + Discord

## Offene Punkte

- Pine Script Code von Maximilian → Python Backtesting Engine bauen
- NordVPN Access Token holen → VPN verbinden
- DeepSeek Guthaben aufladen
- Gemini Pro braucht Billing für Nutzung
- Brave API Key fehlt (web_search geht nicht) — web_fetch auf CoinDesk funktioniert als Alternative
- xurl nicht verbunden — Maximilian will X API nicht (kostet pro Anfrage)
- OpenAI Guthaben aufladen (Embeddings + Whisper)
- Mission Control bauen? (AlexFinn Hack #6)
- ShardiB2 Monitor läuft stabil ✅ (Stand 05.03.)
- Peter Steinberger Report mit echten Transcripts erweitern (nach VPN-Setup)
