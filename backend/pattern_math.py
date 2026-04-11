import pandas as pd
import numpy as np
import ta
from backend.data_fetcher import fetch_data

MIN_BARS_BETWEEN_SWINGS = 3
MAX_PATTERN_WINDOW = 50
TRIANGLE_WINDOW = 60
PATTERN_COOLDOWN = 10
GLOBAL_CAPITAL = 100000.0

def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    df = fetch_data(symbol)
    if df is not None:
        # Capitalize columns to match the new structure
        col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume", "datetime": "Date"}
        df.rename(columns=col_map, inplace=True)
        if "Date" in df.columns:
            df.set_index("Date", inplace=True)
    return df

def enrich_candle_anatomy(df: pd.DataFrame) -> pd.DataFrame:
    """Add body, wick, and validity columns."""
    df = df.copy()
    df["raw_range"] = df["High"] - df["Low"]
    df["valid_candle"] = df["raw_range"] >= 1e-5
    df["range_"] = df["raw_range"].clip(lower=1e-8)
    df["body"] = (df["Close"] - df["Open"]).abs()
    df["upper_wick"] = df["High"] - df[["Open", "Close"]].max(axis=1)
    df["lower_wick"] = df[["Open", "Close"]].min(axis=1) - df["Low"]
    df["body_pct"] = df["body"] / df["range_"]
    return df

# ──────────────────────────────────────────────
# §2  INDICATORS
# ──────────────────────────────────────────────
def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    df["prev_RSI"] = df["RSI"].shift(1)
    df["rsi_delta"] = df["RSI"] - df["prev_RSI"]
    df["rsi_signal"] = df["rsi_delta"].abs() >= 2

    df["SMA_50"] = ta.trend.sma_indicator(df["Close"], window=50)
    df["SMA_200"] = ta.trend.sma_indicator(df["Close"], window=200)
    df["ATR_SMA_50"] = ta.trend.sma_indicator(df["ATR"], window=50)

    df["volume_ma"] = ta.trend.sma_indicator(df["Volume"].astype(float), window=20)
    df["volume_surge"] = df["Volume"] > 1.5 * df["volume_ma"]
    df["tolerance"] = 0.2 * df["ATR"]
    return df

# ──────────────────────────────────────────────
# §3  MARKET REGIME FILTER
# ──────────────────────────────────────────────
def regime_filter(row: pd.Series) -> tuple[bool, bool]:
    """Return (trend_valid, volatility_valid) for a single bar."""
    trend_strength = abs(row["SMA_50"] - row["SMA_200"])
    trend_valid = trend_strength > 0.5 * row["ATR"]
    volatility_valid = row["ATR"] > row["ATR_SMA_50"] * 0.8
    return trend_valid, volatility_valid

# ──────────────────────────────────────────────
# §6  SINGLE-CANDLE PATTERNS
# ──────────────────────────────────────────────
def detect_hammer(row: pd.Series) -> bool:
    return (
        row["body_pct"] <= 0.3
        and row["lower_wick"] >= max(2 * row["body"], 0.6 * row["range_"])
        and row["upper_wick"] <= 0.15 * row["range_"]
    )

def detect_shooting_star(row: pd.Series) -> bool:
    return (
        row["body_pct"] <= 0.3
        and row["upper_wick"] >= max(2 * row["body"], 0.6 * row["range_"])
        and row["lower_wick"] <= 0.15 * row["range_"]
    )

def detect_doji(row: pd.Series) -> bool:
    return row["body_pct"] <= 0.05

# ──────────────────────────────────────────────
# §7  MULTI-CANDLE (Morning Star / Evening Star)
# ──────────────────────────────────────────────
def detect_morning_star(df: pd.DataFrame, idx: int) -> bool:
    if idx < 2:
        return False
    c1 = df.iloc[idx - 2]
    c2 = df.iloc[idx - 1]
    c3 = df.iloc[idx]
    c1_bearish = c1["Close"] < c1["Open"]
    c2_small = c2["body_pct"] <= 0.3
    c3_bullish = c3["Close"] > c3["Open"]
    c3_closes_into_c1 = c3["Close"] > (c1["Open"] + c1["Close"]) / 2
    return c1_bearish and c2_small and c3_bullish and c3_closes_into_c1

