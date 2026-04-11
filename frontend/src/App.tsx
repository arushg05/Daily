import { useState, useEffect } from "react";
import Header from "./components/Header";
import TickerTable from "./components/TickerTable";
import SetupDetail from "./components/SetupDetail";
import ChartingArea from "./components/ChartingArea";
import type { Setup, ScanResult, Timeframe } from "./types";

export default function App() {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [activeSetup, setActiveSetup] = useState<Setup | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("daily");
  const [loading, setLoading] = useState(true);
  const [showSpecializedOnly, setShowSpecializedOnly] = useState(false);

  useEffect(() => {
    fetch("/data/setups.json")
      .then((res) => res.json())
      .then((data: ScanResult) => {
        setScanResult(data);
        if (data.setups.length > 0) {
          setActiveSetup(data.setups[0]);
        }
      })
      .catch((err) => console.error("Failed to load setups:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = (setup: Setup) => {
    setActiveSetup(setup);
    setTimeframe(setup.timeframe === "1wk" ? "weekly" : "daily");
  };

  const setups = scanResult?.setups ?? [];
  
  // Filter setups based on specialized pattern toggle
  const specializedNames = ["Double Bottom", "Double Top", "EMA Knots", "Triangle Breakout", "Triangle Breakdown"];
  const filteredSetups = showSpecializedOnly
    ? setups.filter(s => (s.is_specialized ?? false) || specializedNames.includes(s.pattern_name))
    : setups;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-950">
      <Header
        lastScan={scanResult?.meta.last_scan ?? null}
        tickersScanned={scanResult?.meta.tickers_scanned ?? 0}
        totalSetups={filteredSetups.length}
        showSpecializedOnly={showSpecializedOnly}
        onToggleSpecialized={setShowSpecializedOnly}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left sidebar: Setups table + detail ────────────── */}
        <aside className="w-[400px] shrink-0 border-r border-surface-700/50 bg-surface-900/50 flex flex-col overflow-hidden">
          {/* Setups list */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <div className="text-text-muted text-sm shimmer px-8 py-2 rounded">
                  Loading scanner data...
                </div>
              </div>
            ) : (
              <TickerTable
                setups={filteredSetups}
                activeId={activeSetup?.id ?? null}
                onSelect={handleSelect}
              />
            )}
          </div>

          {/* Detail panel at bottom */}
          <div className="border-t border-surface-700/50 shrink-0">
            <SetupDetail setup={activeSetup} />
          </div>
        </aside>

        {/* ── Main pane: Chart ────────────────────────────────── */}
        <main className="flex-1 bg-surface-950 relative flex flex-col overflow-hidden">
          {/* Top bar with symbol info and timeframe toggle */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-surface-700/50 bg-surface-900/30 shrink-0">
            <div className="flex items-center gap-3">
              {activeSetup ? (
                <>
                  <span className="text-lg font-bold text-text-primary font-mono">
                    {activeSetup.symbol}
                  </span>
                  <span
                    className={`badge ${
                      activeSetup.direction === "bullish"
                        ? "badge-green"
                        : activeSetup.direction === "bearish"
                        ? "badge-red"
                        : "badge-amber"
                    }`}
                  >
                    {activeSetup.pattern_name}
                  </span>
                  <span className="badge badge-blue">
                    {activeSetup.timeframe === "1d" ? "Daily" : "Weekly"}
                  </span>
                </>
              ) : (
                <span className="text-sm text-text-muted">
                  Select a setup to view chart
                </span>
              )}
            </div>

            {/* Timeframe toggle */}
            <div className="flex gap-1 glass-light rounded-lg p-1">
              <button
                className={`tf-btn ${timeframe === "daily" ? "tf-btn-active" : ""}`}
                onClick={() => setTimeframe("daily")}
              >
                1D
              </button>
              <button
                className={`tf-btn ${timeframe === "weekly" ? "tf-btn-active" : ""}`}
                onClick={() => setTimeframe("weekly")}
              >
                1W
              </button>
            </div>
          </div>

          {/* Chart area */}
          <div className="flex-1 relative">
            <ChartingArea
              symbol={activeSetup?.symbol ?? null}
              activeSetup={activeSetup}
              timeframe={timeframe}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
