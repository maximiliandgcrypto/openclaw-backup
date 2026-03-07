#!/usr/bin/env python3
"""
Trend Suite (GRÄTZ) Backtester V4
=================================
V4: Extended TradingView data (tradingview-max/), 5 timeframes, full metrics.
Changes from V3:
- Data source: data/tradingview-max/ (544k+ bars, up to 10k per CSV)
- NEW timeframe: 15min (5 TFs: 5min, 15min, 1H, 4H, 1D)
- Initial capital: 10,000 EUR
- Commission: 0 (Bybit rates later)
- Full TradingView Strategy Tester metrics per backtest
- Output: mission-control/backtest-results.json (no version suffix)

Components:
1. Reversal Bars (Bollinger Band Breakout + Return + Confirmations)
2. TrendLine (ATR 10, Factor 3.0)
3. Bollinger Bands (Length 19, Mult 2)
4. Micro Dots (VMA + SMA + TrendLine Confluence)
5. VMA Trend Line (Fast=9, Medium=18, Slow=27)
6. Exhaustion Lines (Swing Length 40, Bar Count 10)
7. 24h Volume (Filter only)
"""

import json
import sys
import warnings
import traceback
from datetime import datetime, timedelta
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
TICKERS = [
    'SPY', 'AAPL', 'NVDA', 'TSLA', 'META', 'GOOGL', 'AMZN',
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'BNB-USD',
    'DOGE-USD', 'LINK-USD', 'ADA-USD', 'TRX-USD', 'AVAX-USD',
    'SUI20947-USD', 'PEPE24478-USD',
]

TICKER_TO_CSV = {
    'SPY': 'SPY', 'AAPL': 'AAPL', 'NVDA': 'NVDA', 'TSLA': 'TSLA',
    'META': 'META', 'GOOGL': 'GOOGL', 'AMZN': 'AMZN',
    'BTC-USD': 'BTCUSD', 'ETH-USD': 'ETHUSD', 'SOL-USD': 'SOLUSD',
    'XRP-USD': 'XRPUSD', 'BNB-USD': 'BNBUSD', 'DOGE-USD': 'DOGEUSD',
    'LINK-USD': 'LINKUSD', 'ADA-USD': 'ADAUSD', 'TRX-USD': 'TRXUSD',
    'AVAX-USD': 'AVAXUSD', 'SUI20947-USD': 'SUIUSD',
    'PEPE24478-USD': 'PEPEUSD',
}

TF_TO_CSV_SUFFIX = {
    '5min':  '5min',
    '15min': '15min',
    '1h':    '1H',
    '4h':    '4H',
    'Daily': '1D',
}

TIMEFRAMES = ['5min', '15min', '1h', '4h', 'Daily']

CSV_DATA_DIR = Path('/home/openclaw/.openclaw/workspace/data/tradingview-max')

INITIAL_CAPITAL = 10000  # 10k EUR
COMMISSION = 0.0         # 0 for now, Bybit rates later

INDICATOR_NAMES = [
    'Reversal', 'TrendLine', 'Bollinger', 'MicroDots',
    'VMA_Trend', 'Exhaustion', 'VMA_Color',
]

OUTPUT_DIR = Path('/home/openclaw/.openclaw/workspace/mission-control')
RESULTS_JSON = OUTPUT_DIR / 'backtest-results.json'
EQUITY_PNG = OUTPUT_DIR / 'backtest-equity.png'


