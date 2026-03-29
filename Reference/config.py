"""
Asymptote V1 — Configuration
=============================
Place your Twelve Data API key in the TWELVEDATA_API_KEY variable below,
or set the environment variable TWELVEDATA_API_KEY.
"""
import os

# ─── API Keys ───────────────────────────────────────────────────────────────
# >>> PUT YOUR API KEY HERE or set env var TWELVEDATA_API_KEY <<<
TWELVEDATA_API_KEY: str = "f9014fc890ef49c391c766fc8dd5af49"

TWELVEDATA_BASE_URL: str = "https://api.twelvedata.com"

# ─── Rate Limits (Free Tier) ────────────────────────────────────────────────
RATE_LIMIT_PER_MIN: int = 8          # max credits per minute
RATE_LIMIT_PER_DAY: int = 800        # max credits per day
POLL_INTERVAL_SEC: float = 7.5       # seconds between consecutive API calls

# ─── Symbols ────────────────────────────────────────────────────────────────
SYMBOLS_SP50: list[str] = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL",
    "META", "BRK.B", "UNH", "XOM", "JNJ",
    "JPM", "V", "PG", "MA", "AVGO",
    "HD", "CVX", "MRK", "ABBV", "LLY",
    "PEP", "KO", "COST", "TMO", "WMT",
    "MCD", "CSCO", "ACN", "ABT", "CRM",
    "DHR", "LIN", "NKE", "ADBE", "TXN",
    "AMD", "PM", "NEE", "UPS", "RTX",
    "ORCL", "HON", "LOW", "QCOM", "UNP",
    "INTC", "CAT", "SPGI", "BA", "GS",
]

SYMBOLS_FOREX: list[str] = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
]

ALL_SYMBOLS: list[str] = SYMBOLS_SP50 + SYMBOLS_FOREX

# ─── Candle Settings ────────────────────────────────────────────────────────
CANDLE_INTERVAL: str = "15min"
CANDLE_OUTPUTSIZE: int = 30          # how many historical candles to fetch

# ─── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD", None)

# TTLs in seconds
CANDLE_TTL: int = 1200               # 20 minutes
INDICATOR_TTL: int = 1200
STATE_TTL: int = 86400               # 24 hours

# ─── Scoring Weights ────────────────────────────────────────────────────────
SCORE_PATTERN_BASE: int = 30
SCORE_TREND: int = 20
SCORE_MOMENTUM: int = 20
SCORE_VOLUME: int = 15
SCORE_VOLATILITY: int = 15

# ─── Risk Management Constants ──────────────────────────────────────────────
PENETRATION_RULE_PCT: float = 3.0
VOLUME_SURGE_MULTIPLIER: float = 1.5
ATR_SL_MULTIPLIER_MIN: float = 1.5
ATR_SL_MULTIPLIER_MAX: float = 2.0

# ─── Server ─────────────────────────────────────────────────────────────────
SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8000
