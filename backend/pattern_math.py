import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple

# Tunable constants (sensible defaults)
MIN_BARS_BETWEEN_SWINGS = 3
MAX_PATTERN_WINDOW = 50
TRIANGLE_WINDOW = 60
PATTERN_COOLDOWN = 10
GLOBAL_CAPITAL = 100000.0


# -------------------- Candle anatomy + indicators --------------------
def enrich_candle_anatomy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["raw_range"] = df["high"] - df["low"]
    df["valid_candle"] = df["raw_range"] >= 1e-5
    df["range_"] = df["raw_range"].clip(lower=1e-8)
    df["body"] = (df["close"] - df["open"]).abs()
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["body_pct"] = df["body"] / df["range_"]
    return df


def _compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window, min_periods=1).mean()


def _compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    # Wilder's smoothing via EWMA with alpha=1/window
    ma_up = up.ewm(alpha=1.0 / window, adjust=False).mean()
    ma_down = down.ewm(alpha=1.0 / window, adjust=False).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    return rsi


def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # ATR
    if "atr" not in df.columns:
        df["atr"] = _compute_atr(df, window=14)
    # RSI
    if "rsi" not in df.columns:
        df["rsi"] = _compute_rsi(df["close"], window=14)
    df["prev_rsi"] = df["rsi"].shift(1)
    df["rsi_delta"] = df["rsi"] - df["prev_rsi"]
    df["rsi_signal"] = df["rsi_delta"].abs() >= 2

    # SMAs
    df["sma_50"] = df["close"].rolling(50, min_periods=1).mean()
    df["sma_200"] = df["close"].rolling(200, min_periods=1).mean()
    df["atr_sma_50"] = df["atr"].rolling(50, min_periods=1).mean()

    # Volume
    if "volume" in df.columns:
        df["volume_ma"] = df["volume"].astype(float).rolling(20, min_periods=1).mean()
        df["volume_surge"] = df["volume"] > 1.5 * df["volume_ma"]
    else:
        df["volume_ma"] = pd.Series(index=df.index, dtype=float)
        df["volume_surge"] = pd.Series(False, index=df.index)

    df["tolerance"] = 0.2 * df["atr"]
    return df


# -------------------- Regime filter --------------------
def regime_filter(row: pd.Series) -> Tuple[bool, bool]:
    sma50, sma200 = row.get("sma_50"), row.get("sma_200")
    atr = row.get("atr")
    if pd.isna(sma50) or pd.isna(sma200) or pd.isna(atr):
        return False, False
    trend_strength = abs(sma50 - sma200)
    trend_valid = trend_strength > 0.5 * atr
    atr_sma50 = row.get("atr_sma_50", np.nan)
    volatility_valid = False
    if pd.notna(atr_sma50):
        volatility_valid = atr > atr_sma50 * 0.8
    return bool(trend_valid), bool(volatility_valid)


# -------------------- Single-candle detectors --------------------
def detect_hammer(row: pd.Series) -> bool:
    return (
        row.get("body_pct", 1.0) <= 0.3
        and row.get("lower_wick", 0.0) >= max(2 * row.get("body", 0.0), 0.6 * row.get("raw_range", 0.0))
        and row.get("upper_wick", 0.0) <= 0.15 * row.get("raw_range", 0.0)
    )


def detect_shooting_star(row: pd.Series) -> bool:
    return (
        row.get("body_pct", 1.0) <= 0.3
        and row.get("upper_wick", 0.0) >= max(2 * row.get("body", 0.0), 0.6 * row.get("raw_range", 0.0))
        and row.get("lower_wick", 0.0) <= 0.15 * row.get("raw_range", 0.0)
    )


def detect_doji(row: pd.Series) -> bool:
    return row.get("body_pct", 1.0) <= 0.05


# -------------------- Multi-candle detectors --------------------
def detect_morning_star(df: pd.DataFrame, idx: int) -> bool:
    if idx < 2:
        return False
    c1 = df.iloc[idx - 2]
    c2 = df.iloc[idx - 1]
    c3 = df.iloc[idx]
    c1_bearish = c1["close"] < c1["open"]
    c2_small = c2["body_pct"] <= 0.3
    c3_bullish = c3["close"] > c3["open"]
    c3_closes_into_c1 = c3["close"] > (c1["open"] + c1["close"]) / 2
    return c1_bearish and c2_small and c3_bullish and c3_closes_into_c1


def detect_evening_star(df: pd.DataFrame, idx: int) -> bool:
    if idx < 2:
        return False
    c1 = df.iloc[idx - 2]
    c2 = df.iloc[idx - 1]
    c3 = df.iloc[idx]
    c1_bullish = c1["close"] > c1["open"]
    c2_small = c2["body_pct"] <= 0.3
    c3_bearish = c3["close"] < c3["open"]
    c3_closes_into_c1 = c3["close"] < (c1["open"] + c1["close"]) / 2
    return c1_bullish and c2_small and c3_bearish and c3_closes_into_c1


