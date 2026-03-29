/* Asymptote-LT shared types */

export interface ConfluenceFlags {
  above_200_sma: boolean;
  volume_surge: boolean;
  rsi_oversold: boolean;
  rsi_overbought: boolean;
}

export interface Setup {
  id: string;
  symbol: string;
  timeframe: string;
  pattern_name: string;
  category: string;
  direction: "bullish" | "bearish" | "neutral";
  confluence_flags: ConfluenceFlags;
  setup_score: number;
  state: "Active" | "Pending" | "Failed";
  matched_timestamps: string[];
  entry_price: number;
  stop_loss_price?: number;
  take_profit_price?: number;
  is_specialized?: boolean; // Flag for specialized patterns (Double Bottom/Top, EMA Knots)
  is_primary?: boolean; // Flag for primary system setups (Triangle Breakout)
}

export interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ScanResult {
  meta: {
    last_scan: string;
    tickers_scanned: number;
    total_setups: number;
  };
  setups: Setup[];
}

export type Timeframe = "daily" | "weekly";
