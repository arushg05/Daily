import { useState } from "react";
import { useSetups } from "./hooks/useSetups";
import Header from "./components/Header";
import SetupsTable from "./components/SetupsTable";
import SetupDetail from "./components/SetupDetail";
import TradingChart from "./components/TradingChart";
import type { Setup } from "./types";

export default function App() {
  const { setups, connected } = useSetups();
  const [activeSetup, setActiveSetup] = useState<Setup | null>(null);

  const handleSelect = (setup: Setup) => {
    setActiveSetup(setup);
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header connected={connected} setupCount={setups.length} />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left sidebar: Setups table ────────────────────────── */}
        <aside className="w-[380px] shrink-0 border-r border-surface-700 bg-surface-900 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-surface-700">
            <h2 className="text-sm font-semibold text-text-secondary">
              Live Setups
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <SetupsTable
              setups={setups}
              activeSymbol={activeSetup?.symbol ?? null}
              onSelect={handleSelect}
            />
          </div>

          {/* Detail panel at bottom of sidebar */}
          <div className="border-t border-surface-700 p-3">
            <SetupDetail setup={activeSetup} />
          </div>
        </aside>

        {/* ── Main pane: Chart ──────────────────────────────────── */}
        <main className="flex-1 bg-surface-900 relative">
          {/* Symbol badge */}
          {activeSetup && (
            <div className="absolute top-4 left-4 z-10 glass rounded-lg px-3 py-1.5 flex items-center gap-2">
              <span className="text-sm font-bold text-text-primary">
                {activeSetup.symbol}
              </span>
              <span className="text-xs text-text-muted">15m</span>
              <span
                className={`text-xs font-semibold ${activeSetup.direction === "bullish"
                    ? "text-neon-green"
                    : activeSetup.direction === "bearish"
                      ? "text-neon-red"
                      : "text-neon-amber"
                  }`}
              >
                {activeSetup.pattern_name}
              </span>
            </div>
          )}
          <TradingChart
            symbol={activeSetup?.symbol ?? null}
            activeSetup={activeSetup}
          />
        </main>
      </div>
    </div>
  );
}
