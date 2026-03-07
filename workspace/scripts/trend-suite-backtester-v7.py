#!/usr/bin/env python3
"""
Trend Suite (GRÄTZ) Backtester V7 — yfinance + Full Signal Matrix
==================================================================
All 7 components converted from Pine Script:
  1) Reversal Bars (BB Breakout + Return + Confirmations)
  2) SuperTrend (ATR 10, Factor 3.0)
  3) Bollinger Bands (Length 19, Mult 2)
  4) Micro Dots (VMA + SMA + SuperTrend Confluence)
  5) VMA Trend Line (Fast=9, Medium=18, Slow=27)
  6) Exhaustion Lines (Swing 40, Count 10)
  7) 24h Volume (Filter only)

Tickers: SPY, AAPL, NVDA, TSLA, BTC-USD, META, GOOGL
Timeframes: 5min, 1h, 4h, Daily

Dynamic Risk Management:
  A-Level: ≥3 confluent signals → full position
  B-Level: 1-2 signals → half position

Stop Loss: VMA Trend Line as dynamic stop

Metrics per signal combination:
  Win Rate, Avg Return, Max Drawdown, Sharpe Ratio, Profit Factor
"""

import json
import sys
import warnings
import traceback
import time
from datetime import datetime, timedelta
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
TICKERS = ['SPY', 'AAPL', 'NVDA', 'TSLA', 'BTC-USD', 'META', 'GOOGL']
TIMEFRAMES = {
    '5min':  {'yf_interval': '5m',  'yf_period': '60d'},
    '1h':    {'yf_interval': '1h',  'yf_period': '730d'},
    '4h':    {'yf_interval': '1h',  'yf_period': '730d', 'resample': '4h'},  # yfinance doesn't have 4h directly
    'Daily': {'yf_interval': '1d',  'yf_period': 'max'},
}

INITIAL_CAPITAL = 10000
COMMISSION = 0.001  # 0.1% per trade (realistic)
MIN_TRADES = 5

# Signal component names
SIGNAL_NAMES = [
    'Reversal',       # 0 - Reversal Bars
    'SuperTrend',     # 1 - SuperTrend direction
    'Bollinger',      # 2 - BB signal
    'MicroDots',      # 3 - Micro Dots confluence
    'VMA_Trend',      # 4 - VMA trend direction
    'Exhaustion',     # 5 - Exhaustion signals
    'VMA_Color',      # 6 - VMA color change (primary signal)
]

OUTPUT_DIR = Path('/home/openclaw/.openclaw/workspace/mission-control')
RESULTS_JSON = OUTPUT_DIR / 'backtest-results-v7.json'
EQUITY_PNG = OUTPUT_DIR / 'backtest-equity-v7.png'
SCRIPT_DIR = Path('/home/openclaw/.openclaw/workspace/scripts')


