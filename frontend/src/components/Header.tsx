import { Activity, Clock, BarChart3, Zap, Filter } from "lucide-react";

interface Props {
  lastScan: string | null;
  tickersScanned: number;
  totalSetups: number;
  showSpecializedOnly: boolean;
  onToggleSpecialized: (show: boolean) => void;
}

function formatScanTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

export default function Header({ lastScan, tickersScanned, totalSetups, showSpecializedOnly, onToggleSpecialized }: Props) {
  return (
    <header className="flex items-center justify-between px-5 py-3 border-b border-surface-700/50 bg-surface-900/80 backdrop-blur-md shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue to-neon-purple flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight gradient-text">
              DailyCharts
            </h1>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6">
        {/* Last scan */}
        <div className="flex items-center gap-2 text-text-muted">
          <Clock className="w-3.5 h-3.5" />
          <span className="text-xs">
            Last Scan: <span className="text-text-secondary font-medium">{formatScanTime(lastScan)}</span>
          </span>
        </div>

        {/* Tickers scanned */}
        <div className="flex items-center gap-2 text-text-muted">
          <BarChart3 className="w-3.5 h-3.5" />
          <span className="text-xs">
            <span className="text-text-secondary font-mono font-semibold">{tickersScanned}</span> Tickers
          </span>
        </div>

        {/* Active setups */}
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-neon-green pulse-dot" />
          <span className="text-xs text-text-muted">
            <span className="text-neon-green font-mono font-semibold">{totalSetups}</span> Setups
          </span>
        </div>

        {/* Specialized Pattern Toggle */}
        <div className="border-l border-surface-700/50 pl-6">
          <button
            onClick={() => onToggleSpecialized(!showSpecializedOnly)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              showSpecializedOnly
                ? "bg-neon-blue/20 text-neon-blue border border-neon-blue/50"
                : "bg-surface-800/50 text-text-muted border border-surface-700/50 hover:bg-surface-700/50"
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            <span>Specialized Setups</span>
          </button>
        </div>
      </div>
    </header>
  );
}
