"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { clampReaderFontSize } from "@/lib/public-format";

export const READER_UI_STORAGE_KEY = "dokushodo-reader-ui";
export const ADMIN_UI_STORAGE_KEY = "dokushodo-admin-ui";
export const LEGACY_UI_STORAGE_KEY = "novelai-ui";

// Zero-legacy policy: the deprecated monolithic key is purged on boot and
// never read, parsed, or migrated.
if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem(LEGACY_UI_STORAGE_KEY);
  } catch {
    // Storage may be unavailable (private mode); stores still work in memory.
  }
}

// Public reader UI state (persisted under "dokushodo-reader-ui")
type ReaderUiState = {
  theme: "light" | "dark" | "sepia";
  fontSize: number;
  width: "compact" | "comfortable" | "wide";
  setTheme: (theme: ReaderUiState["theme"]) => void;
  setFontSize: (size: number) => void;
  setWidth: (width: ReaderUiState["width"]) => void;
};

export const useReaderUiStore = create<ReaderUiState>()(
  persist(
    (set) => ({
      theme: "light",
      fontSize: 18,
      width: "comfortable",
      setTheme: (theme) => set({ theme }),
      setFontSize: (fontSize) =>
        set({ fontSize: clampReaderFontSize(fontSize) }),
      setWidth: (width) => set({ width }),
    }),
    {
      name: READER_UI_STORAGE_KEY,
    },
  ),
);

// Admin-scoped UI state (persisted under "dokushodo-admin-ui")
type AdminUiState = {
  darkMode: boolean;
  sidebarCollapsed: boolean;
  toggleDarkMode: () => void;
  toggleSidebar: () => void;
};

export const useAdminUiStore = create<AdminUiState>()(
  persist(
    (set) => ({
      darkMode: false,
      sidebarCollapsed: false,
      toggleDarkMode: () =>
        set((state) => ({ darkMode: !state.darkMode })),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    }),
    {
      name: ADMIN_UI_STORAGE_KEY,
    },
  ),
);
