import pandas as pd
import numpy as np
import json
import logging
from uuid import uuid4
try:
    from scipy.signal import argrelextrema
except ImportError:
    pass

logger = logging.getLogger("asymptote-lt.pattern_matcher")


# ─── PRE-COMPUTE HELPERS ───────────────────────────────────────────────

def _precompute_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add reusable rolling columns once so individual checks don't recalculate."""
    if '_precomputed' in df.columns:
        return df
    df = df.copy()
    rng = df['high'] - df['low']
    df['_range'] = rng
    df['_avg_range_20'] = rng.rolling(20, min_periods=1).mean()
    df['_body'] = (df['close'] - df['open']).abs()
    df['_avg_body_20'] = df['_body'].rolling(20, min_periods=1).mean()
    df['_upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['_lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['_body_top'] = df[['open', 'close']].max(axis=1)
    df['_body_bottom'] = df[['open', 'close']].min(axis=1)
    df['_is_green'] = df['close'] > df['open']
    df['_is_red'] = df['close'] < df['open']
    df['_precomputed'] = True
    return df


def _is_downtrend(df: pd.DataFrame, i: int, lookback: int = 20) -> bool:
    """Simple trend check: SMA now vs SMA a few bars ago."""
    if i < lookback + 5:
        return False
    sma_now = df['close'].iloc[i - lookback: i + 1].mean()
    sma_prev = df['close'].iloc[i - lookback - 5: i - 5 + 1].mean()
    return sma_now < sma_prev


def _is_uptrend(df: pd.DataFrame, i: int, lookback: int = 20) -> bool:
    if i < lookback + 5:
        return False
    sma_now = df['close'].iloc[i - lookback: i + 1].mean()
    sma_prev = df['close'].iloc[i - lookback - 5: i - 5 + 1].mean()
    return sma_now > sma_prev


# ─── ATOMIC CANDLESTICK LOGIC ──────────────────────────────────────────

def check_marubozu(df: pd.DataFrame, i: int) -> bool:
    body = df['_body'].iloc[i]
    total_range = df['_range'].iloc[i]
    if total_range == 0:
        return False
    if (body / total_range) < 0.90:
        return False
    # Require the candle is meaningful relative to recent context
    avg_body = df['_avg_body_20'].iloc[i]
    if pd.notna(avg_body) and body < avg_body * 0.7:
        return False
    return True


def check_doji(df: pd.DataFrame, i: int) -> str | None:
    body = df['_body'].iloc[i]
    total_range = df['_range'].iloc[i]
    if total_range == 0:
        return None
    if (body / total_range) > 0.10:
        return None

    upper_shadow = df['_upper_shadow'].iloc[i]
    lower_shadow = df['_lower_shadow'].iloc[i]

    # Dragonfly: virtually no upper shadow, long lower shadow
    if upper_shadow <= total_range * 0.1 and lower_shadow >= total_range * 0.8:
        return "dragonfly"
    # Gravestone: virtually no lower shadow, long upper shadow
    if lower_shadow <= total_range * 0.1 and upper_shadow >= total_range * 0.8:
        return "gravestone"
    # Long-Legged Doji: both shadows long, range much larger than average
    avg_range = df['_avg_range_20'].iloc[i]
    if pd.notna(avg_range) and total_range > avg_range * 1.5:
        return "long_legged"
    return "standard"


def check_spinning_top(df: pd.DataFrame, i: int) -> bool:
    body = df['_body'].iloc[i]
    total_range = df['_range'].iloc[i]
    if total_range == 0:
        return False
    upper_shadow = df['_upper_shadow'].iloc[i]
    lower_shadow = df['_lower_shadow'].iloc[i]
    ratio = body / total_range

    is_small_body = 0.10 < ratio <= 0.30
    is_symmetrical = abs(upper_shadow - lower_shadow) / total_range < 0.20
    if not (is_small_body and is_symmetrical):
        return False
    # Exclude if it qualifies as a high-wave candle
    if check_high_wave(df, i):
        return False
    return True


def check_high_wave(df: pd.DataFrame, i: int) -> bool:
    body = df['_body'].iloc[i]
    total_range = df['_range'].iloc[i]
    if total_range == 0:
        return False
    avg_range = df['_avg_range_20'].iloc[i]
    if not pd.notna(avg_range):
        return False
    return (body / total_range) <= 0.20 and total_range > avg_range * 2.5


def check_hammer_star_variants(df: pd.DataFrame, i: int) -> str | None:
    body = df['_body'].iloc[i]
    total_range = df['_range'].iloc[i]
    if total_range == 0:
        return None

    upper_shadow = df['_upper_shadow'].iloc[i]
    lower_shadow = df['_lower_shadow'].iloc[i]

    # Allow very small bodies (dragonfly-hammer hybrids) but range must exist
    # Hammer / Hanging Man: body near top, long lower shadow
    if upper_shadow < total_range * 0.20 and lower_shadow >= max(2 * body, total_range * 0.60):
        if _is_downtrend(df, i):
            return "hammer"
        if _is_uptrend(df, i):
            return "hanging_man"
        return None

    # Inverted Hammer / Shooting Star: body near bottom, long upper shadow
    if lower_shadow < total_range * 0.20 and upper_shadow >= max(2 * body, total_range * 0.60):
        if _is_downtrend(df, i):
            return "inverted_hammer"
        if _is_uptrend(df, i):
            return "shooting_star"
        return None

    return None


def check_belt_hold(df: pd.DataFrame, i: int) -> str | None:
    o, c, h, l = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
    body = abs(c - o)
    total_range = h - l
    if total_range == 0 or body / total_range < 0.80:
        return None
    # Require the candle is large relative to context
    avg_range = df['_avg_range_20'].iloc[i]
    if pd.notna(avg_range) and total_range < avg_range * 0.80:
        return None
    # Bullish Belt Hold: open == low
    if abs(o - l) / total_range < 0.02 and c > o:
        return "bullish"
    # Bearish Belt Hold: open == high
    if abs(o - h) / total_range < 0.02 and c < o:
        return "bearish"
    return None


def check_engulfing(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    curr_o, curr_c = df['open'].iloc[i], df['close'].iloc[i]
    prev_o, prev_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    curr_body = abs(curr_c - curr_o)
    avg_body = df['_avg_body_20'].iloc[i]

    # Reject if the engulfing candle's body is too small relative to context
    if pd.notna(avg_body) and curr_body < avg_body * 0.50:
        return None

    # Bullish: previous red, current green, current body engulfs previous body
    if prev_c < prev_o and curr_c > curr_o:
        if curr_c > prev_o and curr_o < prev_c:
            return "bullish"
    # Bearish: previous green, current red, current body engulfs previous body
    if prev_c > prev_o and curr_c < curr_o:
        if curr_o > prev_c and curr_c < prev_o:
            return "bearish"
    return None


def check_harami(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c, c_h, c_l = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]

    p_body_top = max(p_o, p_c)
    p_body_bottom = min(p_o, p_c)
    c_body_top = max(c_o, c_c)
    c_body_bottom = min(c_o, c_c)

    # Second candle body AND shadows must be inside first candle body
    if not (c_body_top < p_body_top and c_body_bottom > p_body_bottom):
        return None
    if c_h > p_body_top or c_l < p_body_bottom:
        return None

    c_range = c_h - c_l
    is_cross = (c_range > 0 and abs(c_o - c_c) / c_range <= 0.10)

    # Direction is determined by the FIRST candle's color
    if p_c < p_o:
        # First candle red → bullish harami
        return "bullish_harami_cross" if is_cross else "bullish_harami"
    else:
        # First candle green → bearish harami
        return "bearish_harami_cross" if is_cross else "bearish_harami"


def check_piercing_dark_cloud(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]
    avg_body = df['_avg_body_20'].iloc[i]

    p_body = abs(p_c - p_o)
    c_body = abs(c_c - c_o)
    # Both candles must be reasonably large
    if pd.notna(avg_body) and (p_body < avg_body * 0.70 or c_body < avg_body * 0.70):
        return None

    # Piercing Line: Red → Green, green opens below red close, closes above 50 % of red body
    if p_c < p_o and c_c > c_o and c_o < p_c:
        if c_c > (p_o + p_c) / 2:
            return "piercing_line"

    # Dark Cloud Cover: Green → Red, red opens above green close, closes below 50 % of green body
    if p_c > p_o and c_c < c_o and c_o > p_c:
        if c_c < (p_o + p_c) / 2:
            return "dark_cloud_cover"
    return None


def check_tweezer(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]
    p_h, p_l = df['high'].iloc[i - 1], df['low'].iloc[i - 1]
    c_h, c_l = df['high'].iloc[i], df['low'].iloc[i]

    # Tweezer Top: in uptrend, first green then red, identical highs
    if abs(p_h - c_h) / max(p_h, 0.0001) < 0.001:
        if p_c > p_o and c_c < c_o and _is_uptrend(df, i):
            return "tweezer_top"

    # Tweezer Bottom: in downtrend, first red then green, identical lows
    if abs(p_l - c_l) / max(p_l, 0.0001) < 0.001:
        if p_c < p_o and c_c > c_o and _is_downtrend(df, i):
            return "tweezer_bottom"
    return None


def check_kicker(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]

    # Bullish Kicker: prev red, curr green, entire curr body gaps above prev open
    if p_c < p_o and c_c > c_o:
        if min(c_o, c_c) >= p_o:
            return "bullish_kicker"
    # Bearish Kicker: prev green, curr red, entire curr body gaps below prev open
    if p_c > p_o and c_c < c_o:
        if max(c_o, c_c) <= p_o:
            return "bearish_kicker"
    return None


def check_counterattack(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]

    # Opposite coloured candles with (nearly) identical closes
    if p_c < p_o and c_c > c_o:
        if abs(p_c - c_c) / max(abs(p_c), 0.0001) < 0.001:
            return "bullish_counterattack"
    if p_c > p_o and c_c < c_o:
        if abs(p_c - c_c) / max(abs(p_c), 0.0001) < 0.001:
            return "bearish_counterattack"
    return None


def check_separating_lines(df: pd.DataFrame, i: int) -> str | None:
    if i < 1:
        return None
    p_o, p_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]

    # Same open, opposite directions — continuation pattern
    if abs(p_o - c_o) / max(abs(p_o), 0.0001) < 0.001:
        if p_c < p_o and c_c > c_o:
            return "bullish_separating_lines"
        if p_c > p_o and c_c < c_o:
            return "bearish_separating_lines"
    return None


# ─── MULTI-CANDLE LOGIC ────────────────────────────────────────────────

def check_abandoned_baby(df: pd.DataFrame, i: int) -> str | None:
    if i < 2:
        return None
    o1, c1, h1, l1 = df['open'].iloc[i - 2], df['close'].iloc[i - 2], df['high'].iloc[i - 2], df['low'].iloc[i - 2]
    o2, c2, h2, l2 = df['open'].iloc[i - 1], df['close'].iloc[i - 1], df['high'].iloc[i - 1], df['low'].iloc[i - 1]
    o3, c3, h3, l3 = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]

    # 2nd candle must be a doji
    range2 = h2 - l2
    if range2 == 0:
        return None
    if abs(o2 - c2) / range2 > 0.10:
        return None

    # Candles 1 and 3 should have meaningful bodies
    avg_body = df['_avg_body_20'].iloc[i]
    p1_body = abs(c1 - o1)
    p3_body = abs(c3 - o3)
    if pd.notna(avg_body) and (p1_body < avg_body * 0.70 or p3_body < avg_body * 0.70):
        return None

    # Bullish: 1st red, doji gaps down (h2 < l1), 3rd green gaps up (l3 > h2)
    if c1 < o1 and l1 > h2 and l3 > h2 and c3 > o3:
        return "bullish_abandoned_baby"
    # Bearish: 1st green, doji gaps up (l2 > h1), 3rd red gaps down (h3 < l2)
    if c1 > o1 and l2 > h1 and h3 < l2 and c3 < o3:
        return "bearish_abandoned_baby"
    return None