# ============================================================
# DATA LOADING
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
# INDICATORS
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
    df['bull_confirm1'] = (
        (lo.shift(2) < lower.shift(2)) & (c.shift(2) < o.shift(2)) &
        (c.shift(1) > lower.shift(1)) & (c.shift(1) > o.shift(1)) & (c > h.shift(1))
    )
    df['bull_confirm2'] = (
        (lo.shift(3) < lower.shift(3)) & (c.shift(3) < o.shift(3)) &
        (c.shift(2) > lower.shift(2)) & (c.shift(2) > o.shift(2)) & (c > h.shift(2))
    )
    df['bear_reversal'] = (
        (h.shift(1) > upper.shift(1)) & (c.shift(1) > o.shift(1)) &
        (c < upper) & (c < o)
    )
    df['bear_confirm1'] = (
        (h.shift(2) > upper.shift(2)) & (c.shift(2) > o.shift(2)) &
        (c.shift(1) < upper.shift(1)) & (c.shift(1) < o.shift(1)) & (c < lo.shift(1))
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

    st_up = np.zeros(len(df))
    st_dn = np.zeros(len(df))
    st_dir = np.ones(len(df))

    for i in range(1, len(df)):
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
        fast_rising = vma_fast[i] > vma_fast[i-1]
        fast_above_med = vma_fast[i] > vma_med[i]
        fast_falling = vma_fast[i] < vma_fast[i-1]
        fast_below_med = vma_fast[i] < vma_med[i]

        if fast_rising and fast_above_med:
            color[i] = 1
        elif fast_falling and fast_below_med:
            color[i] = -1
        else:
            color[i] = 0

    df['vma_color'] = color
    df['vma_trend'] = np.where(color == 1, 1, np.where(color == -1, -1, 0))
    df['vma_color_prev'] = pd.Series(color).shift(1).fillna(0).astype(int)

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
    n = len(df)
    exhaust = np.zeros(n)
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
    resistance = np.full(n, np.nan); support = np.full(n, np.nan)
    last_res = np.nan; last_sup = np.nan
    for i in range(n):
        if exhaust[i] == -1: last_res = h[i]
        if exhaust[i] == 1: last_sup = lo[i]
        resistance[i] = last_res; support[i] = last_sup
    df['exhaust_resistance'] = resistance
    df['exhaust_support'] = support
    return df


# ============================================================
# SIGNAL EXTRACTION & GENERATION
# ============================================================
def extract_indicator_signals(df):
    return {
        'Reversal': df['reversal_signal'].values.copy(),
        'TrendLine': df['st_direction'].values.copy(),
        'Bollinger': df['bb_signal'].values.copy(),
        'MicroDots': df['micro_signal'].values.copy(),
        'VMA_Trend': df['vma_trend'].values.copy(),
        'Exhaustion': df['exhaustion'].values.copy(),
        'VMA_Color': df['vma_color_signal'].values.copy(),
    }


def generate_signals(df):
    n = len(df)
    signals = np.zeros(n)
    confluence = np.zeros(n)
    setup = [''] * n

    for i in range(1, n):
        bull = 0; bear = 0
        vma_cs = df['vma_color_signal'].iloc[i]
        if vma_cs == 1: bull += 2.5
        elif vma_cs == -1: bear += 2.5
        if df['setup_type'].iloc[i] == 'A':
            if vma_cs == 1: bull += 1.0
            elif vma_cs == -1: bear += 1.0
        if df['bull_reversal'].iloc[i]: bull += 1
        if df['bull_confirm1'].iloc[i] or df['bull_confirm2'].iloc[i]: bull += 1.5
        if df['bear_reversal'].iloc[i]: bear += 1
        if df['bear_confirm1'].iloc[i] or df['bear_confirm2'].iloc[i]: bear += 1.5
        if df['st_direction'].iloc[i] == 1: bull += 1
        else: bear += 1
        if df['vma_trend'].iloc[i] == 1: bull += 1
        elif df['vma_trend'].iloc[i] == -1: bear += 1
        if df['micro_up'].iloc[i]: bull += 1.5
        if df['micro_down'].iloc[i]: bear += 1.5
        if df['exhaustion'].iloc[i] == 1: bull += 1.5
        if df['exhaustion'].iloc[i] == -1: bear += 1.5
        if df['bb_signal'].iloc[i] == 1: bull += 0.5
        elif df['bb_signal'].iloc[i] == -1: bear += 0.5

        net = bull - bear
        if net >= 2: signals[i] = 1; confluence[i] = bull
        elif net <= -2: signals[i] = -1; confluence[i] = bear
        else: confluence[i] = max(bull, bear)
        setup[i] = df['setup_type'].iloc[i]

    df['signal'] = signals
    df['confluence'] = confluence
    df['trade_setup'] = setup
    return df


# ============================================================
# BACKTESTING ENGINE (V4: 10k capital, 0 commission, full trade tracking)
# ============================================================
def backtest(df, initial_capital=INITIAL_CAPITAL):
    n = len(df)
    equity = np.full(n, initial_capital, dtype=float)
    position = 0; entry_price = 0.0; position_size = 0.0
    trades = []; entry_idx = 0

    for i in range(1, n):
        equity[i] = equity[i-1]
        if position != 0:
            pnl = position * (df['close'].iloc[i] - df['close'].iloc[i-1]) * position_size
            equity[i] += pnl

        sig = df['signal'].iloc[i]
        conf = df['confluence'].iloc[i]
        trade_setup = df['trade_setup'].iloc[i]

        # Dynamic stop loss: VMA trend line cross
        if position == 1 and df['close'].iloc[i] < df['vma'].iloc[i] and df['vma_color'].iloc[i] == -1:
            exit_price = float(df['close'].iloc[i])
            pnl_abs = (exit_price - entry_price) * position_size
            ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0
            commission_paid = abs(position_size * entry_price) * COMMISSION + abs(position_size * exit_price) * COMMISSION
            equity[i] -= commission_paid
            trades.append({
                'direction': 'LONG', 'entry': entry_price, 'exit': exit_price,
                'return': ret, 'pnl': pnl_abs - commission_paid,
                'entry_bar': entry_idx, 'exit_bar': i,
                'bars_held': i - entry_idx, 'reason': 'VMA Stop',
                'setup': trades[-1]['setup'] if trades else '',
                'confluence': float(conf),
                'is_a_setup': trades[-1].get('is_a_setup', False) if trades else False,
                'commission': commission_paid,
                'position_size': position_size,
            })
            position = 0

        elif position == -1 and df['close'].iloc[i] > df['vma'].iloc[i] and df['vma_color'].iloc[i] == 1:
            exit_price = float(df['close'].iloc[i])
            pnl_abs = (entry_price - exit_price) * position_size
            ret = (entry_price - exit_price) / entry_price if entry_price != 0 else 0
            commission_paid = abs(position_size * entry_price) * COMMISSION + abs(position_size * exit_price) * COMMISSION
            equity[i] -= commission_paid
            trades.append({
                'direction': 'SHORT', 'entry': entry_price, 'exit': exit_price,
                'return': ret, 'pnl': pnl_abs - commission_paid,
                'entry_bar': entry_idx, 'exit_bar': i,
                'bars_held': i - entry_idx, 'reason': 'VMA Stop',
                'setup': trades[-1]['setup'] if trades else '',
                'confluence': float(conf),
                'is_a_setup': trades[-1].get('is_a_setup', False) if trades else False,
                'commission': commission_paid,
                'position_size': position_size,
            })
            position = 0

        # New signal
        if sig != 0 and sig != position:
            if position != 0:
                exit_price = float(df['close'].iloc[i])
                if position == 1:
                    ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (exit_price - entry_price) * position_size
                else:
                    ret = (entry_price - exit_price) / entry_price if entry_price != 0 else 0
                    pnl_abs = (entry_price - exit_price) * position_size
                commission_paid = abs(position_size * entry_price) * COMMISSION + abs(position_size * exit_price) * COMMISSION
                equity[i] -= commission_paid
                trades.append({
                    'direction': 'LONG' if position == 1 else 'SHORT',
                    'entry': entry_price, 'exit': exit_price,
                    'return': ret, 'pnl': pnl_abs - commission_paid,
                    'entry_bar': entry_idx, 'exit_bar': i,
                    'bars_held': i - entry_idx, 'reason': 'Signal Flip',
                    'setup': trade_setup, 'confluence': float(conf),
                    'is_a_setup': trade_setup == 'A',
                    'commission': commission_paid,
                    'position_size': position_size,
                })

            position = int(sig)
            entry_price = df['close'].iloc[i]
            entry_idx = i
            is_a = trade_setup == 'A' or conf >= 5
            if is_a:
                position_size = equity[i] / df['close'].iloc[i]
            else:
                position_size = (equity[i] * 0.5) / df['close'].iloc[i]
            equity[i] -= abs(position_size * df['close'].iloc[i]) * COMMISSION

    df['equity'] = equity
    return df, trades


# ============================================================
# FULL METRICS (TradingView Strategy Tester Format)
# ============================================================
def calc_metrics(trades, equity_series, initial_capital=INITIAL_CAPITAL):
    eq = np.array(equity_series)
    n_bars = len(eq)

    if not trades:
        return _empty_metrics(initial_capital, n_bars)

    # Separate winning/losing
    pnls = [t['pnl'] for t in trades]
    returns = [t['return'] for t in trades]
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]
    win_pnls = [t['pnl'] for t in winners]
    loss_pnls = [t['pnl'] for t in losers]
    win_returns = [t['return'] for t in winners]
    loss_returns = [t['return'] for t in losers]

    final_eq = eq[-1] if len(eq) > 0 else initial_capital
    net_profit = final_eq - initial_capital
    net_profit_pct = (net_profit / initial_capital) * 100

    gross_profit = sum(win_pnls) if win_pnls else 0
    gross_loss = sum(loss_pnls) if loss_pnls else 0  # negative
    gross_loss_abs = abs(gross_loss)
    total_profit = gross_profit + gross_loss  # = net
    total_loss = gross_loss

    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else 99.99
    if profit_factor == float('inf'): profit_factor = 99.99

    commission_paid = sum(t.get('commission', 0) for t in trades)

    total_trades = len(trades)
    # Count open trades (position still open at end = 0 in our case since we close on signal)
    total_open = 0
    winning_count = len(winners)
    losing_count = len(losers)
    pct_profitable = (winning_count / total_trades * 100) if total_trades > 0 else 0

    avg_trade_pnl = np.mean(pnls) if pnls else 0
    avg_trade_pnl_pct = np.mean(returns) * 100 if returns else 0

    avg_win = np.mean(win_pnls) if win_pnls else 0
    avg_win_pct = np.mean(win_returns) * 100 if win_returns else 0
    avg_loss = np.mean(loss_pnls) if loss_pnls else 0
    avg_loss_pct = np.mean(loss_returns) * 100 if loss_returns else 0

    ratio_avg_win_loss = (abs(avg_win) / abs(avg_loss)) if avg_loss != 0 else 99.99

    # Largest winning/losing trade
    largest_win = max(win_pnls) if win_pnls else 0
    largest_win_pct = max(win_returns) * 100 if win_returns else 0
    largest_loss = min(loss_pnls) if loss_pnls else 0
    largest_loss_pct = min(loss_returns) * 100 if loss_returns else 0

    # % of gross profit/loss from largest trade
    pct_gross_profit_largest = (largest_win / gross_profit * 100) if gross_profit > 0 else 0
    pct_gross_loss_largest = (abs(largest_loss) / gross_loss_abs * 100) if gross_loss_abs > 0 else 0

    # Avg bars in winning/losing trades
    avg_bars_win = np.mean([t['bars_held'] for t in winners]) if winners else 0
    avg_bars_loss = np.mean([t['bars_held'] for t in losers]) if losers else 0

    # Drawdown analysis
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    dd_pct = dd / peak * 100

    max_dd = abs(np.min(dd)) if len(dd) > 0 else 0
    max_dd_pct = abs(np.min(dd_pct)) if len(dd_pct) > 0 else 0

    # Avg drawdown
    in_dd = dd < 0
    if np.any(in_dd):
        avg_dd = abs(np.mean(dd[in_dd]))
    else:
        avg_dd = 0

    # Max drawdown duration (bars)
    max_dd_duration = 0
    current_dd_duration = 0
    for i in range(len(dd)):
        if dd[i] < 0:
            current_dd_duration += 1
            max_dd_duration = max(max_dd_duration, current_dd_duration)
        else:
            current_dd_duration = 0

    # Run-up / Drawdown history (sampled for JSON size)
    sample_step = max(1, n_bars // 500)
    runup_history = []
    dd_history = []
    for i in range(0, n_bars, sample_step):
        runup_history.append(round(float(eq[i] - initial_capital), 2))
        dd_history.append(round(float(dd[i]), 2))

    # Sharpe ratio
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(min(252, len(returns)))
    else:
        sharpe = 0

    # A/B setup stats
    a_trades = [t for t in trades if t.get('is_a_setup', False)]
    b_trades = [t for t in trades if not t.get('is_a_setup', False)]
    a_winners = [t for t in a_trades if t['pnl'] > 0]
    b_winners = [t for t in b_trades if t['pnl'] > 0]

    return {
        # Net
        'net_profit': round(net_profit, 2),
        'net_profit_pct': round(net_profit_pct, 2),
        'total_profit': round(total_profit, 2),
        'total_loss': round(total_loss, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'profit_factor': round(min(profit_factor, 99.99), 2),
        'commission_paid': round(commission_paid, 4),
        # Trades
        'total_trades': total_trades,
        'total_open_trades': total_open,
        'winning_trades': winning_count,
        'losing_trades': losing_count,
        'percent_profitable': round(pct_profitable, 1),
        # Averages
        'avg_trade_pnl': round(avg_trade_pnl, 2),
        'avg_trade_pnl_pct': round(avg_trade_pnl_pct, 2),
        'avg_winning_trade': round(avg_win, 2),
        'avg_winning_trade_pct': round(avg_win_pct, 2),
        'avg_losing_trade': round(avg_loss, 2),
        'avg_losing_trade_pct': round(avg_loss_pct, 2),
        'ratio_avg_win_loss': round(min(ratio_avg_win_loss, 99.99), 2),
        # Largest
        'largest_winning_trade': round(largest_win, 2),
        'largest_winning_trade_pct': round(largest_win_pct, 2),
        'largest_losing_trade': round(largest_loss, 2),
        'largest_losing_trade_pct': round(largest_loss_pct, 2),
        'pct_gross_profit_largest_win': round(pct_gross_profit_largest, 1),
        'pct_gross_loss_largest_loss': round(pct_gross_loss_largest, 1),
        # Bars
        'avg_bars_winning': round(avg_bars_win, 1),
        'avg_bars_losing': round(avg_bars_loss, 1),
        # Drawdown
        'max_drawdown': round(max_dd, 2),
        'max_drawdown_pct': round(max_dd_pct, 2),
        'avg_drawdown': round(avg_dd, 2),
        'max_drawdown_duration_bars': max_dd_duration,
        # Sharpe
        'sharpe_ratio': round(sharpe, 2),
        # Total return (convenience)
        'total_return': round(net_profit_pct, 2),
        'win_rate': round(pct_profitable, 1),
        # Run-up/Drawdown history
        'runup_history': runup_history,
        'drawdown_history': dd_history,
        # A/B setup
        'a_setup_trades': len(a_trades),
        'b_setup_trades': len(b_trades),
        'a_setup_win_rate': round(len(a_winners) / len(a_trades) * 100, 1) if a_trades else 0,
        'b_setup_win_rate': round(len(b_winners) / len(b_trades) * 100, 1) if b_trades else 0,
    }


def _empty_metrics(initial_capital, n_bars):
    return {
        'net_profit': 0, 'net_profit_pct': 0, 'total_profit': 0, 'total_loss': 0,
        'gross_profit': 0, 'gross_loss': 0, 'profit_factor': 0, 'commission_paid': 0,
        'total_trades': 0, 'total_open_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
        'percent_profitable': 0, 'avg_trade_pnl': 0, 'avg_trade_pnl_pct': 0,
        'avg_winning_trade': 0, 'avg_winning_trade_pct': 0, 'avg_losing_trade': 0,
        'avg_losing_trade_pct': 0, 'ratio_avg_win_loss': 0,
        'largest_winning_trade': 0, 'largest_winning_trade_pct': 0,
        'largest_losing_trade': 0, 'largest_losing_trade_pct': 0,
        'pct_gross_profit_largest_win': 0, 'pct_gross_loss_largest_loss': 0,
        'avg_bars_winning': 0, 'avg_bars_losing': 0,
        'max_drawdown': 0, 'max_drawdown_pct': 0, 'avg_drawdown': 0,
        'max_drawdown_duration_bars': 0, 'sharpe_ratio': 0,
        'total_return': 0, 'win_rate': 0,
        'runup_history': [], 'drawdown_history': [],
        'a_setup_trades': 0, 'b_setup_trades': 0,
        'a_setup_win_rate': 0, 'b_setup_win_rate': 0,
    }


# ============================================================
# ENTRY/EXIT RULE TEXT GENERATION
# ============================================================
INDICATOR_ENTRY_LONG = {
    'Reversal': 'Bullish Reversal Bar (BB Breakout Return)',
    'TrendLine': 'TrendLine grün (bullish)',
    'Bollinger': 'Preis unter BB Lower (überverkauft)',
    'MicroDots': 'Micro Dots grün (VMA+SMA+ST Confluence)',
    'VMA_Trend': 'VMA Trend steigend',
    'Exhaustion': 'Bullish Exhaustion (Support-Level)',
    'VMA_Color': 'VMA Farbwechsel Rot→Grün',
}
INDICATOR_EXIT = {
    'Reversal': 'Gegenläufiger Reversal Bar',
    'TrendLine': 'TrendLine Farbwechsel',
    'Bollinger': 'BB Gegenband erreicht',
    'MicroDots': 'Micro Dots Farbwechsel',
    'VMA_Trend': 'VMA Trend dreht',
    'Exhaustion': 'Gegenläufige Exhaustion',
    'VMA_Color': 'VMA Farbwechsel (primär)',
}


def generate_rule_text(indicators):
    entry_parts = [INDICATOR_ENTRY_LONG[ind] for ind in indicators]
    exit_parts = [INDICATOR_EXIT[ind] for ind in indicators]
    return {
        'entry_rule': 'LONG wenn ' + ' + '.join(entry_parts),
        'exit_rule': 'EXIT bei ' + ' oder '.join(exit_parts),
        'entry_short': ' + '.join([ind.replace('_', ' ') for ind in indicators]),
    }


# ============================================================
# SIGNAL COMBINATION MATRIX
# ============================================================
def analyze_all_combinations(df, initial_capital=INITIAL_CAPITAL):
    indicator_signals = extract_indicator_signals(df)
    n = len(df)
    combo_results = []

    for size in range(1, min(6, len(INDICATOR_NAMES) + 1)):
        for combo in combinations(INDICATOR_NAMES, size):
            combo_name = ' + '.join(combo)
            needed = len(combo)
            threshold = max(1, needed * 0.6)
            sigs = np.array([indicator_signals[ind_name] for ind_name in combo])
            votes_bull = np.sum(sigs == 1, axis=0)
            votes_bear = np.sum(sigs == -1, axis=0)
            combined = np.zeros(n)
            combined[votes_bull >= threshold] = 1
            combined[votes_bear >= threshold] = -1
            combined[0] = 0

            close_vals = df['close'].values
            equity = np.full(n, initial_capital, dtype=float)
            position = 0; entry_price = 0.0; position_size = 0.0
            trade_returns = []; trade_pnls = []

            for i in range(1, n):
                equity[i] = equity[i-1]
                if position != 0:
                    pnl = position * (close_vals[i] - close_vals[i-1]) * position_size
                    equity[i] += pnl
                sig = combined[i]
                if sig != 0 and sig != position:
                    if position != 0:
                        if position == 1:
                            ret = (close_vals[i] - entry_price) / entry_price if entry_price != 0 else 0
                            pnl_t = (close_vals[i] - entry_price) * position_size
                        else:
                            ret = (entry_price - close_vals[i]) / entry_price if entry_price != 0 else 0
                            pnl_t = (entry_price - close_vals[i]) * position_size
                        trade_returns.append(ret)
                        trade_pnls.append(pnl_t)
                    position = int(sig)
                    entry_price = close_vals[i]
                    position_size = equity[i] / close_vals[i]

            if len(trade_returns) < 3:
                continue

            winners = [r for r in trade_returns if r > 0]
            losers = [r for r in trade_returns if r <= 0]
            wr = len(winners) / len(trade_returns) * 100
            gp = sum(winners) if winners else 0
            gl = abs(sum(losers)) if losers else 0.0001
            pf = gp / gl if gl > 0 else 99.99
            total_ret = (equity[-1] / equity[0] - 1) * 100

            if len(trade_returns) > 1 and np.std(trade_returns) > 0:
                sharpe = np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(min(252, len(trade_returns)))
            else:
                sharpe = 0

            rules = generate_rule_text(list(combo))
            combo_results.append({
                'combination': combo_name,
                'indicators': list(combo),
                'num_indicators': len(combo),
                'total_trades': len(trade_returns),
                'win_rate': round(wr, 1),
                'profit_factor': round(min(pf, 99.99), 2),
                'sharpe_ratio': round(sharpe, 2),
                'total_return': round(total_ret, 2),
                'net_profit': round(equity[-1] - initial_capital, 2),
                'entry_rule': rules['entry_rule'],
                'exit_rule': rules['exit_rule'],
                'entry_short': rules['entry_short'],
            })

    combo_results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
    return combo_results


# ============================================================
# FOMO ANALYSIS
# ============================================================
def fomo_analysis(trades):
    if not trades:
        return {'has_data': False}

    all_returns = [t['return'] for t in trades]
    a_trades = [t for t in trades if t.get('is_a_setup', False)]
    b_trades = [t for t in trades if not t.get('is_a_setup', False)]
    a_returns = [t['return'] for t in a_trades]
    b_returns = [t['return'] for t in b_trades]

    all_wr = len([r for r in all_returns if r > 0]) / len(all_returns) * 100 if all_returns else 0
    a_wr = len([r for r in a_returns if r > 0]) / len(a_returns) * 100 if a_returns else 0
    b_wr = len([r for r in b_returns if r > 0]) / len(b_returns) * 100 if b_returns else 0
    all_avg = np.mean(all_returns) * 100 if all_returns else 0
    a_avg = np.mean(a_returns) * 100 if a_returns else 0
    b_avg = np.mean(b_returns) * 100 if b_returns else 0

    return {
        'has_data': True,
        'all_trades': len(all_returns),
        'all_win_rate': round(all_wr, 1),
        'all_avg_return': round(all_avg, 2),
        'a_setup_trades': len(a_returns),
        'a_setup_win_rate': round(a_wr, 1),
        'a_setup_avg_return': round(a_avg, 2),
        'b_setup_trades': len(b_returns),
        'b_setup_win_rate': round(b_wr, 1),
        'b_setup_avg_return': round(b_avg, 2),
        'fomo_cost_wr': round(all_wr - a_wr, 1) if a_returns else 0,
        'fomo_cost_return': round(all_avg - a_avg, 2) if a_returns else 0,
        'message': (
            f"Nur A-Setups: {round(a_wr,1)}% WR ({len(a_returns)} Trades) vs "
            f"Alle: {round(all_wr,1)}% WR ({len(all_returns)} Trades)"
        ),
    }


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
# EQUITY CURVE CHART
# ============================================================
def plot_equity_curves(all_results):
    fig, axes = plt.subplots(2, 1, figsize=(18, 13), facecolor='#0a0a0f')

    ax1 = axes[0]; ax1.set_facecolor('#14141e')
    plotted = False
    for key, data in all_results.items():
        ticker, tf = key
        if tf != 'Daily' or data.get('equity') is None: continue
        eq = data['equity']
        ax1.plot(range(len(eq)), eq, label=f'{ticker}', linewidth=1.2, alpha=0.85)
        plotted = True

    if plotted:
        ax1.set_title('Trend Suite (GRÄTZ) V4 — Equity Curves (Daily) — 19 Tickers (TradingView Max Data)',
                       color='white', fontsize=14, pad=10)
        ax1.set_ylabel('Portfolio Value (€)', color='#888')
        ax1.legend(loc='upper left', fontsize=7, facecolor='#1e1e2e',
                   edgecolor='#333', labelcolor='white', ncol=4)
        ax1.grid(True, alpha=0.1, color='#333')
        ax1.tick_params(colors='#888')
        for spine in ax1.spines.values(): spine.set_color('#333')

    ax2 = axes[1]; ax2.set_facecolor('#14141e')
    daily_equities = []
    for key, data in all_results.items():
        ticker, tf = key
        if tf == 'Daily' and data.get('equity') is not None:
            eq = np.array(data['equity'])
            daily_equities.append(eq / eq[0])

    if daily_equities:
        min_len = min(len(e) for e in daily_equities)
        combined = np.mean([e[:min_len] for e in daily_equities], axis=0) * INITIAL_CAPITAL
        ax2.plot(range(min_len), combined, color='#00d4aa', linewidth=2)
        ax2.fill_between(range(min_len), INITIAL_CAPITAL, combined,
                         where=combined >= INITIAL_CAPITAL, alpha=0.15, color='#00d4aa')
        ax2.fill_between(range(min_len), INITIAL_CAPITAL, combined,
                         where=combined < INITIAL_CAPITAL, alpha=0.15, color='#ff4757')
        ax2.axhline(y=INITIAL_CAPITAL, color='#444', linestyle='--', linewidth=0.8)
        ax2.set_title(f'Combined Equal-Weight Portfolio ({len(daily_equities)} Tickers)',
                       color='white', fontsize=14, pad=10)
        ax2.set_ylabel('Portfolio Value (€)', color='#888')
        ax2.set_xlabel('Trading Days', color='#888')
        ax2.grid(True, alpha=0.1, color='#333')
        ax2.tick_params(colors='#888')
        for spine in ax2.spines.values(): spine.set_color('#333')

    plt.tight_layout()
    plt.savefig(str(EQUITY_PNG), dpi=150, facecolor='#0a0a0f', bbox_inches='tight')
    plt.close()
    print(f"  ✅ Equity curve saved: {EQUITY_PNG}")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("TREND SUITE (GRÄTZ) BACKTESTER V4 — TRADINGVIEW MAX DATA")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tickers ({len(TICKERS)}): {', '.join(TICKERS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Initial Capital: {INITIAL_CAPITAL:,} EUR | Commission: {COMMISSION}")
    print(f"Data Source: {CSV_DATA_DIR}")
    print()

    all_results = {}
    results_json = {
        'meta': {
            'generated': datetime.now().isoformat(),
            'version': 'V4',
            'data_source': 'TradingView CSV (tradingview-max)',
            'initial_capital': INITIAL_CAPITAL,
            'commission': COMMISSION,
            'currency': 'EUR',
            'tickers': TICKERS,
            'ticker_count': len(TICKERS),
            'timeframes': TIMEFRAMES,
            'components': [
                'Reversal Bars', 'TrendLine', 'Bollinger Bands',
                'Micro Dots', 'VMA Trend Line (+ Color Change)',
                'Exhaustion Lines', '24h Volume Filter'
            ],
            'features': [
                'VMA Color Change Primary Signal',
                'A-Setup (direct Red→Green) vs B-Setup (Red→Yellow→Green)',
                'Exhaustive Signal Combination Matrix (all combos)',
                'FOMO Analysis',
                'Full TradingView Strategy Tester Metrics',
                'Dynamic VMA Stop Loss',
                'Extended Data Periods (tradingview-max)',
                '5 Timeframes incl. 15min',
            ],
        },
        'results': [],
        'combination_rankings': {},
        'best_per_ticker': [],
        'fomo_analysis': {},
        'summary': {}
    }

    total_runs = len(TICKERS) * len(TIMEFRAMES)
    run_idx = 0
    total_bars = 0

    for ticker in TICKERS:
        for tf_key in TIMEFRAMES:
            run_idx += 1
            label = f"{ticker} / {tf_key}"
            print(f"[{run_idx}/{total_runs}] 📊 {label}...")

            try:
                df = fetch_data(ticker, tf_key)
                if df is None or len(df) < 50:
                    bars = 0 if df is None else len(df)
                    print(f"  ⚠️ Insufficient data ({bars} bars)")
                    continue

                date_info = get_date_range(df)
                total_bars += date_info['bars']
                print(f"  📅 {date_info['label']}")

                # Calculate all indicators
                df = calc_bollinger(df)
                df = calc_reversals(df)
                df = calc_supertrend(df)
                df = calc_vma_trend(df, vma_length=9)
                df = calc_micro_dots(df)
                df = calc_exhaustion(df)
                df = generate_signals(df)
                df, trades = backtest(df)

                # Full metrics
                metrics = calc_metrics(trades, df['equity'].values, INITIAL_CAPITAL)
                fomo = fomo_analysis(trades)

                # Signal combination matrix (skip 5min and 15min — too many bars)
                combo_ranking = []
                if tf_key not in ('5min', '15min'):
                    print(f"  🔬 Testing indicator combinations...")
                    combo_ranking = analyze_all_combinations(df)
                best_combo = combo_ranking[0] if combo_ranking else None
                top3 = combo_ranking[:3] if combo_ranking else []
                for rank, cr in enumerate(top3, 1):
                    print(f"     #{rank}: {cr['combination']} — "
                          f"WR {cr['win_rate']}%, Sharpe {cr['sharpe_ratio']}, "
                          f"PF {cr['profit_factor']}, Ret {cr['total_return']}%")

                print(f"  ✅ {date_info['bars']} bars | {metrics['total_trades']} trades | "
                      f"WR: {metrics['win_rate']}% | Net: {metrics['net_profit']:.0f}€ ({metrics['net_profit_pct']:.1f}%) | "
                      f"Sharpe: {metrics['sharpe_ratio']} | MDD: {metrics['max_drawdown_pct']:.1f}%")
                if fomo.get('has_data') and fomo.get('a_setup_trades', 0) > 0:
                    print(f"  🎯 FOMO: {fomo['message']}")

                all_results[(ticker, tf_key)] = {
                    'equity': df['equity'].values.tolist(),
                    'dates': list(range(len(df))),
                    'metrics': metrics,
                }

                # Strip histories from per-result JSON to keep file manageable
                metrics_for_json = {k: v for k, v in metrics.items()
                                    if k not in ('runup_history', 'drawdown_history')}
                result_entry = {
                    'ticker': ticker,
                    'timeframe': tf_key,
                    'date_range': date_info,
                    'bars': date_info['bars'],
                    'metrics': metrics_for_json,
                    'fomo': fomo,
                    'best_combination': best_combo,
                }
                results_json['results'].append(result_entry)

                key = f"{ticker}_{tf_key}"
                if combo_ranking:
                    results_json['combination_rankings'][key] = combo_ranking[:15]
                if fomo.get('has_data'):
                    results_json['fomo_analysis'][key] = fomo

            except Exception as e:
                print(f"  ❌ Error: {e}")
                traceback.print_exc()

    # Equity curve chart
    print(f"\n📈 Generating equity curves for {len(all_results)} results...")
    plot_equity_curves(all_results)

    # Best per ticker
    for r in results_json['results']:
        bc = r.get('best_combination')
        if bc:
            dr = r.get('date_range', {})
            results_json['best_per_ticker'].append({
                'ticker': r['ticker'], 'timeframe': r['timeframe'],
                'date_range_label': dr.get('label', ''),
                'start': dr.get('start', '?'), 'end': dr.get('end', '?'),
                'bars': dr.get('bars', 0), 'months': dr.get('months', 0),
                'best_combination': bc['combination'],
                'entry_rule': bc.get('entry_rule', ''),
                'exit_rule': bc.get('exit_rule', ''),
                'total_trades': bc['total_trades'],
                'win_rate': bc['win_rate'],
                'sharpe_ratio': bc['sharpe_ratio'],
                'profit_factor': bc['profit_factor'],
                'total_return': bc['total_return'],
                'default_win_rate': r['metrics']['win_rate'],
                'default_return': r['metrics']['total_return'],
                'default_sharpe': r['metrics']['sharpe_ratio'],
            })

    # Summary statistics
    all_with_trades = [r for r in results_json['results'] if r['metrics']['total_trades'] > 0]
    daily_results = [r for r in all_with_trades if r['timeframe'] == 'Daily']

    def _avg(lst, key):
        vals = [r['metrics'][key] for r in lst if r['metrics'].get(key) is not None]
        return round(np.mean(vals), 2) if vals else 0

    if all_with_trades:
        # Best combo overall
        best_combo_overall = None
        if results_json['combination_rankings']:
            all_top = []
            for key, combos in results_json['combination_rankings'].items():
                if combos: all_top.append({'source': key, **combos[0]})
            if all_top:
                best_combo_overall = max(all_top, key=lambda x: x['sharpe_ratio'])

        results_json['summary'] = {
            'total_bars_processed': total_bars,
            'total_results': len(all_with_trades),
            'total_tickers': len(TICKERS),
            'total_timeframes': len(TIMEFRAMES),
            # Averages across ALL timeframes
            'avg_win_rate': _avg(all_with_trades, 'win_rate'),
            'avg_sharpe': _avg(all_with_trades, 'sharpe_ratio'),
            'avg_total_return': _avg(all_with_trades, 'total_return'),
            'avg_net_profit': _avg(all_with_trades, 'net_profit'),
            'avg_max_drawdown_pct': _avg(all_with_trades, 'max_drawdown_pct'),
            'avg_profit_factor': _avg(all_with_trades, 'profit_factor'),
            'avg_percent_profitable': _avg(all_with_trades, 'percent_profitable'),
            'avg_ratio_win_loss': _avg(all_with_trades, 'ratio_avg_win_loss'),
            # Daily-specific
            'daily_avg_win_rate': _avg(daily_results, 'win_rate') if daily_results else 0,
            'daily_avg_sharpe': _avg(daily_results, 'sharpe_ratio') if daily_results else 0,
            'daily_avg_return': _avg(daily_results, 'total_return') if daily_results else 0,
            'daily_avg_net_profit': _avg(daily_results, 'net_profit') if daily_results else 0,
            # A-Setup
            'avg_a_setup_win_rate': round(np.mean([
                r['metrics']['a_setup_win_rate'] for r in all_with_trades
                if r['metrics']['a_setup_trades'] > 0
            ]), 1) if any(r['metrics']['a_setup_trades'] > 0 for r in all_with_trades) else 0,
            # Bests
            'best_ticker_daily': max(daily_results, key=lambda r: r['metrics']['total_return'])['ticker'] if daily_results else 'N/A',
            'worst_ticker_daily': min(daily_results, key=lambda r: r['metrics']['total_return'])['ticker'] if daily_results else 'N/A',
            'best_combination': best_combo_overall,
        }

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(RESULTS_JSON), 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\n✅ Results saved: {RESULTS_JSON}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if results_json.get('summary'):
        s = results_json['summary']
        print(f"  Total Bars Processed: {s['total_bars_processed']:,}")
        print(f"  Total Results:        {s['total_results']}")
        print(f"  Tickers × TFs:        {s['total_tickers']} × {s['total_timeframes']}")
        print(f"  Avg Win Rate:         {s['avg_win_rate']}%")
        print(f"  Avg Sharpe:           {s['avg_sharpe']}")
        print(f"  Avg Total Return:     {s['avg_total_return']}%")
        print(f"  Avg Net Profit:       {s['avg_net_profit']}€")
        print(f"  Avg Max Drawdown:     {s['avg_max_drawdown_pct']}%")
        print(f"  Avg Profit Factor:    {s['avg_profit_factor']}")
        print(f"  Avg Win/Loss Ratio:   {s['avg_ratio_win_loss']}")
        print(f"  A-Setup Avg WR:       {s['avg_a_setup_win_rate']}%")
        if daily_results:
            print(f"  --- Daily Only ---")
            print(f"  Daily Avg WR:         {s['daily_avg_win_rate']}%")
            print(f"  Daily Avg Sharpe:     {s['daily_avg_sharpe']}")
            print(f"  Daily Avg Return:     {s['daily_avg_return']}%")
            print(f"  Best (Daily):         {s['best_ticker_daily']}")
            print(f"  Worst (Daily):        {s['worst_ticker_daily']}")
        if s.get('best_combination'):
            bc = s['best_combination']
            print(f"  Best Combo:           {bc['combination']} (Sharpe {bc['sharpe_ratio']})")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return results_json


if __name__ == '__main__':
    results = main()
