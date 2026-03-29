import {
  TrendingUp,
  TrendingDown,
  Minus,
  ShieldCheck,
  Volume2,
  Activity,
  AlertTriangle,
} from "lucide-react";
import type { Setup } from "../types";

interface Props {
  setups: Setup[];
  activeId: string | null;
  onSelect: (setup: Setup) => void;
}

function getScoreColor(score: number): string {
  if (score >= 80) return "bg-neon-green";
  if (score >= 60) return "bg-neon-blue";
  if (score >= 40) return "bg-neon-amber";
  return "bg-surface-600";
}

function getScoreTextColor(score: number): string {
  if (score >= 80) return "text-neon-green";
  if (score >= 60) return "text-neon-blue";
  if (score >= 40) return "text-neon-amber";
  return "text-text-muted";
}

function DirectionIcon({ dir }: { dir: string }) {
  if (dir === "bullish")
    return <TrendingUp className="w-3.5 h-3.5 text-neon-green" />;
  if (dir === "bearish")
    return <TrendingDown className="w-3.5 h-3.5 text-neon-red" />;
  return <Minus className="w-3.5 h-3.5 text-text-muted" />;
}

export default function TickerTable({ setups, activeId, onSelect }: Props) {
  if (setups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3">
        <AlertTriangle className="w-8 h-8 text-text-dim" />
        <div className="text-center">
          <p className="text-text-muted text-sm">No setups detected</p>
          <p className="text-text-dim text-xs mt-1">
            Scanner runs daily at 7:00 AM ET
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Column header */}
      <div className="px-4 py-2.5 border-b border-surface-700/50 bg-surface-900/50 sticky top-0 z-10">
        <div className="grid grid-cols-[1fr_1.2fr_auto_70px] gap-2 text-[10px] font-semibold text-text-dim uppercase tracking-widest">
          <span>Symbol</span>
          <span>Pattern</span>
          <span>Confluence</span>
          <span className="text-right">Score</span>
        </div>
      </div>

      {/* Rows */}
      {setups.map((setup, i) => {
        const isActive = setup.id === activeId;
        const score = setup.setup_score;

        return (
          <div
            key={setup.id}
            id={`setup-row-${setup.id}`}
            onClick={() => onSelect(setup)}
            className={`setup-row cursor-pointer px-4 py-3 border-b border-surface-700/30 animate-fade-in
              ${
                isActive
                  ? "bg-surface-800/60 border-l-2 border-l-neon-blue"
                  : "border-l-2 border-l-transparent"
              }`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="grid grid-cols-[1fr_1.2fr_auto_70px] gap-2 items-center">
              {/* Symbol + direction */}
              <div className="flex items-center gap-2 overflow-hidden">
                <DirectionIcon dir={setup.direction} />
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-bold text-text-primary font-mono truncate">
                    {setup.symbol}
                  </span>
                  <span className="text-[10px] text-text-dim">
                    {setup.timeframe === "1d" ? "Daily" : "Weekly"} •{" "}
                    <span
                      className={
                        setup.state === "Active"
                          ? "text-neon-green"
                          : "text-neon-amber"
                      }
                    >
                      {setup.state}
                    </span>
                  </span>
                </div>
              </div>

              {/* Pattern name */}
              <span className="text-xs text-text-secondary truncate">
                {setup.pattern_name}
              </span>

              {/* Confluence flag icons */}
              <div className="flex items-center gap-1.5">
                {setup.confluence_flags.above_200_sma && (
                  <div title="Above 200 SMA" className="text-neon-green">
                    <ShieldCheck className="w-3.5 h-3.5" />
                  </div>
                )}
                {setup.confluence_flags.volume_surge && (
                  <div title="Volume Surge >150%" className="text-neon-blue">
                    <Volume2 className="w-3.5 h-3.5" />
                  </div>
                )}
                {(setup.confluence_flags.rsi_oversold ||
                  setup.confluence_flags.rsi_overbought) && (
                  <div
                    title={
                      setup.confluence_flags.rsi_oversold
                        ? "RSI Oversold"
                        : "RSI Overbought"
                    }
                    className="text-neon-purple"
                  >
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>

              {/* Score */}
              <div className="flex flex-col items-end gap-1">
                <span
                  className={`text-sm font-bold font-mono tabular-nums ${getScoreTextColor(
                    score
                  )}`}
                >
                  {score}
                </span>
                <div className="w-full bg-surface-700/50 rounded-full overflow-hidden h-[3px]">
                  <div
                    className={`score-bar ${getScoreColor(score)}`}
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