# -------------------- Tweezer detector --------------------
def detect_tweezer(df: pd.DataFrame, idx: int) -> Optional[str]:
    if idx < MIN_BARS_BETWEEN_SWINGS:
        return None
    cur = df.iloc[idx]
    tol = cur.get("tolerance", 0.0)
    for j in range(MIN_BARS_BETWEEN_SWINGS, min(idx, MAX_PATTERN_WINDOW) + 1):
        prev = df.iloc[idx - j]
        if abs(prev["high"] - cur["high"]) <= tol:
            return "tweezer_top"
        if abs(prev["low"] - cur["low"]) <= tol:
            return "tweezer_bottom"
    return None


# -------------------- Triangle detection (rolling regression) --------------------
def detect_triangle(df: pd.DataFrame, idx: int) -> Optional[Dict]:
    window = TRIANGLE_WINDOW
    if idx < window:
        return None

    cur = df.iloc[idx]
    atr = cur.get("atr", np.nan)
    atr_sma50 = cur.get("atr_sma_50", np.nan)
    if pd.isna(atr) or pd.isna(atr_sma50) or not (atr > atr_sma50 * 0.8):
        return None

    highs = df["high"].iloc[idx - window + 1 : idx + 1].values
    lows = df["low"].iloc[idx - window + 1 : idx + 1].values
    x = np.arange(window, dtype=float)

    try:
        upper_slope, upper_intercept = np.polyfit(x, highs, 1)
        lower_slope, lower_intercept = np.polyfit(x, lows, 1)
    except Exception:
        return None

    t = window - 1
    upper_trend = upper_slope * t + upper_intercept
    lower_trend = lower_slope * t + lower_intercept

    width_start = highs[0] - lows[0]
    width_end = highs[-1] - lows[-1]

    if width_start <= 0:
        return None
    if width_end > 0.95 * width_start:
        return None

    close = cur["close"]
    buffer = max(0.5 * atr, 0.003 * close)

    if close > upper_trend + buffer:
        entry = close
        stop_loss = lower_trend
        target = entry + width_start
        return {
            "pattern_type": "triangle_breakout",
            "direction": "long",
            "entry": float(entry),
            "stop_loss": float(stop_loss),
            "take_profit": float(target),
            "is_primary": True,
        }
    elif close < lower_trend - buffer:
        entry = close
        stop_loss = upper_trend
        target = entry - width_start
        return {
            "pattern_type": "triangle_breakout",
            "direction": "short",
            "entry": float(entry),
            "stop_loss": float(stop_loss),
            "take_profit": float(target),
            "is_primary": True,
        }
    return None


# -------------------- Double top / double bottom (swing-based) --------------------
def _find_swing_points(series: pd.Series, kind: str = "high") -> List[Tuple[int, float]]:
    pts: List[Tuple[int, float]] = []
    for i in range(1, len(series) - 1):
        if kind == "high":
            if series.iloc[i] > series.iloc[i - 1] and series.iloc[i] > series.iloc[i + 1]:
                pts.append((i, float(series.iloc[i])))
        else:
            if series.iloc[i] < series.iloc[i - 1] and series.iloc[i] < series.iloc[i + 1]:
                pts.append((i, float(series.iloc[i])))
    return pts


def detect_double_top(df: pd.DataFrame, idx: int) -> Optional[Dict]:
    window_start = max(0, idx - MAX_PATTERN_WINDOW)
    window_df = df.iloc[window_start : idx + 1]
    if len(window_df) < MIN_BARS_BETWEEN_SWINGS * 3:
        return None

    peaks = _find_swing_points(window_df["high"], "high")
    troughs = _find_swing_points(window_df["low"], "low")

    if len(peaks) < 2 or len(troughs) < 1:
        return None

    for i in range(len(peaks) - 1, 0, -1):
        p2_idx, p2_val = peaks[i]
        for j in range(i - 1, -1, -1):
            p1_idx, p1_val = peaks[j]

            spacing = p2_idx - p1_idx
            if spacing < MIN_BARS_BETWEEN_SWINGS or spacing > MAX_PATTERN_WINDOW:
                continue

            if abs(p2_val - p1_val) > 0.05 * p1_val:
                continue

            mid_troughs = [t for t in troughs if p1_idx < t[0] < p2_idx]
            if not mid_troughs:
                continue
            trough_idx, trough_val = min(mid_troughs, key=lambda t: t[1])

            abs_p1 = window_start + p1_idx
            abs_p2 = window_start + p2_idx
            rsi_p1 = df.iloc[abs_p1].get("rsi", np.nan)
            rsi_p2 = df.iloc[abs_p2].get("rsi", np.nan)
            if not (pd.notna(rsi_p1) and pd.notna(rsi_p2) and rsi_p2 < rsi_p1 - 2):
                continue

            vol_p1 = df.iloc[abs_p1].get("volume", np.nan)
            vol_p2 = df.iloc[abs_p2].get("volume", np.nan)
            if not (pd.notna(vol_p1) and pd.notna(vol_p2) and vol_p2 < vol_p1):
                continue

            cur = df.iloc[idx]
            if not (cur["close"] < trough_val and bool(cur.get("volume_surge", False))):
                continue

            entry = float(cur["close"])
            stop_loss = float(p2_val + 0.3 * float(cur.get("atr", 0.0)))
            target = float(entry - (p2_val - trough_val))

            return {
                "pattern_type": "double_top",
                "direction": "short",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": target,
            }
    return None


