/* Asymptote shared types */

export interface Setup {
    symbol: string;
    pattern_name: string;
    category: string;
    direction: "bullish" | "bearish" | "neutral";
    entry: string;
    stop_loss: string;
    target: string;
    confluence_flags: Record<string, boolean>;
    setup_score: number;
    score?: number;
    state?: "Pending" | "Active" | "Failed";
    stop_loss_price?: number | null;
    take_profit_price?: number | null;
    entry_price?: number | null;
    matched_timestamps?: string[];
}

export interface Candle {
    datetime: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface WsMessage {
    type: "snapshot";
    data: Setup[];
}