# ============================================================
# DATA LOADING VIA YFINANCE
# ============================================================
def fetch_data(ticker, tf_key):
    """Download OHLCV data via yfinance."""
    cfg = TIMEFRAMES[tf_key]
    try:
        tk = yf.Ticker(ticker)
        
        if tf_key == '4h':
            # Download 1h data and resample to 4h
            df = tk.history(period=cfg['yf_period'], interval=cfg['yf_interval'])
            if df.empty:
                return None
            df.columns = [c.lower().replace(' ', '_') for c in df.columns]
            # Rename columns
            col_map = {}
            for c in df.columns:
                if 'open' in c: col_map[c] = 'open'
                elif 'high' in c: col_map[c] = 'high'
                elif 'low' in c: col_map[c] = 'low'
                elif 'close' in c: col_map[c] = 'close'
                elif 'volume' in c and 'capital' not in c: col_map[c] = 'volume'
            df = df.rename(columns=col_map)
            # Resample to 4h
            df = df.resample('4h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
        else:
            df = tk.history(period=cfg['yf_period'], interval=cfg['yf_interval'])
            if df.empty:
                return None
            df.columns = [c.lower().replace(' ', '_') for c in df.columns]
            col_map = {}
            for c in df.columns:
                if 'open' in c: col_map[c] = 'open'
                elif 'high' in c: col_map[c] = 'high'
                elif 'low' in c: col_map[c] = 'low'
                elif 'close' in c: col_map[c] = 'close'
                elif 'volume' in c and 'capital' not in c: col_map[c] = 'volume'
            df = df.rename(columns=col_map)
        
        df = df.reset_index()
        if 'Date' in df.columns:
            df = df.rename(columns={'Date': 'date'})
        elif 'Datetime' in df.columns:
            df = df.rename(columns={'Datetime': 'date'})
        elif 'index' in df.columns:
            df = df.rename(columns={'index': 'date'})
        
        # Ensure date column exists
        if 'date' not in df.columns:
            df['date'] = df.index
        
        df['date'] = pd.to_datetime(df['date'])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        df = df.sort_values('date').reset_index(drop=True)
        
        return df if len(df) >= 50 else None
        
    except Exception as e:
        print(f"  [WARN] fetch_data({ticker}, {tf_key}): {e}")
        return None


# ============================================================
# INDICATOR CALCULATIONS (from Pine Script)
# ============================================================

def calc_bollinger(df, length=19, mult=2.0):
    """Bollinger Bands: SMA(19) ± 2*StdDev"""
    df['bb_basis'] = df['close'].rolling(length).mean()
    df['bb_std'] = df['close'].rolling(length).std()
    df['bb_upper'] = df['bb_basis'] + mult * df['bb_std']
    df['bb_lower'] = df['bb_basis'] - mult * df['bb_std']
    # BB signal: above upper = bearish, below lower = bullish
    df['bb_signal'] = 0
    df.loc[df['close'] > df['bb_upper'], 'bb_signal'] = -1
    df.loc[df['close'] < df['bb_lower'], 'bb_signal'] = 1
    return df


def calc_reversals(df):
    """
    Reversal Bars: BB Breakout + Return + Confirmation
    Pine Script logic:
      Bull: low[1] < lower[1] AND close[1] < open[1] AND close > lower AND close > open
      Bear: high[1] > upper[1] AND close[1] > open[1] AND close < upper AND close < open
    Confirmations add high/low break requirements.
    """
    c, o, h, lo = df['close'], df['open'], df['high'], df['low']
    upper, lower = df['bb_upper'], df['bb_lower']
    
    # Bull Reversal
    df['bull_reversal'] = (
        (lo.shift(1) < lower.shift(1)) & (c.shift(1) < o.shift(1)) &
        (c > lower) & (c > o)
    )
    # Bear Reversal
    df['bear_reversal'] = (
        (h.shift(1) > upper.shift(1)) & (c.shift(1) > o.shift(1)) &
        (c < upper) & (c < o)
    )
    # Confirmation 1
    df['bull_confirm1'] = (
        (lo.shift(2) < lower.shift(2)) & (c.shift(2) < o.shift(2)) &
        (c.shift(1) > lower.shift(1)) & (c.shift(1) > o.shift(1)) & (c > h.shift(1))
    )
    df['bear_confirm1'] = (
        (h.shift(2) > upper.shift(2)) & (c.shift(2) > o.shift(2)) &
        (c.shift(1) < upper.shift(1)) & (c.shift(1) < o.shift(1)) & (c < lo.shift(1))
    )
    # Confirmation 2
    df['bull_confirm2'] = (
        (lo.shift(3) < lower.shift(3)) & (c.shift(3) < o.shift(3)) &
        (c.shift(2) > lower.shift(2)) & (c.shift(2) > o.shift(2)) & (c > h.shift(2))
    )
    df['bear_confirm2'] = (
        (h.shift(3) > upper.shift(3)) & (c.shift(3) > o.shift(3)) &
        (c.shift(2) < upper.shift(2)) & (c.shift(2) < o.shift(2)) & (c < lo.shift(2))
    )
    
    # Combined reversal signal
    df['reversal_signal'] = 0
    df.loc[df['bull_reversal'] | df['bull_confirm1'] | df['bull_confirm2'], 'reversal_signal'] = 1
    df.loc[df['bear_reversal'] | df['bear_confirm1'] | df['bear_confirm2'], 'reversal_signal'] = -1
    return df


def calc_supertrend(df, atr_period=10, factor=3.0):
    """
    SuperTrend: ATR-based trend following.
    Pine: [supertrend, direction] = ta.supertrend(factor, atrPeriod)
    direction < 0 = bullish (green bars), direction > 0 = bearish (red bars)
    """
    hl2 = (df['high'] + df['low']) / 2
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    
    up = hl2 - factor * atr
    dn = hl2 + factor * atr
    n = len(df)
    st_up = np.zeros(n)
    st_dn = np.zeros(n)
    st_dir = np.ones(n)  # 1 = bearish, -1 = bullish (Pine convention)
    
    for i in range(1, n):
        st_up[i] = up.iloc[i]
        if df['close'].iloc[i-1] > st_up[i-1]:
            st_up[i] = max(st_up[i], st_up[i-1])
        
        st_dn[i] = dn.iloc[i]
        if df['close'].iloc[i-1] < st_dn[i-1]:
            st_dn[i] = min(st_dn[i], st_dn[i-1])
        
        if st_dir[i-1] == -1 and df['close'].iloc[i] > st_dn[i-1]:
            st_dir[i] = 1
        elif st_dir[i-1] == 1 and df['close'].iloc[i] < st_up[i-1]:
            st_dir[i] = -1
        else:
            st_dir[i] = st_dir[i-1]
    
    df['st_direction'] = st_dir
    df['st_up'] = st_up
    df['st_dn'] = st_dn
    # Convert to our convention: 1 = bullish, -1 = bearish
    df['supertrend_signal'] = np.where(st_dir < 0, 1, -1)
    return df


def calc_vma(src, vma_length):
    """
    Variable Moving Average (VMA) - exact Pine Script implementation.
    Uses directional movement + volatility index to adapt smoothing.
    """
    n = len(src)
    k = 1.0 / vma_length
    pdm = np.maximum(np.diff(src, prepend=src[0]), 0)
    mdm = np.maximum(-np.diff(src, prepend=src[0]), 0)
    
    pdmS = np.zeros(n); mdmS = np.zeros(n)
    pdiS = np.zeros(n); mdiS = np.zeros(n)
    iS = np.zeros(n); vma = np.zeros(n)
    vma[0] = src[0]
    
    for i in range(1, n):
        pdmS[i] = (1 - k) * pdmS[i-1] + k * pdm[i]
        mdmS[i] = (1 - k) * mdmS[i-1] + k * mdm[i]
        s = pdmS[i] + mdmS[i]
        if s == 0:
            pdi = 0; mdi = 0
        else:
            pdi = pdmS[i] / s; mdi = mdmS[i] / s
        pdiS[i] = (1 - k) * pdiS[i-1] + k * pdi
        mdiS[i] = (1 - k) * mdiS[i-1] + k * mdi
        d = abs(pdiS[i] - mdiS[i])
        s1 = pdiS[i] + mdiS[i]
        if s1 == 0:
            iS[i] = iS[i-1]
        else:
            iS[i] = (1 - k) * iS[i-1] + k * d / s1
    
    hhv = pd.Series(iS).rolling(vma_length, min_periods=1).max().values
    llv = pd.Series(iS).rolling(vma_length, min_periods=1).min().values
    d1 = hhv - llv
    vI = np.where(d1 != 0, (iS - llv) / d1, 0)
    
    for i in range(1, n):
        vma[i] = (1 - k * vI[i]) * vma[i-1] + k * vI[i] * src[i]
    
    return vma


def calc_vma_trend(df):
    """
    VMA Trend Line with color signals (Fast=9, Medium=18, Slow=27).
    Color: Green (rising + above medium), Red (falling + below medium), Orange (flat).
    VMA Color Change = primary signal for entries.
    """
    src = df['close'].values.astype(float)
    vma_fast = calc_vma(src, 9)
    vma_med = calc_vma(src, 18)
    vma_slow = calc_vma(src, 27)
    
    df['vma_fast'] = vma_fast
    df['vma_med'] = vma_med
    df['vma_slow'] = vma_slow
    df['vma'] = vma_fast  # Primary VMA line
    
    n = len(df)
    color = np.zeros(n, dtype=int)  # 1=green, -1=red, 0=orange
    
    for i in range(1, n):
        if vma_fast[i] > vma_fast[i-1] and vma_fast[i] > vma_med[i]:
            color[i] = 1  # Green
        elif vma_fast[i] < vma_fast[i-1] and vma_fast[i] < vma_med[i]:
            color[i] = -1  # Red
        # else: 0 = Orange
    
    df['vma_color'] = color
    df['vma_trend'] = np.where(color == 1, 1, np.where(color == -1, -1, 0))
    
    # VMA Color Change signals (A-Setup and B-Setup)
    vma_signal = np.zeros(n, dtype=int)
    setup_type = [''] * n
    
    for i in range(2, n):
        prev = color[i-1]; curr = color[i]; prev2 = color[i-2]
        
        # A-Setup: Direct Red→Green or Green→Red
        if prev == -1 and curr == 1:
            vma_signal[i] = 1; setup_type[i] = 'A'
        elif prev == 1 and curr == -1:
            vma_signal[i] = -1; setup_type[i] = 'A'
        
        # B-Setup: Red→Orange→Green (or via lookback)
        elif prev == 0 and curr == 1 and prev2 == -1:
            vma_signal[i] = 1; setup_type[i] = 'B'
        elif prev == 0 and curr == -1 and prev2 == 1:
            vma_signal[i] = -1; setup_type[i] = 'B'
        elif prev == 0 and curr == 1:
            for j in range(max(0, i-5), i):
                if color[j] == -1:
                    vma_signal[i] = 1; setup_type[i] = 'B'; break
        elif prev == 0 and curr == -1:
            for j in range(max(0, i-5), i):
                if color[j] == 1:
                    vma_signal[i] = -1; setup_type[i] = 'B'; break
    
    df['vma_color_signal'] = vma_signal
    df['setup_type'] = setup_type
    return df


def calc_micro_dots(df):
    """
    Micro Dots: Confluence of VMA(4) + SMA(18) + SuperTrend.
    Green dot: VMA < price AND price > SMA AND SuperTrend up AND NOT VMA down
    Red dot: VMA > price AND price < SMA AND SuperTrend down AND NOT VMA up
    """
    src = df['close'].values.astype(float)
    md_mult = 1.1; md_periods = 10
    hl2 = ((df['high'] + df['low']) / 2).values
    
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1).values
    
    md_atr = pd.Series(tr).rolling(md_periods).mean().values
    md_up = hl2 - md_mult * md_atr
    md_dn = hl2 + md_mult * md_atr
    
    n = len(df)
    md_trend = np.ones(n)
    
    for i in range(1, n):
        if not np.isnan(md_up[i-1]) and src[i-1] > md_up[i-1]:
            md_up[i] = max(md_up[i], md_up[i-1]) if not np.isnan(md_up[i-1]) else md_up[i]
        if not np.isnan(md_dn[i-1]) and src[i-1] < md_dn[i-1]:
            md_dn[i] = min(md_dn[i], md_dn[i-1]) if not np.isnan(md_dn[i-1]) else md_dn[i]
        
        prev_dn = md_dn[i-1] if not np.isnan(md_dn[i-1]) else md_dn[i]
        prev_up = md_up[i-1] if not np.isnan(md_up[i-1]) else md_up[i]
        
        if md_trend[i-1] == -1 and src[i] > prev_dn:
            md_trend[i] = 1
        elif md_trend[i-1] == 1 and src[i] < prev_up:
            md_trend[i] = -1
        else:
            md_trend[i] = md_trend[i-1]
    
    # VMA(4) for micro dots
    md_vma = calc_vma(src, 4)
    md_sma = pd.Series(src).rolling(18).mean().values
    
    trend_up = md_trend == 1
    vma_up = md_vma < src
    vma_down = md_vma > src
    ma_up = src > md_sma
    ma_down = src < md_sma
    
    df['micro_up'] = vma_up & ma_up & trend_up & ~vma_down
    df['micro_down'] = vma_down & ma_down & ~trend_up & ~vma_up
    df['micro_signal'] = 0
    df.loc[df['micro_up'], 'micro_signal'] = 1
    df.loc[df['micro_down'], 'micro_signal'] = -1
    return df