def detect_double_bottom(df: pd.DataFrame, idx: int) -> Optional[Dict]:
    window_start = max(0, idx - MAX_PATTERN_WINDOW)
    window_df = df.iloc[window_start : idx + 1]
    if len(window_df) < MIN_BARS_BETWEEN_SWINGS * 3:
        return None

    troughs = _find_swing_points(window_df["low"], "low")
    peaks = _find_swing_points(window_df["high"], "high")

    if len(troughs) < 2 or len(peaks) < 1:
        return None

    for i in range(len(troughs) - 1, 0, -1):
        t2_idx, t2_val = troughs[i]
        for j in range(i - 1, -1, -1):
            t1_idx, t1_val = troughs[j]

            spacing = t2_idx - t1_idx
            if spacing < MIN_BARS_BETWEEN_SWINGS or spacing > MAX_PATTERN_WINDOW:
                continue

            if abs(t2_val - t1_val) > 0.05 * t1_val:
                continue

            mid_peaks = [p for p in peaks if t1_idx < p[0] < t2_idx]
            if not mid_peaks:
                continue
            peak_idx, peak_val = max(mid_peaks, key=lambda p: p[1])

            abs_t1 = window_start + t1_idx
            abs_t2 = window_start + t2_idx
            rsi_t1 = df.iloc[abs_t1].get("rsi", np.nan)
            rsi_t2 = df.iloc[abs_t2].get("rsi", np.nan)
            if not (pd.notna(rsi_t1) and pd.notna(rsi_t2) and rsi_t2 > rsi_t1 + 2):
                continue

            vol_t1 = df.iloc[abs_t1].get("volume", np.nan)
            vol_t2 = df.iloc[abs_t2].get("volume", np.nan)
            if not (pd.notna(vol_t1) and pd.notna(vol_t2) and vol_t2 < vol_t1):
                continue

            cur = df.iloc[idx]
            if not (cur["close"] > peak_val and bool(cur.get("volume_surge", False))):
                continue

            entry = float(cur["close"])
            stop_loss = float(t2_val - 0.3 * float(cur.get("atr", 0.0)))
            target = float(entry + (peak_val - t2_val))

            return {
                "pattern_type": "double_bottom",
                "direction": "long",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": target,
            }
    return None


# -------------------- Engulfing --------------------
def detect_engulfing(df: pd.DataFrame, idx: int) -> Optional[str]:
    if idx < 1:
        return None
    prev = df.iloc[idx - 1]
    cur = df.iloc[idx]
    if (
        prev["close"] < prev["open"]
        and cur["close"] > cur["open"]
        and cur["open"] <= prev["close"]
        and cur["close"] >= prev["open"]
    ):
        return "engulfing_bullish"
    if (
        prev["close"] > prev["open"]
        and cur["close"] < cur["open"]
        and cur["open"] >= prev["close"]
        and cur["close"] <= prev["open"]
    ):
        return "engulfing_bearish"
    return None


# -------------------- Risk model --------------------
def risk_gate(entry: float, stop_loss: float, take_profit: float, direction: str) -> Tuple[bool, float, float]:
    risk = abs(entry - stop_loss)
    risk = max(risk, 1e-4)
    reward = abs(take_profit - entry)
    rr = reward / risk if risk > 0 else 0.0
    position_size = (0.01 * GLOBAL_CAPITAL) / risk
    return rr >= 2.0, round(rr, 2), round(position_size, 2)


