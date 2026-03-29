import { useState, useEffect, useCallback } from "react";

export interface OverlayNote {
  id: string;
  price: number;
  timeframe: string;
  label?: string;
}

export function useLocalStorageOverlays(ticker: string | null) {
  const getKey = useCallback((t: string) => `asymptote-overlays-${t}`, []);

  const [overlays, setOverlays] = useState<OverlayNote[]>([]);

  // Load from local storage when ticker changes
  useEffect(() => {
    if (!ticker) {
      setOverlays([]);
      return;
    }

    try {
      const stored = localStorage.getItem(getKey(ticker));
      if (stored) {
        setOverlays(JSON.parse(stored));
      } else {
        setOverlays([]);
      }
    } catch (error) {
      console.error("Failed to parse overlays from local storage", error);
      setOverlays([]);
    }
  }, [ticker, getKey]);

  // Save to local storage when overlays change
  const saveOverlays = useCallback(
    (newOverlays: OverlayNote[]) => {
      setOverlays(newOverlays);
      if (ticker) {
        localStorage.setItem(getKey(ticker), JSON.stringify(newOverlays));
      }
    },
    [ticker, getKey]
  );

  const addOverlay = useCallback(
    (price: number, timeframe: string, label: string = "Note") => {
      saveOverlays([
        ...overlays,
        { id: Math.random().toString(36).substring(7), price, timeframe, label },
      ]);
    },
    [overlays, saveOverlays]
  );

  const removeOverlay = useCallback(
    (id: string) => {
      saveOverlays(overlays.filter((o) => o.id !== id));
    },
    [overlays, saveOverlays]
  );

  const clearOverlays = useCallback(() => {
    saveOverlays([]);
  }, [saveOverlays]);

  return { overlays, addOverlay, removeOverlay, clearOverlays };
}
