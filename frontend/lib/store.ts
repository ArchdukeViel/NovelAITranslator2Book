"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ApiTokenRecord = {
  id: string;
  type: "gemini";
  token: string;
  addedOn: string;
  status: "Active" | "Inactive";
  validationStatus?: "Unchecked" | "Checking" | "Working" | "Failed";
  validationMessage?: string | null;
  validatedOn?: string | null;
  model?: string | null;
};

type UiState = {
  apiToken: string;
  apiTokenLabel: string;
  apiTokens: ApiTokenRecord[];
  darkMode: boolean;
  readerTheme: "light" | "dark" | "sepia";
  readerFontSize: number;
  readerWidth: "compact" | "comfortable" | "wide";
  sidebarCollapsed: boolean;
  addApiToken: (token: string, validation?: Partial<ApiTokenRecord>) => string | null;
  applyDummyApiToken: () => void;
  setActiveApiToken: (id: string) => void;
  removeApiToken: (id: string) => void;
  setApiToken: (token: string) => void;
  updateApiTokenValidation: (id: string, validation: Partial<ApiTokenRecord>) => void;
  toggleDarkMode: () => void;
  setReaderTheme: (theme: UiState["readerTheme"]) => void;
  setReaderFontSize: (size: number) => void;
  setReaderWidth: (width: UiState["readerWidth"]) => void;
  toggleSidebar: () => void;
};

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      apiToken: "",
      apiTokenLabel: "None",
      apiTokens: [],
      darkMode: false,
      readerTheme: "light",
      readerFontSize: 18,
      readerWidth: "comfortable",
      sidebarCollapsed: false,
      addApiToken: (apiToken, validation = {}) => {
        const token = apiToken.trim();
        if (!token) {
          return null;
        }
        const id = createId();

        set((state) => {
          return {
            apiToken: token,
            apiTokenLabel: "Gemini AI",
            apiTokens: [
              ...state.apiTokens.map((entry) => ({ ...entry, status: "Inactive" as const })),
              {
                id,
                type: "gemini",
                token,
                addedOn: new Date().toISOString(),
                status: "Active",
                validationStatus: validation.validationStatus ?? "Unchecked",
                validationMessage: validation.validationMessage ?? null,
                validatedOn: validation.validatedOn ?? null,
                model: validation.model ?? null
              }
            ]
          };
        });
        return id;
      },
      applyDummyApiToken: () => set({ apiToken: "", apiTokenLabel: "dummy" }),
      setActiveApiToken: (id) =>
        set((state) => {
          const active = state.apiTokens.find((entry) => entry.id === id);
          if (!active) {
            return state;
          }
          return {
            apiToken: active.token,
            apiTokenLabel: "Gemini AI",
            apiTokens: state.apiTokens.map((entry) => ({
              ...entry,
              status: entry.id === id ? "Active" : "Inactive"
            }))
          };
        }),
      removeApiToken: (id) =>
        set((state) => {
          const removed = state.apiTokens.find((entry) => entry.id === id);
          const remaining = state.apiTokens.filter((entry) => entry.id !== id);
          if (!removed || removed.token !== state.apiToken) {
            return { apiTokens: remaining };
          }

          const nextActive = remaining.at(-1);
          return {
            apiToken: nextActive?.token ?? "",
            apiTokenLabel: nextActive ? "Gemini AI" : "None",
            apiTokens: remaining.map((entry) => ({
              ...entry,
              status: nextActive && entry.id === nextActive.id ? "Active" : "Inactive"
            }))
          };
        }),
      setApiToken: (apiToken) => set({ apiToken, apiTokenLabel: apiToken.trim() ? "Gemini AI" : "None" }),
      updateApiTokenValidation: (id, validation) =>
        set((state) => ({
          apiTokens: state.apiTokens.map((entry) =>
            entry.id === id
              ? {
                  ...entry,
                  ...validation
                }
              : entry
          )
        })),
      toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
      setReaderTheme: (readerTheme) => set({ readerTheme }),
      setReaderFontSize: (readerFontSize) =>
        set({ readerFontSize: Math.min(24, Math.max(15, Math.round(readerFontSize))) }),
      setReaderWidth: (readerWidth) => set({ readerWidth }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }))
    }),
    {
      name: "novelai-ui"
    }
  )
);