def check_three_inside_outside(df: pd.DataFrame, i: int) -> str | None:
    if i < 2:
        return None

    # --- Three Inside Up / Down ---
    h_type = check_harami(df, i - 1)
    if h_type:
        p_body_top = max(df['open'].iloc[i - 2], df['close'].iloc[i - 2])
        p_body_bottom = min(df['open'].iloc[i - 2], df['close'].iloc[i - 2])
        c_c = df['close'].iloc[i]
        if "bullish" in h_type and c_c > p_body_top:
            return "three_inside_up"
        if "bearish" in h_type and c_c < p_body_bottom:
            return "three_inside_down"

    # --- Three Outside Up / Down ---
    e_type = check_engulfing(df, i - 1)
    if e_type:
        c_c = df['close'].iloc[i]
        p_c = df['close'].iloc[i - 1]
        if e_type == "bullish" and c_c > p_c:
            return "three_outside_up"
        if e_type == "bearish" and c_c < p_c:
            return "three_outside_down"
    return None


def check_three_methods(df: pd.DataFrame, i: int) -> str | None:
    if i < 4:
        return None
    c1_o, c1_c = df['open'].iloc[i - 4], df['close'].iloc[i - 4]
    avg_body = df['_avg_body_20'].iloc[i]

    # ── Rising Three Methods ──
    # 1st candle must be green and large
    if c1_c > c1_o:
        first_body = c1_c - c1_o
        if pd.notna(avg_body) and first_body < avg_body * 1.5:
            pass  # not large enough, skip rising
        else:
            # Middle candles (2,3,4) must stay inside 1st candle's range
            valid = True
            for idx in range(i - 3, i):
                if df['high'].iloc[idx] > c1_c or df['low'].iloc[idx] < c1_o:
                    valid = False
                    break
            if valid:
                # 5th candle green, closes above 1st candle close
                if df['close'].iloc[i] > df['open'].iloc[i] and df['close'].iloc[i] > c1_c:
                    return "rising_three_methods"

    # ── Falling Three Methods ──
    # 1st candle must be red and large
    if c1_c < c1_o:
        first_body = c1_o - c1_c
        if pd.notna(avg_body) and first_body < avg_body * 1.5:
            pass  # not large enough, skip falling
        else:
            valid = True
            for idx in range(i - 3, i):
                if df['high'].iloc[idx] > c1_o or df['low'].iloc[idx] < c1_c:
                    valid = False
                    break
            if valid:
                if df['close'].iloc[i] < df['open'].iloc[i] and df['close'].iloc[i] < c1_c:
                    return "falling_three_methods"

    return None