def calc_exhaustion(df, swing_length=40, bar_count=10):
    """
    Exhaustion Lines: Counts consecutive up/down bars compared to 4 bars ago.
    Pine: if bindex > bars AND close < open AND high >= highest(high, len) → sell exhaustion
    """
    c = df['close'].values
    o = df['open'].values
    h = df['high'].values
    lo = df['low'].values
    n = len(df)
    exhaust = np.zeros(n)
    
    bindex = 0  # buy pressure counter
    sindex = 0  # sell pressure counter
    
    for i in range(4, n):
        if c[i] > c[i-4]:
            bindex += 1
        if c[i] < c[i-4]:
            sindex += 1
        
        highest_high = np.max(h[max(0, i-swing_length+1):i+1])
        lowest_low = np.min(lo[max(0, i-swing_length+1):i+1])
        
        # Sell exhaustion: too much buying pressure + reversal candle at high
        if bindex > bar_count and c[i] < o[i] and h[i] >= highest_high:
            bindex = 0
            exhaust[i] = -1
        # Buy exhaustion: too much selling pressure + reversal candle at low
        elif sindex > bar_count and c[i] > o[i] and lo[i] <= lowest_low:
            sindex = 0
            exhaust[i] = 1
    
    df['exhaustion'] = exhaust
    return df


