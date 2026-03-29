"""
Asymptote-LT — Configuration
"""
import os
import pathlib

# ─── Data Extraction Parameters ──────────────────────────────────────────────
# When testing, we can limit the number of S&P500 stocks to scan
# Set to True to scan all 500. Set to False to scan only a subset for faster testing.
SCAN_ALL_SP500 = True  # Set to True to run a full S&P500 scan
TEST_SUBSET_SIZE = 5

# We fetch both Daily (1d) and Weekly (1wk) timeframes
TIMEFRAMES = ["1d", "1wk"]

# How much historical data to pull for calculating 200-SMA robustly
# 200 SMA requires at least 200 trading days. 5 years allows for macro chart patterns.
HISTORY_PERIOD = "5y"

# ─── Risk & Trading Rule Parameters ──────────────────────────────────────────
PENETRATION_RULE_PCT = 3.0       # 3% rule for breakouts
VOLUME_SURGE_MULTIPLIER = 1.5    # 150% of the 20-day average
ATR_SL_MULTIPLIER_MIN = 1.5      # Minimum Stop Loss buffer
ATR_SL_MULTIPLIER_MAX = 2.0      # Maximum Stop Loss buffer

# Minimum setup score to be considered "Active" rather than "Pending"
SCORE_THRESHOLD_ACTIVE = 60

# Scoring Weights
SCORE_PATTERN_BASE = 40
SCORE_TREND = 20
SCORE_MOMENTUM = 20
SCORE_VOLUME = 20

# ─── Output Directories ──────────────────────────────────────────────────────
# The frontend will be purely static, reading data from its public directory.
BASE_DIR = pathlib.Path(__file__).parent.parent
FRONTEND_DATA_DIR = BASE_DIR / "frontend" / "public" / "data"
CANDLES_DIR = FRONTEND_DATA_DIR / "candles"

# Create directories if they do not exist
os.makedirs(CANDLES_DIR, exist_ok=True)
