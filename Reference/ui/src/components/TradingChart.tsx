import { useEffect, useRef, useState } from "react";
import {
    createChart,
    type IChartApi,
    type ISeriesApi,
    ColorType,
    type CandlestickData,
    type Time,
    LineStyle,
} from "lightweight-charts";
import type { Setup, Candle } from "../types";

interface Props {
    symbol: string | null;
    activeSetup: Setup | null;
}

export default function TradingChart({ symbol, activeSetup }: Props) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // ── Create chart on mount ──────────────────────────────────────────────
    useEffect(() => {
        if (!containerRef.current) return;

        try {
            const chart = createChart(containerRef.current, {
                layout: {
                    background: { type: ColorType.Solid, color: "#09090b" },
                    textColor: "#a1a1aa",
                    fontFamily: "Inter, system-ui, sans-serif",
                },
                grid: {
                    vertLines: { color: "rgba(63,63,70,0.3)" },
                    horzLines: { color: "rgba(63,63,70,0.3)" },
                },
                crosshair: {
                    vertLine: { color: "rgba(56,189,248,0.4)", width: 1, style: LineStyle.Dashed },
                    horzLine: { color: "rgba(56,189,248,0.4)", width: 1, style: LineStyle.Dashed },
                },
                rightPriceScale: {
                    borderColor: "rgba(63,63,70,0.5)",
                },
                timeScale: {
                    borderColor: "rgba(63,63,70,0.5)",
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            const series = chart.addCandlestickSeries({
                upColor: "#00ff87",
                downColor: "#ff3b5c",
                borderUpColor: "#00ff87",
                borderDownColor: "#ff3b5c",
                wickUpColor: "#00ff87aa",
                wickDownColor: "#ff3b5caa",
            });

            chartRef.current = chart;
            seriesRef.current = series;

            // Resize observer
            const ro = new ResizeObserver((entries) => {
                const { width, height } = entries[0].contentRect;
                if (width > 0 && height > 0) {
                    chart.applyOptions({ width, height });
                }
            });
            ro.observe(containerRef.current);

            return () => {
                ro.disconnect();
                chart.remove();
                chartRef.current = null;
                seriesRef.current = null;
            };
        } catch (err: any) {
            setError(err.message || String(err));
        }
    }, []);

    // ── Fetch candles when symbol changes ──────────────────────────────────
    useEffect(() => {
        if (!symbol || !seriesRef.current) return;

        setLoading(true);
        setError(null);

        fetch(`/api/candles/${encodeURIComponent(symbol)}`)
            .then((res) => res.json())
            .then((candles: Candle[]) => {
                if (!seriesRef.current) return;
                if (!candles || candles.length === 0) {
                    setError("No candle data available");
                    seriesRef.current.setData([]);
                    return;
                }

                const data: CandlestickData<Time>[] = candles.map((c) => ({
                    time: (new Date(c.datetime).getTime() / 1000) as Time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                }));

                seriesRef.current.setData(data);
                chartRef.current?.timeScale().fitContent();
            })
            .catch((err) => {
                setError("Failed to load candle data");
                console.error(err);
            })
            .finally(() => setLoading(false));
    }, [symbol]);

    // ── Draw price lines for SL / TP ──────────────────────────────────────
    useEffect(() => {
        if (!seriesRef.current || !activeSetup) return;

        // Clear old price lines
        const series = seriesRef.current;
        // Remove all existing price lines by recreating
        // lightweight-charts doesn't have removeAllPriceLines, so we track them
        const lines: ReturnType<typeof series.createPriceLine>[] = [];

        if (activeSetup.entry_price) {
            lines.push(
                series.createPriceLine({
                    price: activeSetup.entry_price,
                    color: "#38bdf8",
                    lineWidth: 2,
                    lineStyle: LineStyle.Solid,
                    axisLabelVisible: true,
                    title: "Entry",
                })
            );
        }

        if (activeSetup.stop_loss_price) {
            lines.push(
                series.createPriceLine({
                    price: activeSetup.stop_loss_price,
                    color: "#ff3b5c",
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: "Stop Loss",
                })
            );
        }

        if (activeSetup.take_profit_price) {
            lines.push(
                series.createPriceLine({
                    price: activeSetup.take_profit_price,
                    color: "#00ff87",
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: "Take Profit",
                })
            );
        }

        // Add visual markers to highlight the zone where the pattern was detected
        if (activeSetup.matched_timestamps && activeSetup.matched_timestamps.length > 0) {
            const isBullish = activeSetup.direction === "bullish";
            const color = isBullish ? '#00ff87' : (activeSetup.direction === 'bearish' ? '#ff3b5c' : '#fbbf24');
            const position = isBullish ? 'belowBar' : (activeSetup.direction === 'bearish' ? 'aboveBar' : 'inBar');
            const shape = isBullish ? 'arrowUp' : (activeSetup.direction === 'bearish' ? 'arrowDown' : 'circle');

            const markers = activeSetup.matched_timestamps.map((dt, i) => {
                const isLast = i === activeSetup.matched_timestamps!.length - 1;
                return {
                    time: (new Date(dt).getTime() / 1000) as Time,
                    position: position as any,
                    color: color,
                    shape: shape as any,
                    text: isLast ? activeSetup.pattern_name : undefined,
                    size: isLast ? 2 : 1,
                };
            });

            // Must be sorted chronologically for lightweight-charts
            markers.sort((a, b) => (a.time as number) - (b.time as number));
            series.setMarkers(markers);
        } else {
            series.setMarkers([]);
        }

        return () => {
            lines.forEach((line) => {
                try {
                    series.removePriceLine(line);
                } catch {
                    // line may already be removed
                }
            });
        };
    }, [activeSetup]);

    return (
        <div className="relative w-full h-full">
            <div ref={containerRef} className="w-full h-full" />

            {/* Loading overlay */}
            {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-surface-900/60">
                    <div className="text-text-muted text-sm animate-pulse">
                        Loading {symbol}...
                    </div>
                </div>
            )}

            {/* Error overlay */}
            {error && !loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-surface-900/60">
                    <div className="text-text-muted text-sm">{error}</div>
                </div>
            )}

            {/* No symbol selected */}
            {!symbol && !loading && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                        <p className="text-text-muted text-lg">Select a setup to view chart</p>
                        <p className="text-text-muted/60 text-sm mt-1">
                            Click on any pattern in the sidebar
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
