#!/usr/bin/env python3
"""Sync ShardiB2 tracker data to Notion database."""

import json, os, sys, urllib.request
from pathlib import Path

VENV = Path("/home/openclaw/.openclaw/workspace/trading-venv")
for v in ["python3.14", "python3.13", "python3.12"]:
    p = VENV / "lib" / v / "site-packages"
    if p.exists():
        sys.path.insert(0, str(p))

import yfinance as yf

API_KEY = os.environ.get("NOTION_API_KEY", "")
DB_ID = "31a98c30-ea54-815a-bc15-e35683b19885"
SIGNALS_FILE = Path("/home/openclaw/.openclaw/workspace/data/shardib2/signals.json")

def get_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except:
        pass
    return None

def notion_api(method, endpoint, data=None):
    url = f"https://api.notion.com/v1/{endpoint}"
    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }, method=method)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def get_notion_pages():
    """Get all pages from the Notion database."""
    result = notion_api("POST", f"databases/{DB_ID}/query", {"page_size": 100})
    pages = {}
    for page in result.get("results", []):
        title_prop = page["properties"].get("Ticker", {}).get("title", [])
        if title_prop:
            ticker = title_prop[0]["text"]["content"]
            pages[ticker] = page["id"]
    return pages

def update_notion_page(page_id, current_price, pnl_pct):
    """Update a Notion page with new price and P&L."""
    emoji = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"
    notion_api("PATCH", f"pages/{page_id}", {
        "icon": {"type": "emoji", "emoji": emoji},
        "properties": {
            "Current Price": {"number": current_price},
            "P&L %": {"number": round(pnl_pct / 100, 4)}
        }
    })

def main():
    if not API_KEY:
        print("NOTION_API_KEY not set")
        return
    
    # Load signals
    with open(SIGNALS_FILE) as f:
        data = json.load(f)
    
    # Get Notion pages
    notion_pages = get_notion_pages()
    
    # Update prices
    updated = 0
    for s in data["signals"]:
        if s["status"] != "OPEN":
            continue
        
        ticker = s["ticker"]
        price = get_price(ticker)
        if not price:
            continue
        
        # Update local data
        s["current_price"] = price
        if s.get("price_at_signal"):
            if s["direction"] in ["BUY", "HOLD"]:
                s["pnl_pct"] = round((price - s["price_at_signal"]) / s["price_at_signal"] * 100, 2)
            elif s["direction"] in ["SHORT", "SELL"]:
                s["pnl_pct"] = round((s["price_at_signal"] - price) / s["price_at_signal"] * 100, 2)
        
        # Update Notion
        notion_key = f"${ticker}"
        if notion_key in notion_pages:
            try:
                update_notion_page(notion_pages[notion_key], price, s.get("pnl_pct", 0))
                updated += 1
                emoji = "🟢" if s.get("pnl_pct", 0) > 0 else "🔴"
                print(f"{emoji} ${ticker}: ${price:.2f} ({s.get('pnl_pct', 0):+.1f}%)")
            except Exception as e:
                print(f"❌ ${ticker}: {e}")
    
    # Save updated local data
    from datetime import datetime, timezone
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ {updated} Positionen aktualisiert")

if __name__ == "__main__":
    main()