def check_three_line_strike(df: pd.DataFrame, i: int) -> str | None:
    if i < 3:
        return None
    avg_body = df['_avg_body_20'].iloc[i]

    c1_o, c1_c = df['open'].iloc[i - 3], df['close'].iloc[i - 3]
    c2_o, c2_c = df['open'].iloc[i - 2], df['close'].iloc[i - 2]
    c3_o, c3_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c4_o, c4_c = df['open'].iloc[i], df['close'].iloc[i]

    # Validate first three candles have meaningful bodies
    if pd.notna(avg_body):
        for (o, c) in [(c1_o, c1_c), (c2_o, c2_c), (c3_o, c3_c)]:
            if abs(c - o) < avg_body * 0.50:
                return None
        # 4th candle must be significantly larger
        if abs(c4_c - c4_o) < avg_body * 1.50:
            return None

    # Bullish: 3 consecutive red with lower closes, 4th green engulfs all three
    if (c1_c < c1_o and c2_c < c2_o and c3_c < c3_o and
            c2_c < c1_c and c3_c < c2_c):
        if c4_c > c4_o and c4_c > c1_o and c4_o < c3_c:
            return "bullish_three_line_strike"

    # Bearish: 3 consecutive green with higher closes, 4th red engulfs all three
    if (c1_c > c1_o and c2_c > c2_o and c3_c > c3_o and
            c2_c > c1_c and c3_c > c2_c):
        if c4_c < c4_o and c4_c < c1_o and c4_o > c3_c:
            return "bearish_three_line_strike"
    return None


def check_stick_sandwich(df: pd.DataFrame, i: int) -> bool:
    if i < 2:
        return False
    c1_o, c1_c = df['open'].iloc[i - 2], df['close'].iloc[i - 2]
    c2_o, c2_c = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    c3_o, c3_c = df['open'].iloc[i], df['close'].iloc[i]

    # Red, Green, Red with identical closes on 1st and 3rd
    if c1_c < c1_o and c2_c > c2_o and c3_c < c3_o:
        if abs(c1_c - c3_c) / max(abs(c1_c), 0.0001) < 0.001:
            return True
    return False


def check_morning_star(df: pd.DataFrame, i: int) -> bool:
    if i < 2:
        return False
    o1, c1 = df['open'].iloc[i - 2], df['close'].iloc[i - 2]
    o2, c2 = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    o3, c3 = df['open'].iloc[i], df['close'].iloc[i]

    # 1st: red
    if c1 >= o1:
        return False
    # 2nd: gaps down (body below 1st body bottom)
    if max(o2, c2) >= min(o1, c1):
        return False
    # 3rd: green, closes above mid of 1st body
    if c3 <= o3 or c3 <= (o1 + c1) / 2.0:
        return False

    # Body-size validation
    avg_body = df['_avg_body_20'].iloc[i]
    if pd.notna(avg_body):
        if abs(c1 - o1) < avg_body * 0.70:
            return False
        if abs(c3 - o3) < avg_body * 0.70:
            return False
        if abs(c2 - o2) > avg_body * 0.50:
            return False
    return True


def check_evening_star(df: pd.DataFrame, i: int) -> bool:
    if i < 2:
        return False
    o1, c1 = df['open'].iloc[i - 2], df['close'].iloc[i - 2]
    o2, c2 = df['open'].iloc[i - 1], df['close'].iloc[i - 1]
    o3, c3 = df['open'].iloc[i], df['close'].iloc[i]

    # 1st: green
    if c1 <= o1:
        return False
    # 2nd: gaps up
    if min(o2, c2) <= max(o1, c1):
        return False
    # 3rd: red, closes below mid of 1st body
    if c3 >= o3 or c3 >= (o1 + c1) / 2.0:
        return False

    avg_body = df['_avg_body_20'].iloc[i]
    if pd.notna(avg_body):
        if abs(c1 - o1) < avg_body * 0.70:
            return False
        if abs(c3 - o3) < avg_body * 0.70:
            return False
        if abs(c2 - o2) > avg_body * 0.50:
            return False
    return True


def check_three_white_soldiers(df: pd.DataFrame, i: int) -> bool:
    if i < 2:
        return False
    candles = [
        (df['open'].iloc[i - 2], df['close'].iloc[i - 2], df['high'].iloc[i - 2]),
        (df['open'].iloc[i - 1], df['close'].iloc[i - 1], df['high'].iloc[i - 1]),
        (df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i])
    ]
    prev_c = 0
    for idx, (o, c, h) in enumerate(candles):
        if c <= o:
            return False  # must be green
        if c < h * 0.99:
            return False  # short upper shadow
        if idx > 0:
            prev_o, prev_c_val, _ = candles[idx - 1]
            prev_body_low = min(prev_o, prev_c_val)
            prev_body_high = max(prev_o, prev_c_val)
            # Current open should be within previous body
            if not (prev_body_low <= o <= prev_body_high):
                return False
            if c <= prev_c:
                return False  # must have higher close
        prev_c = c
    return True


def check_three_black_crows(df: pd.DataFrame, i: int) -> bool:
    if i < 2:
        return False
    candles = [
        (df['open'].iloc[i - 2], df['close'].iloc[i - 2], df['low'].iloc[i - 2]),
        (df['open'].iloc[i - 1], df['close'].iloc[i - 1], df['low'].iloc[i - 1]),
        (df['open'].iloc[i], df['close'].iloc[i], df['low'].iloc[i])
    ]
    prev_c = float('inf')
    for idx, (o, c, l) in enumerate(candles):
        if c >= o:
            return False  # must be red
        if c > l * 1.01:
            return False  # short lower shadow
        if idx > 0:
            prev_o, prev_c_val, _ = candles[idx - 1]
            prev_body_low = min(prev_o, prev_c_val)
            prev_body_high = max(prev_o, prev_c_val)
            if not (prev_body_low <= o <= prev_body_high):
                return False
            if c >= prev_c:
                return False
        prev_c = c
    return True


# ─── CHART GEOMETRY LOGIC ──────────────────────────────────────────────

def get_pivots(df: pd.DataFrame, order: int = 5):
    try:
        from scipy.signal import argrelextrema
        highs = argrelextrema(df['high'].values, np.greater, order=order)[0]
        lows = argrelextrema(df['low'].values, np.less, order=order)[0]
        return highs, lows
    except ImportError:
        logger.warning("scipy not available – chart geometry patterns disabled")
        return np.array([]), np.array([])


