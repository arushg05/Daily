import pandas as pd
import pandas_ta as ta

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all required technical indicators using pandas_ta.
    Returns a new DataFrame with indicators appended as columns.
    """
    if df is None or df.empty or len(df) < 50:
        return pd.DataFrame() # Not enough data

    df_ind = df.copy()

    # 1. Trend Filter: 200-day Simple Moving Average
    df_ind["sma_200"] = ta.sma(df_ind["close"], length=200)

    # Secondary Trend Filter (Optional for early trend recognition)
    df_ind["ema_20"] = ta.ema(df_ind["close"], length=20)
    df_ind["ema_50"] = ta.ema(df_ind["close"], length=50)

    # EMA Knots Pattern: 21, 34, 55 day EMAs
    df_ind["ema_21"] = ta.ema(df_ind["close"], length=21)
    df_ind["ema_34"] = ta.ema(df_ind["close"], length=34)
    df_ind["ema_55"] = ta.ema(df_ind["close"], length=55)

    # 2. Volume Surge Confirmation: 20-day Volume Average
    df_ind["volume_sma_20"] = ta.sma(df_ind["volume"], length=20)

    # 3. Momentum Divergence: RSI (14)
    df_ind["rsi_14"] = ta.rsi(df_ind["close"], length=14)

    # Momentum: MACD (12, 26, 9)
    macd = ta.macd(df_ind["close"], fast=12, slow=26, signal=9)
    # pandas_ta returns columns like MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    if macd is not None and not macd.empty:
        df_ind["macd"] = macd.iloc[:, 0]
        df_ind["macd_hist"] = macd.iloc[:, 1]
        df_ind["macd_signal"] = macd.iloc[:, 2]

    # Bollinger Bands (used for BBNC detection)
    bb = ta.bbands(df_ind["close"], length=20, std=2)
    if bb is not None and not bb.empty:
        # pandas_ta bband order: lower, middle, upper, percent
        try:
            df_ind["bb_lower"] = bb.iloc[:, 0]
            df_ind["bb_middle"] = bb.iloc[:, 1]
            df_ind["bb_upper"] = bb.iloc[:, 2]
            df_ind["bb_percent"] = bb.iloc[:, 3]
            df_ind["bb_width"] = df_ind["bb_upper"] - df_ind["bb_lower"]
        except Exception:
            pass

    # Institutional Accumulation: On Balance Volume (OBV)
    df_ind["obv"] = ta.obv(df_ind["close"], df_ind["volume"])

    # Volatility / Risk Management: Average True Range (ATR 14)
    df_ind["atr_14"] = ta.atr(df_ind["high"], df_ind["low"], df_ind["close"], length=14)

    # Drop starting rows that have NaN values for the 200 SMA (requires 200 days)
    # But wait, we need to return the full series so we match indices properly. We'll just leave NaNs.
    return df_ind