def calc_volume_filter(df, threshold_pct=50):
    """
    24h Volume filter: marks bars where volume is above the Nth percentile.
    In the original Pine Script, this is a visual filter only.
    We use it as a quality filter for entries.
    """
    if 'volume' not in df.columns or df['volume'].isna().all():
        df['volume_ok'] = True
        return df
    
    vol_ma = df['volume'].rolling(20).mean()
    df['volume_ok'] = df['volume'] >= vol_ma * 0.5  # At least 50% of 20-bar avg volume
    return df


def calc_atr(df, period=14):
    """ATR for position sizing and stops."""
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(period).mean()
    return df


def compute_all_indicators(df):
    """Run all 7 indicator calculations."""
    df = calc_bollinger(df)
    df = calc_reversals(df)
    df = calc_supertrend(df)
    df = calc_vma_trend(df)
    df = calc_micro_dots(df)
    df = calc_exhaustion(df)
    df = calc_volume_filter(df)
    df = calc_atr(df)
    return df


# ============================================================
# SIGNAL EXTRACTION
# ============================================================
def extract_signals(df):
    """Extract 7 signal arrays: each +1 (long), -1 (short), or 0 (neutral)."""
    n = len(df)
    signals = np.zeros((7, n), dtype=np.int8)
    
    signals[0] = df['reversal_signal'].values.astype(np.int8)          # Reversal
    signals[1] = df['supertrend_signal'].values.astype(np.int8)        # SuperTrend
    signals[2] = df['bb_signal'].values.astype(np.int8)                # Bollinger
    signals[3] = df['micro_signal'].values.astype(np.int8)             # MicroDots
    signals[4] = df['vma_trend'].values.astype(np.int8)                # VMA Trend
    signals[5] = df['exhaustion'].values.astype(np.int8)               # Exhaustion
    signals[6] = df['vma_color_signal'].values.astype(np.int8)         # VMA Color
    
    return signals


# ============================================================
# GENERATE ALL SIGNAL COMBINATIONS
# ============================================================
def generate_all_combos():
    """Generate all non-empty combinations of 7 signals (127 total)."""
    combos = []
    for r in range(1, len(SIGNAL_NAMES) + 1):
        for combo in combinations(range(len(SIGNAL_NAMES)), r):
            combos.append(combo)
    return combos


def combo_name(indices):
    return ' + '.join(SIGNAL_NAMES[i] for i in sorted(indices))


