"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

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

export function PublicThemeToggle() {
  const theme = useSyncExternalStore(subscribeToTheme, getInitialTheme, () => "dark");

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    window.dispatchEvent(new Event(THEME_EVENT));
  }

  const isDark = theme === "dark";

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Light theme" : "Dark theme"}
      onClick={toggleTheme}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
