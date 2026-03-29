import { useEffect, useRef, useState, useCallback } from "react";
import type { Setup, WsMessage } from "../types";

/**
 * Hook that connects to the backend WebSocket, receives the initial
 * snapshot, and merges incremental updates into a sorted list.
 */
export function useSetups() {
    const [setups, setSetups] = useState<Setup[]>([]);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

    const connect = useCallback(() => {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const ws = new WebSocket(`${protocol}://${window.location.host}/ws/setups`);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
            console.log("[WS] Connected");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                // Snapshot from initial connect
                if (msg.type === "snapshot" && Array.isArray(msg.data)) {
                    const sorted = (msg.data as Setup[]).sort(
                        (a, b) => (b.setup_score ?? b.score ?? 0) - (a.setup_score ?? a.score ?? 0)
                    );
                    setSetups(sorted);
                    return;
                }

                // Incremental update (single setup object)
                if (msg.symbol && msg.pattern_name) {
                    setSetups((prev) => {
                        const key = `${msg.symbol}:${msg.pattern_name}`;
                        const filtered = prev.filter(
                            (s) => `${s.symbol}:${s.pattern_name}` !== key
                        );
                        const updated = [...filtered, msg as Setup].sort(
                            (a, b) =>
                                (b.setup_score ?? b.score ?? 0) -
                                (a.setup_score ?? a.score ?? 0)
                        );
                        return updated;
                    });
                }
            } catch (err) {
                console.error("[WS] Parse error", err);
            }
        };

        ws.onclose = () => {
            setConnected(false);
            console.log("[WS] Disconnected — reconnecting in 3s");
            reconnectTimer.current = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
            ws.close();
        };
    }, []);

    useEffect(() => {
        connect();
        return () => {
            clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, [connect]);

    return { setups, connected };
}