# ============================================================
# BACKTEST ENGINE WITH DYNAMIC RISK MANAGEMENT
# ============================================================
def backtest(entry_signal, df, signals_matrix, combo_indices,
             initial_capital=INITIAL_CAPITAL):
    """
    Bar-by-bar backtest with:
    - Entry on NEXT bar after signal (no lookahead)
    - Dynamic stop loss: VMA trend line
    - A/B level position sizing
    - Volume filter
    """
    n = len(df)
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    vma = df['vma'].values.astype(np.float64)
    vma_color = df['vma_color'].values.astype(np.int8)
    volume_ok = df['volume_ok'].values.astype(bool)
    setup_type_arr = df['setup_type'].values
    atr = df['atr'].values.astype(np.float64)
    
    equity = np.full(n, float(initial_capital), dtype=np.float64)
    
    position = 0         # +1 long, -1 short, 0 flat
    entry_price = 0.0
    entry_idx = 0
    position_size = 0.0
    pending_signal = 0
    
    trades = []
    
    def count_confluent(bar_idx, direction):
        """Count how many signals agree at this bar."""
        count = 0
        for sig_idx in range(7):
            if signals_matrix[sig_idx, bar_idx] == direction:
                count += 1
        return count
    
    def get_position_fraction(bar_idx, direction):
        """A-Level (≥3 confluent) = 1.0, B-Level = 0.5"""
        confluent = count_confluent(bar_idx, direction)
        if confluent >= 3:
            return 1.0  # A-Level
        else:
            return 0.5  # B-Level
    
    for i in range(1, n):
        equity[i] = equity[i-1]
        
        # Mark-to-market
        if position != 0:
            pnl = position * (close[i] - close[i-1]) * position_size
            equity[i] += pnl
        
        # --- Check exits ---
        if position != 0:
            exited = False
            
            # Dynamic stop: VMA trend line cross
            if position == 1 and close[i] < vma[i] and vma_color[i] == -1:
                ret = (close[i] - entry_price) / entry_price
                pnl = (close[i] - entry_price) * position_size
                trades.append({
                    'direction': 'LONG', 'entry': entry_price, 'exit': close[i],
                    'return': ret, 'pnl': pnl, 'bars': i - entry_idx,
                    'reason': 'VMA Stop'
                })
                position = 0; exited = True
            
            elif position == -1 and close[i] > vma[i] and vma_color[i] == 1:
                ret = (entry_price - close[i]) / entry_price
                pnl = (entry_price - close[i]) * position_size
                trades.append({
                    'direction': 'SHORT', 'entry': entry_price, 'exit': close[i],
                    'return': ret, 'pnl': pnl, 'bars': i - entry_idx,
                    'reason': 'VMA Stop'
                })
                position = 0; exited = True
            
            # Signal flip exit
            if not exited and entry_signal[i] == -position:
                if position == 1:
                    ret = (close[i] - entry_price) / entry_price
                    pnl = (close[i] - entry_price) * position_size
                else:
                    ret = (entry_price - close[i]) / entry_price
                    pnl = (entry_price - close[i]) * position_size
                trades.append({
                    'direction': 'LONG' if position == 1 else 'SHORT',
                    'entry': entry_price, 'exit': close[i],
                    'return': ret, 'pnl': pnl, 'bars': i - entry_idx,
                    'reason': 'Signal Flip'
                })
                position = 0; exited = True
        
        # --- Check entry ---
        if pending_signal != 0 and position == 0:
            # Volume filter
            if volume_ok[i]:
                position = pending_signal
                entry_price = close[i]
                entry_idx = i
                
                # Dynamic position sizing based on confluence
                fraction = get_position_fraction(i, position)
                position_size = (equity[i] * fraction * (1 - COMMISSION)) / close[i] if close[i] > 0 else 0
        
        # Store signal for next bar
        pending_signal = int(entry_signal[i])
    
    # Close open position at end
    if position != 0:
        if position == 1:
            ret = (close[-1] - entry_price) / entry_price
            pnl = (close[-1] - entry_price) * position_size
        else:
            ret = (entry_price - close[-1]) / entry_price
            pnl = (entry_price - close[-1]) * position_size
        trades.append({
            'direction': 'LONG' if position == 1 else 'SHORT',
            'entry': entry_price, 'exit': close[-1],
            'return': ret, 'pnl': pnl, 'bars': len(close) - 1 - entry_idx,
            'reason': 'End of Data'
        })
    
    if len(trades) < MIN_TRADES:
        return None
    
    return equity, trades


# ============================================================
# METRICS CALCULATION
# ============================================================
def calc_metrics(trades, equity, initial_capital=INITIAL_CAPITAL):
    """Calculate comprehensive metrics for a strategy."""
    returns = [t['return'] for t in trades]
    pnls = [t['pnl'] for t in trades]
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]
    
    win_rate = len(winners) / len(trades) * 100 if trades else 0
    avg_return = float(np.mean(returns)) * 100 if returns else 0
    avg_win = float(np.mean([t['return'] for t in winners])) * 100 if winners else 0
    avg_loss = float(np.mean([t['return'] for t in losers])) * 100 if losers else 0
    
    # Max Drawdown
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak * 100
    max_dd = abs(float(np.min(dd))) if len(dd) > 0 else 0
    
    # Sharpe Ratio (annualized)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(min(252, len(returns))))
    else:
        sharpe = 0.0
    
    # Profit Factor
    gross_profit = sum(t['pnl'] for t in winners)
    gross_loss = abs(sum(t['pnl'] for t in losers))
    profit_factor = min(gross_profit / gross_loss if gross_loss > 0 else 99.99, 99.99)
    
    # Net profit
    net_profit = equity[-1] - initial_capital
    total_return = (net_profit / initial_capital) * 100
    
    # Avg bars held
    avg_bars_win = float(np.mean([t['bars'] for t in winners])) if winners else 0
    avg_bars_loss = float(np.mean([t['bars'] for t in losers])) if losers else 0
    
    return {
        'win_rate': round(win_rate, 1),
        'avg_return': round(avg_return, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 2),
        'profit_factor': round(profit_factor, 2),
        'net_profit': round(net_profit, 2),
        'total_return': round(total_return, 2),
        'total_trades': len(trades),
        'winning_trades': len(winners),
        'losing_trades': len(losers),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(-abs(sum(t['pnl'] for t in losers)), 2),
        'avg_bars_win': round(avg_bars_win, 1),
        'avg_bars_loss': round(avg_bars_loss, 1),
        'largest_win': round(max(t['return'] for t in winners) * 100, 2) if winners else 0,
        'largest_loss': round(min(t['return'] for t in losers) * 100, 2) if losers else 0,
    }


