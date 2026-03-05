# HEARTBEAT.md

## Context Usage Warning
Check session_status and warn Maximilian via Telegram if context usage >= 95%.
Use session_status tool, parse the Context percentage.
If >= 95%: send urgent Telegram message to Maximilian (5214734582):
"⚠️ Claude Context bei [X]% — Session wird bald voll! Compaction oder neuer Chat empfohlen."
If < 95%: HEARTBEAT_OK (silent)
