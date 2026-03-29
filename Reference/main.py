"""
Asymptote — Main Entry Point
==============================
asyncio loop that orchestrates:
  1. Round-robin polling  (poller.py)
  2. Indicator computation (indicators.py)
  3. Pattern matching      (pattern_matcher.py)
  4. Setup scoring         (scorer.py)
  5. Redis persistence     (redis_store.py)
"""
from __future__ import annotations

import asyncio
import logging
import sys

import config
from engine.rate_limiter import RateLimiter
from engine.poller import Poller
from engine import indicators as ind_module
from engine import pattern_matcher
from engine import scorer
from engine import redis_store

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("asymptote")


async def process_symbol(symbol: str, candles: list[dict], poller: Poller) -> None:
    """Pipeline for a single symbol: indicators → match → score → store."""
    # 1) Compute indicators locally
    ind = ind_module.compute(candles)
    if not ind:
        logger.warning("%s: indicator computation returned empty", symbol)
        return

    redis_store.store_indicators(symbol, ind)

    # 2) Run pattern matcher
    matches = pattern_matcher.scan(symbol, candles, ind)
    if not matches:
        logger.debug("%s: no patterns detected", symbol)
        return

    logger.info("%s: detected %d pattern(s)", symbol, len(matches))

    # 3) Score and persist each match
    for m in matches:
        setup_score = scorer.score(m, ind)
        risk = scorer.compute_risk(m, ind)

        # Enrich the match dict
        m["setup_score"] = setup_score
        m["entry_price"] = risk.get("entry_price")
        m["stop_loss_price"] = risk.get("stop_loss_price")
        m["take_profit_price"] = risk.get("take_profit_price")

        # Determine state
        existing_state = redis_store.get_state(symbol, m["pattern_name"])
        if existing_state == "Active":
            pass  # already confirmed
        elif setup_score >= 60:
            redis_store.set_state(symbol, m["pattern_name"], "Active")
            m["state"] = "Active"
        else:
            redis_store.set_state(symbol, m["pattern_name"], "Pending")
            m["state"] = "Pending"

        redis_store.upsert_setup(m, setup_score)
        redis_store.publish_update("setups_channel", m)

        logger.info(
            "  → %s | %s | score=%.0f | dir=%s | state=%s",
            m["pattern_name"],
            symbol,
            setup_score,
            m["direction"],
            m.get("state", "?"),
        )


async def run_loop() -> None:
    """Main scanning loop — runs forever."""
    rate_limiter = RateLimiter(
        max_per_minute=config.RATE_LIMIT_PER_MIN,
        max_per_day=config.RATE_LIMIT_PER_DAY,
    )
    poller = Poller(rate_limiter)

    logger.info(
        "Asymptote engine started — scanning %d symbols every %.1fs",
        len(config.ALL_SYMBOLS),
        config.POLL_INTERVAL_SEC,
    )

    try:
        while True:
            symbol, candles = await poller.poll_next()

            if candles:
                try:
                    await process_symbol(symbol, candles, poller)
                except Exception:
                    logger.exception("Error processing %s", symbol)

            await asyncio.sleep(config.POLL_INTERVAL_SEC)

    except asyncio.CancelledError:
        logger.info("Shutdown requested")
    finally:
        await poller.close()
        logger.info("Poller closed — engine stopped")


def main() -> None:
    if config.TWELVEDATA_API_KEY == "YOUR_API_KEY_HERE":
        logger.error(
            "╔════════════════════════════════════════════════════════════╗\n"
            "║  Please set your Twelve Data API key in config.py        ║\n"
            "║  Line 12:  TWELVEDATA_API_KEY = 'your_key_here'          ║\n"
            "║  Or set the env var TWELVEDATA_API_KEY                   ║\n"
            "╚════════════════════════════════════════════════════════════╝"
        )
        sys.exit(1)

    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — exiting")


if __name__ == "__main__":
    main()
