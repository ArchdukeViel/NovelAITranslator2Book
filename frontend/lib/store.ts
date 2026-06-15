"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

// Admin-scoped UI state (persisted under "novelai-ui" key)
// These control the admin dashboard appearance
type AdminUiState = {
  darkMode: boolean;
  sidebarCollapsed: boolean;
  toggleDarkMode: () => void;
  toggleSidebar: () => void;
};

// Public reader UI state (persisted under "novelai-ui" key)
// These control the public reader appearance - never cross-written with admin state
type ReaderUiState = {
  readerTheme: "light" | "dark" | "sepia";
  readerFontSize: number;
  readerWidth: "compact" | "comfortable" | "wide";
  setReaderTheme: (theme: ReaderUiState["readerTheme"]) => void;
  setReaderFontSize: (size: number) => void;
  setReaderWidth: (width: ReaderUiState["readerWidth"]) => void;
};

type UiState = AdminUiState & ReaderUiState;

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      // Admin-scoped state (Task 4: decommission client-side auth token)
      darkMode: false,
      sidebarCollapsed: false,

      // Reader state (Task 4: keep untouched, never cross-write with admin)
      readerTheme: "light",
      readerFontSize: 18,
      readerWidth: "comfortable",

      // Admin UI actions
      toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      // Reader UI actions
      setReaderTheme: (readerTheme) => set({ readerTheme }),
      setReaderFontSize: (readerFontSize) =>
        set({ readerFontSize: Math.min(24, Math.max(15, Math.round(readerFontSize))) }),
      setReaderWidth: (readerWidth) => set({ readerWidth })
    }),
    {
      name: "novelai-ui"
    }
  )
);
