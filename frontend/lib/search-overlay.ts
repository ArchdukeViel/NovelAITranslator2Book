"use client";

import { create } from "zustand";

// Shared search overlay state (DESIGN.md — Search contract). The overlay is
// opened from the desktop header search field, the mobile Search tab, and the
// `/` keyboard shortcut; all three converge on this store so there is exactly
// one search surface, not two search boxes.

type SearchOverlayState = {
  isOpen: boolean;
  /** Element that opened the overlay — focus returns here on Escape/close. */
  openerRef: Element | null;
  open: () => void;
  close: () => void;
  toggle: () => void;
};

export const useSearchOverlay = create<SearchOverlayState>((set) => ({
  isOpen: false,
  openerRef: null,
  open: () =>
    set({
      isOpen: true,
      openerRef: typeof document !== "undefined" ? document.activeElement : null,
    }),
  close: () => set({ isOpen: false }),
  toggle: () =>
    set((state) => ({
      isOpen: !state.isOpen,
      openerRef: state.isOpen ? state.openerRef : typeof document !== "undefined" ? document.activeElement : null,
    })),
}));

// ---------------------------------------------------------------------------
// Local recent searches (DESIGN.md — Search contract). Local-only by design:
// searches can reveal reading interests that should not be stored server-side
// without a privacy review. No API involvement, ever.
// ---------------------------------------------------------------------------

const RECENT_KEY = "novelai:recent-searches";
const RECENT_MAX = 8;

export function loadRecentSearches(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string" && item.trim().length > 0).slice(0, RECENT_MAX);
  } catch {
    return [];
  }
}

export function recordRecentSearch(query: string): string[] {
  const trimmed = query.trim();
  if (typeof window === "undefined" || trimmed.length < 2) return loadRecentSearches();
  const next = [trimmed, ...loadRecentSearches().filter((item) => item.toLowerCase() !== trimmed.toLowerCase())].slice(
    0,
    RECENT_MAX
  );
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // Storage unavailable (private mode / quota) — search still works, recents just don't persist.
  }
  return next;
}

export function clearRecentSearches(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(RECENT_KEY);
  } catch {
    // ignore
  }
}
