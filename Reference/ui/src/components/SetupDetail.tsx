import type { Setup } from "../types";
import { Shield, Crosshair, Target } from "lucide-react";

interface Props {
    setup: Setup | null;
}

export default function SetupDetail({ setup }: Props) {
    if (!setup) {
        return (
            <div className="glass rounded-xl p-4 text-center text-text-muted text-sm">
                Select a setup to view details
            </div>
        );
    }

    const score = setup.setup_score ?? setup.score ?? 0;
    const flags = setup.confluence_flags ?? {};

    return (
        <div className="glass rounded-xl p-4 space-y-3 animate-fade-in">
            {/* Title row */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-bold text-text-primary">{setup.symbol}</h3>
                    <p className="text-xs text-text-muted">{setup.pattern_name}</p>
                </div>
                <div
                    className={`px-2.5 py-1 rounded-full text-xs font-bold ${setup.direction === "bullish"
                            ? "bg-neon-green-dim text-neon-green"
                            : setup.direction === "bearish"
                                ? "bg-neon-red-dim text-neon-red"
                                : "bg-neon-amber-dim text-neon-amber"
                        }`}
                >
                    {setup.direction.toUpperCase()}
                </div>
            </div>

            {/* Score bar */}
            <div>
                <div className="flex justify-between text-xs mb-1">
                    <span className="text-text-muted">Setup Score</span>
                    <span className="font-bold tabular-nums">{score}/100</span>
                </div>
                <div className="w-full h-2 bg-surface-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all duration-700 ${score >= 75
                                ? "bg-gradient-to-r from-neon-green to-neon-blue"
                                : score >= 60
                                    ? "bg-neon-blue"
                                    : score >= 40
                                        ? "bg-neon-amber"
                                        : "bg-surface-600"
                            }`}
                        style={{ width: `${score}%` }}
                    />
                </div>
            </div>

            {/* Confluence flags */}
            <div>
                <p className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
                    Confluence
                </p>
                <div className="flex flex-wrap gap-1.5">
                    {Object.entries(flags).map(([key, val]) => (
                        <span
                            key={key}
                            className={`text-[10px] px-2 py-0.5 rounded-full border ${val
                                    ? "border-neon-green/30 text-neon-green bg-neon-green-dim"
                                    : "border-surface-600 text-text-muted bg-surface-800"
                                }`}
                        >
                            {key}
                        </span>
                    ))}
                </div>
            </div>

            {/* Risk levels */}
            <div className="grid grid-cols-3 gap-2 pt-1">
                <div className="bg-surface-800 rounded-lg p-2 text-center">
                    <Crosshair className="w-3.5 h-3.5 text-neon-blue mx-auto mb-1" />
                    <p className="text-[10px] text-text-muted">Entry</p>
                    <p className="text-xs font-mono font-bold text-text-primary truncate">
                        {setup.entry?.replace(/_/g, " ").slice(0, 12) ?? "—"}
                    </p>
                </div>
                <div className="bg-surface-800 rounded-lg p-2 text-center">
                    <Shield className="w-3.5 h-3.5 text-neon-red mx-auto mb-1" />
                    <p className="text-[10px] text-text-muted">Stop Loss</p>
                    <p className="text-xs font-mono font-bold text-text-primary">
                        {setup.stop_loss_price?.toFixed(2) ?? "—"}
                    </p>
                </div>
                <div className="bg-surface-800 rounded-lg p-2 text-center">
                    <Target className="w-3.5 h-3.5 text-neon-green mx-auto mb-1" />
                    <p className="text-[10px] text-text-muted">Take Profit</p>
                    <p className="text-xs font-mono font-bold text-text-primary">
                        {setup.take_profit_price?.toFixed(2) ?? "—"}
                    </p>
                </div>
            </div>
        </div>
    );
}
