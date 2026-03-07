#!/usr/bin/env python3
"""
Trend Suite (GRÄTZ) Backtester V5 — FIXED
==========================================
V5: BTC+SOL only, 15 signals, AND-logic combinations, all 5 TFs.
Based on V4's proven bar-by-bar backtest engine.

Fix summary (vs broken V5):
- AND logic instead of 60% voting threshold (all selected must agree)
- V4-style bar-by-bar backtest (no ffill_nonzero, no vectorized stop hack)
- Combo sizes 1-5 from 14 entry signals (~3500 combos per ticker/TF)
- VMA stop-loss integrated in backtest loop (like V4)
- Results correctly written to JSON (best_combination, metrics, rankings)

Signals (14 entry + 1 exit):
 0  Reversal          (bull/bear reversal bars incl. confirms)
 1  TrendLine        (ATR 10, Factor 3.0)
 2  Bollinger         (close vs BB bands)
 3  MicroDots         (VMA+SMA+ST confluence)
 4  VMA_Trend         (fast VMA trend direction)
 5  Exhaustion        (swing exhaustion lines)
 6  VMA_Color         (VMA color change signal A/B)
 7  RevConfirm1       (2-bar reversal confirmation)
 8  RevConfirm2       (3-bar reversal confirmation)
 9  Tops              (bearish: touch upper BB, close below)
10  Bottoms           (bullish: touch lower BB, close above)
11  VMA_Cross         (close crosses VMA)
12  VMA_ColorChange   (VMA slope direction change moment)
13  VMA_Cross_Micro   (VMA cross + micro dot confluence)
14  NoMicroDot        (exit-only signal: no micro dot active)
"""

import json
import sys
import warnings
import traceback
import time
from datetime import datetime
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
TICKERS = ['BTC-USD', 'SOL-USD']
TICKER_TO_CSV = {'BTC-USD': 'BTCUSD', 'SOL-USD': 'SOLUSD'}
TF_TO_CSV_SUFFIX = {'5min': '5min', '15min': '15min', '1h': '1H', '4h': '4H', 'Daily': '1D'}
TIMEFRAMES = ['5min', '15min', '1h', '4h', 'Daily']
CSV_DATA_DIR = Path('/home/openclaw/.openclaw/workspace/data/tradingview-max')

INITIAL_CAPITAL = 10000  # EUR
COMMISSION = 0.0

# 14 entry signals + 1 exit signal
SIGNAL_NAMES = [
    'Reversal', 'TrendLine', 'Bollinger', 'MicroDots',
    'VMA_Trend', 'Exhaustion', 'VMA_Color',
    'RevConfirm1', 'RevConfirm2', 'Tops', 'Bottoms',
    'VMA_Cross', 'VMA_ColorChange', 'VMA_Cross_Micro',
    'NoMicroDot',
]
NUM_ENTRY_SIGNALS = 14  # indices 0-13 are entry signals
NO_MICRO_IDX = 14       # index 14 is exit-only

# Combo sizes to test (1 to MAX_COMBO_SIZE)
MAX_COMBO_SIZE = 5

# How many top combos get detailed metrics / stored in JSON
TOP_DETAILED = 50
TOP_STORE = 200

OUTPUT_DIR = Path('/home/openclaw/.openclaw/workspace/mission-control')
RESULTS_JSON = OUTPUT_DIR / 'backtest-results-v5.json'
EQUITY_PNG = OUTPUT_DIR / 'backtest-equity-v5.png'


