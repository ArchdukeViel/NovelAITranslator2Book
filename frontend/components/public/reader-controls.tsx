"use client";

import { useEffect, useState } from "react";
import { RotateCcw, X } from "lucide-react";

import { usePublicAuth } from "@/hooks/public";
import { useReaderPrefsStore } from "@/lib/reader-prefs";

const FONT_SIZES = [16, 18, 20, 22] as const;
const WIDTHS = [
  { value: "compact" as const, label: "Narrow", width: "560px" },
  { value: "comfortable" as const, label: "Standard", width: "680px" },
  { value: "wide" as const, label: "Wide", width: "800px" },
];

export function ReaderControls() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated } = usePublicAuth();
  const { fontSize, theme, width, setFontSize, setTheme, setWidth } = useReaderPrefsStore();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;
      if (event.key === "." && !editing) {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <button
        type="button"
        aria-label="Reading settings"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary font-literary text-sm font-semibold text-primary-foreground shadow-lg"
      >
        Aa
      </button>
      {open && (
        <section role="dialog" aria-modal="true" aria-label="Reading settings" className="fixed inset-x-3 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] z-50 mx-auto max-w-md rounded-xl border border-border bg-background p-5 shadow-2xl">
          <div className="flex items-center justify-between"><h2 className="font-literary text-lg font-semibold">Reading settings</h2><button type="button" aria-label="Close reading settings" onClick={() => setOpen(false)}><X className="h-4 w-4" /></button></div>
          <fieldset className="mt-5"><legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Font size</legend><div className="mt-2 grid grid-cols-4 gap-2">{FONT_SIZES.map((size) => <button key={size} type="button" aria-pressed={fontSize === size} onClick={() => setFontSize(size)} className={`rounded-md border px-2 py-2 text-sm ${fontSize === size ? "border-primary bg-primary/10" : "border-border"}`}>{size}px</button>)}</div></fieldset>
          <fieldset className="mt-5"><legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Text width</legend><div className="mt-2 grid grid-cols-3 gap-2">{WIDTHS.map((item) => <button key={item.value} type="button" aria-pressed={width === item.value} onClick={() => setWidth(item.value)} className={`rounded-md border px-2 py-2 text-xs ${width === item.value ? "border-primary bg-primary/10" : "border-border"}`}><span className="block font-medium">{item.label}</span><span className="text-muted-foreground">{item.width}</span></button>)}</div></fieldset>
          <fieldset className="mt-5"><legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Theme</legend><div className="mt-2 grid grid-cols-3 gap-2">{(["light", "dark", "sepia"] as const).map((value) => <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)} className={`rounded-md border px-2 py-2 text-sm capitalize ${theme === value ? "border-primary bg-primary/10" : "border-border"}`}>{value}</button>)}</div></fieldset>
          <button type="button" onClick={() => { setFontSize(18); setWidth("comfortable"); }} className="mt-5 inline-flex items-center gap-2 text-sm text-muted-foreground"><RotateCcw className="h-4 w-4" /> Reset size and width</button>
          <p className="mt-4 text-xs text-muted-foreground">Shortcuts: ← previous · → next · . settings</p>
          {!isAuthenticated && <p className="mt-2 text-xs text-muted-foreground">Guest reading position stays on this device.</p>}
        </section>
      )}
    </>
  );
}
