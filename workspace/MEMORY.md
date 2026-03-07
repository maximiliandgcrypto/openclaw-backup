# MEMORY.md - Long-Term Memory

_Kuratierte Erinnerungen — das Wichtigste, das ich über Maximilian und unsere Arbeit weiß._

## Wer ist Maximilian?

- Telegram: @maximiliandg
- Schreibt Deutsch (manchmal Englisch gemischt)
- Direkt, kein Blabla
- **Immer sofort starten** — nie fragen ob er anfangen soll, einfach machen
- **Nach JEDER erledigten Aufgabe Report an Telegram** — was wurde gemacht, Ergebnis, was kommt als nächstes
- **Backtester-Code IMMER reviewen lassen** — zweiter Agent prüft vor Ausführung. Kein Backtest ohne Review. V5 war komplett kaputt (0 Trades) weil kein Review.
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

## Aktive Provider (Stand 2026-03-06)

- Anthropic Claude Opus 4.6 → Default für ALLES (Main + alle Cron Jobs) ✅
- Google Gemini → Free Tier Limit erreicht (20 Req/Tag), NICHT MEHR NUTZEN für Crons ⚠️
- DeepSeek (V3 + R1 konfiguriert, aber kein Guthaben!) ⚠️
- Maximilian will Opus für alles — keine Kosten-Optimierung mit schwächeren Modellen

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

## Cron Jobs (Stand 2026-03-06)

- ALLE auf Claude Opus 4.6 (Maximilian will keine günstigeren Modelle!)
- daily-reverse-prompt: 7:00 Berlin → Discord #new-ideas (c620881a)
- shardib2-monitor: alle 5 Min (26813f30)
- daily-backup: 4:30 Berlin (f93d1eed)
- nightly-research: 3:00 Berlin → Telegram + Discord (3daccc8b)
- work-watchdog: alle 30 Min → Telegram (78910bee)

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
- **Sub-Agent fertig → SOFORT live-status.json updaten** (Agent + Todo auf "done"). NIE vergessen!
- **EIGENSTÄNDIG ARBEITEN** — Nicht auf Input warten, selbst denken, selbst handeln. Partner, nicht Tool.

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
- **TradingView Premium** — Cookies erhalten, Browser eingeloggt (Stand 06.03.)
- **Backtester V2 fertig**: 19 Ticker, Signal-Kombinations-Matrix, beste Kombi = Reversal+TrendLine+VMA_Color
- **Maximilian will wissen**: Welche Signal-Kombination funktioniert am besten pro Ticker/TF
- Nächster Schritt: TradingView CSV-Export → Backtester V3 mit echten langen Historien

## Task-Creator UI ✅ (06.03.)

- Modal im Dashboard: Aufgaben erstellen ohne Telegram
- Felder: Titel, Beschreibung, Priorität, AI Modell, Wer darf starten?, erweiterte Optionen, Datei-Upload
- API: POST /api/todos/create + /api/todos/update (beide speichern model + startPermission)
- Start-Berechtigungen: manual (nur Maximilian), watchdog (auto+manuell), auto (jeder Agent)

## Mission Control Dashboard

- Live: http://ubuntu-4gb-hel1-1.tail463d20.ts.net:8080
- Systemd Service `mission-control` (Port 8080, auto-restart)
- Tabs: Dashboard, 🔴 Live, Signals, Research, Cron Jobs, Memory, Automation, System, 📈 Backtest
- Features: Saraton Logo, Börsen-Countdown, Tab-Memory (localStorage), Live Agent Status, System Health
- Update-Script: `scripts/update-mission-control.py`
- live-status.json: Agent-Status Daten (manuell aktualisieren wenn Sub-Agents starten/enden)

## Nacht-Research

- Cron `nightly-research` (ID: 3daccc8b-d4a6-406f-8bb4-cd3ec1c16404)
- 03:00 Berlin, Opus
- REGEL: Nur fertige umgesetzte Arbeit — KEINE Ideen/Vorschläge
- Ergebnisse: `memory/nightly-research/` + Telegram + Discord

## Dashboard Start-Button
- Offene Todos haben ▶️ Start Button
- Klick → System Event + Telegram-Nachricht + Status auf "in-progress"
- Server braucht PATH mit `/home/linuxbrew/.linuxbrew/bin` für Node/openclaw
- Fehler-Feedback im Frontend (Toast + Retry)

## Backtester Versionen
- V2: 76 Runs, 19 Ticker, 7 Signale (yfinance Daten)
- V3: 76 Runs, 19 Ticker, 7 Signale (TV Max Daten, 544k Bars)
- V4: 95 Runs, 19 Ticker × 5 TFs, 39 Metriken, VMA Stop-Loss ← AKTUELL BESTE
- V5: 10 Runs, BTC+SOL × 5 TFs, 15 Signale, AND-Logik, ~7k Combos
  - Problem: Viele Top-Kombis haben nur 3 Trades → statistisch schwach
- Dashboard hat Versions-Dropdown zum Umschalten (V2/V3/V4/V5)

## Offene Punkte

- ~~Pine Script Code von Maximilian → Python Backtesting Engine bauen~~ ✅ (V2 fertig, 06.03.)
- TradingView CSV-Export → Backtester V3 mit echten langen Historien
- NordVPN Access Token holen → VPN verbinden
- DeepSeek Guthaben aufladen
- Gemini Free Tier Limit (20 Req/Tag) — NICHT mehr für Crons nutzen, alles Opus
- Brave API Key fehlt (web_search geht nicht) — web_fetch auf CoinDesk funktioniert als Alternative
- xurl nicht verbunden — Maximilian will X API nicht (kostet pro Anfrage)
- OpenAI Guthaben aufladen (Embeddings + Whisper)
- ~~Mission Control bauen~~ ✅ (gebaut + Live-Tab, Backtest-Tab, Börsen-Header, 06.03.)
- ShardiB2 Monitor läuft stabil ✅ (Stand 05.03.)
- Peter Steinberger Report mit echten Transcripts erweitern (nach VPN-Setup)
- Nightly-Research verifizieren (hat NOCH NIE erfolgreich gelaufen)
- live-status.json manuell updaten wenn Sub-Agents starten/enden
