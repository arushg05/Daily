import pandas as pd
import numpy as np
import json
import logging
from uuid import uuid4
try:
    from scipy.signal import argrelextrema
except ImportError:
    pass # we'll install it

logger = logging.getLogger("asymptote-lt.pattern_matcher")

# ─── ATOMIC CANDLESTICK LOGIC ──────────────────────────────────────────

def check_marubozu(df: pd.DataFrame, i: int) -> bool:
    open_p, close_p, high_p, low_p = df["open"].iloc[i], df["close"].iloc[i], df["high"].iloc[i], df["low"].iloc[i]
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0: return False
    return (body / total_range) >= 0.90

def check_doji(df: pd.DataFrame, i: int) -> str | None:
    open_p, close_p, high_p, low_p = df["open"].iloc[i], df["close"].iloc[i], df["high"].iloc[i], df["low"].iloc[i]
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0: return None
    is_doji = (body / total_range) <= 0.10
    if not is_doji: return None
    
    # Long-Legged Doji: Doji + long shadows (e.g., total range > 2x average ATR or similar, simplified here)
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    if total_range > (df['high'] - df['low']).rolling(20).mean().iloc[i] * 1.5:
        return "long_legged"
    # Dragonfly: open/close/high identical
    if upper_shadow <= total_range * 0.1 and lower_shadow >= total_range * 0.8:
        return "dragonfly"
    # Gravestone: open/close/low identical
    if lower_shadow <= total_range * 0.1 and upper_shadow >= total_range * 0.8:
        return "gravestone"
    return "standard"

def check_spinning_top(df: pd.DataFrame, i: int) -> bool:
    open_p, close_p, high_p, low_p = df["open"].iloc[i], df["close"].iloc[i], df["high"].iloc[i], df["low"].iloc[i]
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0: return False
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    # Small body (10-30% of range) and roughly equal shadows
    is_small_body = 0.1 < (body / total_range) <= 0.3
    is_symmetrical = abs(upper_shadow - lower_shadow) / total_range < 0.2 if total_range > 0 else False
    return is_small_body and is_symmetrical

def check_high_wave(df: pd.DataFrame, i: int) -> bool:
    open_p, close_p, high_p, low_p = df["open"].iloc[i], df["close"].iloc[i], df["high"].iloc[i], df["low"].iloc[i]
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0: return False
    # Small body + extremely long shadows (outlier range)
    avg_range = (df['high'] - df['low']).rolling(20).mean().iloc[i]
    return (body / total_range) <= 0.2 and total_range > avg_range * 2.5

def check_hammer_star_variants(df: pd.DataFrame, i: int) -> str | None:
    # Hammer/Hanging Man/Inverted Hammer/Shooting Star grouped
    open_p, close_p, high_p, low_p = df["open"].iloc[i], df["close"].iloc[i], df["high"].iloc[i], df["low"].iloc[i]
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0 or body == 0: return None
    
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    
    # Body in upper third
    if upper_shadow < total_range * 0.2 and lower_shadow >= 2 * body:
        # If in downtrend (SMA 20) -> Hammer, else Hanging Man
        sma_20 = df['close'].rolling(20).mean().iloc[i]
        return "hammer" if close_p < sma_20 else "hanging_man"
        
    # Body in lower third
    if lower_shadow < total_range * 0.2 and upper_shadow >= 2 * body:
        sma_20 = df['close'].rolling(20).mean().iloc[i]
        return "inverted_hammer" if close_p < sma_20 else "shooting_star"
        
    return None

def check_belt_hold(df: pd.DataFrame, i: int) -> str | None:
    o, c, h, l = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
    body = abs(c - o)
    total_range = h - l
    if total_range == 0 or body / total_range < 0.8: return None
    
    # Bullish: Open is the Low
    if abs(o - l) / total_range < 0.02 and c > o: return "bullish"
    # Bearish: Open is the High
    if abs(o - h) / total_range < 0.02 and c < o: return "bearish"
    return None

