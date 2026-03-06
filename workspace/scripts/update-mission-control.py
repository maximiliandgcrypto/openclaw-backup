#!/usr/bin/env python3
"""Update Mission Control Dashboard with live data."""

import json
import os
import re
from pathlib import Path

WORKSPACE = Path("/home/openclaw/.openclaw/workspace")
MC_DIR = WORKSPACE / "mission-control"
SIGNALS_FILE = WORKSPACE / "data/shardib2/signals.json"
CRON_FILE = Path("/home/openclaw/.openclaw/cron/jobs.json")
RESEARCH_DIR = WORKSPACE / "memory/nightly-research"

def load_signals():
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f).get("signals", [])
    return []

def load_crons():
    if CRON_FILE.exists():
        with open(CRON_FILE) as f:
            data = json.load(f)
            return data.get("jobs", [])
    return []

def load_research():
    research = []
    if RESEARCH_DIR.exists():
        for f in sorted(RESEARCH_DIR.glob("*.md"), reverse=True)[:10]:
            content = f.read_text()
            title = content.split('\n')[0].replace('#', '').strip() if content else f.stem
            summary = content[:200] + '...' if len(content) > 200 else content
            research.append({
                "date": f.stem,
                "title": title,
                "summary": summary.replace('\n', ' ').replace('"', "'")
            })
    return research

def update_dashboard():
    signals = load_signals()
    crons = load_crons()
    research = load_research()
    
    # Read template
    html_path = MC_DIR / "index.html"
    html = html_path.read_text()
    
    # Inject data using simple string replace
    def inject(html, marker, data):
        start = html.find(f'/*{marker}*/')
        if start == -1:
            return html
        # Find the array/object after the marker
        bracket_start = html.find('[', start) if html[start:start+50].find('[') != -1 else html.find('{', start)
        # Find matching close
        depth = 0
        for i in range(bracket_start, len(html)):
            if html[i] in '[{':
                depth += 1
            elif html[i] in ']}':
                depth -= 1
                if depth == 0:
                    return html[:bracket_start] + json.dumps(data) + html[i+1:]
        return html
    
    html = inject(html, 'SIGNALS_JSON', signals)
    def format_schedule(j):
        sched = j.get("schedule", {})
        if sched.get("expr"):
            return f"{sched['expr']} ({sched.get('tz', 'UTC')})"
        elif sched.get("intervalMs"):
            mins = sched["intervalMs"] // 60000
            return f"Alle {mins} Min"
        return "—"
    
    html = inject(html, 'CRON_JSON', [{"name": j["name"], "description": j.get("description",""), "model": j.get("model","default"), "enabled": j.get("enabled", True), "schedule": format_schedule(j)} for j in crons])
    html = inject(html, 'RESEARCH_JSON', research)
    
    html_path.write_text(html)
    print(f"✅ Dashboard updated: {len(signals)} signals, {len(crons)} crons, {len(research)} research items")

if __name__ == "__main__":
    update_dashboard()