def detect_evening_star(df: pd.DataFrame, idx: int) -> bool:
    if idx < 2:
        return False
    c1 = df.iloc[idx - 2]
    c2 = df.iloc[idx - 1]
    c3 = df.iloc[idx]
    c1_bullish = c1["Close"] > c1["Open"]
    c2_small = c2["body_pct"] <= 0.3
    c3_bearish = c3["Close"] < c3["Open"]
    c3_closes_into_c1 = c3["Close"] < (c1["Open"] + c1["Close"]) / 2
    return c1_bullish and c2_small and c3_bearish and c3_closes_into_c1


# ──────────────────────────────────────────────
# §8  TWEEZER TOP / BOTTOM
# ──────────────────────────────────────────────
def detect_tweezer(df: pd.DataFrame, idx: int) -> str | None:
    """Returns 'tweezer_top', 'tweezer_bottom', or None."""
    if idx < MIN_BARS_BETWEEN_SWINGS:
        return None
    cur = df.iloc[idx]
    tol = cur["tolerance"]
    # Search backwards within valid spacing
    for j in range(MIN_BARS_BETWEEN_SWINGS, min(idx, MAX_PATTERN_WINDOW) + 1):
        prev = df.iloc[idx - j]
        if abs(prev["High"] - cur["High"]) <= tol:
            return "tweezer_top"
        if abs(prev["Low"] - cur["Low"]) <= tol:
            return "tweezer_bottom"
    return None

# ──────────────────────────────────────────────
# §9  TRIANGLE (Rolling Regression + Breakout)
# ──────────────────────────────────────────────
def detect_triangle(df: pd.DataFrame, idx: int) -> dict | None:
    """
    Rolling linear regression on upper/lower bounds.
    Returns a signal dict fragment or None.
    """
    window = TRIANGLE_WINDOW
    if idx < window:
        return None

    cur = df.iloc[idx]
    volatility_valid = cur["ATR"] > cur["ATR_SMA_50"] * 0.8
    if not volatility_valid:
        return None

    highs = df["High"].iloc[idx - window + 1 : idx + 1].values
    lows = df["Low"].iloc[idx - window + 1 : idx + 1].values
    x = np.arange(window, dtype=float)

    try:
        upper_slope, upper_intercept = np.polyfit(x, highs, 1)
        lower_slope, lower_intercept = np.polyfit(x, lows, 1)
    except np.linalg.LinAlgError:
        return None

    t = window - 1
    upper_trend = upper_slope * t + upper_intercept
    lower_trend = lower_slope * t + lower_intercept

    width_start = highs[0] - lows[0]
    width_end = highs[-1] - lows[-1]

    if width_start <= 0:
        return None
    if width_end > 0.95 * width_start:
        return None  # Not converging

    close = cur["Close"]
    atr = cur["ATR"]
    buffer = max(0.5 * atr, 0.003 * close)

    if close > upper_trend + buffer:
        entry = close
        stop_loss = lower_trend
        target = entry + width_start
        return {
            "pattern_type": "triangle_breakout",
            "direction": "long",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": target,
        }
    elif close < lower_trend - buffer:
        entry = close
        stop_loss = upper_trend
        target = entry - width_start
        return {
            "pattern_type": "triangle_breakout",
            "direction": "short",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": target,
        }
    return None

# ──────────────────────────────────────────────
# §10  DOUBLE TOP / DOUBLE BOTTOM (Fully Constrained)
# ──────────────────────────────────────────────
def _find_swing_points(series: pd.Series, kind: str = "high") -> list[tuple[int, float]]:
    """Return list of (positional-index, value) for local swing highs/lows."""
    pts = []
    for i in range(1, len(series) - 1):
        if kind == "high":
            if series.iloc[i] > series.iloc[i - 1] and series.iloc[i] > series.iloc[i + 1]:
                pts.append((i, series.iloc[i]))
        else:
            if series.iloc[i] < series.iloc[i - 1] and series.iloc[i] < series.iloc[i + 1]:
                pts.append((i, series.iloc[i]))
    return pts

