import type { Setup } from "../types";
import {
  Target,
  ShieldAlert,
  TrendingUp as TpIcon,
  ShieldCheck,
  Volume2,
  Activity,
  Crosshair,
} from "lucide-react";

interface Props {
  setup: Setup | null;
}

export default function SetupDetail({ setup }: Props) {
  if (!setup) {
    return (
      <div className="px-4 py-6 text-center">
        <Crosshair className="w-6 h-6 text-text-dim mx-auto mb-2" />
        <p className="text-text-dim text-xs">Select a setup to see details</p>
      </div>
    );
  }

  const confluenceCount = [
    setup.confluence_flags.above_200_sma,
    setup.confluence_flags.volume_surge,
    setup.confluence_flags.rsi_oversold || setup.confluence_flags.rsi_overbought,
  ].filter(Boolean).length;

  return (
    <div className="px-4 py-3 animate-fade-in space-y-3">
      {/* Title row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-text-primary font-mono text-sm">
            {setup.symbol}
          </span>
          <span
            className={`badge text-[10px] ${
              setup.direction === "bullish"
                ? "badge-green"
                : setup.direction === "bearish"
                ? "badge-red"
                : "badge-amber"
            }`}
          >
            {setup.direction.toUpperCase()}
          </span>
        </div>
        <span
          className={`text-xs font-semibold ${
            setup.state === "Active" ? "text-neon-green" : "text-neon-amber"
          }`}
        >
          {setup.state}
        </span>
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-3 gap-2">
        {/* Entry */}
        <div className="glass-light rounded-lg px-3 py-2">
          <div className="flex items-center gap-1 mb-1 text-neon-blue">
            <Target className="w-3 h-3" />
            <span className="text-[10px] font-semibold uppercase tracking-wider">
              Entry
            </span>
          </div>
          <span className="text-sm font-bold font-mono text-text-primary">
            ${setup.entry_price?.toFixed(2) ?? "—"}
          </span>
        </div>

        {/* Stop Loss */}
        <div className="glass-light rounded-lg px-3 py-2">
          <div className="flex items-center gap-1 mb-1 text-neon-red">
            <ShieldAlert className="w-3 h-3" />
            <span className="text-[10px] font-semibold uppercase tracking-wider">
              Stop
            </span>
          </div>
          <span className="text-sm font-bold font-mono text-text-primary">
            ${setup.stop_loss_price?.toFixed(2) ?? "—"}
          </span>
        </div>

        {/* Take Profit */}
        <div className="glass-light rounded-lg px-3 py-2">
          <div className="flex items-center gap-1 mb-1 text-neon-green">
            <TpIcon className="w-3 h-3" />
            <span className="text-[10px] font-semibold uppercase tracking-wider">
              Target
            </span>
          </div>
          <span className="text-sm font-bold font-mono text-text-primary">
            ${setup.take_profit_price?.toFixed(2) ?? "—"}
          </span>
        </div>
      </div>

      {/* Confluence summary */}
      <div className="flex items-center gap-3 pt-1">
        <span className="text-[10px] uppercase tracking-widest text-text-dim font-semibold">
          Confluence ({confluenceCount}/3)
        </span>
        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1 text-[10px] ${
              setup.confluence_flags.above_200_sma
                ? "text-neon-green"
                : "text-text-dim"
            }`}
          >
            <ShieldCheck className="w-3 h-3" />
            SMA
          </div>
          <div
            className={`flex items-center gap-1 text-[10px] ${
              setup.confluence_flags.volume_surge
                ? "text-neon-blue"
                : "text-text-dim"
            }`}
          >
            <Volume2 className="w-3 h-3" />
            VOL
          </div>
          <div
            className={`flex items-center gap-1 text-[10px] ${
              setup.confluence_flags.rsi_oversold ||
              setup.confluence_flags.rsi_overbought
                ? "text-neon-purple"
                : "text-text-dim"
            }`}
          >
            <Activity className="w-3 h-3" />
            RSI
          </div>
        </div>
      </div>
    </div>
  );
}
