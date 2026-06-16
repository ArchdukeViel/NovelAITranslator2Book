"use client";

import { Minus, Plus, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useReaderPrefsStore } from "@/lib/reader-prefs";

const DEFAULTS = { theme: "light" as const, fontSize: 18, width: "comfortable" as const };

/**
 * Reader typography, theme, and width controls.
 * Consumes useReaderPrefsStore for font size, theme, and width.
 * NEVER toggles html.dark or document.documentElement.classList.
 * Requirements: 6.1, 6.2, 6.3, 6.5, 15.1
 */
export function ReaderControls() {
  const { fontSize, theme, width, setFontSize, setTheme, setWidth } =
    useReaderPrefsStore();

  const isDefault = fontSize === DEFAULTS.fontSize && theme === DEFAULTS.theme && width === DEFAULTS.width;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Font size controls */}
      <span className="text-xs font-metadata text-muted-foreground select-none">Font size</span>
      <Button
        variant="outline"
        size="icon"
        onClick={() => setFontSize(fontSize - 1)}
        aria-label="Decrease font size"
        disabled={fontSize <= 15}
      >
        <Minus className="h-4 w-4" />
      </Button>
      <span className="min-w-[3ch] text-center text-sm font-metadata tabular-nums">
        {fontSize}
      </span>
      <Button
        variant="outline"
        size="icon"
        onClick={() => setFontSize(fontSize + 1)}
        aria-label="Increase font size"
        disabled={fontSize >= 24}
      >
        <Plus className="h-4 w-4" />
      </Button>

      {/* Theme selector */}
      <select
        className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        value={theme}
        onChange={(e) =>
          setTheme(e.target.value as "light" | "dark" | "sepia")
        }
        aria-label="Reader theme"
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="sepia">Sepia</option>
      </select>

      {/* Width selector */}
      <select
        className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        value={width}
        onChange={(e) =>
          setWidth(e.target.value as "compact" | "comfortable" | "wide")
        }
        aria-label="Content width"
      >
        <option value="compact">Compact</option>
        <option value="comfortable">Comfortable</option>
        <option value="wide">Wide</option>
      </select>

      {/* Reset to defaults */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => {
          setTheme(DEFAULTS.theme);
          setFontSize(DEFAULTS.fontSize);
          setWidth(DEFAULTS.width);
        }}
        aria-label="Reset reader settings to defaults"
        disabled={isDefault}
        title="Reset to defaults"
      >
        <RotateCcw className="h-4 w-4" />
      </Button>
    </div>
  );
}