def check_double_top(df: pd.DataFrame, highs, i: int) -> bool:
    valid_highs = [h for h in highs if h <= i]
    if len(valid_highs) < 2:
        return False
    p1, p2 = valid_highs[-2], valid_highs[-1]
    if i - p2 > 10:
        return False
    if p2 - p1 < 5:
        return False  # need minimum separation
    price1, price2 = df['high'].iloc[p1], df['high'].iloc[p2]
    if abs(price1 - price2) / price1 >= 0.03:
        return False
    # Require a meaningful trough between the two peaks
    trough = df['low'].iloc[p1:p2 + 1].min()
    avg_peak = (price1 + price2) / 2
    if (avg_peak - trough) / avg_peak < 0.02:
        return False
    return True


def check_double_bottom(df: pd.DataFrame, lows, i: int) -> bool:
    valid_lows = [l for l in lows if l <= i]
    if len(valid_lows) < 2:
        return False
    p1, p2 = valid_lows[-2], valid_lows[-1]
    if i - p2 > 10:
        return False
    if p2 - p1 < 5:
        return False
    price1, price2 = df['low'].iloc[p1], df['low'].iloc[p2]
    if abs(price1 - price2) / price1 >= 0.03:
        return False
    # Require a meaningful peak between the two troughs
    peak = df['high'].iloc[p1:p2 + 1].max()
    avg_trough = (price1 + price2) / 2
    if (peak - avg_trough) / avg_trough < 0.02:
        return False
    return True


def check_head_and_shoulders(df: pd.DataFrame, highs, lows, i: int) -> str | None:
    valid_highs = [h for h in highs if h <= i]
    if len(valid_highs) < 3:
        return None
    p1, p2, p3 = valid_highs[-3], valid_highs[-2], valid_highs[-1]
    if i - p3 > 10:
        return None

    h1, h2, h3 = df['high'].iloc[p1], df['high'].iloc[p2], df['high'].iloc[p3]
    if not (h2 > h1 and h2 > h3):
        return None
    if abs(h1 - h3) / h1 >= 0.05:
        return None

    # Validate neckline: troughs between peaks should be roughly horizontal
    trough1 = df['low'].iloc[p1:p2 + 1].min()
    trough2 = df['low'].iloc[p2:p3 + 1].min()
    if abs(trough1 - trough2) / trough1 > 0.03:
        return None

    # Price should be near or breaking the neckline
    neckline = (trough1 + trough2) / 2
    if df['close'].iloc[i] > neckline * 1.02:
        return None  # hasn't broken neckline yet
    return "bearish"


def check_inv_head_and_shoulders(df: pd.DataFrame, highs, lows, i: int) -> str | None:
    valid_lows = [l for l in lows if l <= i]
    if len(valid_lows) < 3:
        return None
    p1, p2, p3 = valid_lows[-3], valid_lows[-2], valid_lows[-1]
    if i - p3 > 10:
        return None

    l1, l2, l3 = df['low'].iloc[p1], df['low'].iloc[p2], df['low'].iloc[p3]
    if not (l2 < l1 and l2 < l3):
        return None
    if abs(l1 - l3) / l1 >= 0.05:
        return None

    # Neckline: peaks between the troughs
    peak1 = df['high'].iloc[p1:p2 + 1].max()
    peak2 = df['high'].iloc[p2:p3 + 1].max()
    if abs(peak1 - peak2) / peak1 > 0.03:
        return None

    neckline = (peak1 + peak2) / 2
    if df['close'].iloc[i] < neckline * 0.98:
        return None
    return "bullish"


def check_triple_top(df: pd.DataFrame, highs, i: int) -> bool:
    valid = [h for h in highs if h <= i]
    if len(valid) < 3:
        return False
    p1, p2, p3 = valid[-3], valid[-2], valid[-1]
    if i - p3 > 15:
        return False
    vals = [df['high'].iloc[p] for p in [p1, p2, p3]]
    avg = sum(vals) / 3
    return all(abs(v - avg) / avg < 0.03 for v in vals)


def check_triple_bottom(df: pd.DataFrame, lows, i: int) -> bool:
    valid = [l for l in lows if l <= i]
    if len(valid) < 3:
        return False
    p1, p2, p3 = valid[-3], valid[-2], valid[-1]
    if i - p3 > 15:
        return False
    vals = [df['low'].iloc[p] for p in [p1, p2, p3]]
    avg = sum(vals) / 3
    return all(abs(v - avg) / avg < 0.03 for v in vals)


# ─── SPECIALIZED PATTERNS: DOUBLE BOTTOMS/TOPS & EMA KNOTS ─────────────

def check_double_bottom_specialized(df: pd.DataFrame, i: int) -> bool:
    """
    Double Bottom Pattern with RSI + MACD divergence.
    The formation candle is RED.  The confirmation (next GREEN candle) is
    checked separately so the two are evaluated on consecutive bars.
    """
    if i < 30:
        return False

    curr_low = df['low'].iloc[i]
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]

    # Formation candle is red
    if curr_close >= curr_open:
        return False

    # Current low should be at or below the previous candle's low
    prev_low = df['low'].iloc[i - 1]
    if curr_low > prev_low:
        return False

    # Find first swing-low in the lookback window via argrelextrema
    lookback_start = max(0, i - 25)
    try:
        from scipy.signal import argrelextrema
        window = df['low'].iloc[lookback_start:i].values
        rel_lows = argrelextrema(window, np.less, order=3)[0]
    except Exception:
        rel_lows = np.array([])

    if len(rel_lows) == 0:
        return False

    first_bottom_idx = lookback_start + int(rel_lows[-1])

    # The two lows should be similar (within 3 %)
    if abs(df['low'].iloc[first_bottom_idx] - curr_low) / max(abs(df['low'].iloc[first_bottom_idx]), 0.0001) > 0.03:
        return False

    # RSI divergence
    if 'rsi_14' not in df.columns:
        return False
    curr_rsi = df['rsi_14'].iloc[i]
    first_rsi = df['rsi_14'].iloc[first_bottom_idx]
    if not (pd.notna(curr_rsi) and pd.notna(first_rsi) and curr_rsi > first_rsi):
        return False

    # MACD histogram divergence
    if 'macd_hist' not in df.columns:
        return False
    curr_macd = df['macd_hist'].iloc[i]
    first_macd = df['macd_hist'].iloc[first_bottom_idx]
    if not (pd.notna(curr_macd) and pd.notna(first_macd) and curr_macd > first_macd):
        return False

    return True


def check_double_top_specialized(df: pd.DataFrame, i: int) -> bool:
    """
    Double Top Pattern with RSI + MACD divergence.
    The formation candle is GREEN.  The confirmation (next RED candle) is
    checked separately so the two are evaluated on consecutive bars.
    """
    if i < 30:
        return False

    curr_high = df['high'].iloc[i]
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]

    # Formation candle is green
    if curr_close <= curr_open:
        return False

    prev_high = df['high'].iloc[i - 1]
    if curr_high < prev_high:
        return False

    lookback_start = max(0, i - 25)
    try:
        from scipy.signal import argrelextrema
        window = df['high'].iloc[lookback_start:i].values
        rel_highs = argrelextrema(window, np.greater, order=3)[0]
    except Exception:
        rel_highs = np.array([])

    if len(rel_highs) == 0:
        return False

    first_top_idx = lookback_start + int(rel_highs[-1])

    if abs(df['high'].iloc[first_top_idx] - curr_high) / max(abs(df['high'].iloc[first_top_idx]), 0.0001) > 0.03:
        return False

    if 'rsi_14' not in df.columns:
        return False
    curr_rsi = df['rsi_14'].iloc[i]
    first_rsi = df['rsi_14'].iloc[first_top_idx]
    if not (pd.notna(curr_rsi) and pd.notna(first_rsi) and curr_rsi < first_rsi):
        return False

    if 'macd_hist' not in df.columns:
        return False
    curr_macd = df['macd_hist'].iloc[i]
    first_macd = df['macd_hist'].iloc[first_top_idx]
    if not (pd.notna(curr_macd) and pd.notna(first_macd) and curr_macd < first_macd):
        return False

    return True


