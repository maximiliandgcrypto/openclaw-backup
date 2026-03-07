#!/usr/bin/env python3
"""
Trend Suite (GRÄTZ) Backtester V6 — Stop-Loss & Take-Profit Matrix
====================================================================
V6 erweitert V5 um eine **SL/TP Matrix**: Jede Entry-Kombi wird mit
13 Stop-Loss-Methoden × 7 Take-Profit-Methoden getestet.

Entry-Kombis: Top-Ergebnisse aus V4 + bekannte Best-Kombis (~30-50 Stück).

SL-Methoden (13):
  VMA Cross, Pivot Low, ATR×1.0/1.5/2.0/3.0, Pct 1%/2%/3%/5%,
  TrendLine Flip, Exhaustion Level, Trailing ATR 2.0

TP-Methoden (7):
  None, R:R 1:1, R:R 1:2, R:R 1:3, BB Band, Counter-Signal, Trailing TP

Regeln:
  - Candle Close Rule (kein Intra-Candle)
  - Entry am NÄCHSTEN Bar nach Signal (kein Lookahead)
  - 100% Equity pro Trade, kein Pyramiding
  - Commission: 0, Initial Capital: 10.000 EUR
"""

import json
import sys
import warnings
import traceback
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

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
MIN_TRADES = 5  # Minimum trades per strategy

SIGNAL_NAMES = [
    'Reversal', 'TrendLine', 'Bollinger', 'MicroDots',
    'VMA_Trend', 'Exhaustion', 'VMA_Color',
    'RevConfirm1', 'RevConfirm2', 'Tops', 'Bottoms',
    'VMA_Cross', 'VMA_ColorChange', 'VMA_Cross_Micro',
    'NoMicroDot',
]
NUM_ENTRY_SIGNALS = 14
NO_MICRO_IDX = 14

# SL Methods
SL_METHODS = [
    'VMA Cross',
    'Pivot Low',
    'ATR 1.0', 'ATR 1.5', 'ATR 2.0', 'ATR 3.0',
    'Pct 1%', 'Pct 2%', 'Pct 3%', 'Pct 5%',
    'TrendLine Flip',
    'Exhaustion Level',
    'Trailing ATR 2.0',
]

# TP Methods
TP_METHODS = [
    'None',
    'R:R 1:1', 'R:R 1:2', 'R:R 1:3',
    'BB Band',
    'Counter-Signal',
    'Trailing TP',
]

# SL methods that produce a fixed numeric stop level (needed for R:R TPs)
SL_HAS_FIXED_LEVEL = {
    'VMA Cross': False,
    'Pivot Low': True,
    'ATR 1.0': True, 'ATR 1.5': True, 'ATR 2.0': True, 'ATR 3.0': True,
    'Pct 1%': True, 'Pct 2%': True, 'Pct 3%': True, 'Pct 5%': True,
    'TrendLine Flip': False,
    'Exhaustion Level': False,
    'Trailing ATR 2.0': True,
}

# Top N results to store per ticker/TF
TOP_PER_RUN = 100

OUTPUT_DIR = Path('/home/openclaw/.openclaw/workspace/mission-control')
RESULTS_JSON = OUTPUT_DIR / 'backtest-results-v6.json'

# V4 results path (for loading top combos)
V4_RESULTS = OUTPUT_DIR / 'backtest-results.json'


# ============================================================
# ENTRY COMBOS FROM V4 + KNOWN BEST
# ============================================================
def get_entry_combos():
    """
    Build list of entry combos to test:
    1. Top combos from V4 results (BTC/SOL)
    2. Known best combos
    3. Deduplicate
    Returns list of tuples of signal indices.
    """
    # Known best combos (signal name tuples)
    known_best = [
        ('Reversal', 'TrendLine'),
        ('Reversal', 'TrendLine', 'Exhaustion'),
        ('Reversal', 'MicroDots'),
        ('VMA_Color', 'TrendLine'),
    ]

    # Collect combo name strings
    combo_names = set()

    # Add known best
    for combo in known_best:
        combo_names.add(' + '.join(combo))

    # Load V4 results
    if V4_RESULTS.exists():
        try:
            with open(str(V4_RESULTS)) as f:
                v4 = json.load(f)

            # Best combo per ticker/TF
            for r in v4.get('results', []):
                ticker = r.get('ticker', '')
                if ticker not in ('BTC-USD', 'SOL-USD'):
                    continue
                bc = r.get('best_combination')
                if bc:
                    combo_str = bc.get('combination', '')
                    if combo_str and '(+NoMicroExit)' not in combo_str:
                        combo_names.add(combo_str)

            # Top from combination_rankings
            for key, rankings in v4.get('combination_rankings', {}).items():
                if 'BTC' not in key and 'SOL' not in key:
                    continue
                for entry in rankings[:5]:
                    combo_str = entry.get('combination', '')
                    if combo_str and '(+NoMicroExit)' not in combo_str:
                        combo_names.add(combo_str)

        except Exception as e:
            print(f"  [WARN] Could not load V4 results: {e}")

    # Add single-signal combos for all 14 entry signals
    for i in range(NUM_ENTRY_SIGNALS):
        combo_names.add(SIGNAL_NAMES[i])

    # Convert name strings to index tuples
    name_to_idx = {name: i for i, name in enumerate(SIGNAL_NAMES[:NUM_ENTRY_SIGNALS])}
    combos = []
    seen = set()

    for combo_str in sorted(combo_names):
        parts = [p.strip() for p in combo_str.split('+')]
        indices = []
        valid = True
        for p in parts:
            if p in name_to_idx:
                indices.append(name_to_idx[p])
            else:
                valid = False
                break
        if valid and len(indices) > 0:
            key = tuple(sorted(indices))
            if key not in seen:
                seen.add(key)
                combos.append(key)

    return combos


