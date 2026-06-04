"use client";

import * as React from "react";

export function useProgressRamp(
  active: boolean,
  {
    start = 8,
    max = 92,
    intervalMs = 350
  }: {
    start?: number;
    max?: number;
    intervalMs?: number;
  } = {}
) {
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    if (!active) {
      return;
    }
    setProgress((current) => Math.max(current, start));
    const timer = window.setInterval(() => {
      setProgress((current) => {
        if (current >= max) {
          return current;
        }
        return Math.min(max, current + Math.max(2, Math.round((max - current) / 8)));
      });
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [active, intervalMs, max, start]);

  const resetProgress = React.useCallback(() => setProgress(0), []);
  const completeProgress = React.useCallback(() => setProgress(100), []);

  return { progress, setProgress, resetProgress, completeProgress };
}