def check_ema_knots(df: pd.DataFrame, i: int) -> str | None:
    """
    EMA Knots: 21 / 34 / 55 EMAs converge tightly then resolve directionally.
    """
    if i < 56:
        return None

    for col in ('ema_21', 'ema_34', 'ema_55'):
        if col not in df.columns:
            return None

    curr_ema21 = df['ema_21'].iloc[i]
    curr_ema34 = df['ema_34'].iloc[i]
    curr_ema55 = df['ema_55'].iloc[i]
    prev_ema21 = df['ema_21'].iloc[i - 1]
    prev_ema34 = df['ema_34'].iloc[i - 1]
    prev_ema55 = df['ema_55'].iloc[i - 1]

    for v in (curr_ema21, curr_ema34, curr_ema55, prev_ema21, prev_ema34, prev_ema55):
        if pd.isna(v):
            return None

    # Convergence: all three EMAs within 0.5 % of each other
    avg_ema = (curr_ema21 + curr_ema34 + curr_ema55) / 3
    spread = max(curr_ema21, curr_ema34, curr_ema55) - min(curr_ema21, curr_ema34, curr_ema55)
    if spread / avg_ema > 0.005:
        return None

    # Bullish resolution: EMA21 crosses above EMA34
    if prev_ema21 <= prev_ema34 and curr_ema21 > curr_ema34:
        return "bullish_ema_knot"
    # Bearish resolution: EMA21 crosses below EMA34
    if prev_ema21 >= prev_ema34 and curr_ema21 < curr_ema34:
        return "bearish_ema_knot"
    return None


# ─── TIDE / WAVE / SUPPORT HELPERS ─────────────────────────────────────

def check_tide_conditions(df: pd.DataFrame, i: int, htf_df: pd.DataFrame | None, direction: str) -> bool:
    """Higher-timeframe momentum filter (Tide)."""
    row = df.iloc[i]

    # Price relative to 50 EMA
    if 'ema_50' not in df.columns or pd.isna(df['ema_50'].iloc[i]):
        return False
    if direction == 'bullish' and row['close'] <= df['ema_50'].iloc[i]:
        return False
    if direction == 'bearish' and row['close'] >= df['ema_50'].iloc[i]:
        return False

    # MACD on execution TF
    if 'macd' not in df.columns or 'macd_signal' not in df.columns:
        return False
    macd = df['macd'].iloc[i]
    macd_sig = df['macd_signal'].iloc[i]
    if direction == 'bullish':
        if not (pd.notna(macd) and pd.notna(macd_sig) and macd > macd_sig and macd > 0):
            return False
    else:
        if not (pd.notna(macd) and pd.notna(macd_sig) and macd < macd_sig and macd < 0):
            return False

    # BBNC: narrowing band width
    if 'bb_width' not in df.columns or 'bb_middle' not in df.columns:
        return False
    try:
        w_recent = df['bb_width'].iloc[max(0, i - 9):i + 1].mean()
        w_prev = (df['bb_width'].iloc[max(0, i - 29):max(1, i - 9)].mean()
                  if i - 9 > 0 else w_recent * 1.1)
        if w_recent >= w_prev * 0.95:
            return False
        # Middle band slope should support the direction
        mid_slope = df['bb_middle'].iloc[i] - df['bb_middle'].iloc[max(0, i - 5)]
        if direction == 'bullish' and mid_slope < 0:
            return False
        if direction == 'bearish' and mid_slope > 0:
            return False
    except Exception:
        return False

    # Double screen: HTF must agree
    if htf_df is None or htf_df.empty:
        return False
    try:
        hmacd = htf_df['macd'].iloc[-1]
        hsig = htf_df['macd_signal'].iloc[-1]
    except Exception:
        return False
    if direction == 'bullish' and not (pd.notna(hmacd) and pd.notna(hsig) and hmacd > hsig and hmacd > 0):
        return False
    if direction == 'bearish' and not (pd.notna(hmacd) and pd.notna(hsig) and hmacd < hsig and hmacd < 0):
        return False

    return True


def check_wave_conditions(df: pd.DataFrame, i: int, direction: str, tlbo: bool, bbc: bool, ungli: bool) -> bool:
    """Evaluate Wave Conditions. Includes its own 50 EMA filter."""
    if 'ema_50' in df.columns and pd.notna(df['ema_50'].iloc[i]):
        if direction == 'bullish' and df['close'].iloc[i] < df['ema_50'].iloc[i]:
            return False
        if direction == 'bearish' and df['close'].iloc[i] > df['ema_50'].iloc[i]:
            return False

    hist_conv = hist_converging_to_zero(df, i, bars=3)
    if (tlbo and bbc) or ungli or (hist_conv and tlbo):
        return True
    return False


# ─── TRIANGLE / BREAKOUT SUPPORTING HELPERS ─────────────────────────────

def _linear_fit_from_points(xs: np.ndarray, ys: np.ndarray):
    if len(xs) < 2:
        return None
    try:
        coef = np.polyfit(xs, ys, 1)
        return coef  # [slope, intercept]
    except Exception:
        return None