def combo_name(indices):
    """Convert signal index tuple to readable name."""
    return ' + '.join(SIGNAL_NAMES[i] for i in sorted(indices))


# ============================================================
# DATA LOADING (from V5)
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
# INDICATORS (from V5, identical)
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


def calc_atr14(df):
    """Compute ATR(14) and store on DataFrame."""
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr14'] = tr.rolling(14).mean()
    return df


# ============================================================
# EXTRACT 15 SIGNAL ARRAYS (from V5)
# ============================================================
def extract_signals(df):
    n = len(df)
    signals = np.zeros((15, n), dtype=np.int8)
    signals[0] = df['reversal_signal'].values.astype(np.int8)
    signals[1] = df['st_direction'].values.astype(np.int8)
    signals[2] = df['bb_signal'].values.astype(np.int8)
    signals[3] = df['micro_signal'].values.astype(np.int8)
    signals[4] = df['vma_trend'].values.astype(np.int8)
    signals[5] = df['exhaustion'].values.astype(np.int8)
    signals[6] = df['vma_color_signal'].values.astype(np.int8)

    rc1 = np.zeros(n, dtype=np.int8)
    rc1[df['bull_confirm1'].values.astype(bool)] = 1
    rc1[df['bear_confirm1'].values.astype(bool)] = -1
    signals[7] = rc1

    rc2 = np.zeros(n, dtype=np.int8)
    rc2[df['bull_confirm2'].values.astype(bool)] = 1
    rc2[df['bear_confirm2'].values.astype(bool)] = -1
    signals[8] = rc2

    h = df['high'].values; upper = df['bb_upper'].values; c = df['close'].values
    tops = np.zeros(n, dtype=np.int8)
    mask_top = np.isfinite(upper) & (h >= upper) & (c < upper)
    tops[mask_top] = -1
    signals[9] = tops

    lo = df['low'].values; lower = df['bb_lower'].values
    bottoms = np.zeros(n, dtype=np.int8)
    mask_bot = np.isfinite(lower) & (lo <= lower) & (c > lower)
    bottoms[mask_bot] = 1
    signals[10] = bottoms

    vma = df['vma'].values
    prev_c = np.roll(c, 1); prev_vma = np.roll(vma, 1)
    cross_up = (c > vma) & (prev_c <= prev_vma)
    cross_dn = (c < vma) & (prev_c >= prev_vma)
    cross_up[0] = False; cross_dn[0] = False
    vma_cross = np.zeros(n, dtype=np.int8)
    vma_cross[cross_up] = 1
    vma_cross[cross_dn] = -1
    signals[11] = vma_cross

    rising = np.zeros(n, dtype=bool); falling = np.zeros(n, dtype=bool)
    rising[1:] = vma[1:] > vma[:-1]
    falling[1:] = vma[1:] < vma[:-1]
    prev_rising = np.roll(rising, 1); prev_rising[0] = False
    prev_falling = np.roll(falling, 1); prev_falling[0] = False
    color_change = np.zeros(n, dtype=np.int8)
    color_change[rising & ~prev_rising] = 1
    color_change[falling & ~prev_falling] = -1
    signals[12] = color_change

    micro_up = df['micro_up'].values.astype(bool)
    micro_dn = df['micro_down'].values.astype(bool)
    cross_micro = np.zeros(n, dtype=np.int8)
    cross_micro[cross_up & micro_up] = 1
    cross_micro[cross_dn & micro_dn] = -1
    signals[13] = cross_micro

    no_micro = ~micro_up & ~micro_dn
    exit_sig = np.zeros(n, dtype=np.int8)
    exit_sig[no_micro] = 1
    signals[14] = exit_sig

    return signals


# ============================================================
# COMBINE ENTRY SIGNALS (AND logic)
# ============================================================
def combine_entry_signals(combo_indices, signals_matrix):
    """
    AND-combine entry signals. Returns +1/-1/0 array.
    All selected signals must be +1 for LONG, all -1 for SHORT.
    """
    n = signals_matrix.shape[1]
    selected = signals_matrix[list(combo_indices)]
    if len(combo_indices) == 1:
        combined = selected[0].copy()
    else:
        all_bull = np.all(selected == 1, axis=0)
        all_bear = np.all(selected == -1, axis=0)
        combined = np.zeros(n, dtype=np.int8)
        combined[all_bull] = 1
        combined[all_bear] = -1
    combined[0] = 0
    return combined


