"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PublicTheme = "light" | "dark";

const STORAGE_KEY = "dokushodo-theme";
const THEME_EVENT = "dokushodo-theme-change";

function getInitialTheme(): PublicTheme {
  if (typeof window === "undefined") {
    return "dark";
  }

  const stored = window.localStorage?.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }

  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

function applyTheme(theme: PublicTheme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  window.localStorage?.setItem(STORAGE_KEY, theme);
}

function subscribeToTheme(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(THEME_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(THEME_EVENT, onChange);
  };
}

export function usePublicTheme() {
  const theme = useSyncExternalStore(
    subscribeToTheme,
    getInitialTheme,
    () => "dark",
  );

  function setTheme(next: PublicTheme) {
    applyTheme(next);
    window.dispatchEvent(new Event(THEME_EVENT));
  }

  function toggleTheme() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  return {
    theme,
    isDark: theme === "dark",
    setTheme,
    toggleTheme,
  };
}

export function PublicThemeToggle({ className }: { className?: string }) {
  const { isDark, toggleTheme } = usePublicTheme();

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={className}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Light theme" : "Dark theme"}
      onClick={toggleTheme}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

export function PublicThemeSegmentedControl() {
  const { theme, setTheme } = usePublicTheme();

  return (
    <div
      role="group"
      aria-label="Theme selection"
      className="inline-flex w-full items-center rounded-md border border-border/70 bg-muted/40 p-0.5 text-xs"
    >
      <button
        type="button"
        onClick={() => setTheme("light")}
        aria-pressed={theme === "light"}
        className={cn(
          "inline-flex flex-1 items-center justify-center gap-1.5 rounded-sm py-1 font-medium transition-all",
          theme === "light"
            ? "bg-background text-foreground shadow-xs"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Sun className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Light</span>
      </button>
      <button
        type="button"
        onClick={() => setTheme("dark")}
        aria-pressed={theme === "dark"}
        className={cn(
          "inline-flex flex-1 items-center justify-center gap-1.5 rounded-sm py-1 font-medium transition-all",
          theme === "dark"
            ? "bg-background text-foreground shadow-xs"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Moon className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Dark</span>
      </button>
    </div>
  );
}
