import { useEffect, useState, useSyncExternalStore } from "react";
import { paper, serverMode } from "./api/paper";
import type { LiveTradingStatus } from "./api/server";
export const usePaper = () =>
  useSyncExternalStore(paper.subscribe, paper.snapshot);
export function useTradingStatus(refreshKey = "") {
  const [status, setStatus] = useState<LiveTradingStatus | null>(null);
  useEffect(() => {
    if (!serverMode) return;
    let disposed = false;
    let pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const value = await paper.liveTradingStatus();
        if (!disposed) setStatus(value);
      } catch {
        if (!disposed) setStatus(null);
      } finally { pending = false; }
    }
    void refresh();
    const update = () => void refresh();
    const timer = window.setInterval(update, 60000);
    window.addEventListener("focus", update);
    window.addEventListener("gnk-trading-status-changed", update);
    return () => {
      disposed = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", update);
      window.removeEventListener("gnk-trading-status-changed", update);
    };
  }, [refreshKey]);
  return status;
}
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function run(fn: () => Promise<void>, message = "") {
    if (busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await fn();
      setSuccess(message);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Something went wrong. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, success, run, setError };
}