def detect_triangle_compression(df: pd.DataFrame, i: int, lookback: int = 60) -> dict | None:
    """
    Detects triangle compression up to index *i*.
    Supports symmetrical, ascending and descending triangles.
    """
    if i < 30:
        return None

    end = i
    start = max(0, end - lookback)
    win = df.iloc[start:end + 1].reset_index(drop=True)
    if len(win) < 20:
        return None

    try:
        from scipy.signal import argrelextrema
        highs_idx = argrelextrema(win['high'].values, np.greater, order=3)[0]
        lows_idx = argrelextrema(win['low'].values, np.less, order=3)[0]
    except Exception:
        return None

    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return None

    highs_abs = [start + int(h) for h in highs_idx]
    lows_abs = [start + int(l) for l in lows_idx]

    high_vals = [df['high'].iloc[h] for h in highs_abs]
    low_vals = [df['low'].iloc[l] for l in lows_abs]

    # Allow descending highs OR flat highs, ascending lows OR flat lows
    # But at least one must be converging
    highs_descending = high_vals[-1] <= high_vals[-2]
    lows_ascending = low_vals[-1] >= low_vals[-2]
    if not (highs_descending or lows_ascending):
        return None

    # Fit trendlines
    xs_h = np.array(highs_abs, dtype=float)
    ys_h = np.array(high_vals, dtype=float)
    xs_l = np.array(lows_abs, dtype=float)
    ys_l = np.array(low_vals, dtype=float)

    fit_h = _linear_fit_from_points(xs_h, ys_h)
    fit_l = _linear_fit_from_points(xs_l, ys_l)
    if fit_h is None or fit_l is None:
        return None

    x_start = float(start)
    x_end = float(end)
    width_start = np.polyval(fit_h, x_start) - np.polyval(fit_l, x_start)
    width_end = np.polyval(fit_h, x_end) - np.polyval(fit_l, x_end)
    if width_end <= 0 or width_start <= 0:
        return None
    if width_end > width_start * 0.95:
        return None

    # Volatility contraction
    if 'atr_14' in df.columns and not df['atr_14'].isna().all():
        recent_atr = df['atr_14'].iloc[max(0, end - 9):end + 1].mean()
        prev_atr = (df['atr_14'].iloc[max(start, end - 29):max(1, end - 9)].mean()
                    if end - 9 > start else recent_atr * 1.1)
        if recent_atr >= prev_atr * 0.95:
            return None
    else:
        bodies = (df['high'] - df['low']).abs()
        recent_body = bodies.iloc[max(0, end - 9):end + 1].mean()
        prev_body = (bodies.iloc[max(start, end - 29):max(1, end - 9)].mean()
                     if end - 9 > start else recent_body * 1.1)
        if recent_body >= prev_body * 0.95:
            return None

    # Minimum alternating touches (relaxed: at least 4, not all same type)
    combined = sorted(
        [(int(x), 'H') for x in highs_abs] + [(int(x), 'L') for x in lows_abs],
        key=lambda x: x[0]
    )
    if len(combined) < 4:
        return None
    types = [t for _, t in combined[-4:]]
    if len(set(types)) < 2:
        return None  # all same type

    # Prior directional thrust
    pre_start = max(0, start - 30)
    if pre_start < start:
        denom = df['close'].iloc[pre_start] if df['close'].iloc[pre_start] != 0 else 1
        pre_change = abs(df['close'].iloc[start] - df['close'].iloc[pre_start]) / denom
        if pre_change <= 0.04:
            return None
    else:
        return None

    return {
        'start': start,
        'end': end,
        'high_pivots': highs_abs,
        'low_pivots': lows_abs,
        'high_fit': fit_h,
        'low_fit': fit_l,
        'width_start': width_start,
        'width_end': width_end,
        'height': width_start
    }


def check_bbc(row: pd.Series, avg_body: float, vol_avg: float, direction: str) -> bool:
    body = abs(row['close'] - row['open'])
    total_range = row['high'] - row['low'] if row['high'] - row['low'] > 0 else 1.0
    if direction == 'bullish':
        closes_near_extreme = row['close'] >= row['high'] - 0.15 * total_range
    else:
        closes_near_extreme = row['close'] <= row['low'] + 0.15 * total_range
    return (body >= avg_body * 1.0) and closes_near_extreme and (row['volume'] >= vol_avg * 1.3)


def check_ungli_bullish(df: pd.DataFrame, idx: int) -> bool:
    o = df['open'].iloc[idx]
    c = df['close'].iloc[idx]
    h = df['high'].iloc[idx]
    l = df['low'].iloc[idx]
    body = abs(c - o)
    lower_wick = min(o, c) - l
    if body <= 0:
        return False
    return (lower_wick >= 2 * body) and (c >= h - 0.1 * (h - l))


def check_ungli_bearish(df: pd.DataFrame, idx: int) -> bool:
    o = df['open'].iloc[idx]
    c = df['close'].iloc[idx]
    h = df['high'].iloc[idx]
    l = df['low'].iloc[idx]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    if body <= 0:
        return False
    return (upper_wick >= 2 * body) and (c <= l + 0.1 * (h - l))


def hist_converging_to_zero(df: pd.DataFrame, i: int, bars: int = 3) -> bool:
    if 'macd_hist' not in df.columns or i - bars < 0:
        return False
    vals = df['macd_hist'].iloc[i - bars + 1:i + 1].abs().values
    if len(vals) < 2:
        return False
    return all(vals[j] < vals[j - 1] for j in range(1, len(vals)))


# ─── MASTER SCANNER ROUTINE ────────────────────────────────────────────

