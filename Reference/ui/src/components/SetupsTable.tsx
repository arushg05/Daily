import { useMemo } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { Setup } from "../types";

interface Props {
    setups: Setup[];
    activeSymbol: string | null;
    onSelect: (setup: Setup) => void;
}

function getScore(s: Setup): number {
    return s.setup_score ?? s.score ?? 0;
}

function getGlowClass(s: Setup): string {
    const score = getScore(s);
    if (score < 60) return "glow-amber";
    if (s.direction === "bullish") return "glow-green";
    if (s.direction === "bearish") return "glow-red";
    return "glow-amber";
}

function getScoreColor(score: number): string {
    if (score >= 75) return "bg-neon-green";
    if (score >= 60) return "bg-neon-blue";
    if (score >= 40) return "bg-neon-amber";
    return "bg-surface-600";
}

function getDirectionIcon(dir: string) {
    if (dir === "bullish")
        return <TrendingUp className="w-4 h-4 text-neon-green" />;
    if (dir === "bearish")
        return <TrendingDown className="w-4 h-4 text-neon-red" />;
    return <Minus className="w-4 h-4 text-text-muted" />;
}

function getStateLabel(s: Setup) {
    const state = s.state ?? "Pending";
    const colors: Record<string, string> = {
        Active: "text-neon-green",
        Pending: "text-neon-amber",
        Failed: "text-neon-red",
    };
    return (
        <span className={`text-xs font-medium ${colors[state] ?? "text-text-muted"}`}>
            {state}
        </span>
    );
}

export default function SetupsTable({ setups, activeSymbol, onSelect }: Props) {
    const groupedSetups = useMemo(() => {
        const map = new Map<string, Setup[]>();
        setups.forEach((s) => {
            if (!map.has(s.symbol)) map.set(s.symbol, []);
            map.get(s.symbol)!.push(s);
        });

        const groups = Array.from(map.values()).map((group) => {
            // Sort to find the highest scoring setup
            group.sort((a, b) => getScore(b) - getScore(a));
            const primary = group[0];
            const allPatterns = Array.from(new Set(group.map((s) => s.pattern_name))).join(", ");
            return {
                symbol: primary.symbol,
                primarySetup: primary,
                allPatterns,
                score: getScore(primary),
                group,
            };
        });

        // Sort the entire table by the highest score
        return groups.sort((a, b) => b.score - a.score);
    }, [setups]);

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="px-4 py-3 border-b border-surface-700">
                <div className="grid grid-cols-[1fr_1.2fr_auto_auto_80px] gap-2 text-xs font-semibold text-text-muted uppercase tracking-wider">
                    <span>Symbol</span>
                    <span>Pattern</span>
                    <span>Dir</span>
                    <span>State</span>
                    <span className="text-right">Score</span>
                </div>
            </div>

            {/* Rows */}
            <div className="flex-1 overflow-y-auto">
                {groupedSetups.length === 0 && (
                    <div className="flex items-center justify-center h-32 text-text-muted text-sm">
                        Waiting for signals...
                    </div>
                )}
                {groupedSetups.map(({ symbol, primarySetup, allPatterns, score, group }, i) => {
                    const isActive = symbol === activeSymbol;
                    return (
                        <div
                            key={`${symbol}-${i}`}
                            onClick={() => {
                                // Merge all timestamps into the primary setup so we see ALL markers on the chart!
                                const allTimestamps = Array.from(
                                    new Set(group.flatMap((g) => g.matched_timestamps || []))
                                );
                                onSelect({ ...primarySetup, matched_timestamps: allTimestamps });
                            }}
                            className={`setup-row cursor-pointer px-4 py-3 border-b border-surface-700/50 animate-fade-in
                ${isActive ? "bg-surface-700/40 border-l-2 border-l-neon-blue" : "border-l-2 border-l-transparent"}
              `}
                            style={{ animationDelay: `${i * 30}ms` }}
                        >
                            <div className="grid grid-cols-[1fr_1.2fr_auto_auto_80px] gap-2 items-center">
                                {/* Symbol */}
                                <div className="flex flex-col overflow-hidden">
                                    <span className="text-sm font-semibold text-text-primary truncate">
                                        {symbol}
                                    </span>
                                    <span className="text-[10px] text-text-muted">{primarySetup.category}</span>
                                </div>

                                {/* Pattern */}
                                <span className="text-xs text-text-secondary truncate" title={allPatterns}>
                                    {allPatterns}
                                </span>

                                {/* Direction icon */}
                                {getDirectionIcon(primarySetup.direction)}

                                {/* State */}
                                {getStateLabel(primarySetup)}

                                {/* Score */}
                                <div className="flex flex-col items-end gap-1">
                                    <span className="text-sm font-bold tabular-nums">{score}</span>
                                    <div className="w-full bg-surface-700 rounded-full overflow-hidden">
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
        </div>
    );
}