# ============================================================
# V6 BACKTEST ENGINE
# ============================================================
def backtest_v6(entry_signal, close, high, low, vma, vma_color,
                st_direction, bb_upper, bb_lower, exhaustion, atr,
                sl_method, tp_method, initial_capital=INITIAL_CAPITAL):
    """
    Bar-by-bar backtest with configurable SL and TP.

    entry_signal: +1/-1/0 array (AND-combined). Entry on NEXT bar after signal.
    Returns: (equity_array, trades_list) or None if < MIN_TRADES trades.
    """
    n = len(close)
    equity = np.full(n, initial_capital, dtype=np.float64)

    position = 0       # +1 LONG, -1 SHORT, 0 flat
    entry_price = 0.0
    entry_idx = 0
    position_size = 0.0
    stop_level = 0.0
    tp_level = 0.0
    pending_signal = 0  # signal from previous bar, to enter on current bar
    trailing_stop = 0.0
    trailing_tp = 0.0

    trades = []
    exit_reasons = {'Stop-Loss': 0, 'Take-Profit': 0, 'Signal Flip': 0, 'End of Data': 0}

    # Parse SL params
    sl_type = sl_method  # string key
    atr_sl_mult = 0.0
    pct_sl = 0.0
    if sl_type.startswith('ATR '):
        atr_sl_mult = float(sl_type.split(' ')[1])
    elif sl_type.startswith('Pct '):
        pct_sl = float(sl_type.replace('Pct ', '').replace('%', '')) / 100.0

    # Parse TP params
    tp_type = tp_method
    rr_mult = 0.0
    if tp_type.startswith('R:R 1:'):
        rr_mult = float(tp_type.split(':')[-1])

    # Check if this SL/TP combination is valid
    needs_fixed_sl = tp_type in ('R:R 1:1', 'R:R 1:2', 'R:R 1:3')
    if needs_fixed_sl and not SL_HAS_FIXED_LEVEL.get(sl_method, False):
        return None  # Skip: R:R TP needs a fixed SL level

    def _compute_stop(direction, entry_p, bar_idx):
        """Compute initial stop level at entry."""
        if sl_type == 'VMA Cross':
            return 0.0  # No fixed level; checked via condition
        elif sl_type == 'Pivot Low':
            lookback = 5
            start = max(0, bar_idx - lookback)
            if direction == 1:
                return float(np.min(low[start:bar_idx + 1]))
            else:
                return float(np.max(high[start:bar_idx + 1]))
        elif sl_type.startswith('ATR '):
            atr_val = atr[bar_idx]
            if np.isnan(atr_val) or atr_val <= 0:
                atr_val = abs(entry_p) * 0.02  # fallback 2%
            if direction == 1:
                return entry_p - atr_sl_mult * atr_val
            else:
                return entry_p + atr_sl_mult * atr_val
        elif sl_type.startswith('Pct '):
            if direction == 1:
                return entry_p * (1 - pct_sl)
            else:
                return entry_p * (1 + pct_sl)
        elif sl_type == 'TrendLine Flip':
            return 0.0  # Checked via st_direction
        elif sl_type == 'Exhaustion Level':
            return 0.0  # Checked via exhaustion signal
        elif sl_type == 'Trailing ATR 2.0':
            atr_val = atr[bar_idx]
            if np.isnan(atr_val) or atr_val <= 0:
                atr_val = abs(entry_p) * 0.02
            if direction == 1:
                return entry_p - 2.0 * atr_val
            else:
                return entry_p + 2.0 * atr_val
        return 0.0

    def _compute_tp(direction, entry_p, sl_level, bar_idx):
        """Compute initial take-profit level at entry."""
        if tp_type == 'None':
            return 0.0
        elif tp_type.startswith('R:R 1:'):
            risk = abs(entry_p - sl_level)
            if risk <= 0:
                return 0.0
            if direction == 1:
                return entry_p + rr_mult * risk
            else:
                return entry_p - rr_mult * risk
        elif tp_type == 'BB Band':
            if direction == 1:
                val = bb_upper[bar_idx]
                return float(val) if np.isfinite(val) else 0.0
            else:
                val = bb_lower[bar_idx]
                return float(val) if np.isfinite(val) else 0.0
        elif tp_type == 'Counter-Signal':
            return 0.0  # Checked via signal
        elif tp_type == 'Trailing TP':
            atr_val = atr[bar_idx]
            if np.isnan(atr_val) or atr_val <= 0:
                atr_val = abs(entry_p) * 0.02
            if direction == 1:
                return entry_p + 3.0 * atr_val
            else:
                return entry_p - 3.0 * atr_val
        return 0.0

    def _record_trade(direction, entry_p, exit_p, e_idx, x_idx, reason, sl_lev, tp_lev):
        if direction == 1:
            ret = (exit_p - entry_p) / entry_p if entry_p != 0 else 0
            pnl = (exit_p - entry_p) * position_size
        else:
            ret = (entry_p - exit_p) / entry_p if entry_p != 0 else 0
            pnl = (entry_p - exit_p) * position_size
        trades.append({
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'entry_price': round(float(entry_p), 6),
            'exit_price': round(float(exit_p), 6),
            'stop_level': round(float(sl_lev), 6),
            'tp_level': round(float(tp_lev), 6),
            'return': ret,
            'pnl': pnl,
            'entry_bar': e_idx,
            'exit_bar': x_idx,
            'bars_held': x_idx - e_idx,
            'exit_reason': reason,
        })
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    for i in range(1, n):
        equity[i] = equity[i - 1]

        # Mark-to-market open position
        if position != 0:
            pnl = position * (close[i] - close[i - 1]) * position_size
            equity[i] += pnl

        # --- Check exits for open position ---
        if position != 0:
            exited = False

            # 1. Stop-Loss check
            if sl_type == 'VMA Cross':
                if position == 1 and close[i] < vma[i] and vma_color[i] == -1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True
                elif position == -1 and close[i] > vma[i] and vma_color[i] == 1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True

            elif sl_type == 'Pivot Low':
                # Trailing pivot stop: update each bar
                lookback = 5
                start = max(0, i - lookback)
                if position == 1:
                    new_stop = float(np.min(low[start:i + 1]))
                    if new_stop > stop_level:
                        stop_level = new_stop
                    if close[i] < stop_level:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                        position = 0; exited = True
                else:
                    new_stop = float(np.max(high[start:i + 1]))
                    if new_stop < stop_level:
                        stop_level = new_stop
                    if close[i] > stop_level:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                        position = 0; exited = True

            elif sl_type.startswith('ATR ') or sl_type.startswith('Pct '):
                # Fixed stop, no trailing
                if position == 1 and close[i] <= stop_level:
                    _record_trade(position, entry_price, stop_level, entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    # Adjust equity for stop fill at stop_level instead of close
                    equity[i] = equity[i] - position * (close[i] - stop_level) * position_size
                    position = 0; exited = True
                elif position == -1 and close[i] >= stop_level:
                    _record_trade(position, entry_price, stop_level, entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    equity[i] = equity[i] - position * (close[i] - stop_level) * position_size
                    position = 0; exited = True

            elif sl_type == 'TrendLine Flip':
                if position == 1 and i > 0 and st_direction[i] == -1 and st_direction[i-1] == 1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True
                elif position == -1 and i > 0 and st_direction[i] == 1 and st_direction[i-1] == -1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True

            elif sl_type == 'Exhaustion Level':
                if position == 1 and exhaustion[i] == -1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True
                elif position == -1 and exhaustion[i] == 1:
                    _record_trade(position, entry_price, close[i], entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                    position = 0; exited = True

            elif sl_type == 'Trailing ATR 2.0':
                # Update trailing stop
                atr_val = atr[i]
                if np.isnan(atr_val) or atr_val <= 0:
                    atr_val = abs(entry_price) * 0.02
                if position == 1:
                    new_trailing = high[i] - 2.0 * atr_val
                    if new_trailing > trailing_stop:
                        trailing_stop = new_trailing
                        stop_level = trailing_stop
                    if close[i] <= stop_level:
                        _record_trade(position, entry_price, stop_level, entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                        equity[i] = equity[i] - position * (close[i] - stop_level) * position_size
                        position = 0; exited = True
                else:
                    new_trailing = low[i] + 2.0 * atr_val
                    if new_trailing < trailing_stop:
                        trailing_stop = new_trailing
                        stop_level = trailing_stop
                    if close[i] >= stop_level:
                        _record_trade(position, entry_price, stop_level, entry_idx, i, 'Stop-Loss', stop_level, tp_level)
                        equity[i] = equity[i] - position * (close[i] - stop_level) * position_size
                        position = 0; exited = True

            # 2. Take-Profit check (only if not already exited by SL)
            if not exited and position != 0:
                if tp_type == 'None':
                    pass  # No TP

                elif tp_type.startswith('R:R 1:'):
                    if tp_level != 0:
                        if position == 1 and close[i] >= tp_level:
                            _record_trade(position, entry_price, tp_level, entry_idx, i, 'Take-Profit', stop_level, tp_level)
                            equity[i] = equity[i] - position * (close[i] - tp_level) * position_size
                            position = 0; exited = True
                        elif position == -1 and close[i] <= tp_level:
                            _record_trade(position, entry_price, tp_level, entry_idx, i, 'Take-Profit', stop_level, tp_level)
                            equity[i] = equity[i] - position * (close[i] - tp_level) * position_size
                            position = 0; exited = True

                elif tp_type == 'BB Band':
                    if position == 1 and np.isfinite(bb_upper[i]) and close[i] >= bb_upper[i]:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Take-Profit', stop_level, tp_level)
                        position = 0; exited = True
                    elif position == -1 and np.isfinite(bb_lower[i]) and close[i] <= bb_lower[i]:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Take-Profit', stop_level, tp_level)
                        position = 0; exited = True

                elif tp_type == 'Counter-Signal':
                    # Exit when entry signal fires in opposite direction
                    if position == 1 and entry_signal[i] == -1:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Take-Profit', stop_level, tp_level)
                        position = 0; exited = True
                    elif position == -1 and entry_signal[i] == 1:
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Take-Profit', stop_level, tp_level)
                        position = 0; exited = True

                elif tp_type == 'Trailing TP':
                    # Update trailing TP
                    atr_val = atr[i]
                    if np.isnan(atr_val) or atr_val <= 0:
                        atr_val = abs(entry_price) * 0.02
                    if position == 1:
                        new_tp = high[i] - 3.0 * atr_val
                        if new_tp > trailing_tp:
                            trailing_tp = new_tp
                            tp_level = trailing_tp
                        # Trailing TP triggers when price pulls back below trailing level
                        # BUT only if we're in profit
                        if trailing_tp > entry_price and close[i] <= trailing_tp:
                            _record_trade(position, entry_price, trailing_tp, entry_idx, i, 'Take-Profit', stop_level, tp_level)
                            equity[i] = equity[i] - position * (close[i] - trailing_tp) * position_size
                            position = 0; exited = True
                    else:
                        new_tp = low[i] + 3.0 * atr_val
                        if new_tp < trailing_tp:
                            trailing_tp = new_tp
                            tp_level = trailing_tp
                        if trailing_tp < entry_price and close[i] >= trailing_tp:
                            _record_trade(position, entry_price, trailing_tp, entry_idx, i, 'Take-Profit', stop_level, tp_level)
                            equity[i] = equity[i] - position * (close[i] - trailing_tp) * position_size
                            position = 0; exited = True

            # 3. Signal Flip (entry signal changes direction)
            if not exited and position != 0:
                # Use pending_signal (signal from previous bar i-1) to check for flip
                # The entry_signal[i-1] was the signal generated on bar i-1
                # If it flips our position, we exit at open of bar i (≈close[i] for simplicity)
                if entry_signal[i] == -position:
                    # Don't double-count with Counter-Signal TP
                    if tp_type != 'Counter-Signal':
                        _record_trade(position, entry_price, close[i], entry_idx, i, 'Signal Flip', stop_level, tp_level)
                        position = 0; exited = True

        # --- Check for new entry ---
        # Candle close rule: signal on bar i-1, entry on bar i
        if pending_signal != 0 and position == 0:
            position = pending_signal
            entry_price = close[i]  # Enter at close of current bar
            entry_idx = i
            position_size = equity[i] / close[i] if close[i] > 0 else 0

            stop_level = _compute_stop(position, entry_price, i)
            tp_level = _compute_tp(position, entry_price, stop_level, i)

            # Init trailing values
            if sl_type == 'Trailing ATR 2.0':
                trailing_stop = stop_level
            if tp_type == 'Trailing TP':
                atr_val = atr[i]
                if np.isnan(atr_val) or atr_val <= 0:
                    atr_val = abs(entry_price) * 0.02
                if position == 1:
                    trailing_tp = high[i] - 3.0 * atr_val
                else:
                    trailing_tp = low[i] + 3.0 * atr_val
                tp_level = trailing_tp

        # Store signal for next bar's entry
        pending_signal = int(entry_signal[i])

    # Close any open position at end of data
    if position != 0:
        exit_p = close[-1]
        _record_trade(position, entry_price, exit_p, entry_idx, n - 1, 'End of Data', stop_level, tp_level)

    if len(trades) < MIN_TRADES:
        return None

    return equity, trades, exit_reasons


# ============================================================
# FULL METRICS (from V5, 39 fields)
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
# HELPER FUNCTIONS (from V5)
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


def generate_rule_text(signal_names):
    entry_parts = signal_names
    return {
        'entry_rule': 'LONG wenn ALLE: ' + ' UND '.join(entry_parts),
        'entry_short': ' + '.join(signal_names),
    }


# ============================================================
# MAIN
# ============================================================
def main():
    t_start = time.time()
    print("=" * 70)
    print("TREND SUITE (GRÄTZ) BACKTESTER V6 — SL/TP MATRIX")
    print("BTC+SOL | V4 Top Combos | 13 SL × 7 TP Methods")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"SL Methods ({len(SL_METHODS)}): {', '.join(SL_METHODS)}")
    print(f"TP Methods ({len(TP_METHODS)}): {', '.join(TP_METHODS)}")
    print(f"Capital: {INITIAL_CAPITAL:,}€ | Min Trades: {MIN_TRADES}")
    print()

    # --- Phase 1: Get entry combos ---
    entry_combos = get_entry_combos()
    print(f"📋 Entry Combos: {len(entry_combos)}")
    for idx, combo in enumerate(entry_combos):
        print(f"  {idx+1:2d}. {combo_name(combo)}")

    # Count valid SL/TP combos (skip invalid R:R + non-fixed-SL)
    valid_sl_tp = 0
    for sl in SL_METHODS:
        for tp in TP_METHODS:
            if tp in ('R:R 1:1', 'R:R 1:2', 'R:R 1:3') and not SL_HAS_FIXED_LEVEL.get(sl, False):
                continue
            valid_sl_tp += 1
    total_strategies = len(entry_combos) * valid_sl_tp
    print(f"\n🔢 Valid SL/TP combinations: {valid_sl_tp}")
    print(f"🔢 Total strategies per ticker/TF: {total_strategies:,}")
    print(f"🔢 Grand total: {total_strategies * len(TICKERS) * len(TIMEFRAMES):,}")
    print()

    # --- Build results JSON ---
    results_json = {
        'meta': {
            'generated': datetime.now().isoformat(),
            'version': 'V6',
            'data_source': 'TradingView CSV (tradingview-max)',
            'initial_capital': INITIAL_CAPITAL,
            'commission': COMMISSION,
            'currency': 'EUR',
            'tickers': TICKERS,
            'timeframes': TIMEFRAMES,
            'entry_combos_count': len(entry_combos),
            'entry_combos': [combo_name(c) for c in entry_combos],
            'sl_methods': SL_METHODS,
            'tp_methods': TP_METHODS,
            'valid_sl_tp_pairs': valid_sl_tp,
            'total_strategies_per_run': total_strategies,
            'min_trades': MIN_TRADES,
            'combination_logic': 'AND (all selected signals must agree)',
            'entry_rule': 'Entry on NEXT bar after signal (candle close rule)',
            'stop_loss': 'Configurable (13 methods)',
            'take_profit': 'Configurable (7 methods)',
            'features': [
                'V4 top combos as entry basis',
                '13 SL methods (VMA, Pivot, ATR×4, Pct×4, TrendLine, Exhaustion, Trailing)',
                '7 TP methods (None, R:R×3, BB Band, Counter-Signal, Trailing TP)',
                'R:R TPs skipped for non-fixed SL methods',
                'Full 39-metric analysis for top 100 per ticker/TF',
                'No lookahead bias (entry on next bar)',
                'Candle close rule',
            ],
        },
        'results': [],
        'global_best': [],
        'best_per_sl': {},
        'best_per_tp': {},
        'summary': {},
    }

    total_runs = len(TICKERS) * len(TIMEFRAMES)
    run_idx = 0
    total_bars = 0
    global_all_results = []  # For global best ranking

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
                    continue

                date_info = get_date_range(df)
                total_bars += date_info['bars']
                print(f"  📅 {date_info['label']}")

                # --- Compute all indicators ONCE ---
                print(f"  🔧 Computing indicators...")
                df = calc_bollinger(df)
                df = calc_reversals(df)
                df = calc_supertrend(df)
                df = calc_vma_trend(df, vma_length=9)
                df = calc_micro_dots(df)
                df = calc_exhaustion(df)
                df = calc_atr14(df)

                # Extract signal arrays
                signals_matrix = extract_signals(df)
                n = len(df)

                # Precompute arrays for backtest
                close_vals = df['close'].values.astype(np.float64)
                high_vals = df['high'].values.astype(np.float64)
                low_vals = df['low'].values.astype(np.float64)
                vma_vals = df['vma'].values.astype(np.float64)
                vma_color_vals = df['vma_color'].values.astype(np.float64)
                st_dir_vals = df['st_direction'].values.astype(np.float64)
                bb_upper_vals = df['bb_upper'].values.astype(np.float64)
                bb_lower_vals = df['bb_lower'].values.astype(np.float64)
                exhaust_vals = df['exhaustion'].values.astype(np.float64)
                atr_vals = df['atr14'].values.astype(np.float64)

                # --- Precompute entry signals for all combos ---
                print(f"  🔬 Precomputing {len(entry_combos)} entry signal combos...")
                entry_signals = {}
                for combo in entry_combos:
                    combined = combine_entry_signals(combo, signals_matrix)
                    n_bull = int(np.sum(combined == 1))
                    n_bear = int(np.sum(combined == -1))
                    if n_bull + n_bear >= 2:  # At least 2 signal bars
                        entry_signals[combo] = combined

                print(f"  ✅ {len(entry_signals)} combos with sufficient signals")

                # --- Run all SL/TP combinations ---
                print(f"  🔬 Testing {len(entry_signals)} × {valid_sl_tp} = {len(entry_signals) * valid_sl_tp:,} strategies...")
                run_results = []
                strategy_count = 0
                t_run_start = time.time()

                for combo, entry_sig in entry_signals.items():
                    c_name = combo_name(combo)

                    for sl_method in SL_METHODS:
                        for tp_method in TP_METHODS:
                            # Skip invalid R:R + non-fixed-SL
                            if tp_method in ('R:R 1:1', 'R:R 1:2', 'R:R 1:3') and not SL_HAS_FIXED_LEVEL.get(sl_method, False):
                                continue

                            strategy_count += 1

                            result = backtest_v6(
                                entry_sig, close_vals, high_vals, low_vals,
                                vma_vals, vma_color_vals, st_dir_vals,
                                bb_upper_vals, bb_lower_vals, exhaust_vals, atr_vals,
                                sl_method, tp_method, INITIAL_CAPITAL
                            )

                            if result is not None:
                                equity, trades, exit_reasons = result

                                # Quick metrics
                                trade_returns = [t['return'] for t in trades]
                                winners = [r for r in trade_returns if r > 0]
                                losers = [r for r in trade_returns if r <= 0]
                                wr = len(winners) / len(trade_returns) * 100 if trade_returns else 0
                                total_ret = (equity[-1] / equity[0] - 1) * 100
                                if len(trade_returns) > 1 and np.std(trade_returns) > 0:
                                    sharpe = float(np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(min(252, len(trade_returns))))
                                else:
                                    sharpe = 0.0

                                gp = sum(winners) if winners else 0
                                gl = abs(sum(losers)) if losers else 0.0001
                                pf = min(gp / gl if gl > 0 else 99.99, 99.99)

                                strategy_id = f"{ticker}_{tf_key}_{c_name.replace(' ', '')}_{sl_method.replace(' ', '')}_{tp_method.replace(' ', '')}"

                                run_results.append({
                                    'ticker': ticker,
                                    'timeframe': tf_key,
                                    'entry_combo': c_name,
                                    'sl_method': sl_method,
                                    'tp_method': tp_method,
                                    'strategy_id': strategy_id,
                                    'trade_count': len(trades),
                                    'win_rate': round(wr, 1),
                                    'sharpe': round(sharpe, 2),
                                    'total_return': round(total_ret, 2),
                                    'profit_factor': round(pf, 2),
                                    'net_profit': round(float(equity[-1] - INITIAL_CAPITAL), 2),
                                    'exit_reasons': dict(exit_reasons),
                                    '_equity': equity,
                                    '_trades': trades,
                                })

                            # Progress
                            if strategy_count % 100 == 0:
                                elapsed = time.time() - t_run_start
                                print(f"    ... {strategy_count:,} tested — "
                                      f"{len(run_results)} valid — {elapsed:.1f}s")

                run_elapsed = time.time() - t_run_start
                print(f"  📊 {len(run_results):,} valid strategies (≥{MIN_TRADES} trades) "
                      f"from {strategy_count:,} tested in {run_elapsed:.1f}s")

                if not run_results:
                    continue

                # Sort by Sharpe
                run_results.sort(key=lambda x: (x['sharpe'], x['total_return']), reverse=True)

                # Top 3 preview
                for rank, rr in enumerate(run_results[:3], 1):
                    print(f"    #{rank}: {rr['entry_combo']} | SL: {rr['sl_method']} | TP: {rr['tp_method']} — "
                          f"Ret {rr['total_return']}%, Sharpe {rr['sharpe']}, "
                          f"WR {rr['win_rate']}%, PF {rr['profit_factor']}, "
                          f"Trades {rr['trade_count']}")

                # --- Full metrics for top 100 ---
                print(f"  🎯 Computing full metrics for top {min(TOP_PER_RUN, len(run_results))}...")
                top_results = []
                for rr in run_results[:TOP_PER_RUN]:
                    full_metrics = calc_full_metrics(rr['_trades'], rr['_equity'], INITIAL_CAPITAL)
                    entry = {
                        'ticker': rr['ticker'],
                        'timeframe': rr['timeframe'],
                        'entry_combo': rr['entry_combo'],
                        'sl_method': rr['sl_method'],
                        'tp_method': rr['tp_method'],
                        'strategy_id': rr['strategy_id'],
                        'metrics': full_metrics,
                        'trade_count': rr['trade_count'],
                        'win_rate': rr['win_rate'],
                        'sharpe': rr['sharpe'],
                        'total_return': rr['total_return'],
                        'profit_factor': rr['profit_factor'],
                        'net_profit': rr['net_profit'],
                        'exit_reasons': rr['exit_reasons'],
                    }
                    top_results.append(entry)
                    global_all_results.append(entry)

                results_json['results'].extend(top_results)

                # Best result for this ticker/TF
                best = run_results[0]
                m = top_results[0]['metrics']
                print(f"  ✅ Best: {best['entry_combo']} | SL: {best['sl_method']} | TP: {best['tp_method']}")
                print(f"     Net: {m['net_profit']:.0f}€ ({m['net_profit_pct']:.1f}%) | "
                      f"Trades: {m['total_trades']} | WR: {m['win_rate']}% | "
                      f"Sharpe: {m['sharpe_ratio']} | PF: {m['profit_factor']} | "
                      f"MDD: {m['max_drawdown_pct']:.1f}%")

            except Exception as e:
                print(f"  ❌ Error: {e}")
                traceback.print_exc()

    # --- Global rankings ---
    print(f"\n{'='*70}")
    print("BUILDING GLOBAL RANKINGS...")

    # Global best (Top 20 by Sharpe)
    global_all_results.sort(key=lambda x: (x['sharpe'], x['total_return']), reverse=True)
    results_json['global_best'] = []
    for entry in global_all_results[:20]:
        results_json['global_best'].append({
            'ticker': entry['ticker'],
            'timeframe': entry['timeframe'],
            'entry_combo': entry['entry_combo'],
            'sl_method': entry['sl_method'],
            'tp_method': entry['tp_method'],
            'strategy_id': entry['strategy_id'],
            'sharpe': entry['sharpe'],
            'total_return': entry['total_return'],
            'win_rate': entry['win_rate'],
            'profit_factor': entry['profit_factor'],
            'trade_count': entry['trade_count'],
            'net_profit': entry['net_profit'],
        })

    # Best per SL method
    for sl in SL_METHODS:
        sl_results = [r for r in global_all_results if r['sl_method'] == sl]
        if sl_results:
            best_sl = sl_results[0]  # Already sorted by sharpe
            results_json['best_per_sl'][sl] = {
                'ticker': best_sl['ticker'],
                'timeframe': best_sl['timeframe'],
                'entry_combo': best_sl['entry_combo'],
                'tp_method': best_sl['tp_method'],
                'sharpe': best_sl['sharpe'],
                'total_return': best_sl['total_return'],
                'win_rate': best_sl['win_rate'],
                'trade_count': best_sl['trade_count'],
                'count_valid': len(sl_results),
            }

    # Best per TP method
    for tp in TP_METHODS:
        tp_results = [r for r in global_all_results if r['tp_method'] == tp]
        if tp_results:
            best_tp = tp_results[0]
            results_json['best_per_tp'][tp] = {
                'ticker': best_tp['ticker'],
                'timeframe': best_tp['timeframe'],
                'entry_combo': best_tp['entry_combo'],
                'sl_method': best_tp['sl_method'],
                'sharpe': best_tp['sharpe'],
                'total_return': best_tp['total_return'],
                'win_rate': best_tp['win_rate'],
                'trade_count': best_tp['trade_count'],
                'count_valid': len(tp_results),
            }

    # Summary
    elapsed = time.time() - t_start
    if global_all_results:
        all_sharpes = [r['sharpe'] for r in global_all_results]
        all_returns = [r['total_return'] for r in global_all_results]
        all_wrs = [r['win_rate'] for r in global_all_results]
        all_pfs = [r['profit_factor'] for r in global_all_results]

        results_json['summary'] = {
            'total_bars_processed': total_bars,
            'total_valid_strategies': len(global_all_results),
            'total_tickers': len(TICKERS),
            'total_timeframes': len(TIMEFRAMES),
            'entry_combos_tested': len(entry_combos),
            'sl_methods': len(SL_METHODS),
            'tp_methods': len(TP_METHODS),
            'avg_sharpe': round(float(np.mean(all_sharpes)), 2),
            'max_sharpe': round(float(np.max(all_sharpes)), 2),
            'avg_return': round(float(np.mean(all_returns)), 2),
            'max_return': round(float(np.max(all_returns)), 2),
            'avg_win_rate': round(float(np.mean(all_wrs)), 1),
            'avg_profit_factor': round(float(np.mean(all_pfs)), 2),
            'runtime_seconds': round(elapsed, 1),
        }

    # --- Save JSON ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(RESULTS_JSON), 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\n✅ Results saved: {RESULTS_JSON}")

    # --- Print summary ---
    print(f"\n{'='*70}")
    print("SUMMARY — V6 (SL/TP MATRIX)")
    print(f"{'='*70}")
    print(f"  Runtime:              {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Total Bars:           {total_bars:,}")
    if results_json.get('summary'):
        s = results_json['summary']
        print(f"  Valid Strategies:     {s['total_valid_strategies']:,}")
        print(f"  Entry Combos:        {s['entry_combos_tested']}")
        print(f"  SL Methods:          {s['sl_methods']}")
        print(f"  TP Methods:          {s['tp_methods']}")
        print(f"  Avg Sharpe:          {s['avg_sharpe']}")
        print(f"  Max Sharpe:          {s['max_sharpe']}")
        print(f"  Avg Return:          {s['avg_return']}%")
        print(f"  Max Return:          {s['max_return']}%")
        print(f"  Avg Win Rate:        {s['avg_win_rate']}%")
        print(f"  Avg Profit Factor:   {s['avg_profit_factor']}")

    if results_json['global_best']:
        print(f"\n  🏆 TOP 5 GLOBAL (by Sharpe):")
        for i, g in enumerate(results_json['global_best'][:5], 1):
            print(f"    #{i}: {g['ticker']} {g['timeframe']} — {g['entry_combo']}")
            print(f"        SL: {g['sl_method']} | TP: {g['tp_method']}")
            print(f"        Ret {g['total_return']}% | Sharpe {g['sharpe']} | "
                  f"WR {g['win_rate']}% | PF {g['profit_factor']} | {g['trade_count']} trades")

    if results_json['best_per_sl']:
        print(f"\n  📉 BEST PER SL METHOD:")
        for sl, info in results_json['best_per_sl'].items():
            print(f"    {sl:20s}: Sharpe {info['sharpe']:6.2f} | Ret {info['total_return']:8.1f}% | "
                  f"{info['ticker']} {info['timeframe']} | {info['count_valid']} valid")

    if results_json['best_per_tp']:
        print(f"\n  📈 BEST PER TP METHOD:")
        for tp, info in results_json['best_per_tp'].items():
            print(f"    {tp:20s}: Sharpe {info['sharpe']:6.2f} | Ret {info['total_return']:8.1f}% | "
                  f"{info['ticker']} {info['timeframe']} | {info['count_valid']} valid")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return results_json


if __name__ == '__main__':
    results = main()
