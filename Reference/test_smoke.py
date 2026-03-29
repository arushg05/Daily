"""Quick smoke test for the Asymptote engine modules."""
import sys
sys.path.insert(0, ".")

from engine import indicators, pattern_matcher, scorer

# ── Fabricate a "perfect Doji" scenario ─────────────────────────────────
candles = []
# 28 neutral candles for indicator warmup
for i in range(28):
    candles.append({
        "datetime": f"2025-01-{i+1:02d} 09:30:00",
        "open": 100.0 + i * 0.1,
        "high": 101.0 + i * 0.1,
        "low": 99.0 + i * 0.1,
        "close": 100.0 + i * 0.1 + 0.05,
        "volume": 1_000_000.0,
    })

# 29th candle: volume surge
candles.append({
    "datetime": "2025-01-29 09:30:00",
    "open": 103.0,
    "high": 104.0,
    "low": 102.0,
    "close": 103.05,
    "volume": 2_000_000.0,  # 2x baseline = surge
})

# 30th candle: perfect Doji with RSI overbought
candles.append({
    "datetime": "2025-01-30 09:30:00",
    "open": 105.0,
    "high": 107.0,     # long upper shadow
    "low": 103.0,      # long lower shadow
    "close": 105.001,  # body ≈ 0
    "volume": 2_500_000.0,
})

print(f"Total candles: {len(candles)}")

# Compute indicators
ind = indicators.compute(candles)
print(f"Indicators computed: {len(ind)} keys")
for k in sorted(ind.keys()):
    print(f"  {k}: {ind[k]}")

# Run pattern matcher
matches = pattern_matcher.scan("TEST", candles, ind)
print(f"\nMatches found: {len(matches)}")
for m in matches:
    s = scorer.score(m, ind)
    risk = scorer.compute_risk(m, ind)
    print(f"  {m['pattern_name']:<25} dir={m['direction']:<8} score={s:.0f}  "
          f"SL={risk['stop_loss_price']}  TP={risk['take_profit_price']}")
    print(f"    confluence: {m['confluence_flags']}")

print("\n[OK] Smoke test passed!")