def detect_double_top(df: pd.DataFrame, idx: int) -> dict | None:
    """
    Double Top:  peak1_idx < trough_idx < peak2_idx
    peak2 > peak1, abs(peak2 - peak1) <= 0.05 * peak1
    RSI divergence, volume divergence, neckline break + volume surge.
    """
    window_start = max(0, idx - MAX_PATTERN_WINDOW)
    window_df = df.iloc[window_start : idx + 1]
    if len(window_df) < MIN_BARS_BETWEEN_SWINGS * 3:
        return None

    peaks = _find_swing_points(window_df["High"], "high")
    troughs = _find_swing_points(window_df["Low"], "low")

    if len(peaks) < 2 or len(troughs) < 1:
        return None

    # Try pairs starting from the most recent
    for i in range(len(peaks) - 1, 0, -1):
        p2_idx, p2_val = peaks[i]
        for j in range(i - 1, -1, -1):
            p1_idx, p1_val = peaks[j]

            spacing = p2_idx - p1_idx
            if spacing < MIN_BARS_BETWEEN_SWINGS or spacing > MAX_PATTERN_WINDOW:
                continue

            # Price proximity
            if abs(p2_val - p1_val) > 0.05 * p1_val:
                continue

            # Find trough between peaks
            mid_troughs = [t for t in troughs if p1_idx < t[0] < p2_idx]
            if not mid_troughs:
                continue
            trough_idx, trough_val = min(mid_troughs, key=lambda t: t[1])

            # RSI divergence:  RSI at peak2 < RSI at peak1 - 2
            abs_p1 = window_start + p1_idx
            abs_p2 = window_start + p2_idx
            rsi_p1 = df.iloc[abs_p1]["RSI"]
            rsi_p2 = df.iloc[abs_p2]["RSI"]
            if not (rsi_p2 < rsi_p1 - 2):
                continue

            # Volume divergence
            vol_p1 = df.iloc[abs_p1]["Volume"]
            vol_p2 = df.iloc[abs_p2]["Volume"]
            if not (vol_p2 < vol_p1):
                continue

            # Neckline break + volume surge
            cur = df.iloc[idx]
            if not (cur["Close"] < trough_val and cur["volume_surge"]):
                continue

            entry = cur["Close"]
            stop_loss = p2_val + 0.3 * cur["ATR"]
            target = entry - (p2_val - trough_val)

            return {
                "pattern_type": "double_top",
                "direction": "short",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": target,
            }
    return None

def detect_double_bottom(df: pd.DataFrame, idx: int) -> dict | None:
    """
    Double Bottom: trough1_idx < peak_idx < trough2_idx
    trough2 < trough1, abs(trough2 - trough1) <= 0.05 * trough1
    RSI divergence, volume contraction, neckline break + volume surge.
    """
    window_start = max(0, idx - MAX_PATTERN_WINDOW)
    window_df = df.iloc[window_start : idx + 1]
    if len(window_df) < MIN_BARS_BETWEEN_SWINGS * 3:
        return None

    troughs = _find_swing_points(window_df["Low"], "low")
    peaks = _find_swing_points(window_df["High"], "high")

    if len(troughs) < 2 or len(peaks) < 1:
        return None

    for i in range(len(troughs) - 1, 0, -1):
        t2_idx, t2_val = troughs[i]
        for j in range(i - 1, -1, -1):
            t1_idx, t1_val = troughs[j]

            spacing = t2_idx - t1_idx
            if spacing < MIN_BARS_BETWEEN_SWINGS or spacing > MAX_PATTERN_WINDOW:
                continue

            # Price proximity
            if abs(t2_val - t1_val) > 0.05 * t1_val:
                continue

            # Find peak between troughs
            mid_peaks = [p for p in peaks if t1_idx < p[0] < t2_idx]
            if not mid_peaks:
                continue
            peak_idx, peak_val = max(mid_peaks, key=lambda p: p[1])

            # RSI divergence: RSI at trough2 > RSI at trough1 + 2
            abs_t1 = window_start + t1_idx
            abs_t2 = window_start + t2_idx
            rsi_t1 = df.iloc[abs_t1]["RSI"]
            rsi_t2 = df.iloc[abs_t2]["RSI"]
            if not (rsi_t2 > rsi_t1 + 2):
                continue

            # Volume contraction at formation
            vol_t1 = df.iloc[abs_t1]["Volume"]
            vol_t2 = df.iloc[abs_t2]["Volume"]
            if not (vol_t2 < vol_t1):
                continue

            # Neckline break + volume surge
            cur = df.iloc[idx]
            if not (cur["Close"] > peak_val and cur["volume_surge"]):
                continue

            entry = cur["Close"]
            stop_loss = t2_val - 0.3 * cur["ATR"]
            target = entry + (peak_val - t2_val)

            return {
                "pattern_type": "double_bottom",
                "direction": "long",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": target,
            }
    return None