# ============================================================
# EQUITY CURVE PLOTTING
# ============================================================
def plot_equity_curves(all_results, output_path):
    """Generate equity curve chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), facecolor='#0a0a0f')
    
    # --- Top plot: Best strategy per ticker (Daily only) ---
    ax1 = axes[0]
    ax1.set_facecolor('#0a0a0f')
    
    colors = ['#00d4aa', '#ff4757', '#5dade2', '#f39c12', '#9b59b6', '#e74c3c', '#2ecc71']
    ticker_idx = 0
    
    for ticker in TICKERS:
        # Find best strategy for this ticker on Daily
        best = None
        for r in all_results:
            if r['ticker'] == ticker and r['timeframe'] == 'Daily':
                if best is None or r['metrics']['sharpe_ratio'] > best['metrics']['sharpe_ratio']:
                    best = r
        
        if best and best.get('equity') is not None:
            eq = best['equity']
            color = colors[ticker_idx % len(colors)]
            ax1.plot(eq, label=f"{ticker}", color=color, linewidth=1.2, alpha=0.9)
        ticker_idx += 1
    
    ax1.set_title('Trend Suite (GRÄTZ) V7 — Best Strategy per Ticker (Daily)',
                   color='white', fontsize=14, fontweight='bold', pad=15)
    ax1.set_ylabel('Portfolio Value (€)', color='white', fontsize=11)
    ax1.legend(loc='upper left', fontsize=9, facecolor='#14141e', edgecolor='#1e1e2e',
               labelcolor='white', ncol=4)
    ax1.grid(True, alpha=0.1, color='white')
    ax1.tick_params(colors='white')
    ax1.spines['bottom'].set_color('#1e1e2e')
    ax1.spines['left'].set_color('#1e1e2e')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    
    # --- Bottom plot: Combined equal-weight portfolio ---
    ax2 = axes[1]
    ax2.set_facecolor('#0a0a0f')
    
    # Collect all Daily best equities and average them
    daily_equities = []
    for ticker in TICKERS:
        best = None
        for r in all_results:
            if r['ticker'] == ticker and r['timeframe'] == 'Daily':
                if best is None or r['metrics']['sharpe_ratio'] > best['metrics']['sharpe_ratio']:
                    best = r
        if best and best.get('equity') is not None:
            daily_equities.append(best['equity'])
    
    if daily_equities:
        # Normalize to same length (shortest)
        min_len = min(len(eq) for eq in daily_equities)
        combined = np.zeros(min_len)
        for eq in daily_equities:
            combined += eq[:min_len] / len(daily_equities)
        
        ax2.fill_between(range(min_len), INITIAL_CAPITAL, combined,
                         where=combined >= INITIAL_CAPITAL, alpha=0.3, color='#00d4aa')
        ax2.fill_between(range(min_len), INITIAL_CAPITAL, combined,
                         where=combined < INITIAL_CAPITAL, alpha=0.3, color='#ff4757')
        ax2.plot(combined, color='#00d4aa', linewidth=1.5)
        ax2.axhline(y=INITIAL_CAPITAL, color='#ff4757', linestyle='--', alpha=0.5, linewidth=0.8)
    
    ax2.set_title(f'Combined Equal-Weight Portfolio ({len(TICKERS)} Tickers)',
                   color='white', fontsize=14, fontweight='bold', pad=15)
    ax2.set_xlabel('Trading Days', color='white', fontsize=11)
    ax2.set_ylabel('Portfolio Value (€)', color='white', fontsize=11)
    ax2.grid(True, alpha=0.1, color='white')
    ax2.tick_params(colors='white')
    ax2.spines['bottom'].set_color('#1e1e2e')
    ax2.spines['left'].set_color('#1e1e2e')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    
    plt.tight_layout(pad=3)
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight', facecolor='#0a0a0f')
    plt.close()
    print(f"  📊 Equity curve saved: {output_path}")


# ============================================================
# MAIN
# ============================================================
def main():
    t_start = time.time()
    print("=" * 70)
    print("TREND SUITE (GRÄTZ) BACKTESTER V7 — yfinance + Full Signal Matrix")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES.keys())}")
    print(f"Capital: {INITIAL_CAPITAL:,}€ | Commission: {COMMISSION*100:.1f}%")
    print(f"Min Trades: {MIN_TRADES}")
    print()
    
    # Generate all signal combinations
    all_combos = generate_all_combos()
    print(f"📋 Signal combinations to test: {len(all_combos)} (all combos of {len(SIGNAL_NAMES)} signals)")
    print()
    
    all_results = []
    results_json = {
        'meta': {
            'generated': datetime.now().isoformat(),
            'version': 'V7',
            'data_source': 'yfinance',
            'initial_capital': INITIAL_CAPITAL,
            'commission': COMMISSION,
            'currency': 'EUR',
            'tickers': TICKERS,
            'timeframes': list(TIMEFRAMES.keys()),
            'components': SIGNAL_NAMES,
            'total_combos': len(all_combos),
            'features': [
                'All 7 Pine Script components converted',
                'yfinance data (live)',
                'Dynamic Risk Management (A/B Level)',
                'VMA Trend Line as dynamic stop',
                'Volume filter',
                'No lookahead bias',
                'Candle close entry rule',
                '127 signal combinations tested',
            ],
        },
        'results': [],
        'best_per_ticker': {},
        'best_per_timeframe': {},
        'best_per_combo': {},
        'top_20_global': [],
        'signal_stats': {},
    }
    
    total_runs = len(TICKERS) * len(TIMEFRAMES)
    run_idx = 0
    
    for ticker in TICKERS:
        for tf_key in TIMEFRAMES:
            run_idx += 1
            label = f"{ticker} / {tf_key}"
            print(f"\n[{run_idx}/{total_runs}] {'='*50}")
            print(f"📊 {label}")
            
            try:
                df = fetch_data(ticker, tf_key)
                if df is None:
                    print(f"  ⚠️ No data available")
                    continue
                
                n_bars = len(df)
                date_start = df['date'].iloc[0].strftime('%Y-%m-%d')
                date_end = df['date'].iloc[-1].strftime('%Y-%m-%d')
                print(f"  📅 {date_start} → {date_end} ({n_bars} bars)")
                
                # Compute indicators
                print(f"  🔧 Computing all 7 indicators...")
                df = compute_all_indicators(df)
                
                # Extract signals
                signals_matrix = extract_signals(df)
                
                # Test all combinations
                print(f"  🔬 Testing {len(all_combos)} signal combinations...")
                run_results = []
                t_run = time.time()
                
                for combo in all_combos:
                    # AND-combine signals
                    selected = signals_matrix[list(combo)]
                    if len(combo) == 1:
                        combined = selected[0].copy()
                    else:
                        all_bull = np.all(selected == 1, axis=0)
                        all_bear = np.all(selected == -1, axis=0)
                        combined = np.zeros(n_bars, dtype=np.int8)
                        combined[all_bull] = 1
                        combined[all_bear] = -1
                    combined[0] = 0
                    
                    # Check minimum signals
                    n_signals = int(np.sum(combined != 0))
                    if n_signals < MIN_TRADES:
                        continue
                    
                    # Run backtest
                    result = backtest(combined, df, signals_matrix, combo)
                    if result is None:
                        continue
                    
                    equity, trades = result
                    metrics = calc_metrics(trades, equity)
                    
                    c_name = combo_name(combo)
                    entry = {
                        'ticker': ticker,
                        'timeframe': tf_key,
                        'combination': c_name,
                        'combo_indices': list(combo),
                        'n_signals': len(combo),
                        'metrics': metrics,
                        'equity': equity,  # Keep for plotting
                        'data_range': f"{date_start} → {date_end}",
                        'bars': n_bars,
                    }
                    run_results.append(entry)
                    all_results.append(entry)
                
                run_time = time.time() - t_run
                print(f"  ✅ {len(run_results)} valid strategies in {run_time:.1f}s")
                
                if run_results:
                    # Sort by Sharpe
                    run_results.sort(key=lambda x: (x['metrics']['sharpe_ratio'], x['metrics']['total_return']), reverse=True)
                    
                    # Top 3 preview
                    for rank, rr in enumerate(run_results[:3], 1):
                        m = rr['metrics']
                        print(f"    #{rank}: {rr['combination']}")
                        print(f"        WR {m['win_rate']}% | Sharpe {m['sharpe_ratio']} | "
                              f"Ret {m['total_return']}% | PF {m['profit_factor']} | "
                              f"MDD {m['max_drawdown']}% | {m['total_trades']} trades")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                traceback.print_exc()
    
    # ============================================================
    # BUILD RANKINGS
    # ============================================================
    print(f"\n{'='*70}")
    print("BUILDING RANKINGS...")
    
    # Strip equity arrays for JSON (keep separately for plotting)
    for r in all_results:
        # Store serializable version
        r_json = {k: v for k, v in r.items() if k != 'equity'}
        results_json['results'].append(r_json)
    
    # Top 20 global by Sharpe
    all_results.sort(key=lambda x: (x['metrics']['sharpe_ratio'], x['metrics']['total_return']), reverse=True)
    for entry in all_results[:20]:
        results_json['top_20_global'].append({
            'ticker': entry['ticker'],
            'timeframe': entry['timeframe'],
            'combination': entry['combination'],
            'n_signals': entry['n_signals'],
            'win_rate': entry['metrics']['win_rate'],
            'sharpe_ratio': entry['metrics']['sharpe_ratio'],
            'total_return': entry['metrics']['total_return'],
            'profit_factor': entry['metrics']['profit_factor'],
            'max_drawdown': entry['metrics']['max_drawdown'],
            'total_trades': entry['metrics']['total_trades'],
            'net_profit': entry['metrics']['net_profit'],
        })
    
    # Best per ticker
    for ticker in TICKERS:
        ticker_results = [r for r in all_results if r['ticker'] == ticker]
        if ticker_results:
            best = ticker_results[0]  # Already sorted by Sharpe
            results_json['best_per_ticker'][ticker] = {
                'timeframe': best['timeframe'],
                'combination': best['combination'],
                'sharpe_ratio': best['metrics']['sharpe_ratio'],
                'total_return': best['metrics']['total_return'],
                'win_rate': best['metrics']['win_rate'],
                'profit_factor': best['metrics']['profit_factor'],
                'total_trades': best['metrics']['total_trades'],
            }
    
    # Best per timeframe
    for tf in TIMEFRAMES:
        tf_results = [r for r in all_results if r['timeframe'] == tf]
        if tf_results:
            best = tf_results[0]
            results_json['best_per_timeframe'][tf] = {
                'ticker': best['ticker'],
                'combination': best['combination'],
                'sharpe_ratio': best['metrics']['sharpe_ratio'],
                'total_return': best['metrics']['total_return'],
                'win_rate': best['metrics']['win_rate'],
                'profit_factor': best['metrics']['profit_factor'],
                'total_trades': best['metrics']['total_trades'],
            }
    
    # Signal statistics: how often each individual signal appears in top results
    signal_appearances = {name: {'top_20': 0, 'top_50': 0, 'avg_sharpe': [], 'avg_wr': []} 
                         for name in SIGNAL_NAMES}
    
    for rank, entry in enumerate(all_results[:50]):
        for idx in entry['combo_indices']:
            name = SIGNAL_NAMES[idx]
            if rank < 20:
                signal_appearances[name]['top_20'] += 1
            signal_appearances[name]['top_50'] += 1
            signal_appearances[name]['avg_sharpe'].append(entry['metrics']['sharpe_ratio'])
            signal_appearances[name]['avg_wr'].append(entry['metrics']['win_rate'])
    
    for name, stats in signal_appearances.items():
        results_json['signal_stats'][name] = {
            'top_20_appearances': stats['top_20'],
            'top_50_appearances': stats['top_50'],
            'avg_sharpe_in_top50': round(float(np.mean(stats['avg_sharpe'])), 2) if stats['avg_sharpe'] else 0,
            'avg_win_rate_in_top50': round(float(np.mean(stats['avg_wr'])), 1) if stats['avg_wr'] else 0,
        }
    
    # ============================================================
    # SUMMARY
    # ============================================================
    elapsed = time.time() - t_start
    
    if all_results:
        all_sharpes = [r['metrics']['sharpe_ratio'] for r in all_results]
        all_returns = [r['metrics']['total_return'] for r in all_results]
        all_wrs = [r['metrics']['win_rate'] for r in all_results]
        
        results_json['summary'] = {
            'total_valid_strategies': len(all_results),
            'total_bars_processed': sum(r['bars'] for r in all_results[:len(TICKERS)*len(TIMEFRAMES)]),
            'avg_sharpe': round(float(np.mean(all_sharpes)), 2),
            'max_sharpe': round(float(np.max(all_sharpes)), 2),
            'avg_return': round(float(np.mean(all_returns)), 2),
            'max_return': round(float(np.max(all_returns)), 2),
            'avg_win_rate': round(float(np.mean(all_wrs)), 1),
            'profitable_strategies_pct': round(sum(1 for r in all_returns if r > 0) / len(all_returns) * 100, 1),
            'runtime_seconds': round(elapsed, 1),
        }
    
    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(RESULTS_JSON), 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\n✅ Results saved: {RESULTS_JSON}")
    
    # Plot equity curves
    print("\n📊 Generating equity curves...")
    try:
        plot_equity_curves(all_results, EQUITY_PNG)
    except Exception as e:
        print(f"  ❌ Equity plot error: {e}")
        traceback.print_exc()
    
    # Copy script to expected location
    import shutil
    dest = Path('/home/openclaw/.openclaw/workspace/scripts/trend-suite-backtester.py')
    shutil.copy2(__file__, str(dest))
    print(f"✅ Script copied to: {dest}")
    
    # ============================================================
    # PRINT FINAL REPORT
    # ============================================================
    print(f"\n{'='*70}")
    print("FINAL REPORT — TREND SUITE V7")
    print(f"{'='*70}")
    print(f"  Runtime: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Valid Strategies: {len(all_results):,}")
    
    if results_json.get('summary'):
        s = results_json['summary']
        print(f"  Avg Sharpe:     {s['avg_sharpe']}")
        print(f"  Max Sharpe:     {s['max_sharpe']}")
        print(f"  Avg Return:     {s['avg_return']}%")
        print(f"  Max Return:     {s['max_return']}%")
        print(f"  Avg Win Rate:   {s['avg_win_rate']}%")
        print(f"  Profitable:     {s['profitable_strategies_pct']}%")
    
    if results_json['top_20_global']:
        print(f"\n  🏆 TOP 10 GLOBAL (by Sharpe):")
        for i, g in enumerate(results_json['top_20_global'][:10], 1):
            print(f"    #{i}: {g['ticker']} {g['timeframe']} — {g['combination']}")
            print(f"        Sharpe {g['sharpe_ratio']} | Ret {g['total_return']}% | "
                  f"WR {g['win_rate']}% | PF {g['profit_factor']} | "
                  f"MDD {g['max_drawdown']}% | {g['total_trades']} trades")
    
    if results_json['signal_stats']:
        print(f"\n  📊 SIGNAL POWER RANKING (Top 50 appearances):")
        sorted_signals = sorted(results_json['signal_stats'].items(),
                               key=lambda x: x[1]['top_50_appearances'], reverse=True)
        for name, stats in sorted_signals:
            print(f"    {name:15s}: Top20={stats['top_20_appearances']:2d} | "
                  f"Top50={stats['top_50_appearances']:2d} | "
                  f"Avg Sharpe={stats['avg_sharpe_in_top50']:.2f} | "
                  f"Avg WR={stats['avg_win_rate_in_top50']:.1f}%")
    
    if results_json['best_per_ticker']:
        print(f"\n  🎯 BEST PER TICKER:")
        for ticker, info in results_json['best_per_ticker'].items():
            print(f"    {ticker:10s}: {info['combination']} ({info['timeframe']})")
            print(f"               Sharpe {info['sharpe_ratio']} | Ret {info['total_return']}% | "
                  f"WR {info['win_rate']}% | {info['total_trades']} trades")
    
    if results_json['best_per_timeframe']:
        print(f"\n  ⏰ BEST PER TIMEFRAME:")
        for tf, info in results_json['best_per_timeframe'].items():
            print(f"    {tf:8s}: {info['combination']} ({info['ticker']})")
            print(f"             Sharpe {info['sharpe_ratio']} | Ret {info['total_return']}% | "
                  f"WR {info['win_rate']}%")
    
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return results_json


if __name__ == '__main__':
    results = main()