def scan_for_patterns(symbol: str, df: pd.DataFrame, timeframe: str, htf_df: pd.DataFrame | None = None) -> list[dict]:
    if df is None or len(df) < 50:
        return []

    df = _precompute_columns(df)

    setups: list[dict] = []

    # Calculate global pivots once for chart patterns
    highs, lows = get_pivots(df, order=4)

    # Scan only the last candle to avoid duplicate firings
    i = len(df) - 1
    if i < 20:
        return []

    row = df.iloc[i]
    date_str = str(row["datetime"])

    # ── Confluence flags ──
    sma_200 = row.get("sma_200", None)
    is_above_200 = bool(row["close"] > sma_200) if pd.notna(sma_200) else False
    vol = row["volume"]
    vol_avg = row.get("volume_sma_20", None)
    is_volume_surge = bool(vol > (vol_avg * 1.5)) if pd.notna(vol_avg) else False
    rsi = row.get("rsi_14", None)
    is_oversold = bool(rsi < 30) if pd.notna(rsi) else False
    is_overbought = bool(rsi > 70) if pd.notna(rsi) else False

    confluence_flags = {
        "above_200_sma": is_above_200,
        "volume_surge": is_volume_surge,
        "rsi_oversold": is_oversold,
        "rsi_overbought": is_overbought
    }

    def _pattern_sl(direction: str, pattern_start: int, pattern_end: int) -> float:
        """Stop-loss across the whole pattern range."""
        idx_range = range(max(0, pattern_start), pattern_end + 1)
        if direction == "bullish":
            return float(df['low'].iloc[list(idx_range)].min())
        return float(df['high'].iloc[list(idx_range)].max())

    def add_setup(name: str, category: str, direction: str, base_score: int, marks: list,
                  is_specialized: bool = False, is_primary: bool = False,
                  sl_override: float | None = None, tp_override: float | None = None):
        score = base_score
        if direction == "bullish" and is_above_200:
            score += 15
        if direction == "bearish" and not is_above_200:
            score += 15
        if is_volume_surge:
            score += 15
        if direction == "bullish" and is_oversold:
            score += 10
        if direction == "bearish" and is_overbought:
            score += 10

        if sl_override is not None:
            sl = sl_override
        else:
            # Default: use the lowest/highest across all candles in the pattern
            n_candles = len(marks)
            sl = _pattern_sl(direction, max(0, i - n_candles + 1), i)

        entry = float(row["close"])
        risk = abs(entry - sl) if abs(entry - sl) > 0 else entry * 0.01

        if tp_override is not None:
            tp = tp_override
        else:
            tp = entry + (1.5 * risk) if direction == "bullish" else entry - (1.5 * risk)

        setups.append({
            "id": str(uuid4()),
            "symbol": symbol,
            "timeframe": timeframe,
            "pattern_name": name,
            "category": category,
            "direction": direction,
            "confluence_flags": confluence_flags,
            "setup_score": score,
            "state": "Active" if score >= 60 else "Pending",
            "matched_timestamps": marks,
            "entry_price": entry,
            "stop_loss_price": sl,
            "take_profit_price": tp,
            "is_specialized": is_specialized,
            "is_primary": is_primary
        })

    # Base timestamps
    m1 = str(df.iloc[i - 2]["datetime"]) if i >= 2 else date_str
    m2 = str(df.iloc[i - 1]["datetime"]) if i >= 1 else date_str
    m3 = date_str

    # ════════════════════════════════════════════════════════════════
    #  ATOMIC CANDLESTICK PATTERNS
    # ════════════════════════════════════════════════════════════════

    if check_marubozu(df, i):
        d = "bullish" if row["close"] > row["open"] else "bearish"
        add_setup("Marubozu", "candlestick_atomic", d, 40, [m3])

    doji_type = check_doji(df, i)
    if doji_type:
        name = f"{doji_type.replace('_', ' ').title()} Doji" if doji_type != "standard" else "Doji"
        add_setup(name, "candlestick_atomic", "neutral", 30, [m3])

    if check_spinning_top(df, i):
        add_setup("Spinning Top", "candlestick_atomic", "neutral", 30, [m3])

    if check_high_wave(df, i):
        add_setup("High-Wave", "candlestick_atomic", "neutral", 40, [m3])

    hs_type = check_hammer_star_variants(df, i)
    if hs_type:
        name = hs_type.replace("_", " ").title()
        direction = "bullish" if hs_type in ("hammer", "inverted_hammer") else "bearish"
        add_setup(name, "candlestick_atomic", direction, 40, [m3])

    bh_dir = check_belt_hold(df, i)
    if bh_dir:
        add_setup("Belt Hold", "candlestick_atomic", bh_dir, 45, [m3])

    eng_dir = check_engulfing(df, i)
    if eng_dir:
        add_setup("Engulfing", "candlestick_atomic", eng_dir, 50, [m2, m3])

    harami_type = check_harami(df, i)
    if harami_type:
        name = harami_type.replace("_", " ").title()
        direction = "bullish" if "bullish" in harami_type else "bearish"
        add_setup(name, "candlestick_atomic", direction, 45, [m2, m3])

    pdc_type = check_piercing_dark_cloud(df, i)
    if pdc_type:
        name = pdc_type.replace("_", " ").title()
        direction = "bullish" if pdc_type == "piercing_line" else "bearish"
        add_setup(name, "candlestick_atomic", direction, 50, [m2, m3])

    tweezer = check_tweezer(df, i)
    if tweezer:
        name = tweezer.replace("_", " ").title()
        direction = "bearish" if tweezer == "tweezer_top" else "bullish"
        add_setup(name, "candlestick_atomic", direction, 45, [m2, m3])

    kicker = check_kicker(df, i)
    if kicker:
        name = kicker.replace("_", " ").title()
        direction = "bullish" if "bullish" in kicker else "bearish"
        add_setup(name, "candlestick_atomic", direction, 65, [m2, m3])

    ca = check_counterattack(df, i)
    if ca:
        name = ca.replace("_", " ").title()
        direction = "bullish" if "bullish" in ca else "bearish"
        add_setup(name, "candlestick_atomic", direction, 40, [m2, m3])

    sl = check_separating_lines(df, i)
    if sl:
        name = sl.replace("_", " ").title()
        direction = "bullish" if "bullish" in sl else "bearish"
        add_setup(name, "candlestick_atomic", direction, 40, [m2, m3])

    # ════════════════════════════════════════════════════════════════
    #  MULTI-CANDLE PATTERNS
    # ════════════════════════════════════════════════════════════════

    if check_morning_star(df, i):
        add_setup("Morning Star", "candlestick_multi", "bullish", 60, [m1, m2, m3])

    if check_evening_star(df, i):
        add_setup("Evening Star", "candlestick_multi", "bearish", 60, [m1, m2, m3])

    if check_three_white_soldiers(df, i):
        add_setup("Three White Soldiers", "candlestick_multi", "bullish", 65, [m1, m2, m3])

    if check_three_black_crows(df, i):
        add_setup("Three Black Crows", "candlestick_multi", "bearish", 65, [m1, m2, m3])

    ab = check_abandoned_baby(df, i)
    if ab:
        name = ab.replace("_", " ").title()
        direction = "bullish" if "bullish" in ab else "bearish"
        add_setup(name, "candlestick_multi", direction, 80, [m1, m2, m3])

    tio = check_three_inside_outside(df, i)
    if tio:
        name = tio.replace("_", " ").title()
        direction = "bullish" if "up" in tio else "bearish"
        add_setup(name, "candlestick_multi", direction, 70, [m1, m2, m3])

    tm = check_three_methods(df, i)
    if tm:
        name = tm.replace("_", " ").title()
        direction = "bullish" if "rising" in tm else "bearish"
        if i >= 4:
            m4 = str(df.iloc[i - 3]["datetime"])
            m5 = str(df.iloc[i - 4]["datetime"])
            add_setup(name, "candlestick_multi", direction, 75, [m5, m4, m1, m2, m3])

    tls = check_three_line_strike(df, i)
    if tls:
        name = tls.replace("_", " ").title()
        direction = "bullish" if "bullish" in tls else "bearish"
        m0 = str(df.iloc[i - 3]["datetime"]) if i >= 3 else m1
        add_setup(name, "candlestick_multi", direction, 70, [m0, m1, m2, m3])

    if check_stick_sandwich(df, i):
        add_setup("Stick Sandwich", "candlestick_multi", "bullish", 60, [m1, m2, m3])

    # ════════════════════════════════════════════════════════════════
    #  CHART GEOMETRY
    # ════════════════════════════════════════════════════════════════

    if check_double_top(df, highs, i):
        vh = [h for h in highs if h <= i]
        p1_ts = str(df.iloc[vh[-2]]["datetime"])
        p2_ts = str(df.iloc[vh[-1]]["datetime"])
        add_setup("Double Top", "macro_market_geometry", "bearish", 70, [p1_ts, p2_ts, m3])

    if check_double_bottom(df, lows, i):
        vl = [l for l in lows if l <= i]
        p1_ts = str(df.iloc[vl[-2]]["datetime"])
        p2_ts = str(df.iloc[vl[-1]]["datetime"])
        add_setup("Double Bottom", "macro_market_geometry", "bullish", 70, [p1_ts, p2_ts, m3])

    if check_triple_top(df, highs, i):
        vh = [h for h in highs if h <= i]
        pts = [str(df.iloc[vh[j]]["datetime"]) for j in (-3, -2, -1)]
        add_setup("Triple Top", "macro_market_geometry", "bearish", 85, pts + [m3])

    if check_triple_bottom(df, lows, i):
        vl = [l for l in lows if l <= i]
        pts = [str(df.iloc[vl[j]]["datetime"]) for j in (-3, -2, -1)]
        add_setup("Triple Bottom", "macro_market_geometry", "bullish", 85, pts + [m3])

    hs = check_head_and_shoulders(df, highs, lows, i)
    if hs:
        vh = [h for h in highs if h <= i]
        pts = [str(df.iloc[vh[j]]["datetime"]) for j in (-3, -2, -1)]
        add_setup("Head and Shoulders", "macro_market_geometry", "bearish", 80, pts + [m3])

    ihs = check_inv_head_and_shoulders(df, highs, lows, i)
    if ihs:
        vl = [l for l in lows if l <= i]
        pts = [str(df.iloc[vl[j]]["datetime"]) for j in (-3, -2, -1)]
        add_setup("Inv Head & Shoulders", "macro_market_geometry", "bullish", 80, pts + [m3])

    # ════════════════════════════════════════════════════════════════
    #  SPECIALIZED: DOUBLE BOTTOM/TOP + EMA KNOTS
    # ════════════════════════════════════════════════════════════════

    # Formation is checked on the PREVIOUS candle; confirmation on the CURRENT candle.
    if i >= 1:
        if check_double_bottom_specialized(df, i - 1):
            # Confirmation: current candle is green
            if df['close'].iloc[i] > df['open'].iloc[i]:
                add_setup("Double Bottom (Divergence)", "specialized_patterns", "bullish", 75, [m2, m3],
                          is_specialized=True)

        if check_double_top_specialized(df, i - 1):
            # Confirmation: current candle is red
            if df['close'].iloc[i] < df['open'].iloc[i]:
                add_setup("Double Top (Divergence)", "specialized_patterns", "bearish", 75, [m2, m3],
                          is_specialized=True)

    ema_knot = check_ema_knots(df, i)
    if ema_knot:
        direction = "bullish" if "bullish" in ema_knot else "bearish"
        add_setup("EMA Knots", "specialized_patterns", direction, 70, [m3], is_specialized=True)

    # ════════════════════════════════════════════════════════════════
    #  TRIANGLE BREAKOUT / BREAKDOWN
    # ════════════════════════════════════════════════════════════════

    tri = detect_triangle_compression(df, i, lookback=60)
    if tri is not None:
        try:
            upper_val = float(np.polyval(tri['high_fit'], i))
            lower_val = float(np.polyval(tri['low_fit'], i))
        except Exception:
            upper_val = None
            lower_val = None

        avg_body = df['_avg_body_20'].iloc[i] if pd.notna(df['_avg_body_20'].iloc[i]) else abs(row['close'] - row['open'])
        vol_avg_local = row.get('volume_sma_20', None)
        if pd.isna(vol_avg_local) or vol_avg_local == 0:
            vol_avg_local = df['volume'].rolling(20, min_periods=1).mean().iloc[i]

        body = abs(row['close'] - row['open'])

        # Compute TLBO threshold
        atr_col = df.get('atr_14', pd.Series())
        if not atr_col.empty and pd.notna(atr_col.iloc[i]):
            tlbo_threshold = float(atr_col.iloc[i]) * 0.5
        else:
            tlbo_threshold = upper_val * 0.005 if upper_val and upper_val > 0 else 0

        marks_tri = [str(df.iloc[p]['datetime']) for p in (tri['high_pivots'] + tri['low_pivots']) if p < len(df)]
        marks_tri.append(m3)

        # ── Bullish breakout ──
        if upper_val is not None and row['close'] > upper_val:
            tlbo = (row['close'] - upper_val) > tlbo_threshold
            if tlbo and body > avg_body and row['volume'] >= vol_avg_local:
                bbc = check_bbc(row, avg_body, vol_avg_local, 'bullish')
                ungli = check_ungli_bullish(df, i - 1) if i >= 1 else False
                tide_ok = check_tide_conditions(df, i, htf_df, 'bullish')
                wave_ok = check_wave_conditions(df, i, 'bullish', tlbo, bbc, ungli)
                if tide_ok and wave_ok:
                    breakout_level = float(row['close'])
                    tri_height = float(tri.get('height', 0))
                    tp_primary = breakout_level + tri_height
                    sl_val = float(min(row['low'], df['low'].iloc[i - 1] if i >= 1 else row['low']))
                    add_setup("Triangle Breakout", "specialized_patterns", "bullish", 85, marks_tri,
                              is_specialized=True, is_primary=True,
                              sl_override=sl_val, tp_override=tp_primary)

        # ── Bearish breakdown ──
        if lower_val is not None and row['close'] < lower_val:
            tlbo = (lower_val - row['close']) > tlbo_threshold
            if tlbo and body > avg_body and row['volume'] >= vol_avg_local:
                bbc = check_bbc(row, avg_body, vol_avg_local, 'bearish')
                ungli = check_ungli_bearish(df, i - 1) if i >= 1 else False
                tide_ok = check_tide_conditions(df, i, htf_df, 'bearish')
                wave_ok = check_wave_conditions(df, i, 'bearish', tlbo, bbc, ungli)
                if tide_ok and wave_ok:
                    breakout_level = float(row['close'])
                    tri_height = float(tri.get('height', 0))
                    tp_primary = breakout_level - tri_height
                    sl_val = float(max(row['high'], df['high'].iloc[i - 1] if i >= 1 else row['high']))
                    add_setup("Triangle Breakdown", "specialized_patterns", "bearish", 85, marks_tri,
                              is_specialized=True, is_primary=True,
                              sl_override=sl_val, tp_override=tp_primary)

    # Integrate optional pattern-mathematics module (user-provided logic)
    try:
        import importlib
        pm = importlib.import_module("backend.pattern_math")
    except Exception:
        pm = None

    if pm is not None:
        try:
            math_signals = pm.analyze_df(df, symbol=symbol)
            for sig in math_signals:
                sig_dir = sig.get("direction", "long")
                direction = "bullish" if sig_dir in ("long", "bullish") else "bearish"
                name = sig.get("pattern_type", "Pattern").replace("_", " ").title()
                marks = sig.get("marks", [m3]) if isinstance(sig.get("marks", None), list) else [m3]
                base_score = 80
                sl = sig.get("stop_loss", None)
                tp = sig.get("take_profit", None)
                is_primary = bool(sig.get("is_primary", False))
                add_setup(name, "pattern_math", direction, base_score, marks,
                          is_specialized=True, is_primary=is_primary,
                          sl_override=sl, tp_override=tp)
        except Exception:
            # Don't let optional module errors break main scanner
            pass

    # ════════════════════════════════════════════════════════════════
    #  DEDUPLICATION
    # ════════════════════════════════════════════════════════════════
    # Key by (pattern_name, category) so that the same pattern name under
    # different categories (e.g. "Double Top" in geometry vs specialized)
    # are kept as separate entries.

    unique_setups: dict[str, dict] = {}
    for s in setups:
        key = f"{s['pattern_name']}_{s['category']}"
        if key not in unique_setups:
            unique_setups[key] = s
            continue

        existing = unique_setups[key]
        # Prefer primary setups
        if s.get("is_primary", False) and not existing.get("is_primary", False):
            unique_setups[key] = s
            continue
        if existing.get("is_primary", False) and not s.get("is_primary", False):
            continue

        # Prefer specialized setups
        if s.get("is_specialized", False) and not existing.get("is_specialized", False):
            unique_setups[key] = s
            continue
        if existing.get("is_specialized", False) and not s.get("is_specialized", False):
            continue

        # Otherwise highest score wins
        if s["setup_score"] > existing["setup_score"]:
            unique_setups[key] = s

    return list(unique_setups.values())