# ──────────────────────────────────────────────
# ENGULFING PATTERNS
# ──────────────────────────────────────────────
def detect_engulfing(df: pd.DataFrame, idx: int) -> str | None:
    if idx < 1:
        return None
    prev = df.iloc[idx - 1]
    cur = df.iloc[idx]
    if (
        prev["Close"] < prev["Open"]
        and cur["Close"] > cur["Open"]
        and cur["Open"] <= prev["Close"]
        and cur["Close"] >= prev["Open"]
    ):
        return "engulfing_bullish"
    if (
        prev["Close"] > prev["Open"]
        and cur["Close"] < cur["Open"]
        and cur["Open"] >= prev["Close"]
        and cur["Close"] <= prev["Open"]
    ):
        return "engulfing_bearish"
    return None

# ──────────────────────────────────────────────
# §11 RISK MODEL
# ──────────────────────────────────────────────
def risk_gate(entry: float, stop_loss: float, take_profit: float, direction: str) -> tuple[bool, float, float]:
    """
    Returns (valid, risk_reward, position_size).
    Hard constraint: RR ≥ 2.0.
    """
    risk = abs(entry - stop_loss)
    risk = max(risk, 1e-4)
    reward = abs(take_profit - entry)

    rr = reward / risk
    position_size = (0.01 * GLOBAL_CAPITAL) / risk

    return rr >= 2.0, round(rr, 2), round(position_size, 2)

# ──────────────────────────────────────────────
# §5 + §12  PATTERN LABELING + SIGNAL EXECUTION
# ──────────────────────────────────────────────
def build_single_candle_signal(row, pattern: str) -> dict:
    """Construct entry/SL/TP for single-candle patterns using ATR."""
    atr = row["ATR"]
    close = row["Close"]
    if pattern == "hammer":
        return {"direction": "long", "entry": close, "stop_loss": row["Low"] - 0.3 * atr, "take_profit": close + 2.5 * atr}
    elif pattern == "shooting_star":
        return {"direction": "short", "entry": close, "stop_loss": row["High"] + 0.3 * atr, "take_profit": close - 2.5 * atr}
    elif pattern == "doji":
        # Doji is neutral — directional bias from trend
        if row["SMA_50"] > row["SMA_200"]:
            return {"direction": "long", "entry": close, "stop_loss": row["Low"] - 0.3 * atr, "take_profit": close + 2.0 * atr}
        else:
            return {"direction": "short", "entry": close, "stop_loss": row["High"] + 0.3 * atr, "take_profit": close - 2.0 * atr}
    return {}

def build_tweezer_signal(df, idx, kind):
    cur = df.iloc[idx]
    atr = cur["ATR"]
    close = cur["Close"]
    if kind == "tweezer_bottom":
        sl = cur["Low"] - 0.3 * atr
        tp = close + 2.5 * atr
        return {"direction": "long", "entry": close, "stop_loss": sl, "take_profit": tp}
    else:
        sl = cur["High"] + 0.3 * atr
        tp = close - 2.5 * atr
        return {"direction": "short", "entry": close, "stop_loss": sl, "take_profit": tp}

