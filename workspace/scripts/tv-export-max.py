#!/usr/bin/env python3
"""TradingView WebSocket API — Export maximum historical bars for all tickers/timeframes."""

import json
import random
import string
import time
import csv
import os
import sys
import websocket

# TradingView session cookies
SESSION_ID = "pq5r3tnbbi8eycmunl4u2r4821g7u2lf"
SESSION_SIGN = "v3:VNNLVzlzZNGVvOAPhnvsApQwGyXKh0/tS09Xct0OU/A="

OUTPUT_DIR = "/home/openclaw/.openclaw/workspace/data/tradingview-max/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Tickers
STOCK_TICKERS = {
    "SPY": "AMEX:SPY", "AAPL": "NASDAQ:AAPL", "NVDA": "NASDAQ:NVDA",
    "TSLA": "NASDAQ:TSLA", "META": "NASDAQ:META", "GOOGL": "NASDAQ:GOOGL", "AMZN": "NASDAQ:AMZN"
}
CRYPTO_TICKERS = {
    "BTCUSD": "BITSTAMP:BTCUSD", "ETHUSD": "BITSTAMP:ETHUSD", "SOLUSD": "BITSTAMP:SOLUSD",
    "XRPUSD": "BITSTAMP:XRPUSD", "BNBUSD": "COINBASE:BNBUSD", "DOGEUSD": "BITSTAMP:DOGEUSD",
    "LINKUSD": "BITSTAMP:LINKUSD", "ADAUSD": "BITSTAMP:ADAUSD", "TRXUSD": "KRAKEN:TRXUSD",
    "AVAXUSD": "BITSTAMP:AVAXUSD", "SUIUSD": "BITSTAMP:SUIUSD", "PEPEUSD": "BITSTAMP:PEPEUSD"
}
ALL_TICKERS = {**STOCK_TICKERS, **CRYPTO_TICKERS}

# Timeframes: TradingView format
TIMEFRAMES = {
    "5min": "5",
    "15min": "15",
    "1H": "60",
    "4H": "240",
    "1D": "1D"
}

MAX_BARS = 10000  # TradingView max


def gen_session():
    return "qs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


def send_msg(ws, method, params):
    msg = json.dumps({"m": method, "p": params})
    frame = f"~m~{len(msg)}~m~{msg}"
    ws.send(frame)


def parse_messages(raw):
    """Parse TradingView WebSocket frames."""
    messages = []
    i = 0
    while i < len(raw):
        if raw[i:i+3] == "~m~":
            i += 3
            end = raw.index("~m~", i)
            length = int(raw[i:end])
            i = end + 3
            payload = raw[i:i+length]
            i += length
            if payload.startswith("~h~"):
                messages.append(("heartbeat", payload))
            elif payload.startswith("{"):
                try:
                    messages.append(("json", json.loads(payload)))
                except json.JSONDecodeError:
                    pass
        else:
            i += 1
    return messages