# -------------------- Signal builders --------------------
def build_single_candle_signal(row: pd.Series, pattern: str) -> Dict:
    atr = float(row.get("atr", 0.0))
    close = float(row["close"])
    if pattern == "hammer":
        return {"direction": "long", "entry": close, "stop_loss": float(row["low"] - 0.3 * atr), "take_profit": float(close + 2.5 * atr)}
    elif pattern == "shooting_star":
        return {"direction": "short", "entry": close, "stop_loss": float(row["high"] + 0.3 * atr), "take_profit": float(close - 2.5 * atr)}
    elif pattern == "doji":
        if row.get("sma_50", 0.0) > row.get("sma_200", 0.0):
            return {"direction": "long", "entry": close, "stop_loss": float(row["low"] - 0.3 * atr), "take_profit": float(close + 2.0 * atr)}
        else:
            return {"direction": "short", "entry": close, "stop_loss": float(row["high"] + 0.3 * atr), "take_profit": float(close - 2.0 * atr)}
    return {}


def build_tweezer_signal(df: pd.DataFrame, idx: int, kind: str) -> Dict:
    cur = df.iloc[idx]
    atr = float(cur.get("atr", 0.0))
    close = float(cur["close"])
    if kind == "tweezer_bottom":
        sl = float(cur["low"] - 0.3 * atr)
        tp = float(close + 2.5 * atr)
        return {"direction": "long", "entry": close, "stop_loss": sl, "take_profit": tp}
    else:
        sl = float(cur["high"] + 0.3 * atr)
        tp = float(close - 2.5 * atr)
        return {"direction": "short", "entry": close, "stop_loss": sl, "take_profit": tp}


def build_multi_candle_signal(df: pd.DataFrame, idx: int, kind: str) -> Dict:
    cur = df.iloc[idx]
    atr = float(cur.get("atr", 0.0))
    close = float(cur["close"])
    if kind == "morning_star":
        sl = float(df.iloc[idx - 1]["low"] - 0.3 * atr)
        tp = float(close + 2.5 * atr)
        return {"direction": "long", "entry": close, "stop_loss": sl, "take_profit": tp}
    else:
        sl = float(df.iloc[idx - 1]["high"] + 0.3 * atr)
        tp = float(close - 2.5 * atr)
        return {"direction": "short", "entry": close, "stop_loss": sl, "take_profit": tp}


# -------------------- Analyzer (run on dataframe) --------------------
def analyze_df(df: pd.DataFrame, symbol: Optional[str] = None) -> List[Dict]:
    if df is None or len(df) < 200:
        return []

    df = df.copy()
    df = enrich_candle_anatomy(df)
    df = enrich_indicators(df)
    df = df.dropna(subset=["atr", "rsi", "sma_50", "sma_200", "atr_sma_50", "volume_ma"]).copy()

    if len(df) < TRIANGLE_WINDOW + 10:
        return []

    signals: List[Dict] = []

    idx = len(df) - 2
    if idx < TRIANGLE_WINDOW:
        return []

    row = df.iloc[idx]

    trend_valid, volatility_valid = regime_filter(row)
    if not (trend_valid and volatility_valid):
        return []

    detected = None

    tri = detect_triangle(df, idx)
    if tri is not None:
        detected = tri

    if detected is None:
        dt = detect_double_top(df, idx)
        if dt is not None:
            detected = dt

    if detected is None:
        db = detect_double_bottom(df, idx)
        if db is not None:
            detected = db

    if detected is None and detect_morning_star(df, idx):
        frag = build_multi_candle_signal(df, idx, "morning_star")
        detected = {"pattern_type": "morning_star", **frag}

    if detected is None and detect_evening_star(df, idx):
        frag = build_multi_candle_signal(df, idx, "evening_star")
        detected = {"pattern_type": "evening_star", **frag}

    if detected is None:
        tw = detect_tweezer(df, idx)
        if tw is not None:
            frag = build_tweezer_signal(df, idx, tw)
            detected = {"pattern_type": tw, **frag}

    if detected is None:
        eng = detect_engulfing(df, idx)
        if eng is not None:
            direction = "long" if eng == "engulfing_bullish" else "short"
            atr = float(row.get("atr", 0.0))
            close = float(row["close"])
            if direction == "long":
                sl = float(row["low"] - 0.3 * atr)
                tp = float(close + 2.5 * atr)
            else:
                sl = float(row["high"] + 0.3 * atr)
                tp = float(close - 2.5 * atr)
            detected = {"pattern_type": eng, "direction": direction, "entry": float(close), "stop_loss": sl, "take_profit": tp}

    if detected is None:
        for sc_name, sc_fn in [("hammer", detect_hammer), ("shooting_star", detect_shooting_star), ("doji", detect_doji)]:
            if sc_fn(row):
                frag = build_single_candle_signal(row, sc_name)
                detected = {"pattern_type": sc_name, **frag}
                break

    if detected is None:
        return []

    # Apply risk gate
    valid, rr, position_size = risk_gate(detected["entry"], detected["stop_loss"], detected["take_profit"], detected.get("direction", "long"))
    if not valid:
        return []

    detected["rr"] = rr
    detected["position_size"] = position_size
    if symbol:
        detected["symbol"] = symbol
    signals.append(detected)

    return signals
