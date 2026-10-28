import { useState, useSyncExternalStore } from "react";
import { paper } from "./api/paper";
export const usePaper = () =>
  useSyncExternalStore(paper.subscribe, paper.snapshot);
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