def fetch_bars(ticker_label, tv_symbol, tf_label, tv_tf):
    """Fetch maximum bars for a single ticker/timeframe."""
    chart_session = "cs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    quote_session = gen_session()
    
    ws = websocket.create_connection(
        "wss://data.tradingview.com/socket.io/websocket",
        origin="https://www.tradingview.com",
        headers={
            "Cookie": f"sessionid={SESSION_ID}; sessionid_sign={SESSION_SIGN}"
        }
    )
    
    bars = []
    
    try:
        # Auth
        send_msg(ws, "set_auth_token", ["unauthorized_user_token"])
        
        # Create sessions
        send_msg(ws, "chart_create_session", [chart_session, ""])
        send_msg(ws, "quote_create_session", [quote_session])
        
        # Resolve symbol
        send_msg(ws, "resolve_symbol", [chart_session, "sds_sym_1", f"={{\"symbol\":\"{tv_symbol}\",\"adjustment\":\"splits\"}}"])
        
        # Create series with MAX bars
        send_msg(ws, "create_series", [chart_session, "sds_1", "s1", "sds_sym_1", tv_tf, MAX_BARS, ""])
        
        # Collect data
        timeout = time.time() + 30  # 30 sec timeout
        complete = False
        
        while time.time() < timeout and not complete:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutError:
                break
            
            messages = parse_messages(raw)
            for msg_type, msg in messages:
                if msg_type == "heartbeat":
                    # Echo heartbeat
                    ws.send(f"~m~{len(msg)}~m~{msg}")
                elif msg_type == "json":
                    m = msg.get("m", "")
                    p = msg.get("p", [])
                    
                    if m == "timescale_update":
                        # Main data payload
                        if len(p) >= 2 and isinstance(p[1], dict):
                            sds = p[1].get("sds_1", {})
                            series = sds.get("s", [])
                            for point in series:
                                v = point.get("v", [])
                                if len(v) >= 6:
                                    bars.append({
                                        "time": v[0],
                                        "open": v[1],
                                        "high": v[2],
                                        "low": v[3],
                                        "close": v[4],
                                        "volume": v[5] if len(v) > 5 else 0
                                    })
                    
                    elif m == "series_completed":
                        complete = True
                    
                    elif m == "symbol_error" or m == "critical_error":
                        print(f"  ❌ Error for {ticker_label}/{tf_label}: {p}")
                        return None
        
    finally:
        try:
            ws.close()
        except:
            pass
    
    if not bars:
        return None
    
    # Sort by time
    bars.sort(key=lambda b: b["time"])
    
    # Remove duplicates
    seen = set()
    unique_bars = []
    for b in bars:
        if b["time"] not in seen:
            seen.add(b["time"])
            unique_bars.append(b)
    
    return unique_bars


def save_csv(bars, filename):
    """Save bars to CSV."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for b in bars:
            # Convert timestamp to ISO
            ts = b["time"]
            if isinstance(ts, (int, float)):
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                b["time"] = dt.isoformat()
            writer.writerow(b)
    return filepath


def main():
    results = []
    total = len(ALL_TICKERS) * len(TIMEFRAMES)
    done = 0
    
    print(f"🚀 TradingView Max-Bars Export: {len(ALL_TICKERS)} Ticker × {len(TIMEFRAMES)} TFs = {total} exports")
    print(f"📁 Output: {OUTPUT_DIR}")
    print()
    
    for ticker_label, tv_symbol in ALL_TICKERS.items():
        for tf_label, tv_tf in TIMEFRAMES.items():
            done += 1
            filename = f"{ticker_label}_{tf_label}.csv"
            print(f"[{done}/{total}] {ticker_label} {tf_label}...", end=" ", flush=True)
            
            try:
                bars = fetch_bars(ticker_label, tv_symbol, tf_label, tv_tf)
                if bars:
                    save_csv(bars, filename)
                    print(f"✅ {len(bars)} bars")
                    results.append({"ticker": ticker_label, "tf": tf_label, "bars": len(bars), "status": "ok", "file": filename})
                else:
                    print("❌ no data")
                    results.append({"ticker": ticker_label, "tf": tf_label, "bars": 0, "status": "error", "file": filename})
            except Exception as e:
                print(f"❌ {e}")
                results.append({"ticker": ticker_label, "tf": tf_label, "bars": 0, "status": "error", "error": str(e), "file": filename})
            
            time.sleep(0.5)  # Rate limiting
    
    # Save log
    log = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "TradingView WebSocket API (max bars)",
        "maxBarsRequested": MAX_BARS,
        "totalExports": len(results),
        "successful": sum(1 for r in results if r["status"] == "ok"),
        "totalBars": sum(r["bars"] for r in results),
        "exports": results
    }
    with open(os.path.join(OUTPUT_DIR, "export-log.json"), "w") as f:
        json.dump(log, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Done: {log['successful']}/{log['totalExports']} exports, {log['totalBars']:,} total bars")
    print(f"📁 Files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
