"use client";

import { useEffect, useState } from "react";
import { RotateCcw, X } from "lucide-react";

import { usePublicAuth } from "@/hooks/public";
import { useReaderUiStore } from "@/lib/store";

const FONT_SIZES = [16, 18, 20, 22] as const;
const WIDTHS = [
  { value: "compact" as const, label: "Narrow", width: "560px" },
  { value: "comfortable" as const, label: "Standard", width: "680px" },
  { value: "wide" as const, label: "Wide", width: "800px" },
];

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tagName = target.tagName;
  return (
    tagName === "INPUT" ||
    tagName === "TEXTAREA" ||
    tagName === "SELECT" ||
    target.isContentEditable ||
    Boolean(target.closest("[contenteditable='true']"))
  );
}

export function ReaderControls() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated } = usePublicAuth();
  const { fontSize, theme, width, setFontSize, setTheme, setWidth } = useReaderUiStore();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }
      if (isEditableTarget(event.target)) return;
      if (event.key === ".") {
        event.preventDefault();
        setOpen(true);
      }
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
        className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary font-literary text-sm font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 transition-transform active:scale-95 motion-reduce:transition-none"
      >
        Aa
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-xs"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Reading settings"
            className="fixed inset-x-3 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] z-50 mx-auto max-w-md rounded-xl border border-border bg-background p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-literary text-lg font-semibold text-foreground">
                Reading settings
              </h2>
              <button
                type="button"
                aria-label="Close reading settings"
                onClick={() => setOpen(false)}
                className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <fieldset className="mt-5">
              <legend className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Font size
              </legend>
              <div className="mt-2 grid grid-cols-4 gap-2">
                {FONT_SIZES.map((size) => (
                  <button
                    key={size}
                    type="button"
                    aria-pressed={fontSize === size}
                    onClick={() => setFontSize(size)}
                    className={`min-h-[44px] rounded-lg border px-2 py-2 text-sm font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                      fontSize === size
                        ? "border-primary bg-primary/10 text-primary font-semibold"
                        : "border-border text-foreground hover:bg-muted"
                    }`}
                  >
                    {size}px
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset className="mt-5">
              <legend className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Text width
              </legend>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {WIDTHS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    aria-label={`${item.label} ${item.width}`}
                    aria-pressed={width === item.value}
                    onClick={() => setWidth(item.value)}
                    className={`min-h-[44px] rounded-lg border px-2 py-2 text-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                      width === item.value
                        ? "border-primary bg-primary/10 text-primary font-semibold"
                        : "border-border text-foreground hover:bg-muted"
                    }`}
                  >
                    <span className="block font-medium">{item.label}</span>
                    <span className="text-muted-foreground">{item.width}</span>
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset className="mt-5">
              <legend className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Theme
              </legend>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {(["light", "dark", "sepia"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={theme === value}
                    onClick={() => setTheme(value)}
                    className={`min-h-[44px] rounded-lg border px-2 py-2 text-sm capitalize font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                      theme === value
                        ? "border-primary bg-primary/10 text-primary font-semibold"
                        : "border-border text-foreground hover:bg-muted"
                    }`}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </fieldset>
            <button
              type="button"
              onClick={() => {
                setFontSize(18);
                setWidth("comfortable");
              }}
              className="mt-5 inline-flex min-h-[44px] items-center gap-2 rounded-lg px-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <RotateCcw className="h-4 w-4" /> Reset size and width
            </button>
            <p className="mt-4 font-metadata text-xs text-muted-foreground">
              Shortcuts: ← previous · → next · . settings
            </p>
            {!isAuthenticated && (
              <p className="mt-2 font-metadata text-xs text-muted-foreground">
                Guest reading position stays on this device.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
