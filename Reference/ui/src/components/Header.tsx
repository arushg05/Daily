import { Activity } from "lucide-react";

interface Props {
    connected: boolean;
    setupCount: number;
}

export default function Header({ connected, setupCount }: Props) {
    return (
        <header className="glass border-b border-surface-700 px-6 py-3 flex items-center justify-between shrink-0">
            {/* Logo & title */}
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-green to-neon-blue flex items-center justify-center">
                    <Activity className="w-5 h-5 text-surface-900" />
                </div>
                <div>
                    <h1 className="text-lg font-bold tracking-tight text-text-primary">
                        Asymptote
                    </h1>
                    <p className="text-[10px] text-text-muted uppercase tracking-widest">
                        Detection Engine
                    </p>
                </div>
            </div>

            {/* Status indicators */}
            <div className="flex items-center gap-5">
                <div className="flex items-center gap-2 text-xs text-text-secondary">
                    <span className="font-medium tabular-nums">{setupCount}</span>
                    <span className="text-text-muted">active setups</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div
                        className={`w-2 h-2 rounded-full ${connected ? "bg-neon-green pulse-dot" : "bg-neon-red"
                            }`}
                    />
                    <span className="text-xs text-text-muted">
                        {connected ? "Live" : "Disconnected"}
                    </span>
                </div>
            </div>
        </header>
    );
}