# ============================================================
# DATA LOADING (same as V4)
# ============================================================
def fetch_data(ticker, tf_key):
    csv_prefix = TICKER_TO_CSV.get(ticker, ticker)
    csv_suffix = TF_TO_CSV_SUFFIX.get(tf_key, tf_key)
    csv_file = CSV_DATA_DIR / f"{csv_prefix}_{csv_suffix}.csv"
    if not csv_file.exists():
        print(f"  [WARN] CSV not found: {csv_file}")
        return None
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return None
        df.columns = [c.lower().strip() for c in df.columns]
        if 'time' in df.columns:
            df.rename(columns={'time': 'date'}, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        return df
    except Exception as e:
        print(f"  [WARN] fetch_data({ticker}, {tf_key}): {e}")
        return None


# ============================================================
# INDICATORS (identical to V4)
# ============================================================
def calc_bollinger(df, length=19, mult=2.0):
    df['bb_basis'] = df['close'].rolling(length).mean()
    df['bb_std'] = df['close'].rolling(length).std()
    df['bb_upper'] = df['bb_basis'] + mult * df['bb_std']
    df['bb_lower'] = df['bb_basis'] - mult * df['bb_std']
    df['bb_signal'] = 0
    df.loc[df['close'] > df['bb_upper'], 'bb_signal'] = -1
    df.loc[df['close'] < df['bb_lower'], 'bb_signal'] = 1
    return df


def calc_reversals(df):
    c, o, h, lo = df['close'], df['open'], df['high'], df['low']
    upper, lower = df['bb_upper'], df['bb_lower']
    df['bull_reversal'] = (
        (lo.shift(1) < lower.shift(1)) & (c.shift(1) < o.shift(1)) &
        (c > lower) & (c > o)
    )
    df['bear_reversal'] = (
        (h.shift(1) > upper.shift(1)) & (c.shift(1) > o.shift(1)) &
        (c < upper) & (c < o)
    )
    df['bull_confirm1'] = (
        (lo.shift(2) < lower.shift(2)) & (c.shift(2) < o.shift(2)) &
        (c.shift(1) > lower.shift(1)) & (c.shift(1) > o.shift(1)) & (c > h.shift(1))
    )
    df['bear_confirm1'] = (
        (h.shift(2) > upper.shift(2)) & (c.shift(2) > o.shift(2)) &
        (c.shift(1) < upper.shift(1)) & (c.shift(1) < o.shift(1)) & (c < lo.shift(1))
    )
    df['bull_confirm2'] = (
        (lo.shift(3) < lower.shift(3)) & (c.shift(3) < o.shift(3)) &
        (c.shift(2) > lower.shift(2)) & (c.shift(2) > o.shift(2)) & (c > h.shift(2))
    )
    df['bear_confirm2'] = (
        (h.shift(3) > upper.shift(3)) & (c.shift(3) > o.shift(3)) &
        (c.shift(2) < upper.shift(2)) & (c.shift(2) < o.shift(2)) & (c < lo.shift(2))
    )
    df['reversal_signal'] = 0
    df.loc[df['bull_reversal'] | df['bull_confirm1'] | df['bull_confirm2'], 'reversal_signal'] = 1
    df.loc[df['bear_reversal'] | df['bear_confirm1'] | df['bear_confirm2'], 'reversal_signal'] = -1
    return df


def calc_supertrend(df, atr_period=10, factor=3.0):
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
    st_up = np.zeros(n); st_dn = np.zeros(n); st_dir = np.ones(n)
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
    return df


def calc_vma(src, vma_length):
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
        if s == 0: pdi = 0; mdi = 0
        else: pdi = pdmS[i] / s; mdi = mdmS[i] / s
        pdiS[i] = (1 - k) * pdiS[i-1] + k * pdi
        mdiS[i] = (1 - k) * mdiS[i-1] + k * mdi
        d = abs(pdiS[i] - mdiS[i])
        s1 = pdiS[i] + mdiS[i]
        if s1 == 0: iS[i] = iS[i-1]
        else: iS[i] = (1 - k) * iS[i-1] + k * d / s1
    hhv = pd.Series(iS).rolling(vma_length, min_periods=1).max().values
    llv = pd.Series(iS).rolling(vma_length, min_periods=1).min().values
    d1 = hhv - llv
    vI = np.where(d1 != 0, (iS - llv) / d1, 0)
    for i in range(1, n):
        vma[i] = (1 - k * vI[i]) * vma[i-1] + k * vI[i] * src[i]
    return vma


def calc_vma_trend(df, vma_length=9):
    src = df['close'].values.astype(float)
    vma_fast = calc_vma(src, 9)
    vma_med = calc_vma(src, 18)
    vma_slow = calc_vma(src, 27)
    df['vma_fast'] = vma_fast
    df['vma_med'] = vma_med
    df['vma_slow'] = vma_slow
    df['vma'] = vma_fast
    n = len(df)
    color = np.zeros(n, dtype=int)
    for i in range(1, n):
        if vma_fast[i] > vma_fast[i-1] and vma_fast[i] > vma_med[i]:
            color[i] = 1
        elif vma_fast[i] < vma_fast[i-1] and vma_fast[i] < vma_med[i]:
            color[i] = -1
    df['vma_color'] = color
    df['vma_trend'] = np.where(color == 1, 1, np.where(color == -1, -1, 0))

    vma_signal = np.zeros(n, dtype=int)
    setup_type = [''] * n
    for i in range(2, n):
        prev = color[i-1]; curr = color[i]; prev2 = color[i-2]
        if prev == -1 and curr == 1:
            vma_signal[i] = 1; setup_type[i] = 'A'
        elif prev == 0 and curr == 1 and prev2 == -1:
            vma_signal[i] = 1; setup_type[i] = 'B'
        elif prev == 0 and curr == 1:
            for j in range(max(0, i-5), i):
                if color[j] == -1:
                    vma_signal[i] = 1; setup_type[i] = 'B'; break
        if prev == 1 and curr == -1:
            vma_signal[i] = -1; setup_type[i] = 'A'
        elif prev == 0 and curr == -1 and prev2 == 1:
            vma_signal[i] = -1; setup_type[i] = 'B'
        elif prev == 0 and curr == -1:
            for j in range(max(0, i-5), i):
                if color[j] == 1:
                    vma_signal[i] = -1; setup_type[i] = 'B'; break
    df['vma_color_signal'] = vma_signal
    df['setup_type'] = setup_type
    return df


def calc_micro_dots(df):
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
    md_trend = np.ones(len(df))
    for i in range(1, len(df)):
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
    md_vma = calc_vma(src, 4)
    md_sma = pd.Series(src).rolling(18).mean().values
    trend_up = md_trend == 1
    vma_up = md_vma < src; vma_down = md_vma > src
    ma_up = src > md_sma; ma_down = src < md_sma
    df['micro_up'] = vma_up & ma_up & trend_up & ~vma_down
    df['micro_down'] = vma_down & ma_down & ~trend_up & ~vma_up
    df['micro_signal'] = 0
    df.loc[df['micro_up'], 'micro_signal'] = 1
    df.loc[df['micro_down'], 'micro_signal'] = -1
    return df


def calc_exhaustion(df, swing_length=40, bar_count=10):
    c = df['close'].values; o = df['open'].values
    h = df['high'].values; lo = df['low'].values
    n = len(df); exhaust = np.zeros(n)
    bindex = 0; sindex = 0
    for i in range(4, n):
        if c[i] > c[i-4]: bindex += 1
        if c[i] < c[i-4]: sindex += 1
        highest_high = np.max(h[max(0, i-swing_length+1):i+1])
        lowest_low = np.min(lo[max(0, i-swing_length+1):i+1])
        if bindex > bar_count and c[i] < o[i] and h[i] >= highest_high:
            bindex = 0; exhaust[i] = -1
        elif sindex > bar_count and c[i] > o[i] and lo[i] <= lowest_low:
            sindex = 0; exhaust[i] = 1
    df['exhaustion'] = exhaust
    return df


# ============================================================
# EXTRACT 15 SIGNAL ARRAYS
# ============================================================
def extract_signals(df):
    """
    Returns (15, N) int8 array.
    Signals 0-13: entry signals (+1 bull, -1 bear, 0 neutral)
    Signal 14 (NoMicroDot): 1 = no micro dot (exit condition), 0 = micro dot active
    """
    n = len(df)
    signals = np.zeros((15, n), dtype=np.int8)

    # 0: Reversal (combined: basic + confirm1 + confirm2)
    signals[0] = df['reversal_signal'].values.astype(np.int8)

    # 1: TrendLine (persistent: always +1 or -1)
    signals[1] = df['st_direction'].values.astype(np.int8)

    # 2: Bollinger (close vs bands)
    signals[2] = df['bb_signal'].values.astype(np.int8)

    # 3: MicroDots (persistent-ish: +1, -1, or 0)
    signals[3] = df['micro_signal'].values.astype(np.int8)

    # 4: VMA_Trend (persistent: +1, -1, or 0)
    signals[4] = df['vma_trend'].values.astype(np.int8)

    # 5: Exhaustion (sparse: fires rarely)
    signals[5] = df['exhaustion'].values.astype(np.int8)

    # 6: VMA_Color (color change signal A/B, sparse)
    signals[6] = df['vma_color_signal'].values.astype(np.int8)

    # 7: RevConfirm1 (2-bar confirmation only, sparse)
    rc1 = np.zeros(n, dtype=np.int8)
    rc1[df['bull_confirm1'].values.astype(bool)] = 1
    rc1[df['bear_confirm1'].values.astype(bool)] = -1
    signals[7] = rc1

    # 8: RevConfirm2 (3-bar confirmation only, sparse)
    rc2 = np.zeros(n, dtype=np.int8)
    rc2[df['bull_confirm2'].values.astype(bool)] = 1
    rc2[df['bear_confirm2'].values.astype(bool)] = -1
    signals[8] = rc2

    # 9: Tops (bearish only: high >= upper BB AND close < upper)
    h = df['high'].values; upper = df['bb_upper'].values; c = df['close'].values
    tops = np.zeros(n, dtype=np.int8)
    mask_top = np.isfinite(upper) & (h >= upper) & (c < upper)
    tops[mask_top] = -1
    signals[9] = tops

    # 10: Bottoms (bullish only: low <= lower BB AND close > lower)
    lo = df['low'].values; lower = df['bb_lower'].values
    bottoms = np.zeros(n, dtype=np.int8)
    mask_bot = np.isfinite(lower) & (lo <= lower) & (c > lower)
    bottoms[mask_bot] = 1
    signals[10] = bottoms

    # 11: VMA Cross (crossover/crossunder of close and VMA)
    vma = df['vma'].values
    prev_c = np.roll(c, 1); prev_vma = np.roll(vma, 1)
    cross_up = (c > vma) & (prev_c <= prev_vma)
    cross_dn = (c < vma) & (prev_c >= prev_vma)
    cross_up[0] = False; cross_dn[0] = False
    vma_cross = np.zeros(n, dtype=np.int8)
    vma_cross[cross_up] = 1
    vma_cross[cross_dn] = -1
    signals[11] = vma_cross

    # 12: VMA_ColorChange (slope direction change moment)
    rising = np.zeros(n, dtype=bool); falling = np.zeros(n, dtype=bool)
    rising[1:] = vma[1:] > vma[:-1]
    falling[1:] = vma[1:] < vma[:-1]
    prev_rising = np.roll(rising, 1); prev_rising[0] = False
    prev_falling = np.roll(falling, 1); prev_falling[0] = False
    color_change = np.zeros(n, dtype=np.int8)
    color_change[rising & ~prev_rising] = 1
    color_change[falling & ~prev_falling] = -1
    signals[12] = color_change

    # 13: VMA_Cross + Micro confluence
    micro_up = df['micro_up'].values.astype(bool)
    micro_dn = df['micro_down'].values.astype(bool)
    cross_micro = np.zeros(n, dtype=np.int8)
    cross_micro[cross_up & micro_up] = 1
    cross_micro[cross_dn & micro_dn] = -1
    signals[13] = cross_micro

    # 14: NoMicroDot (exit signal: 1 = no micro dot, 0 = micro dot present)
    no_micro = ~micro_up & ~micro_dn
    exit_sig = np.zeros(n, dtype=np.int8)
    exit_sig[no_micro] = 1
    signals[14] = exit_sig

    return signals


# ============================================================
# COMBINATION BACKTEST — V4-STYLE WITH AND LOGIC
# ============================================================
def backtest_combination(combo_indices, signals_matrix, close_vals, vma_vals,
                         vma_color_vals, initial_capital=INITIAL_CAPITAL,
                         use_no_micro_exit=False, no_micro_signal=None):
    """
    Backtest a combination of entry signals using AND logic.
    AND = all selected signals must be +1 for bull, all -1 for bear.
    0 (neutral) in any signal means no consensus → hold current position.
    Uses V4's proven bar-by-bar engine with VMA stop-loss.

    Returns: (equity_array, trades_list, quick_metrics_dict) or None if <3 trades.
    """
    n = len(close_vals)

    # --- Compute AND-combined signal ---
    selected = signals_matrix[combo_indices]  # (k, N)
    if len(combo_indices) == 1:
        combined = selected[0].copy()
    else:
        all_bull = np.all(selected == 1, axis=0)
        all_bear = np.all(selected == -1, axis=0)
        combined = np.zeros(n, dtype=np.int8)
        combined[all_bull] = 1
        combined[all_bear] = -1
    combined[0] = 0

    # Quick check: enough signal bars to potentially produce trades?
    n_bull = int(np.sum(combined == 1))
    n_bear = int(np.sum(combined == -1))
    if n_bull + n_bear < 2:
        return None

    # --- Bar-by-bar backtest (V4 engine) ---
    equity = np.full(n, initial_capital, dtype=np.float64)
    position = 0
    entry_price = 0.0
    position_size = 0.0
    entry_idx = 0
    trades = []

    for i in range(1, n):
        equity[i] = equity[i - 1]

        # Mark-to-market
        if position != 0:
            pnl = position * (close_vals[i] - close_vals[i - 1]) * position_size
            equity[i] += pnl

        # --- VMA Stop-Loss (same as V4) ---
        if position == 1 and close_vals[i] < vma_vals[i] and vma_color_vals[i] == -1:
            exit_price = close_vals[i]
            ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0
            pnl_abs = (exit_price - entry_price) * position_size
            trades.append({
                'direction': 'LONG', 'entry': float(entry_price),
                'exit': float(exit_price), 'return': ret, 'pnl': pnl_abs,
                'entry_bar': entry_idx, 'exit_bar': i,
                'bars_held': i - entry_idx, 'reason': 'VMA Stop',
            })
            position = 0

        elif position == -1 and close_vals[i] > vma_vals[i] and vma_color_vals[i] == 1:
            exit_price = close_vals[i]
            ret = (entry_price - exit_price) / entry_price if entry_price != 0 else 0
            pnl_abs = (entry_price - exit_price) * position_size
            trades.append({
                'direction': 'SHORT', 'entry': float(entry_price),
                'exit': float(exit_price), 'return': ret, 'pnl': pnl_abs,
                'entry_bar': entry_idx, 'exit_bar': i,
                'bars_held': i - entry_idx, 'reason': 'VMA Stop',
            })
            position = 0

        # --- NoMicroDot Exit (optional) ---
        if use_no_micro_exit and position != 0 and no_micro_signal is not None:
            if no_micro_signal[i] == 1:  # no micro dot → force exit
                exit_price = close_vals[i]
                if position == 1:
                    ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (exit_price - entry_price) * position_size
                else:
                    ret = (entry_price - exit_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (entry_price - exit_price) * position_size
                trades.append({
                    'direction': 'LONG' if position == 1 else 'SHORT',
                    'entry': float(entry_price), 'exit': float(exit_price),
                    'return': ret, 'pnl': pnl_abs,
                    'entry_bar': entry_idx, 'exit_bar': i,
                    'bars_held': i - entry_idx, 'reason': 'NoMicroDot Exit',
                })
                position = 0
                continue

        # --- New entry / flip signal ---
        sig = combined[i]
        if sig != 0 and sig != position:
            # Close existing position
            if position != 0:
                exit_price = close_vals[i]
                if position == 1:
                    ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (exit_price - entry_price) * position_size
                else:
                    ret = (entry_price - exit_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (entry_price - exit_price) * position_size
                trades.append({
                    'direction': 'LONG' if position == 1 else 'SHORT',
                    'entry': float(entry_price), 'exit': float(exit_price),
                    'return': ret, 'pnl': pnl_abs,
                    'entry_bar': entry_idx, 'exit_bar': i,
                    'bars_held': i - entry_idx, 'reason': 'Signal Flip',
                })

            # Open new position
            position = int(sig)
            entry_price = close_vals[i]
            entry_idx = i
            position_size = equity[i] / close_vals[i]

    # Minimum 3 trades
    if len(trades) < 3:
        return None

    # --- Quick metrics ---
    trade_returns = [t['return'] for t in trades]
    trade_pnls = [t['pnl'] for t in trades]
    winners = [r for r in trade_returns if r > 0]
    losers = [r for r in trade_returns if r <= 0]
    wr = len(winners) / len(trade_returns) * 100
    gp = sum(winners) if winners else 0
    gl = abs(sum(losers)) if losers else 0.0001
    pf = min(gp / gl if gl > 0 else 99.99, 99.99)
    total_ret = (equity[-1] / equity[0] - 1) * 100

    if len(trade_returns) > 1 and np.std(trade_returns) > 0:
        sharpe = np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(min(252, len(trade_returns)))
    else:
        sharpe = 0.0

    quick = {
        'total_trades': len(trades),
        'win_rate': round(wr, 1),
        'profit_factor': round(pf, 2),
        'sharpe_ratio': round(sharpe, 2),
        'total_return': round(total_ret, 2),
        'net_profit': round(float(equity[-1] - initial_capital), 2),
    }

    return equity, trades, quick


# ============================================================
# FULL METRICS (V4-compatible, 39 fields)
# ============================================================
def calc_full_metrics(trades, equity_series, initial_capital=INITIAL_CAPITAL):
    eq = np.array(equity_series)
    n_bars = len(eq)
    if not trades:
        return _empty_metrics()

    pnls = [t['pnl'] for t in trades]
    returns = [t['return'] for t in trades]
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]
    win_pnls = [t['pnl'] for t in winners]
    loss_pnls = [t['pnl'] for t in losers]
    win_returns = [t['return'] for t in winners]
    loss_returns = [t['return'] for t in losers]

    final_eq = eq[-1]
    net_profit = final_eq - initial_capital
    net_profit_pct = (net_profit / initial_capital) * 100
    gross_profit = sum(win_pnls) if win_pnls else 0
    gross_loss = sum(loss_pnls) if loss_pnls else 0
    gross_loss_abs = abs(gross_loss)
    profit_factor = min((gross_profit / gross_loss_abs) if gross_loss_abs > 0 else 99.99, 99.99)

    total_trades = len(trades)
    winning_count = len(winners)
    losing_count = len(losers)
    pct_profitable = (winning_count / total_trades * 100) if total_trades > 0 else 0

    avg_trade_pnl = float(np.mean(pnls)) if pnls else 0
    avg_trade_pnl_pct = float(np.mean(returns)) * 100 if returns else 0
    avg_win = float(np.mean(win_pnls)) if win_pnls else 0
    avg_win_pct = float(np.mean(win_returns)) * 100 if win_returns else 0
    avg_loss = float(np.mean(loss_pnls)) if loss_pnls else 0
    avg_loss_pct = float(np.mean(loss_returns)) * 100 if loss_returns else 0
    ratio_avg_win_loss = min((abs(avg_win) / abs(avg_loss)) if avg_loss != 0 else 99.99, 99.99)

    largest_win = max(win_pnls) if win_pnls else 0
    largest_win_pct = max(win_returns) * 100 if win_returns else 0
    largest_loss = min(loss_pnls) if loss_pnls else 0
    largest_loss_pct = min(loss_returns) * 100 if loss_returns else 0
    pct_gross_profit_largest = (largest_win / gross_profit * 100) if gross_profit > 0 else 0
    pct_gross_loss_largest = (abs(largest_loss) / gross_loss_abs * 100) if gross_loss_abs > 0 else 0

    avg_bars_win = float(np.mean([t['bars_held'] for t in winners])) if winners else 0
    avg_bars_loss = float(np.mean([t['bars_held'] for t in losers])) if losers else 0

    # Drawdown
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    dd_pct = np.where(peak > 0, dd / peak * 100, 0)
    max_dd = abs(float(np.min(dd))) if len(dd) > 0 else 0
    max_dd_pct = abs(float(np.min(dd_pct))) if len(dd_pct) > 0 else 0
    in_dd = dd < 0
    avg_dd = abs(float(np.mean(dd[in_dd]))) if np.any(in_dd) else 0
    max_dd_duration = 0; cur = 0
    for i in range(len(dd)):
        if dd[i] < 0:
            cur += 1; max_dd_duration = max(max_dd_duration, cur)
        else:
            cur = 0

    # Sharpe
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(min(252, len(returns))))
    else:
        sharpe = 0.0

    # Sampled histories
    sample_step = max(1, n_bars // 500)
    runup_history = [round(float(eq[i] - initial_capital), 2) for i in range(0, n_bars, sample_step)]
    dd_history = [round(float(dd[i]), 2) for i in range(0, n_bars, sample_step)]

    return {
        'net_profit': round(net_profit, 2),
        'net_profit_pct': round(net_profit_pct, 2),
        'total_profit': round(net_profit, 2),
        'total_loss': round(gross_loss, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'commission_paid': 0,
        'total_trades': total_trades,
        'total_open_trades': 0,
        'winning_trades': winning_count,
        'losing_trades': losing_count,
        'percent_profitable': round(pct_profitable, 1),
        'avg_trade_pnl': round(avg_trade_pnl, 2),
        'avg_trade_pnl_pct': round(avg_trade_pnl_pct, 2),
        'avg_winning_trade': round(avg_win, 2),
        'avg_winning_trade_pct': round(avg_win_pct, 2),
        'avg_losing_trade': round(avg_loss, 2),
        'avg_losing_trade_pct': round(avg_loss_pct, 2),
        'ratio_avg_win_loss': round(ratio_avg_win_loss, 2),
        'largest_winning_trade': round(largest_win, 2),
        'largest_winning_trade_pct': round(largest_win_pct, 2),
        'largest_losing_trade': round(largest_loss, 2),
        'largest_losing_trade_pct': round(largest_loss_pct, 2),
        'pct_gross_profit_largest_win': round(pct_gross_profit_largest, 1),
        'pct_gross_loss_largest_loss': round(pct_gross_loss_largest, 1),
        'avg_bars_winning': round(avg_bars_win, 1),
        'avg_bars_losing': round(avg_bars_loss, 1),
        'max_drawdown': round(max_dd, 2),
        'max_drawdown_pct': round(max_dd_pct, 2),
        'avg_drawdown': round(avg_dd, 2),
        'max_drawdown_duration_bars': max_dd_duration,
        'sharpe_ratio': round(sharpe, 2),
        'total_return': round(net_profit_pct, 2),
        'win_rate': round(pct_profitable, 1),
        'runup_history': runup_history,
        'drawdown_history': dd_history,
    }


def _empty_metrics():
    return {k: 0 for k in [
        'net_profit', 'net_profit_pct', 'total_profit', 'total_loss',
        'gross_profit', 'gross_loss', 'profit_factor', 'commission_paid',
        'total_trades', 'total_open_trades', 'winning_trades', 'losing_trades',
        'percent_profitable', 'avg_trade_pnl', 'avg_trade_pnl_pct',
        'avg_winning_trade', 'avg_winning_trade_pct', 'avg_losing_trade',
        'avg_losing_trade_pct', 'ratio_avg_win_loss',
        'largest_winning_trade', 'largest_winning_trade_pct',
        'largest_losing_trade', 'largest_losing_trade_pct',
        'pct_gross_profit_largest_win', 'pct_gross_loss_largest_loss',
        'avg_bars_winning', 'avg_bars_losing',
        'max_drawdown', 'max_drawdown_pct', 'avg_drawdown',
        'max_drawdown_duration_bars', 'sharpe_ratio', 'total_return', 'win_rate',
    ]}


# ============================================================
# DATE RANGE
# ============================================================
def get_date_range(df):
    if 'date' not in df.columns or df.empty:
        return {'start': '?', 'end': '?', 'days': 0, 'months': 0, 'bars': len(df)}
    start_dt = pd.Timestamp(df['date'].iloc[0])
    end_dt = pd.Timestamp(df['date'].iloc[-1])
    delta = end_dt - start_dt
    days = delta.days; months = round(days / 30.44, 1)
    return {
        'start': start_dt.strftime('%d.%m.%Y'), 'end': end_dt.strftime('%d.%m.%Y'),
        'start_iso': start_dt.isoformat(), 'end_iso': end_dt.isoformat(),
        'days': days, 'months': months, 'bars': len(df),
        'label': f"{start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')} ({months} Mon, {len(df)} Bars)",
    }


# ============================================================
# ENTRY/EXIT RULE TEXT
# ============================================================
SIGNAL_ENTRY_LONG = {
    'Reversal': 'Bullish Reversal Bar (BB Breakout Return)',
    'TrendLine': 'TrendLine bullish (grün)',
    'Bollinger': 'Preis unter BB Lower (überverkauft)',
    'MicroDots': 'Micro Dots grün (VMA+SMA+ST Confluence)',
    'VMA_Trend': 'VMA Trend steigend',
    'Exhaustion': 'Bullish Exhaustion (Support-Level)',
    'VMA_Color': 'VMA Farbwechsel Rot→Grün',
    'RevConfirm1': '2-Bar Reversal Bestätigung (bullish)',
    'RevConfirm2': '3-Bar Reversal Bestätigung (bullish)',
    'Tops': 'BB-Top Touch (bearisch)',
    'Bottoms': 'BB-Bottom Touch (bullisch)',
    'VMA_Cross': 'Close kreuzt VMA nach oben',
    'VMA_ColorChange': 'VMA Richtungswechsel (steigend)',
    'VMA_Cross_Micro': 'VMA Cross + Micro Dot Confluence',
}

SIGNAL_EXIT = {
    'Reversal': 'Gegenläufiger Reversal Bar',
    'TrendLine': 'TrendLine Farbwechsel',
    'Bollinger': 'BB Gegenband erreicht',
    'MicroDots': 'Micro Dots Farbwechsel',
    'VMA_Trend': 'VMA Trend dreht',
    'Exhaustion': 'Gegenläufige Exhaustion',
    'VMA_Color': 'VMA Farbwechsel (primär)',
    'RevConfirm1': 'Gegenläufige 2-Bar Bestätigung',
    'RevConfirm2': 'Gegenläufige 3-Bar Bestätigung',
    'Tops': 'BB-Top beendet',
    'Bottoms': 'BB-Bottom beendet',
    'VMA_Cross': 'Close kreuzt VMA zurück',
    'VMA_ColorChange': 'VMA Richtungswechsel (fallend)',
    'VMA_Cross_Micro': 'Confluence-Bedingung endet',
}


def generate_rule_text(signal_names):
    entry_parts = [SIGNAL_ENTRY_LONG.get(s, s) for s in signal_names]
    exit_parts = [SIGNAL_EXIT.get(s, s) for s in signal_names]
    return {
        'entry_rule': 'LONG wenn ALLE: ' + ' UND '.join(entry_parts),
        'exit_rule': 'EXIT bei VMA Stop-Loss ODER Signal-Flip (' + ' / '.join(exit_parts) + ')',
        'entry_short': ' + '.join(signal_names),
    }


# ============================================================
# EQUITY CHART
# ============================================================
def plot_equity_curves(all_equity_data):
    fig, axes = plt.subplots(2, 1, figsize=(18, 13), facecolor='#0a0a0f')

    ax1 = axes[0]; ax1.set_facecolor('#14141e')
    plotted = False
    for key, data in all_equity_data.items():
        ticker, tf = key
        if tf != 'Daily' or data.get('equity') is None:
            continue
        eq = data['equity']
        label = f"{ticker} — {data.get('combo_name', 'default')}"
        ax1.plot(range(len(eq)), eq, label=label, linewidth=1.5, alpha=0.9)
        plotted = True
    if plotted:
        ax1.set_title('Trend Suite V5 — Best Combo Equity (Daily) — BTC + SOL',
                       color='white', fontsize=14, pad=10)
        ax1.set_ylabel('Portfolio Value (€)', color='#888')
        ax1.legend(loc='upper left', fontsize=9, facecolor='#1e1e2e',
                   edgecolor='#333', labelcolor='white')
        ax1.grid(True, alpha=0.1, color='#333'); ax1.tick_params(colors='#888')
        for spine in ax1.spines.values(): spine.set_color('#333')
        ax1.axhline(y=INITIAL_CAPITAL, color='#444', linestyle='--', linewidth=0.8)

    ax2 = axes[1]; ax2.set_facecolor('#14141e')
    colors_tf = {'5min': '#ff6b6b', '15min': '#ffa500', '1h': '#ffd93d', '4h': '#6bcb77', 'Daily': '#4d96ff'}
    for key, data in all_equity_data.items():
        ticker, tf = key
        if ticker != 'BTC-USD' or data.get('equity') is None:
            continue
        eq = data['equity']
        ax2.plot(range(len(eq)), eq, label=f"BTC {tf}",
                 color=colors_tf.get(tf, '#888'), linewidth=1.2, alpha=0.85)
    ax2.set_title('BTC-USD — Best Combo Equity by Timeframe',
                   color='white', fontsize=14, pad=10)
    ax2.set_ylabel('Portfolio Value (€)', color='#888')
    ax2.set_xlabel('Bars', color='#888')
    ax2.legend(loc='upper left', fontsize=9, facecolor='#1e1e2e',
               edgecolor='#333', labelcolor='white')
    ax2.grid(True, alpha=0.1, color='#333'); ax2.tick_params(colors='#888')
    for spine in ax2.spines.values(): spine.set_color('#333')
    ax2.axhline(y=INITIAL_CAPITAL, color='#444', linestyle='--', linewidth=0.8)

    plt.tight_layout()
    plt.savefig(str(EQUITY_PNG), dpi=150, facecolor='#0a0a0f', bbox_inches='tight')
    plt.close()
    print(f"  ✅ Equity chart saved: {EQUITY_PNG}")


# ============================================================
# MAIN
# ============================================================
def main():
    t_start = time.time()
    print("=" * 70)
    print("TREND SUITE (GRÄTZ) BACKTESTER V5 — FIXED")
    print("BTC+SOL | 15 Signals | AND-Logic Combos | All 5 TFs")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Entry Signals ({NUM_ENTRY_SIGNALS}): {', '.join(SIGNAL_NAMES[:NUM_ENTRY_SIGNALS])}")
    print(f"Exit Signal: {SIGNAL_NAMES[NO_MICRO_IDX]}")
    print(f"Combo sizes: 1 to {MAX_COMBO_SIZE}")

    # Count total combos
    total_combos = sum(
        len(list(combinations(range(NUM_ENTRY_SIGNALS), size)))
        for size in range(1, MAX_COMBO_SIZE + 1)
    )
    print(f"Combinations per ticker/TF: {total_combos:,}")
    print(f"Capital: {INITIAL_CAPITAL:,}€ | Commission: {COMMISSION}")
    print()

    results_json = {
        'meta': {
            'generated': datetime.now().isoformat(),
            'version': 'V5',
            'data_source': 'TradingView CSV (tradingview-max)',
            'initial_capital': INITIAL_CAPITAL,
            'commission': COMMISSION,
            'currency': 'EUR',
            'tickers': TICKERS,
            'ticker_count': len(TICKERS),
            'timeframes': TIMEFRAMES,
            'signals': SIGNAL_NAMES,
            'signal_count': len(SIGNAL_NAMES),
            'entry_signals': SIGNAL_NAMES[:NUM_ENTRY_SIGNALS],
            'exit_signal': SIGNAL_NAMES[NO_MICRO_IDX],
            'combination_logic': 'AND (all selected signals must agree)',
            'max_combo_size': MAX_COMBO_SIZE,
            'total_combos_per_run': total_combos,
            'vma_length': 9,
            'stop_loss': 'VMA Trend Line Cross (same as V4)',
            'features': [
                '15 signals (14 entry + 1 exit)',
                f'{total_combos} AND-logic combinations per ticker/TF (sizes 1-{MAX_COMBO_SIZE})',
                'V4-proven bar-by-bar backtest engine',
                'VMA Stop Loss',
                'Full metrics for top combos',
                'NoMicroDot exit variant tested for each combo',
            ],
        },
        'results': [],
        'combination_rankings': {},
        'best_per_ticker': [],
        'global_best': [],
        'summary': {},
    }

    all_equity_data = {}
    total_runs = len(TICKERS) * len(TIMEFRAMES)
    run_idx = 0
    total_bars = 0
    global_best_combos = []

    for ticker in TICKERS:
        for tf_key in TIMEFRAMES:
            run_idx += 1
            label = f"{ticker} / {tf_key}"
            print(f"\n[{run_idx}/{total_runs}] {'='*50}")
            print(f"📊 {label}")

            try:
                df = fetch_data(ticker, tf_key)
                if df is None or len(df) < 50:
                    bars = 0 if df is None else len(df)
                    print(f"  ⚠️ Insufficient data ({bars} bars)")
                    results_json['results'].append({
                        'ticker': ticker, 'timeframe': tf_key,
                        'bars': bars, 'valid_combos': 0,
                        'best_combination': None, 'metrics': _empty_metrics(),
                        'top_combinations': [], 'combination_ranking': [],
                    })
                    continue

                date_info = get_date_range(df)
                total_bars += date_info['bars']
                print(f"  📅 {date_info['label']}")

                # Calculate all indicators
                print(f"  🔧 Computing indicators...")
                df = calc_bollinger(df)
                df = calc_reversals(df)
                df = calc_supertrend(df)
                df = calc_vma_trend(df, vma_length=9)
                df = calc_micro_dots(df)
                df = calc_exhaustion(df)

                # Extract signal arrays
                signals_matrix = extract_signals(df)
                n = len(df)

                # Signal activity stats
                for si in range(len(SIGNAL_NAMES)):
                    bull_c = int(np.sum(signals_matrix[si] == 1))
                    bear_c = int(np.sum(signals_matrix[si] == -1))
                    if bull_c + bear_c > 0:
                        print(f"    {SIGNAL_NAMES[si]:20s}: bull={bull_c:5d}  bear={bear_c:5d}")

                # Precompute arrays for backtest
                close_vals = df['close'].values.astype(np.float64)
                vma_vals = df['vma'].values.astype(np.float64)
                vma_color_vals = df['vma_color'].values.astype(np.float64)
                no_micro_signal = signals_matrix[NO_MICRO_IDX]

                # --- Test all AND combinations ---
                print(f"  🔬 Testing {total_combos:,} AND-logic combinations...")
                combo_results = []
                tested = 0
                t_combo_start = time.time()

                for size in range(1, MAX_COMBO_SIZE + 1):
                    for combo in combinations(range(NUM_ENTRY_SIGNALS), size):
                        tested += 1

                        # Test WITHOUT NoMicroDot exit
                        result = backtest_combination(
                            list(combo), signals_matrix, close_vals,
                            vma_vals, vma_color_vals, INITIAL_CAPITAL,
                            use_no_micro_exit=False,
                        )
                        if result is not None:
                            equity, trades, quick = result
                            combo_name = ' + '.join(SIGNAL_NAMES[j] for j in combo)
                            rules = generate_rule_text([SIGNAL_NAMES[j] for j in combo])
                            combo_results.append({
                                'combination': combo_name,
                                'signals': [SIGNAL_NAMES[j] for j in combo],
                                'signal_indices': list(combo),
                                'num_signals': len(combo),
                                'no_micro_exit': False,
                                'entry_rule': rules['entry_rule'],
                                'exit_rule': rules['exit_rule'],
                                'entry_short': rules['entry_short'],
                                '_equity': equity,
                                '_trades': trades,
                                **quick,
                            })

                        # Test WITH NoMicroDot exit
                        result_nme = backtest_combination(
                            list(combo), signals_matrix, close_vals,
                            vma_vals, vma_color_vals, INITIAL_CAPITAL,
                            use_no_micro_exit=True,
                            no_micro_signal=no_micro_signal,
                        )
                        if result_nme is not None:
                            equity_nme, trades_nme, quick_nme = result_nme
                            combo_name_nme = ' + '.join(SIGNAL_NAMES[j] for j in combo) + ' (+NoMicroExit)'
                            rules = generate_rule_text([SIGNAL_NAMES[j] for j in combo])
                            combo_results.append({
                                'combination': combo_name_nme,
                                'signals': [SIGNAL_NAMES[j] for j in combo] + ['NoMicroDot'],
                                'signal_indices': list(combo) + [NO_MICRO_IDX],
                                'num_signals': len(combo),
                                'no_micro_exit': True,
                                'entry_rule': rules['entry_rule'],
                                'exit_rule': rules['exit_rule'] + ' + NoMicroDot Exit',
                                'entry_short': rules['entry_short'] + ' +NME',
                                '_equity': equity_nme,
                                '_trades': trades_nme,
                                **quick_nme,
                            })

                        # Progress
                        if tested % 500 == 0:
                            elapsed = time.time() - t_combo_start
                            pct = tested / total_combos * 100
                            print(f"    ... {pct:.0f}% ({tested}/{total_combos}) — "
                                  f"{len(combo_results)} valid — {elapsed:.1f}s")

                combo_elapsed = time.time() - t_combo_start
                print(f"  📊 {len(combo_results):,} valid combos (≥3 trades) in {combo_elapsed:.1f}s")

                if not combo_results:
                    results_json['results'].append({
                        'ticker': ticker, 'timeframe': tf_key,
                        'date_range': date_info, 'bars': date_info['bars'],
                        'valid_combos': 0,
                        'best_combination': None, 'metrics': _empty_metrics(),
                        'top_combinations': [], 'combination_ranking': [],
                    })
                    continue

                # Sort by Sharpe (primary), total_return (secondary)
                combo_results.sort(key=lambda x: (x['sharpe_ratio'], x['total_return']), reverse=True)

                # Top 3 preview
                for rank, cr in enumerate(combo_results[:3], 1):
                    print(f"    #{rank}: {cr['combination']} — "
                          f"Ret {cr['total_return']}%, Sharpe {cr['sharpe_ratio']}, "
                          f"WR {cr['win_rate']}%, PF {cr['profit_factor']}, "
                          f"Trades {cr['total_trades']}")

                # --- Full metrics for top combos ---
                print(f"  🎯 Computing full metrics for top {min(TOP_DETAILED, len(combo_results))} combos...")
                top_detailed = []
                for rank, cr in enumerate(combo_results[:TOP_DETAILED]):
                    full_metrics = calc_full_metrics(cr['_trades'], cr['_equity'], INITIAL_CAPITAL)
                    # Strip histories from per-entry to save space
                    metrics_compact = {k: v for k, v in full_metrics.items()
                                       if k not in ('runup_history', 'drawdown_history')}
                    top_detailed.append({
                        'rank': rank + 1,
                        'combination': cr['combination'],
                        'signals': cr['signals'],
                        'num_signals': cr['num_signals'],
                        'no_micro_exit': cr['no_micro_exit'],
                        'entry_rule': cr['entry_rule'],
                        'exit_rule': cr['exit_rule'],
                        'metrics': metrics_compact,
                    })

                # Store best equity for chart
                best_cr = combo_results[0]
                all_equity_data[(ticker, tf_key)] = {
                    'equity': best_cr['_equity'].tolist(),
                    'combo_name': best_cr['combination'],
                }

                # Combination ranking (lightweight, no equity/_trades)
                top_ranking = []
                for cr in combo_results[:TOP_STORE]:
                    top_ranking.append({
                        'combination': cr['combination'],
                        'signals': cr['signals'],
                        'num_signals': cr['num_signals'],
                        'no_micro_exit': cr['no_micro_exit'],
                        'total_trades': cr['total_trades'],
                        'win_rate': cr['win_rate'],
                        'profit_factor': cr['profit_factor'],
                        'sharpe_ratio': cr['sharpe_ratio'],
                        'total_return': cr['total_return'],
                        'net_profit': cr['net_profit'],
                    })

                # Best combo for this ticker/TF
                best = combo_results[0]
                best_full_metrics = calc_full_metrics(best['_trades'], best['_equity'], INITIAL_CAPITAL)
                best_metrics_compact = {k: v for k, v in best_full_metrics.items()
                                        if k not in ('runup_history', 'drawdown_history')}

                best_combo_entry = {
                    'combination': best['combination'],
                    'signals': best['signals'],
                    'num_signals': best['num_signals'],
                    'no_micro_exit': best['no_micro_exit'],
                    'entry_rule': best['entry_rule'],
                    'exit_rule': best['exit_rule'],
                    'total_trades': best['total_trades'],
                    'win_rate': best['win_rate'],
                    'profit_factor': best['profit_factor'],
                    'sharpe_ratio': best['sharpe_ratio'],
                    'total_return': best['total_return'],
                    'net_profit': best['net_profit'],
                }

                # Print best detailed metrics
                m = best_metrics_compact
                print(f"  ✅ Best: {best['combination']}")
                print(f"     Net: {m['net_profit']:.0f}€ ({m['net_profit_pct']:.1f}%) | "
                      f"Trades: {m['total_trades']} | WR: {m['win_rate']}% | "
                      f"Sharpe: {m['sharpe_ratio']} | PF: {m['profit_factor']} | "
                      f"MDD: {m['max_drawdown_pct']:.1f}%")

                # Store in results JSON
                result_key = f"{ticker}_{tf_key}"
                results_json['results'].append({
                    'ticker': ticker,
                    'timeframe': tf_key,
                    'date_range': date_info,
                    'bars': date_info['bars'],
                    'valid_combos': len(combo_results),
                    'best_combination': best_combo_entry,
                    'metrics': best_metrics_compact,
                    'top_combinations': top_detailed,
                })
                results_json['combination_rankings'][result_key] = top_ranking

                # Best per ticker
                results_json['best_per_ticker'].append({
                    'ticker': ticker,
                    'timeframe': tf_key,
                    'date_range_label': date_info.get('label', ''),
                    'start': date_info.get('start', '?'),
                    'end': date_info.get('end', '?'),
                    'bars': date_info.get('bars', 0),
                    'months': date_info.get('months', 0),
                    'best_combination': best['combination'],
                    'entry_rule': best['entry_rule'],
                    'exit_rule': best['exit_rule'],
                    'total_trades': best['total_trades'],
                    'win_rate': best['win_rate'],
                    'sharpe_ratio': best['sharpe_ratio'],
                    'profit_factor': best['profit_factor'],
                    'total_return': best['total_return'],
                    'net_profit': best['net_profit'],
                })

                # Global best
                global_best_combos.append({
                    'ticker': ticker,
                    'timeframe': tf_key,
                    'combination': best['combination'],
                    'total_return': best['total_return'],
                    'sharpe': best['sharpe_ratio'],
                    'trades': best['total_trades'],
                    'win_rate': best['win_rate'],
                    'profit_factor': best['profit_factor'],
                    'net_profit': best['net_profit'],
                    'date_range': date_info.get('label', ''),
                })

            except Exception as e:
                print(f"  ❌ Error: {e}")
                traceback.print_exc()

    # Global best rankings
    global_best_combos.sort(key=lambda x: x['sharpe'], reverse=True)
    results_json['global_best'] = global_best_combos

    # Summary
    all_with_data = [r for r in results_json['results'] if r.get('valid_combos', 0) > 0]
    if all_with_data:
        all_best_returns = [r['metrics']['total_return'] for r in all_with_data if r.get('metrics')]
        all_best_sharpes = [r['metrics']['sharpe_ratio'] for r in all_with_data if r.get('metrics')]
        all_best_wrs = [r['metrics']['win_rate'] for r in all_with_data if r.get('metrics')]
        all_valid = [r['valid_combos'] for r in all_with_data]
        all_best_pfs = [r['metrics']['profit_factor'] for r in all_with_data if r.get('metrics')]
        all_best_mdds = [r['metrics']['max_drawdown_pct'] for r in all_with_data if r.get('metrics')]

        results_json['summary'] = {
            'total_bars_processed': total_bars,
            'total_results': len(all_with_data),
            'total_tickers': len(TICKERS),
            'total_timeframes': len(TIMEFRAMES),
            'combos_per_run': total_combos,
            'total_valid_combos': sum(all_valid),
            'avg_valid_combos_per_run': round(float(np.mean(all_valid)), 0) if all_valid else 0,
            'best_combo_return': max(all_best_returns) if all_best_returns else 0,
            'avg_best_return': round(float(np.mean(all_best_returns)), 2) if all_best_returns else 0,
            'avg_best_sharpe': round(float(np.mean(all_best_sharpes)), 2) if all_best_sharpes else 0,
            'avg_best_win_rate': round(float(np.mean(all_best_wrs)), 1) if all_best_wrs else 0,
            'avg_best_profit_factor': round(float(np.mean(all_best_pfs)), 2) if all_best_pfs else 0,
            'avg_best_max_drawdown_pct': round(float(np.mean(all_best_mdds)), 2) if all_best_mdds else 0,
            'runtime_seconds': round(time.time() - t_start, 1),
        }

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(RESULTS_JSON), 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\n✅ Results saved: {RESULTS_JSON}")

    # Equity chart
    if all_equity_data:
        print(f"\n📈 Generating equity chart...")
        plot_equity_curves(all_equity_data)

    # Print summary
    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print("SUMMARY — V5 (FIXED)")
    print(f"{'='*70}")
    print(f"  Runtime:              {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Total Bars:           {total_bars:,}")
    if results_json.get('summary'):
        s = results_json['summary']
        print(f"  Valid Combos Total:   {s['total_valid_combos']:,}")
        print(f"  Avg Valid/Run:        {s['avg_valid_combos_per_run']:.0f}")
        print(f"  Best Return:          {s['best_combo_return']}%")
        print(f"  Avg Best Return:      {s['avg_best_return']}%")
        print(f"  Avg Best Sharpe:      {s['avg_best_sharpe']}")
        print(f"  Avg Best WR:          {s['avg_best_win_rate']}%")
        print(f"  Avg Best PF:          {s['avg_best_profit_factor']}")
        print(f"  Avg Best MDD:         {s['avg_best_max_drawdown_pct']}%")

    if global_best_combos:
        print(f"\n  🏆 TOP 5 GLOBAL (by Sharpe):")
        for i, g in enumerate(global_best_combos[:5], 1):
            print(f"    #{i}: {g['ticker']} {g['timeframe']} — {g['combination']}")
            print(f"        Ret {g['total_return']}% | Sharpe {g['sharpe']} | "
                  f"WR {g['win_rate']}% | PF {g['profit_factor']} | {g['trades']} trades")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return results_json


if __name__ == '__main__':
    results = main()
