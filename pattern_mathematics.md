# Quantitative Pattern Detection Logic

The following technical and mathematical conditions define how the Asymptote-LT Pattern Matcher identifies trading setups.

## Atomic Candlestick Patterns

*   **Marubozu:** Candle body must make up \>= 90% of the total candle range (High - Low) and must be significantly sized (\>= 70% of the 20-period average body).
*   **Doji:** Candle body must be \<= 10% of the total range.
    *   **Dragonfly:** Lower shadow is \>= 80% of range, upper shadow \<= 10%.
    *   **Gravestone:** Upper shadow is \>= 80% of range, lower shadow \<= 10%.
    *   **Long-Legged:** Shadows are balanced, but total candle range is \> 1.5x the 20-period average range.
*   **Spinning Top:** Body is small (between 10% and 30% of total range). Upper and lower shadows are symmetrical (difference between their sizes is \< 20% of total range).
*   **High Wave:** Very small body (\<= 20% of range) combined with immense volatility (range is \> 2.5x the 20-period average range).
*   **Hammer / Hanging Man:** Very short upper shadow (\< 20% of range) with a long lower shadow that is strictly \>= max(2x body size, 60% of total range). Lookback determines trend.
*   **Inverted Hammer / Shooting Star:** Very short lower shadow (\< 20% of range) with a long upper shadow that is strictly \>= max(2x body size, 60% of total range).
*   **Belt Hold:** Solid candle where the body makes up \>= 80% of total range and the candle is large (\>= 80% of the 20-period average range). Must lack a shadow on its opening side (Open price vs High/Low extreme is within 2%).
*   **Engulfing:** Two opposite colored candles. The body of the current candle is \>= 50% of the 20-day average body, and its open/close bounds strictly engulf the previous candle's body.
*   **Harami / Cross:** The second candle body (and its shadows) fit entirely inside the high/low bounds of the preceding candle's body. Cross implies the second candle is a Doji.
*   **Piercing Line / Dark Cloud Cover:** Both candles represent strong momentum (\>= 70% of the 20-period average body size). Second candle gaps up/down past the previous close, but reverses to close securely past the 50% midpoint of the first candle.
*   **Tweezer Top / Bottom:** Successive candles in a trend where the absolute difference between their extreme highs (or lows) is mathematically near-identical (\< 0.1% percentage difference).
*   **Counterattack:** Two opposite colored candles closing at nearly identical prices (\< 0.1% difference).
*   **Separating Lines:** Two opposite direction candles opening at identical prices (\< 0.1% difference) and pushing away from each other.
*   **Kicker:** Severe gap setup where the second candle opens completely beyond the open price of the preceding candle, kicking violently in the reverse direction.

## Multi-Candle Patterns

*   **Abandoned Baby:** A 3-candle setup where a central Doji (body \< 10% range) gaps cleanly away from a large trend candle (\>= 70% 20-period average body), and is followed by another large gap back. Neither shadow of the Doji can overlap the adjacent bodies. 
*   **Three Inside / Outside (Up/Down):** Either a confirmed *Harami* (Inside) or *Engulfing* (Outside) pattern followed by a third trend-confirming candle that cleanly clears the primary body bounds.
*   **Three Methods (Rising/Falling):** Heavy 5-candle continuation. Initial trend candle is massive (\>= 1.5x average body). Middle 3 counter-trend candles must stay entirely within the high/low bounds of the 1st candle. The 5th candle breaks out in the primary direction, breaching the 1st candle's close.
*   **Three Line Strike:** Three consecutive strong trend candles (\>= 50% average body) making higher-highs/lower-lows. This is followed by a massive 4th counter-trend candle (\>= 1.5x average body) that engulfs the opening price of the 1st candle.
*   **Stick Sandwich:** Red, Green, Red layout where the closing prices of the first and third Red candles are practically mathematically identical (\< 0.1% difference).
*   **Morning / Evening Star:** 1st candle is large (\>= 70% avg body), 2nd is small returning counter-trend (body \<= 50% avg body), and 3rd is large (\>= 70% avg body) closing aggressively past the 50% visual midpoint of the 1st candle.
*   **Three White Soldiers / Black Crows:** 3 successive identical colored trend candles. Forward wicks/shadows are essentially non-existent (close is within 1% of the extreme high/low constraint). Successive candles open tucked inside the previous candle's body bounds.

## Macro Market Geometries (Using `scipy.signal.argrelextrema`)

*   **Double Top / Bottom:** Identifies 2 distinct local peaks or troughs. The price difference between the two extreme peaks must be very small (\< 3%). An intermediate opposite swing-point (trough/peak) must exist with a mathematically meaningful dip (\> 2% difference from the peaks).
*   **Triple Top / Bottom:** Identifies 3 localized peaks/troughs sequentially. Checks that all 3 points deviate by no more than 3% from their collective arithmetic average.
*   **Head & Shoulders (Standard / Inverse):** Captures 3 swing points where the middle node breaches highest/lowest sequentially. Validates that shoulders (points 1 and 3) have extremely tight symmetry (\< 5% height difference). Additionally validates that the "Neckline" troughs between the peaks are roughly horizontal (\< 3% difference).

## Specialized Confluence Setups

*   **Double Bottom / Top (with RSI & MACD Divergence):** Searches for flat bottoms/tops similarly to the macro geometry (\< 3% price diff over a lookback window), while systematically mandating that `rsi_14` AND `macd_hist` values exhibit positive technical divergence between the identical price extremes. The setup only triggers when a green/red confirmation candle fires immediately after the formation touch.
*   **EMA Knots:** Requires massive moving-average compression where the `21`, `34` and `55` EMAs converge tightly forming a bottleneck where the maximum spread between any of the 3 EMAs is \<= 0.5% against their average. Fire condition is when EMA21 sharply crosses EMA34.
*   **Triangle Breakout / Breakdown (Volatility Contraction):**
    *   **Geometry:** Fits dynamic linear trendlines (`np.polyfit`) across 60-bar local highs/lows.
    *   **Contraction:** Demands mathematically narrower band-width today vs the baseline (Width End \<= Width Start * 0.95).
    *   **Volatility:** Demands local ATR (Average True Range) compression or local bar-range compression indicating quiet markets (recent 10-bar ATR \<= prior 20-bar ATR * 0.95).
    *   **True Breakout:** Once price forcefully closes beyond the fitted bounds by a required threshold (`0.5 * atr` or `0.005 * price`), it validates multi-timeframe "Tide" alignment (Execution MACD, 50 EMA alignment, and Bollinger Band Squeeze context) coupled with momentum thresholds (Big Body Candlesticks and Volume Surges).
