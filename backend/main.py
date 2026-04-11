"""
Asymptote-LT — Main Orchestrator
==================================
Fetches EOD data for all S&P 500 tickers asynchronously, computes indicators,
runs pattern matching, and serializes results into static JSON
files consumed by the React frontend.
"""
import json
import logging
import sys
import os
import datetime
import numpy as np
import pandas as pd
import concurrent.futures

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_fetcher import get_sp500_tickers, fetch_data
from indicators import compute_indicators
from pattern_matcher import scan_for_patterns

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("asymptote-lt")


# ── Custom JSON encoder for numpy/pandas types ──────────────────────────────
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


def serialize_candles(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame of OHLCV data into a clean JSON-serializable list."""
    if df is None or df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        dt = row["datetime"]
        # Convert to ISO string
        if isinstance(dt, pd.Timestamp):
            dt_str = dt.strftime("%Y-%m-%d")
        else:
            dt_str = str(dt)[:10]  # Take only the date part

        records.append({
            "time": dt_str,
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
        })

    return records


def process_ticker(ticker: str, data_map: dict):
    """Processes pre-fetched data for a ticker across all timeframes."""
    ticker_setups = []
    # Pre-compute indicators for all available timeframes so we can perform double-screen checks
    ind_map = {}
    for tf, df in data_map.items():
        if df is None or len(df) < 50:
            ind_map[tf] = pd.DataFrame()
            continue
        ind_map[tf] = compute_indicators(df)

    for timeframe, df_ind in ind_map.items():
        if df_ind is None or df_ind.empty:
            continue

        # Determine higher timeframe df for double-screen confirmation (daily <-> weekly)
        htf_df = None
        if timeframe == "1d" and "1wk" in ind_map and not ind_map["1wk"].empty:
            htf_df = ind_map["1wk"]
        if timeframe == "1wk" and "1d" in ind_map and not ind_map["1d"].empty:
            htf_df = ind_map["1d"]

        setups = scan_for_patterns(ticker, df_ind, timeframe, htf_df)
        if setups:
            ticker_setups.extend(setups)

        # Serialize candle data for frontend (only keep last 300 candles)
        candle_data = serialize_candles(df_ind.tail(300))
        
        # Write per-ticker candle file
        tf_label = "daily" if timeframe == "1d" else "weekly"
        candle_dir = config.CANDLES_DIR / tf_label
        os.makedirs(candle_dir, exist_ok=True)
        
        safe_ticker = ticker.replace("/", "_").replace(".", "_")
        candle_path = candle_dir / f"{safe_ticker}.json"
        with open(candle_path, "w") as f:
            json.dump(candle_data, f, cls=NumpyEncoder)
            
    return ticker_setups


def run():
    """Main orchestration pipeline using bulk data fetching."""
    logger.info("=" * 60)
    logger.info("  Asymptote-LT — Fast Scanner Starting")
    logger.info("=" * 60)

    # 1. Get ticker list
    tickers = get_sp500_tickers()
    logger.info(f"Scanning {len(tickers)} S&P 500 tickers... (Bulk Data Fetching)")

    # 2. Bulk fetch data for all timeframes
    from data_fetcher import fetch_bulk_data
    
    daily_map = fetch_bulk_data(tickers, interval="1d", period=config.HISTORY_PERIOD)
    weekly_map = fetch_bulk_data(tickers, interval="1wk", period=config.HISTORY_PERIOD)
    
    # Organize by ticker
    mega_map = {}
    for ticker in tickers:
        mega_map[ticker] = {}
        if ticker in daily_map:
            mega_map[ticker]["1d"] = daily_map[ticker]
        if ticker in weekly_map:
            mega_map[ticker]["1wk"] = weekly_map[ticker]

    all_setups = []
    scan_meta = {
        "last_scan": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tickers_scanned": len(tickers),
        "total_setups": 0,
    }

    # 3. Process each ticker
    logger.info("Processing patterns and indicators...")
    completed_count = 0
    for ticker, data_map in mega_map.items():
        completed_count += 1
        if completed_count % 100 == 0 or completed_count == len(tickers):
            logger.info(f"Progress: [{completed_count}/{len(tickers)}] tickers processed.")
        
        try:
            if not data_map:
                continue
            res = process_ticker(ticker, data_map)
            if res:
                all_setups.extend(res)
        except Exception as exc:
            logger.error(f"{ticker} generated an exception: {exc}")

    # 3. Sort setups by score descending
    all_setups.sort(key=lambda s: s.get("setup_score", 0), reverse=True)

    scan_meta["total_setups"] = len(all_setups)

    # 4. Write the main setups file
    output = {
        "meta": scan_meta,
        "setups": all_setups,
    }

    setups_path = config.FRONTEND_DATA_DIR / "setups.json"
    with open(setups_path, "w") as f:
        json.dump(output, f, cls=NumpyEncoder, indent=2)

    logger.info("=" * 60)
    logger.info(f"  Scan complete! {len(all_setups)} setups written to {setups_path}")
    logger.info(f"  Candle data written to {config.CANDLES_DIR}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
