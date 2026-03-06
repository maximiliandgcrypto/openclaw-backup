#!/usr/bin/env python3
"""
ShardiB2 Trading Signal Tracker & Backtester
=============================================
Tracks buy/sell signals from ShardiB2's posts, maps them to real price data,
and calculates performance metrics.

Data source: Yahoo Finance (free, no API key needed)
Storage: JSON + CSV files, can sync to Google Sheets later
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Activate venv
VENV = Path("/home/openclaw/.openclaw/workspace/trading-venv")
sys.path.insert(0, str(VENV / "lib" / "python3.13" / "site-packages"))
# Try multiple python versions
for v in ["python3.14", "python3.13", "python3.12"]:
    p = VENV / "lib" / v / "site-packages"
    if p.exists():
        sys.path.insert(0, str(p))

import yfinance as yf
import pandas as pd

# Paths
DATA_DIR = Path("/home/openclaw/.openclaw/workspace/data/shardib2")
SIGNALS_FILE = DATA_DIR / "signals.json"
PERFORMANCE_FILE = DATA_DIR / "performance.json"
TRADES_CSV = DATA_DIR / "trades.csv"

def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_signals():
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {"signals": [], "last_updated": None}

def save_signals(data):
    data["last_updated"] = datetime.utcnow().isoformat()
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_price(ticker, date_str=None):
    """Get price for a ticker. If date_str given, get close price on that date."""
    try:
        stock = yf.Ticker(ticker)
        if date_str:
            dt = datetime.fromisoformat(date_str)
            start = dt - timedelta(days=3)
            end = dt + timedelta(days=3)
            hist = stock.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if not hist.empty:
                # Get closest date
                target = pd.Timestamp(dt).tz_localize(hist.index.tz) if hist.index.tz else pd.Timestamp(dt)
                idx = hist.index.get_indexer([target], method='nearest')[0]
                return float(hist['Close'].iloc[idx])
        else:
            hist = stock.history(period="1d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"Error getting price for {ticker}: {e}")
    return None

def get_current_prices(tickers):
    """Get current prices for multiple tickers."""
    prices = {}
    for t in tickers:
        price = get_price(t)
        if price:
            prices[t] = price
    return prices

def add_signal(ticker, direction, date_str, price=None, note="", source_msg_id=""):
    """Add a trading signal.
    
    Args:
        ticker: e.g. "MU", "RKLB" (without $)
        direction: "BUY", "SELL", "SHORT", "CLOSE", "HOLD"
        date_str: ISO date string when signal was posted
        price: price at time of signal (auto-fetched if None)
        note: text from the post
        source_msg_id: Discord message ID
    """
    ensure_dirs()
    data = load_signals()
    
    if price is None:
        price = get_price(ticker, date_str)
    
    signal = {
        "id": len(data["signals"]) + 1,
        "ticker": ticker.upper().replace("$", ""),
        "direction": direction.upper(),
        "date": date_str,
        "price_at_signal": price,
        "current_price": get_price(ticker),
        "note": note,
        "source_msg_id": source_msg_id,
        "status": "OPEN",  # OPEN, CLOSED, EXPIRED
        "close_date": None,
        "close_price": None,
        "pnl_pct": None
    }
    
    # Calculate unrealized P&L
    if signal["price_at_signal"] and signal["current_price"]:
        if signal["direction"] in ["BUY", "HOLD"]:
            signal["pnl_pct"] = round(
                (signal["current_price"] - signal["price_at_signal"]) / signal["price_at_signal"] * 100, 2
            )
        elif signal["direction"] in ["SHORT", "SELL"]:
            signal["pnl_pct"] = round(
                (signal["price_at_signal"] - signal["current_price"]) / signal["price_at_signal"] * 100, 2
            )
    
    data["signals"].append(signal)
    save_signals(data)
    return signal

def close_signal(signal_id, close_price=None):
    """Close a signal (position exited)."""
    data = load_signals()
    for s in data["signals"]:
        if s["id"] == signal_id:
            s["status"] = "CLOSED"
            s["close_date"] = datetime.utcnow().isoformat()
            s["close_price"] = close_price or get_price(s["ticker"])
            if s["price_at_signal"] and s["close_price"]:
                if s["direction"] in ["BUY", "HOLD"]:
                    s["pnl_pct"] = round(
                        (s["close_price"] - s["price_at_signal"]) / s["price_at_signal"] * 100, 2
                    )
                elif s["direction"] in ["SHORT", "SELL"]:
                    s["pnl_pct"] = round(
                        (s["price_at_signal"] - s["close_price"]) / s["price_at_signal"] * 100, 2
                    )
            save_signals(data)
            return s
    return None

def update_prices():
    """Update current prices and P&L for all open signals."""
    data = load_signals()
    tickers = list(set(s["ticker"] for s in data["signals"] if s["status"] == "OPEN"))
    prices = get_current_prices(tickers)
    
    for s in data["signals"]:
        if s["status"] == "OPEN" and s["ticker"] in prices:
            s["current_price"] = prices[s["ticker"]]
            if s["price_at_signal"] and s["current_price"]:
                if s["direction"] in ["BUY", "HOLD"]:
                    s["pnl_pct"] = round(
                        (s["current_price"] - s["price_at_signal"]) / s["price_at_signal"] * 100, 2
                    )
                elif s["direction"] in ["SHORT", "SELL"]:
                    s["pnl_pct"] = round(
                        (s["price_at_signal"] - s["current_price"]) / s["price_at_signal"] * 100, 2
                    )
    
    save_signals(data)
    return data

def generate_report():
    """Generate performance report."""
    data = load_signals()
    signals = data["signals"]
    
    if not signals:
        return "No signals tracked yet."
    
    total = len(signals)
    open_signals = [s for s in signals if s["status"] == "OPEN"]
    closed = [s for s in signals if s["status"] == "CLOSED"]
    
    # Win rate (closed only)
    if closed:
        winners = [s for s in closed if s["pnl_pct"] and s["pnl_pct"] > 0]
        losers = [s for s in closed if s["pnl_pct"] and s["pnl_pct"] <= 0]
        win_rate = len(winners) / len(closed) * 100 if closed else 0
        avg_win = sum(s["pnl_pct"] for s in winners) / len(winners) if winners else 0
        avg_loss = sum(s["pnl_pct"] for s in losers) / len(losers) if losers else 0
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
    
    # Unrealized P&L on open positions
    open_pnl = [s["pnl_pct"] for s in open_signals if s["pnl_pct"] is not None]
    avg_open_pnl = sum(open_pnl) / len(open_pnl) if open_pnl else 0
    
    report = f"""📊 **ShardiB2 Signal Performance Report**
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Gesamt:** {total} Signale | {len(open_signals)} offen | {len(closed)} geschlossen