def build_multi_candle_signal(df, idx, kind):
    cur = df.iloc[idx]
    atr = cur["ATR"]
    close = cur["Close"]
    if kind == "morning_star":
        sl = df.iloc[idx - 1]["Low"] - 0.3 * atr
        tp = close + 2.5 * atr
        return {"direction": "long", "entry": close, "stop_loss": sl, "take_profit": tp}
    else:  # evening_star
        sl = df.iloc[idx - 1]["High"] + 0.3 * atr
        tp = close - 2.5 * atr
        return {"direction": "short", "entry": close, "stop_loss": sl, "take_profit": tp}

def analyze_ticker(ticker_info: dict) -> list[dict]:
    """
    Run the full pattern suite on one ticker.
    Returns a list of valid signal dicts (may be empty).
    """
    symbol = ticker_info.get("symbol")
    df = fetch_ohlcv(symbol)
    if df is None:
        return []

    # Discard bad ticks (§ Data Integrity: Low == High)
    df = df[df["High"] != df["Low"]].copy()
    if len(df) < 200:
        return []

    df = enrich_candle_anatomy(df)
    df = enrich_indicators(df)
    df = df.dropna(subset=["ATR", "RSI", "SMA_50", "SMA_200", "ATR_SMA_50", "volume_ma"]).copy()
    df = df.reset_index(drop=False)  # keep Date as column

    if len(df) < TRIANGLE_WINDOW + 10:
        return []

    signals: list[dict] = []
    last_pattern_bar = -PATTERN_COOLDOWN - 1  # allow first bar

    idx = len(df) - 2
    if idx < TRIANGLE_WINDOW:
        return []

    row = df.iloc[idx]

    # §3 Regime filter
    trend_valid, volatility_valid = regime_filter(row)
    if not (trend_valid and volatility_valid):
        return []

    # §5 Priority-ordered detection — one signal per bar
    detected = None

    # ── TRIANGLE ──
    tri = detect_triangle(df, idx)
    if tri is not None:
        detected = tri

    # ── DOUBLE TOP ──
    if detected is None:
        dt = detect_double_top(df, idx)
        if dt is not None:
            detected = dt

    # ── DOUBLE BOTTOM ──
    if detected is None:
        db = detect_double_bottom(df, idx)
        if db is not None:
            detected = db

    # ── MORNING STAR ──
    if detected is None and detect_morning_star(df, idx):
        frag = build_multi_candle_signal(df, idx, "morning_star")
        detected = {"pattern_type": "morning_star", **frag}

    # ── EVENING STAR ──
    if detected is None and detect_evening_star(df, idx):
        frag = build_multi_candle_signal(df, idx, "evening_star")
        detected = {"pattern_type": "evening_star", **frag}

    # ── TWEEZER ──
    if detected is None:
        tw = detect_tweezer(df, idx)
        if tw is not None:
            frag = build_tweezer_signal(df, idx, tw)
            detected = {"pattern_type": tw, **frag}

    # ── ENGULFING ──
    if detected is None:
        eng = detect_engulfing(df, idx)
        if eng is not None:
            direction = "long" if eng == "engulfing_bullish" else "short"
            atr = row["ATR"]
            close = row["Close"]
            if direction == "long":
                sl = row["Low"] - 0.3 * atr
                tp = close + 2.5 * atr
            else:
                sl = row["High"] + 0.3 * atr
                tp = close - 2.5 * atr
            detected = {"pattern_type": eng, "direction": direction, "entry": close, "stop_loss": sl, "take_profit": tp}

    # ── SINGLE CANDLE ──
    if detected is None:
        for sc_name, sc_fn in [("hammer", detect_hammer), ("shooting_star", detect_shooting_star), ("doji", detect_doji)]:
            if sc_fn(row):
                frag = build_single_candle_signal(row, sc_name)
                detected = {"pattern_type": sc_name, **frag}
                break

    if detected is None:
        return []
        
    return [detected]

# Wrapper for compatibility with pattern_matcher
def analyze_df(df: pd.DataFrame, symbol: str = None) -> list[dict]:
    if not symbol:
        return []
    return analyze_ticker({"symbol": symbol})
