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
import type { Setup, Timeframe, CandleData } from "../types";
import { useLocalStorageOverlays } from "../hooks/useLocalStorageOverlays";

interface Props {
  symbol: string | null;
  activeSetup: Setup | null;
  timeframe: Timeframe;
}

export default function ChartingArea({ symbol, activeSetup, timeframe }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { overlays, addOverlay, clearOverlays } = useLocalStorageOverlays(symbol);

  // ── Create chart on mount ──────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#030712" },
        textColor: "#71717a",
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(39,39,42,0.4)" },
        horzLines: { color: "rgba(39,39,42,0.4)" },
      },
      crosshair: {
        vertLine: {
          color: "rgba(56,189,248,0.3)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#18181b",
        },
        horzLine: {
          color: "rgba(56,189,248,0.3)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#18181b",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(39,39,42,0.5)",
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "rgba(39,39,42,0.5)",
        timeVisible: false,
        rightOffset: 5,
        barSpacing: 8,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#00ff87",
      downColor: "#ff3b5c",
      borderUpColor: "#00ff87",
      borderDownColor: "#ff3b5c",
      wickUpColor: "rgba(0,255,135,0.6)",
      wickDownColor: "rgba(255,59,92,0.6)",
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    volumeRef.current = volumeSeries;

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
      volumeRef.current = null;
    };
  }, []);

  // ── Handle Chart Clicks ──────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;

    const chart = chartRef.current;
    
    // Using a ref to keep track of current addOverlay function and timeframe 
    // to avoid re-subscribing on every change
    const clickHandler = (param: any) => {
      if (!param.point || !param.sourceEvent?.shiftKey || !seriesRef.current) return;
      const price = seriesRef.current.coordinateToPrice(param.point.y);
      if (price !== null) {
        addOverlay(price, timeframe);
      }
    };

    chart.subscribeClick(clickHandler);
    return () => {
      chart.unsubscribeClick(clickHandler);
    };
  }, [addOverlay, timeframe]);

  // ── Fetch candles when symbol or timeframe changes ─────────────────────
  useEffect(() => {
    if (!symbol || !seriesRef.current || !volumeRef.current) return;

    setLoading(true);
    setError(null);

    const safeTicker = symbol.replace("/", "_").replace(".", "_");
    const url = `/data/candles/${timeframe}/${safeTicker}.json`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((candles: CandleData[]) => {
        if (!seriesRef.current || !volumeRef.current) return;
        if (!candles || candles.length === 0) {
          setError("No candle data available for this timeframe");
          seriesRef.current.setData([]);
          volumeRef.current.setData([]);
          return;
        }

        // Map to lightweight-charts format
        const candleData: CandlestickData<Time>[] = candles.map((c) => ({
          time: c.time as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));

        const volumeData = candles.map((c) => ({
          time: c.time as Time,
          value: c.volume,
          color:
            c.close >= c.open
              ? "rgba(0,255,135,0.15)"
              : "rgba(255,59,92,0.15)",
        }));

        seriesRef.current.setData(candleData);
        volumeRef.current.setData(volumeData);
        chartRef.current?.timeScale().fitContent();
      })
      .catch((err) => {
        setError(`Failed to load ${timeframe} data for ${symbol}`);
        console.error(err);
      })
      .finally(() => setLoading(false));
  }, [symbol, timeframe]);

  // ── Draw price lines for SL / TP / Entry & Overlays ──────────────────
  useEffect(() => {
    if (!seriesRef.current) return;

    const series = seriesRef.current;
    const lines: ReturnType<typeof series.createPriceLine>[] = [];

    if (activeSetup?.entry_price) {
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

    if (activeSetup?.stop_loss_price) {
      lines.push(
        series.createPriceLine({
          price: activeSetup.stop_loss_price,
          color: "#ff3b5c",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Stop Loss",
        })
      );
    }

    if (activeSetup?.take_profit_price) {
      lines.push(
        series.createPriceLine({
          price: activeSetup.take_profit_price,
          color: "#00ff87",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Take Profit",
        })
      );
    }

    // Custom Local Overlays
    overlays.forEach((overlay) => {
      // only show overlays specifically saved for this timeframe, or show all, let's show all
      if (overlay.timeframe === timeframe) {
        lines.push(
          series.createPriceLine({
            price: overlay.price,
            color: "#fbbf24", // Yellow for custom lines
            lineWidth: 1,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: overlay.label || "Note",
          })
        );
      }
    });

    // Pattern markers
    if (
      activeSetup?.matched_timestamps &&
      activeSetup.matched_timestamps.length > 0
    ) {
      const isBullish = activeSetup.direction === "bullish";
      const isBearish = activeSetup.direction === "bearish";
      const color = isBullish
        ? "#00ff87"
        : isBearish
        ? "#ff3b5c"
        : "#fbbf24";
      const position = isBullish
        ? "belowBar"
        : isBearish
        ? "aboveBar"
        : "inBar";
      const shape = isBullish
        ? "arrowUp"
        : isBearish
        ? "arrowDown"
        : "circle";

      const markers = activeSetup.matched_timestamps.map((dt, i) => {
        const dateStr = dt.split(" ")[0]; // Extract only YYYY-MM-DD
        const isLast = i === activeSetup.matched_timestamps!.length - 1;
        return {
          time: dateStr as Time,
          position: position as "belowBar" | "aboveBar" | "inBar",
          color,
          shape: shape as "arrowUp" | "arrowDown" | "circle",
          text: isLast ? activeSetup.pattern_name : undefined,
          size: isLast ? 2 : 1,
        };
      });

      markers.sort(
        (a, b) => (a.time as string).localeCompare(b.time as string)
      );
      series.setMarkers(markers);
    } else {
      series.setMarkers([]);
    }

    return () => {
      lines.forEach((line) => {
        try {
          series.removePriceLine(line);
        } catch {
          // line may have been removed already
        }
      });
      try {
        series.setMarkers([]);
      } catch {
        // ignore
      }
    };
  }, [activeSetup, overlays, timeframe]);

  return (
    <div className="relative w-full h-full flex flex-col">
      {/* UI for Custom Overlays */}
      {symbol && overlays.length > 0 && (
        <div className="absolute top-4 left-4 z-10">
          <button
            onClick={clearOverlays}
            className="bg-surface-800 hover:bg-surface-700 text-xs text-text-muted px-2 py-1 rounded border border-surface-700 transition"
          >
            Clear Drawn Lines ({overlays.length})
          </button>
        </div>
      )}
      
      {symbol && (
        <div className="absolute top-4 right-4 z-10 opacity-50 select-none pointer-events-none text-[10px] text-text-dim px-2 bg-surface-900 rounded">
          Shift + Click to draw line
        </div>
      )}

      <div ref={containerRef} className="w-full flex-1" />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-950/70 backdrop-blur-sm">
          <div className="glass rounded-xl px-6 py-3 flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-text-muted text-sm">
              Loading {symbol}...
            </span>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {error && !loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-950/70">
          <div className="glass rounded-xl px-6 py-3 border border-red-500/20">
            <span className="text-red-400 text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* No symbol selected */}
      {!symbol && !loading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center animate-fade-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-800/50 flex items-center justify-center border border-surface-700/50">
              <svg
                className="w-8 h-8 text-text-dim"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M3 13h8V3H3v10zm0 8h8V15H3v6zm10 0h8v-10h-8v10zm0-18v6h8V3h-8z"
                />
              </svg>
            </div>
            <p className="text-text-muted text-base font-medium">
              Select a setup to view chart
            </p>
            <p className="text-text-dim text-xs mt-1">
              Click any pattern in the sidebar
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