**Geschlossene Positionen:**
• Win Rate: {win_rate:.1f}%
• Avg Winner: +{avg_win:.1f}%
• Avg Loser: {avg_loss:.1f}%
• Profit Factor: {abs(avg_win/avg_loss) if avg_loss != 0 else 'N/A'}

**Offene Positionen:**
• Anzahl: {len(open_signals)}
• Avg Unrealized P&L: {avg_open_pnl:+.1f}%

**Aktive Signale:**"""
    
    for s in sorted(open_signals, key=lambda x: x.get("pnl_pct", 0) or 0, reverse=True):
        emoji = "🟢" if (s["pnl_pct"] or 0) > 0 else "🔴"
        pnl = f"{s['pnl_pct']:+.1f}%" if s["pnl_pct"] is not None else "N/A"
        entry = f"${s['price_at_signal']:.2f}" if s.get('price_at_signal') else "N/A"
        current = f"${s['current_price']:.2f}" if s.get('current_price') else "N/A"
        report += f"\n{emoji} **${s['ticker']}** ({s['direction']}) — Entry: {entry} → Now: {current} — **{pnl}**"
    
    return report

def export_csv():
    """Export all signals to CSV."""
    ensure_dirs()
    data = load_signals()
    if not data["signals"]:
        return
    
    df = pd.DataFrame(data["signals"])
    df.to_csv(TRADES_CSV, index=False)
    return str(TRADES_CSV)


# ─── CLI Interface ──────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ShardiB2 Trading Signal Tracker")
    sub = parser.add_subparsers(dest="cmd")
    
    # Add signal
    add_p = sub.add_parser("add", help="Add a signal")
    add_p.add_argument("ticker")
    add_p.add_argument("direction", choices=["BUY", "SELL", "SHORT", "CLOSE", "HOLD"])
    add_p.add_argument("--date", default=datetime.utcnow().isoformat())
    add_p.add_argument("--price", type=float)
    add_p.add_argument("--note", default="")
    add_p.add_argument("--msg-id", default="")
    
    # Close signal
    close_p = sub.add_parser("close", help="Close a signal")
    close_p.add_argument("signal_id", type=int)
    close_p.add_argument("--price", type=float)
    
    # Update prices
    sub.add_parser("update", help="Update all open positions")
    
    # Report
    sub.add_parser("report", help="Generate performance report")
    
    # Export
    sub.add_parser("export", help="Export to CSV")
    
    # List
    sub.add_parser("list", help="List all signals")
    
    args = parser.parse_args()
    
    if args.cmd == "add":
        s = add_signal(args.ticker, args.direction, args.date, args.price, args.note, args.msg_id)
        print(f"✅ Signal #{s['id']}: ${s['ticker']} {s['direction']} @ ${s['price_at_signal']:.2f}")
    
    elif args.cmd == "close":
        s = close_signal(args.signal_id, args.price)
        if s:
            print(f"✅ Closed #{s['id']}: ${s['ticker']} — P&L: {s['pnl_pct']:+.1f}%")
        else:
            print("Signal not found")
    
    elif args.cmd == "update":
        data = update_prices()
        open_count = len([s for s in data["signals"] if s["status"] == "OPEN"])
        print(f"✅ Updated {open_count} open positions")
    
    elif args.cmd == "report":
        print(generate_report())
    
    elif args.cmd == "export":
        path = export_csv()
        print(f"✅ Exported to {path}")
    
    elif args.cmd == "list":
        data = load_signals()
        for s in data["signals"]:
            emoji = "🟢" if (s["pnl_pct"] or 0) > 0 else "🔴" if s["pnl_pct"] else "⚪"
            status = s["status"]
            pnl = f"{s['pnl_pct']:+.1f}%" if s["pnl_pct"] is not None else "N/A"
            print(f"#{s['id']} {emoji} ${s['ticker']} {s['direction']} [{status}] — Entry: ${s.get('price_at_signal', 0):.2f} — P&L: {pnl}")
    
    else:
        parser.print_help()