def check_harami(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    p_o, p_c, p_h, p_l = df['open'].iloc[i-1], df['close'].iloc[i-1], df['high'].iloc[i-1], df['low'].iloc[i-1]
    c_o, c_c, c_h, c_l = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
    
    p_body_top, p_body_bottom = max(p_o, p_c), min(p_o, p_c)
    c_body_top, c_body_bottom = max(c_o, c_c), min(c_o, c_c)
    
    # Second body inside first body
    if c_body_top < p_body_top and c_body_bottom > p_body_bottom:
        # Cross: second is a doji
        is_cross = abs(c_o - c_c) / (c_h - c_l) <= 0.1 if (c_h - c_l) > 0 else False
        return "harami_cross" if is_cross else "harami"
    return None

def check_piercing_dark_cloud(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    p_o, p_c = df['open'].iloc[i-1], df['close'].iloc[i-1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]
    
    # Piercing: Red then Green, Green gaps down but closes > 50% of Red
    if p_c < p_o and c_c > c_o and c_o < p_c:
        if c_c > (p_o + p_c) / 2: return "piercing_line"
    
    # Dark Cloud: Green then Red, Red gaps up but closes < 50% of Green
    if p_c > p_o and c_c < c_o and c_o > p_c:
        if c_c < (p_o + p_c) / 2: return "dark_cloud_cover"
    return None

def check_tweezer(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    p_h, p_l = df['high'].iloc[i-1], df['low'].iloc[i-1]
    c_h, c_l = df['high'].iloc[i], df['low'].iloc[i]
    
    # Identical highs/lows within 0.1%
    if abs(p_h - c_h) / p_h < 0.001: return "tweezer_top"
    if abs(p_l - c_l) / p_l < 0.001: return "tweezer_bottom"
    return None

def check_kicker(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    p_o, p_c = df['open'].iloc[i-1], df['close'].iloc[i-1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]
    
    # Bullish Kicker: Red then Green, Green gaps up above Red's Open
    if p_c < p_o and c_c > c_o and c_o >= p_o: return "bullish_kicker"
    # Bearish Kicker: Green then Red, Red gaps down below Green's Open
    if p_c > p_o and c_c < c_o and c_o <= p_o: return "bearish_kicker"
    return None

def check_counterattack_separating(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    p_o, p_c = df['open'].iloc[i-1], df['close'].iloc[i-1]
    c_o, c_c = df['open'].iloc[i], df['close'].iloc[i]
    
    # Counterattack: Opposite directions, identical close
    if (p_c > p_o and c_c < c_o or p_c < p_o and c_c > c_o):
        if abs(p_c - c_c) / p_c < 0.001: return "counterattack"
    
    # Separating Lines: Opposite directions, identical open
    if (p_c > p_o and c_c < c_o or p_c < p_o and c_c > c_o):
        if abs(p_o - c_o) / p_o < 0.001: return "separating_lines"
    return None

def check_engulfing(df: pd.DataFrame, i: int) -> str | None:
    if i < 1: return None
    curr_o, curr_c = df["open"].iloc[i], df["close"].iloc[i]
    prev_o, prev_c = df["open"].iloc[i-1], df["close"].iloc[i-1]
    if prev_c < prev_o and curr_c > curr_o:
        if curr_c > prev_o and curr_o < prev_c: return "bullish"
    if prev_c > prev_o and curr_c < curr_o:
        if curr_o > prev_c and curr_c < prev_o: return "bearish"
    return None


# ─── MULTI-CANDLE LOGIC ────────────────────────────────────────────────

def check_abandoned_baby(df: pd.DataFrame, i: int) -> str | None:
    if i < 2: return None
    o1, c1, h1, l1 = df['open'].iloc[i-2], df['close'].iloc[i-2], df['high'].iloc[i-2], df['low'].iloc[i-2]
    o2, c2, h2, l2 = df['open'].iloc[i-1], df['close'].iloc[i-1], df['high'].iloc[i-1], df['low'].iloc[i-1]
    o3, c3, h3, l3 = df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i], df['low'].iloc[i]
    
    # 2nd is doji
    if abs(o2 - c2) / (h2 - l2) > 0.1 if (h2-l2)>0 else True: return None
    
    # Bullish: 1st Red, 2nd gaps down (low < low1), 3rd Green gaps up (low3 > high2)
    if c1 < o1 and l1 > h2 and l3 > h2 and c3 > o3: return "bullish_abandoned_baby"
    # Bearish: 1st Green, 2nd gaps up (low2 > high1), 3rd Red gaps down (low2 > high3)
    if c1 > o1 and l2 > h1 and l2 > h3 and c3 < o3: return "bearish_abandoned_baby"
    return None

def check_three_inside_outside(df: pd.DataFrame, i: int) -> str | None:
    if i < 2: return None
    # Inside: Harami + 3rd candle closes outside 1st candle range
    h_type = check_harami(df, i-1)
    if h_type:
        p_h, p_l = df['high'].iloc[i-2], df['low'].iloc[i-2]
        c_c = df['close'].iloc[i]
        if c_c > p_h: return "three_inside_up"
        if c_c < p_l: return "three_inside_down"
        
    # Outside: Engulfing + 3rd candle closes further in direction
    e_type = check_engulfing(df, i-1)
    if e_type:
        c_c, p_c = df['close'].iloc[i], df['close'].iloc[i-1]
        if e_type == "bullish" and c_c > p_c: return "three_outside_up"
        if e_type == "bearish" and c_c < p_c: return "three_outside_down"
    return None

def check_three_methods(df: pd.DataFrame, i: int) -> str | None:
    if i < 4: return None
    # 5-candle pattern
    # Rising: 1st Long Green, 2,3,4 Small Red inside 1st range, 5th Long Green breaks 1st high
    c1_o, c1_c, c1_h, c1_l = df['open'].iloc[i-4], df['close'].iloc[i-4], df['high'].iloc[i-4], df['low'].iloc[i-4]
    if c1_c < c1_o: # Starting candle must be green for Rising
        # Falling: 1st Long Red...
        if c1_c < c1_o * 0.98: # Significant red
            # Check 2,3,4 are small green/neutral inside range
            for idx in range(i-3, i):
                if df['high'].iloc[idx] > c1_o or df['low'].iloc[idx] < c1_c: return None
            if df['close'].iloc[i] < df['open'].iloc[i] and df['close'].iloc[i] < c1_c: return "falling_three_methods"
    else:
        if c1_c > c1_o * 1.02: # Significant green
            for idx in range(i-3, i):
                if df['high'].iloc[idx] > c1_c or df['low'].iloc[idx] < c1_o: return None
            if df['close'].iloc[i] > df['open'].iloc[i] and df['close'].iloc[i] > c1_c: return "rising_three_methods"
    return None

def check_three_line_strike(df: pd.DataFrame, i: int) -> str | None:
    if i < 3: return None
    # 3 directional, 4th massive engulfing
    c1, c2, c3, c4 = df.iloc[i-3], df.iloc[i-2], df.iloc[i-1], df.iloc[i]
    # Bullish: 3 Red decreasing, 4th Green opens < 3rd low and closes > 1st high
    if c1['close'] < c1['open'] and c2['close'] < c1['close'] and c3['close'] < c2['close']:
        if c4['close'] > c4['open'] and c4['close'] > c1['open'] and c4['open'] < c3['close']:
            return "bullish_three_line_strike"
    # Bearish: 3 Green increasing, 4th Red opens > 3rd high and closes < 1st low
    if c1['close'] > c1['open'] and c2['close'] > c1['close'] and c3['close'] > c2['close']:
        if c4['close'] < c4['open'] and c4['close'] < c1['open'] and c4['open'] > c3['close']:
            return "bearish_three_line_strike"
    return None

def check_stick_sandwich(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    # Bullish Sandwich: Red, Green, Red with identical lows
    c1, c2, c3 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
    if c1['close'] < c1['open'] and c2['close'] > c2['open'] and c3['close'] < c3['open']:
        if abs(c1['close'] - c3['close']) / c1['close'] < 0.001:
            return True
    return False

def check_morning_star(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    o1, c1 = df['open'].iloc[i-2], df['close'].iloc[i-2]
    o2, c2 = df['open'].iloc[i-1], df['close'].iloc[i-1]
    o3, c3 = df['open'].iloc[i], df['close'].iloc[i]
    
    # 1st: red
    if c1 >= o1: return False
    # 2nd: gaps down (its body is below 1st body)
    if max(o2, c2) >= min(o1, c1): return False
    # 3rd: green, closes > mid of 1st
    if c3 <= o3 or c3 <= (o1+c1)/2.0: return False
    return True

def check_evening_star(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    o1, c1 = df['open'].iloc[i-2], df['close'].iloc[i-2]
    o2, c2 = df['open'].iloc[i-1], df['close'].iloc[i-1]
    o3, c3 = df['open'].iloc[i], df['close'].iloc[i]
    
    # 1st: green
    if c1 <= o1: return False
    # 2nd: gaps up
    if min(o2, c2) <= max(o1, c1): return False
    # 3rd: red, closes < mid of 1st
    if c3 >= o3 or c3 >= (o1+c1)/2.0: return False
    return True

def check_three_white_soldiers(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    candles = [
        (df['open'].iloc[i-2], df['close'].iloc[i-2], df['high'].iloc[i-2]),
        (df['open'].iloc[i-1], df['close'].iloc[i-1], df['high'].iloc[i-1]),
        (df['open'].iloc[i], df['close'].iloc[i], df['high'].iloc[i])
    ]
    prev_c = 0
    for idx, (o, c, h) in enumerate(candles):
        if c <= o: return False # Must be green
        if c < h * 0.99: return False # Short upper shadow
        if idx > 0 and o < candles[idx-1][0]: return False # Open within prev body usually
        if idx > 0 and c <= prev_c: return False # Higher close
        prev_c = c
    return True

def check_three_black_crows(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    candles = [
        (df['open'].iloc[i-2], df['close'].iloc[i-2], df['low'].iloc[i-2]),
        (df['open'].iloc[i-1], df['close'].iloc[i-1], df['low'].iloc[i-1]),
        (df['open'].iloc[i], df['close'].iloc[i], df['low'].iloc[i])
    ]
    prev_c = float('inf')
    for idx, (o, c, l) in enumerate(candles):
        if c >= o: return False # Must be red
        if c > l * 1.01: return False # Short lower shadow
        if idx > 0 and c >= prev_c: return False # Lower close
        prev_c = c
    return True


# ─── CHART GEOMETRY LOGIC ──────────────────────────────────────────────

def get_pivots(df: pd.DataFrame, order=5):
    try:
        from scipy.signal import argrelextrema
        highs = argrelextrema(df['high'].values, np.greater, order=order)[0]
        lows = argrelextrema(df['low'].values, np.less, order=order)[0]
        return highs, lows
    except:
        return [], []

def check_double_top(df: pd.DataFrame, highs, i) -> bool:
    valid_highs = [h for h in highs if h <= i]
    if len(valid_highs) < 2: return False
    p1, p2 = valid_highs[-2], valid_highs[-1]
    if i - p2 > 10: return False # Only flag if the last peak was very recent
    price1, price2 = df['high'].iloc[p1], df['high'].iloc[p2]
    return abs(price1 - price2) / price1 < 0.03

def check_double_bottom(df: pd.DataFrame, lows, i) -> bool:
    valid_lows = [l for l in lows if l <= i]
    if len(valid_lows) < 2: return False
    p1, p2 = valid_lows[-2], valid_lows[-1]
    if i - p2 > 10: return False 
    price1, price2 = df['low'].iloc[p1], df['low'].iloc[p2]
    return abs(price1 - price2) / price1 < 0.03

def check_head_and_shoulders(df: pd.DataFrame, highs, i) -> str | None:
    valid_highs = [h for h in highs if h <= i]
    if len(valid_highs) < 3: return None
    p1, p2, p3 = valid_highs[-3], valid_highs[-2], valid_highs[-1]
    if i - p3 > 10: return None
    
    h1, h2, h3 = df['high'].iloc[p1], df['high'].iloc[p2], df['high'].iloc[p3]
    if h2 > h1 and h2 > h3:
        if abs(h1 - h3) / h1 < 0.05:
            return "bearish"
    return None

def check_inv_head_and_shoulders(df: pd.DataFrame, lows, i) -> str | None:
    valid_lows = [l for l in lows if l <= i]
    if len(valid_lows) < 3: return None
    p1, p2, p3 = valid_lows[-3], valid_lows[-2], valid_lows[-1]
    if i - p3 > 10: return None
    
    l1, l2, l3 = df['low'].iloc[p1], df['low'].iloc[p2], df['low'].iloc[p3]
    if l2 < l1 and l2 < l3:
        if abs(l1 - l3) / l1 < 0.05:
            return "bullish"
    return None

def check_triple_pivots(df: pd.DataFrame, pivots, i) -> bool:
    valid_pivots = [p for p in pivots if p <= i]
    if len(valid_pivots) < 3: return False
    p1, p2, p3 = valid_pivots[-3], valid_pivots[-2], valid_pivots[-1]
    if i - p3 > 15: return False
    
    vals = [df['high'].iloc[p1] if p1 in pivots else df['low'].iloc[p1], 
            df['high'].iloc[p2] if p2 in pivots else df['low'].iloc[p2], 
            df['high'].iloc[p3] if p3 in pivots else df['low'].iloc[p3]]
    
    # Check variance between the three peaks/troughs < 3%
    avg = sum(vals) / 3
    return all(abs(v - avg) / avg < 0.03 for v in vals)

# ─── SPECIALIZED PATTERNS: DOUBLE BOTTOMS/TOPS & EMA KNOTS ─────────────

def check_double_bottom_specialized(df: pd.DataFrame, i: int) -> bool:
    """
    Double Bottom Pattern:
    1. Current candle low <= previous candle low
    2. Check for RSI divergence (RSI higher at current than at first bottom)
    3. Check for MACD divergence (MACD histogram higher at current than at first bottom)
    4. Current candle should be RED (bearish continuation)
    """
    if i < 30: return False
    
    curr_low = df['low'].iloc[i]
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]
    prev_low = df['low'].iloc[i-1]
    
    # Current candle is red (close < open)
    if curr_close >= curr_open:
        return False
    
    # Current low <= previous low
    if curr_low > prev_low:
        return False
    
    # Look for first bottom in the last 20-25 candles
    lookback_start = max(0, i - 25)
    recent_lows = df['low'].iloc[lookback_start:i-1]
    if len(recent_lows) == 0:
        return False
    
    first_bottom_idx = recent_lows.idxmin()
    first_bottom_idx = first_bottom_idx if isinstance(first_bottom_idx, int) else lookback_start + recent_lows.tolist().index(min(recent_lows))
    
    # Check RSI divergence if available
    curr_rsi = df.get('rsi_14', pd.Series()).iloc[i] if 'rsi_14' in df.columns else None
    first_rsi = df.get('rsi_14', pd.Series()).iloc[first_bottom_idx] if 'rsi_14' in df.columns else None
    
    # Check MACD divergence if available
    curr_macd = df.get('macd_hist', pd.Series()).iloc[i] if 'macd_hist' in df.columns else None
    first_macd = df.get('macd_hist', pd.Series()).iloc[first_bottom_idx] if 'macd_hist' in df.columns else None
    
    # Verify divergences
    has_rsi_div = (curr_rsi is not None and first_rsi is not None and 
                   pd.notna(curr_rsi) and pd.notna(first_rsi) and curr_rsi > first_rsi)
    has_macd_div = (curr_macd is not None and first_macd is not None and 
                    pd.notna(curr_macd) and pd.notna(first_macd) and curr_macd > first_macd)
    
    # Both divergences should be present
    return has_rsi_div and has_macd_div

def check_double_top_specialized(df: pd.DataFrame, i: int) -> bool:
    """
    Double Top Pattern (opposite of Double Bottom):
    1. Current candle high >= previous candle high
    2. Check for RSI divergence (RSI lower at current than at first top)
    3. Check for MACD divergence (MACD histogram lower at current than at first top)
    4. Current candle should be GREEN (bearish continuation)
    """
    if i < 30: return False
    
    curr_high = df['high'].iloc[i]
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]
    prev_high = df['high'].iloc[i-1]
    
    # Current candle is green (close > open)
    if curr_close <= curr_open:
        return False
    
    # Current high >= previous high
    if curr_high < prev_high:
        return False
    
    # Look for first top in the last 20-25 candles
    lookback_start = max(0, i - 25)
    recent_highs = df['high'].iloc[lookback_start:i-1]
    if len(recent_highs) == 0:
        return False
    
    first_top_idx = recent_highs.idxmax()
    first_top_idx = first_top_idx if isinstance(first_top_idx, int) else lookback_start + recent_highs.tolist().index(max(recent_highs))
    
    # Check RSI divergence if available
    curr_rsi = df.get('rsi_14', pd.Series()).iloc[i] if 'rsi_14' in df.columns else None
    first_rsi = df.get('rsi_14', pd.Series()).iloc[first_top_idx] if 'rsi_14' in df.columns else None
    
    # Check MACD divergence if available
    curr_macd = df.get('macd_hist', pd.Series()).iloc[i] if 'macd_hist' in df.columns else None
    first_macd = df.get('macd_hist', pd.Series()).iloc[first_top_idx] if 'macd_hist' in df.columns else None
    
    # Verify divergences (lower for bearish)
    has_rsi_div = (curr_rsi is not None and first_rsi is not None and 
                   pd.notna(curr_rsi) and pd.notna(first_rsi) and curr_rsi < first_rsi)
    has_macd_div = (curr_macd is not None and first_macd is not None and 
                    pd.notna(curr_macd) and pd.notna(first_macd) and curr_macd < first_macd)
    
    # Both divergences should be present
    return has_rsi_div and has_macd_div

def check_ema_knots(df: pd.DataFrame, i: int) -> str | None:
    """
    EMA Knots Pattern:
    Check for 21, 34, 55 day EMA crossovers on the same candle.
    Bullish: EMA21 > EMA34 > EMA55 (all three in order on same candle)
    Bearish: EMA21 < EMA34 < EMA55 (opposite order on same candle)
    """
    if i < 55: return None  # Need 55 days of history for EMA55
    
    ema21 = df.get('ema_21', pd.Series())
    ema34 = df.get('ema_34', pd.Series())
    ema55 = df.get('ema_55', pd.Series())
    
    # If these EMAs don't exist, return None
    if ema21.empty or ema34.empty or ema55.empty:
        return None
    
    curr_ema21 = ema21.iloc[i]
    curr_ema34 = ema34.iloc[i]
    curr_ema55 = ema55.iloc[i]
    prev_ema21 = ema21.iloc[i-1]
    prev_ema34 = ema34.iloc[i-1]
    prev_ema55 = ema55.iloc[i-1]
    
    if pd.isna(curr_ema21) or pd.isna(curr_ema34) or pd.isna(curr_ema55):
        return None
    if pd.isna(prev_ema21) or pd.isna(prev_ema34) or pd.isna(prev_ema55):
        return None
    
    # Bullish Knot: EMA21 crosses above EMA34, which is above EMA55
    # Check if EMA21 was below EMA34 and is now above (crossover)
    if (prev_ema21 <= prev_ema34 and curr_ema21 > curr_ema34 and 
        curr_ema34 > curr_ema55):
        return "bullish_ema_knot"
    
    # Bearish Knot: EMA21 crosses below EMA34, which is below EMA55
    # Check if EMA21 was above EMA34 and is now below (crossover)
    if (prev_ema21 >= prev_ema34 and curr_ema21 < curr_ema34 and 
        curr_ema34 < curr_ema55):
        return "bearish_ema_knot"
    
    return None

def check_double_bottom_bullish_confirmation(df: pd.DataFrame, i: int) -> bool:
    """
    Checks if current candle is the first BULLISH (GREEN) candle after a double bottom was formed.
    Used to trigger the actual setup entry signal.
    """
    if i < 1: return False
    
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]
    
    # Current candle must be GREEN (bullish)
    return curr_close > curr_open

def check_double_top_bearish_confirmation(df: pd.DataFrame, i: int) -> bool:
    """
    Checks if current candle is the first BEARISH (RED) candle after a double top was formed.
    Used to trigger the actual setup entry signal.
    """
    if i < 1: return False
    
    curr_close = df['close'].iloc[i]
    curr_open = df['open'].iloc[i]
    
    # Current candle must be RED (bearish)
    return curr_close < curr_open


def check_tide_conditions(df: pd.DataFrame, i: int, htf_df: pd.DataFrame | None, direction: str) -> bool:
    """Higher-timeframe momentum filter (Tide). Requires MACD alignment, BBNC condition, double-screen and 50 EMA."""
    row = df.iloc[i]
    # Mandatory: Price relative to 50 EMA
    if 'ema_50' not in df.columns or pd.isna(df['ema_50'].iloc[i]):
        return False
    if direction == 'bullish' and not (row['close'] > df['ema_50'].iloc[i]):
        return False
    if direction == 'bearish' and not (row['close'] < df['ema_50'].iloc[i]):
        return False

    # MACD conditions on execution timeframe
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

    # BBNC: check narrowing band width and middle slope direction
    if 'bb_width' not in df.columns or 'bb_middle' not in df.columns:
        return False
    try:
        w_recent = df['bb_width'].iloc[max(0, i-9):i+1].mean()
        w_prev = df['bb_width'].iloc[max(0, i-29):max(0, i-9)].mean() if i-9 > 0 else w_recent * 1.1
        if not (w_recent < w_prev * 0.95):
            return False
        # middle band slope
        mid_slope = df['bb_middle'].iloc[i] - df['bb_middle'].iloc[max(0, i-5)]
        if direction == 'bullish' and not (mid_slope < 0):
            # bullish tide expects bb middle has some downward bias per spec
            return False
        if direction == 'bearish' and not (mid_slope > 0):
            return False
    except Exception:
        return False

    # Double screen: HTF must agree with direction
    if htf_df is None or htf_df.empty:
        return False
    # use last available in HTF
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
    """Evaluate Wave Conditions per spec. Price vs 50 EMA should be checked before calling."""
    # TLBO + BBC OR Ungli OR Histogram convergence toward zero + TLBO
    hist_conv = hist_converging_to_zero(df, i, bars=3)
    if direction == 'bullish':
        if (tlbo and bbc) or ungli or (hist_conv and tlbo):
            return True
    else:
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
    """Detects triangle compression up to index i. Returns triangle info or None.
    The detection is heuristic: finds pivot highs/lows, requires at least 2 lower highs
    and 2 higher lows, checks convergence (shrinking width) and volatility contraction.
    """
    if i < 30:
        return None

    end = i
    start = max(0, end - lookback)
    win = df.iloc[start:end+1].reset_index(drop=True)
    if len(win) < 20:
        return None

    # find local pivots within window
    try:
        from scipy.signal import argrelextrema
        highs_idx = argrelextrema(win['high'].values, np.greater, order=3)[0]
        lows_idx = argrelextrema(win['low'].values, np.less, order=3)[0]
    except Exception:
        highs_idx = []
        lows_idx = []

    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return None

    # Convert to absolute indices relative to df
    highs_abs = [start + int(h) for h in highs_idx]
    lows_abs = [start + int(l) for l in lows_idx]

    # Check at least 2 lower highs (descending) and 2 higher lows (ascending)
    high_vals = [df['high'].iloc[h] for h in highs_abs]
    low_vals = [df['low'].iloc[l] for l in lows_abs]
    # Use last two pivots for check
    if len(high_vals) >= 2 and not (high_vals[-1] < high_vals[-2]):
        # require last high lower than previous high
        return None
    if len(low_vals) >= 2 and not (low_vals[-1] > low_vals[-2]):
        return None

    # Fit trendlines to pivot highs and pivot lows
    xs_h = np.array(highs_abs)
    ys_h = np.array(high_vals)
    xs_l = np.array(lows_abs)
    ys_l = np.array(low_vals)

    fit_h = _linear_fit_from_points(xs_h, ys_h)
    fit_l = _linear_fit_from_points(xs_l, ys_l)
    if fit_h is None or fit_l is None:
        return None

    # Evaluate width at start and at end: width should shrink
    x_start = float(start)
    x_end = float(end)
    width_start = (np.polyval(fit_h, x_start) - np.polyval(fit_l, x_start))
    width_end = (np.polyval(fit_h, x_end) - np.polyval(fit_l, x_end))
    if width_end <= 0 or width_start <= 0:
        return None
    if width_end > width_start * 0.95:
        # not converging enough
        return None

    # Volatility contraction: ATR or body size shrinking
    if 'atr_14' in df.columns and not df['atr_14'].isna().all():
        recent_atr = df['atr_14'].iloc[end-9:end+1].mean() if end-9 >= 0 else df['atr_14'].iloc[:end+1].mean()
        prev_atr = df['atr_14'].iloc[max(start, end-29):end-9].mean() if end-29 >= 0 and end-9 > start else recent_atr * 1.1
        if recent_atr >= prev_atr * 0.95:
            return None
    else:
        # fallback: average body size shrink
        bodies = (df['high'] - df['low']).abs()
        recent_body = bodies.iloc[end-9:end+1].mean() if end-9 >= 0 else bodies.iloc[:end+1].mean()
        prev_body = bodies.iloc[max(start, end-29):end-9].mean() if end-29 >= 0 and end-9 > start else recent_body * 1.1
        if recent_body >= prev_body * 0.95:
            return None

    # Minimum alternating touches: ensure at least 4 pivot touches combined and alternating
    combined = sorted([(int(x), 'H') for x in highs_abs] + [(int(x), 'L') for x in lows_abs], key=lambda x: x[0])
    if len(combined) < 4:
        return None
    # Check alternation in the last 4 touches
    last4 = combined[-4:]
    types = [t for _, t in last4]
    if not (types == ['H', 'L', 'H', 'L'] or types == ['L', 'H', 'L', 'H']):
        return None

    # Prior directional thrust: check momentum before the pattern (20 candles prior)
    thrust_ok = False
    pre_start = max(0, start - 30)
    if pre_start < start:
        pre_change = abs(df['close'].iloc[start] - df['close'].iloc[pre_start]) / df['close'].iloc[pre_start] if df['close'].iloc[pre_start] != 0 else 0
        if pre_change > 0.04:
            thrust_ok = True
    if not thrust_ok:
        # not mandatory for weaker scans, but require it for this triangle
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
    # large body
    body = abs(row['close'] - row['open'])
    total_range = row['high'] - row['low'] if row['high'] - row['low'] > 0 else 1.0
    closes_near_extreme = False
    if direction == 'bullish':
        closes_near_extreme = row['close'] >= row['high'] - 0.15 * total_range
    else:
        closes_near_extreme = row['close'] <= row['low'] + 0.15 * total_range

    return (body >= avg_body * 1.0) and closes_near_extreme and (row['volume'] >= vol_avg)


def check_ungli_bullish(df: pd.DataFrame, idx: int) -> bool:
    o = df['open'].iloc[idx]
    c = df['close'].iloc[idx]
    h = df['high'].iloc[idx]
    l = df['low'].iloc[idx]
    body = abs(c - o)
    lower_wick = min(o, c) - l
    if body <= 0: return False
    cond = (lower_wick >= 2 * body) and (c >= h - 0.1 * (h - l))
    return cond


def check_ungli_bearish(df: pd.DataFrame, idx: int) -> bool:
    o = df['open'].iloc[idx]
    c = df['close'].iloc[idx]
    h = df['high'].iloc[idx]
    l = df['low'].iloc[idx]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    if body <= 0: return False
    cond = (upper_wick >= 2 * body) and (c <= l + 0.1 * (h - l))
    return cond


def hist_converging_to_zero(df: pd.DataFrame, i: int, bars: int = 3) -> bool:
    if 'macd_hist' not in df.columns or i - bars < 0:
        return False
    vals = df['macd_hist'].iloc[i-bars+1:i+1].abs().values
    return all(vals[j] < vals[j-1] for j in range(1, len(vals)))


# ─── MASTER SCANNER ROUTINE ────────────────────────────────────────────

def scan_for_patterns(symbol: str, df: pd.DataFrame, timeframe: str, htf_df: pd.DataFrame | None = None) -> list[dict]:
    if df is None or len(df) < 50:
        return []

    setups = []
    
    # Calculate global pivots once for chart patterns
    highs, lows = get_pivots(df, order=4)
    
    # Analyze the last 3 visible candles to give realtime feedback
    for i in range(len(df) - 3, len(df)):
        if i < 20: continue
            
        row = df.iloc[i]
        date_str = str(row["datetime"])
        
        # Confluence
        sma_200 = row.get("sma_200", 0)
        is_above_200 = row["close"] > sma_200 if pd.notna(sma_200) else False
        vol = row["volume"]
        vol_avg = row.get("volume_sma_20", 0)
        is_volume_surge = vol > (vol_avg * 1.5) if pd.notna(vol_avg) else False
        rsi = row.get("rsi_14", 50)
        is_oversold = rsi < 30 if pd.notna(rsi) else False
        is_overbought = rsi > 70 if pd.notna(rsi) else False
        
        confluence_flags = {
            "above_200_sma": bool(is_above_200),
            "volume_surge": bool(is_volume_surge),
            "rsi_oversold": bool(is_oversold),
            "rsi_overbought": bool(is_overbought)
        }
        
        def add_setup(name: str, category: str, direction: str, base_score: int, marks: list, is_specialized: bool = False, is_primary: bool = False):
            score = base_score
            if direction == "bullish" and is_above_200: score += 15
            if direction == "bearish" and not is_above_200: score += 15
            if is_volume_surge: score += 15
            if direction == "bullish" and is_oversold: score += 10
            if direction == "bearish" and is_overbought: score += 10
            
            sl = float(row["low"]) if direction == "bullish" else float(row["high"])
            tp = float(row["close"]) + (1.5 * abs(float(row["close"]) - sl)) if direction == "bullish" else float(row["close"]) - (1.5 * abs(float(row["close"]) - sl))

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
                "entry_price": float(row["close"]),
                "stop_loss_price": sl,
                "take_profit_price": tp,
                "is_specialized": is_specialized,
                "is_primary": is_primary
            })

        # Base candle timestamps
        m1 = str(df.iloc[i-2]["datetime"]) if i>=2 else date_str
        m2 = str(df.iloc[i-1]["datetime"]) if i>=1 else date_str
        m3 = date_str

        # ATOMIC
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
            direction = "bullish" if hs_type in ["hammer", "inverted_hammer"] else "bearish"
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
            direction = "bullish" if row["close"] > row["open"] else "bearish"
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
            
        cas = check_counterattack_separating(df, i)
        if cas:
            name = cas.replace("_", " ").title()
            direction = "bullish" if row["close"] > row["open"] else "bearish"
            add_setup(name, "candlestick_atomic", direction, 40, [m2, m3])

        # MULTI
        if check_morning_star(df, i):
            add_setup("Morning Star", "candlestick_multi", "bullish", 60, [m1, m2, m3])
        if check_evening_star(df, i):
            add_setup("Evening Star", "candlestick_multi", "bearish", 60, [m1, m2, m3])
        ts_soldiers = check_three_white_soldiers(df, i)
        if ts_soldiers:
            add_setup("Three White Soldiers", "candlestick_multi", "bullish", 65, [m1, m2, m3])
            
        ts_crows = check_three_black_crows(df, i)
        if ts_crows:
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
            m4, m5 = str(df.iloc[i-3]["datetime"]), str(df.iloc[i-4]["datetime"])
            add_setup(name, "candlestick_multi", direction, 75, [m5, m4, m1, m2, m3])
            
        tls = check_three_line_strike(df, i)
        if tls:
            name = tls.replace("_", " ").title()
            direction = "bullish" if "bullish" in tls else "bearish"
            add_setup(name, "candlestick_multi", direction, 70, [m1, m2, m3])
            
        if check_stick_sandwich(df, i):
            add_setup("Stick Sandwich", "candlestick_multi", "bullish", 60, [m1, m2, m3])

        # CHART GEOMETRY
        # We define them based on finding tops/bottoms using argrelextrema. 
        # If it matches, we point to the last 2-3 pivot points found
        p_list = []
        if check_double_top(df, highs, i):
            # Extract timestamps for the peaks
            p1 = str(df.iloc[highs[-2]]["datetime"])
            p2 = str(df.iloc[highs[-1]]["datetime"])
            add_setup("Double Top", "macro_market_geometry", "bearish", 70, [p1, p2, m3])
            
        if check_double_bottom(df, lows, i):
            p1 = str(df.iloc[lows[-2]]["datetime"])
            p2 = str(df.iloc[lows[-1]]["datetime"])
            add_setup("Double Bottom", "macro_market_geometry", "bullish", 70, [p1, p2, m3])

        if check_triple_pivots(df, highs, i):
            p1 = str(df.iloc[highs[-3]]["datetime"])
            p2 = str(df.iloc[highs[-2]]["datetime"])
            p3 = str(df.iloc[highs[-1]]["datetime"])
            add_setup("Triple Top", "macro_market_geometry", "bearish", 85, [p1, p2, p3, m3])

        if check_triple_pivots(df, lows, i):
            p1 = str(df.iloc[lows[-3]]["datetime"])
            p2 = str(df.iloc[lows[-2]]["datetime"])
            p3 = str(df.iloc[lows[-1]]["datetime"])
            add_setup("Triple Bottom", "macro_market_geometry", "bullish", 85, [p1, p2, p3, m3])

        hs = check_head_and_shoulders(df, highs, i)
        if hs:
            p1 = str(df.iloc[highs[-3]]["datetime"])
            p2 = str(df.iloc[highs[-2]]["datetime"])
            p3 = str(df.iloc[highs[-1]]["datetime"])
            add_setup("Head and Shoulders", "macro_market_geometry", "bearish", 80, [p1, p2, p3, m3])
            
        ihs = check_inv_head_and_shoulders(df, lows, i)
        if ihs:
            p1 = str(df.iloc[lows[-3]]["datetime"])
            p2 = str(df.iloc[lows[-2]]["datetime"])
            p3 = str(df.iloc[lows[-1]]["datetime"])
            add_setup("Inv Head & Shoulders", "macro_market_geometry", "bullish", 80, [p1, p2, p3, m3])

        # SPECIALIZED PATTERNS: DOUBLE BOTTOMS/TOPS & EMA KNOTS
        # Double Bottom with Bullish Confirmation
        if check_double_bottom_specialized(df, i) and check_double_bottom_bullish_confirmation(df, i):
            add_setup("Double Bottom", "specialized_patterns", "bullish", 75, [m3], is_specialized=True)
        
        # Double Top with Bearish Confirmation
        if check_double_top_specialized(df, i) and check_double_top_bearish_confirmation(df, i):
            add_setup("Double Top", "specialized_patterns", "bearish", 75, [m3], is_specialized=True)
        
        # EMA Knots Pattern
        ema_knot = check_ema_knots(df, i)
        if ema_knot:
            direction = "bullish" if "bullish" in ema_knot else "bearish"
            add_setup("EMA Knots", "specialized_patterns", direction, 70, [m3], is_specialized=True)

        # TRIANGLE BREAKOUT / BREAKDOWN (Primary specialized system)
        tri = detect_triangle_compression(df, i, lookback=60)
        if tri is not None:
            # compute upper/lower trendline value at index i
            try:
                upper_val = np.polyval(tri['high_fit'], i)
                lower_val = np.polyval(tri['low_fit'], i)
            except Exception:
                upper_val = None
                lower_val = None

            avg_body = df[['close', 'open']].apply(lambda r: abs(r['close'] - r['open']), axis=1).rolling(10).mean().iloc[i] if i >= 10 else abs(row['close'] - row['open'])
            vol_avg = row.get('volume_sma_20', None)
            if pd.isna(vol_avg) or vol_avg == 0:
                vol_avg = df['volume'].rolling(20).mean().iloc[i] if i >= 20 else df['volume'].mean()

            # Bullish breakout
            if upper_val is not None and row['close'] > upper_val:
                body = abs(row['close'] - row['open'])
                if body > avg_body and row['volume'] >= vol_avg:
                    tlbo = True
                    bbc = check_bbc(row, avg_body, vol_avg, 'bullish')
                    ungli = check_ungli_bullish(df, i-1) if i-1 >= 0 else False
                    tide_ok = check_tide_conditions(df, i, htf_df, 'bullish')
                    wave_ok = check_wave_conditions(df, i, 'bullish', tlbo, bbc, ungli)
                    vol_confirm = row['volume'] >= vol_avg
                    if tide_ok and wave_ok and vol_confirm:
                        # Targets
                        breakout_level = float(row['close'])
                        tri_height = float(tri.get('height', 0))
                        primary_target = breakout_level + tri_height
                        # compute pre-triangle thrust distance
                        pre_idx = max(0, tri['start'] - 20)
                        thrust_dist = abs(df['close'].iloc[tri['start']] - df['close'].iloc[pre_idx]) if tri['start'] > pre_idx else tri_height
                        alt_target = breakout_level + 0.62 * thrust_dist
                        sl = float(min(row['low'], df['low'].iloc[i-1] if i-1>=0 else row['low']))
                        marks = [str(df.iloc[p]['datetime']) for p in (tri['high_pivots'] + tri['low_pivots']) if p < len(df)]
                        marks.append(m3)
                        setup_name = "Triangle Breakout"
                        add_setup(setup_name, "specialized_patterns", "bullish", 85, marks, is_specialized=True, is_primary=True)

            # Bearish breakdown
            if lower_val is not None and row['close'] < lower_val:
                body = abs(row['close'] - row['open'])
                if body > avg_body and row['volume'] >= vol_avg:
                    tlbd = True
                    bbc = check_bbc(row, avg_body, vol_avg, 'bearish')
                    ungli = check_ungli_bearish(df, i-1) if i-1 >= 0 else False
                    tide_ok = check_tide_conditions(df, i, htf_df, 'bearish')
                    wave_ok = check_wave_conditions(df, i, 'bearish', tlbd, bbc, ungli)
                    vol_confirm = row['volume'] >= vol_avg
                    if tide_ok and wave_ok and vol_confirm:
                        breakout_level = float(row['close'])
                        tri_height = float(tri.get('height', 0))
                        primary_target = breakout_level - tri_height
                        pre_idx = max(0, tri['start'] - 20)
                        thrust_dist = abs(df['close'].iloc[tri['start']] - df['close'].iloc[pre_idx]) if tri['start'] > pre_idx else tri_height
                        alt_target = breakout_level - 0.62 * thrust_dist
                        sl = float(max(row['high'], df['high'].iloc[i-1] if i-1>=0 else row['high']))
                        marks = [str(df.iloc[p]['datetime']) for p in (tri['high_pivots'] + tri['low_pivots']) if p < len(df)]
                        marks.append(m3)
                        setup_name = "Triangle Breakdown"
                        add_setup(setup_name, "specialized_patterns", "bearish", 85, marks, is_specialized=True, is_primary=True)


    # Deduplicate returning one entry per pattern name.
    # Prefer primary setups, then specialized setups, then highest score.
    unique_setups = {}
    for s in setups:
        key = s["pattern_name"]
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

        # Prefer specialized setups over generic ones
        if s.get("is_specialized", False) and not existing.get("is_specialized", False):
            unique_setups[key] = s
            continue
        if existing.get("is_specialized", False) and not s.get("is_specialized", False):
            continue

        # Otherwise choose the one with the higher score
        if s["setup_score"] > existing["setup_score"]:
            unique_setups[key] = s

    return list(unique_setups.values())
