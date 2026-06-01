"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ApiTokenRecord = {
  id: string;
  type: "gemini";
  token: string;
  addedOn: string;
  status: "Active" | "Inactive";
};

type UiState = {
  apiToken: string;
  apiTokenLabel: string;
  apiTokens: ApiTokenRecord[];
  darkMode: boolean;
  sidebarCollapsed: boolean;
  addApiToken: (token: string) => void;
  applyDummyApiToken: () => void;
  removeApiToken: (id: string) => void;
  setApiToken: (token: string) => void;
  toggleDarkMode: () => void;
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
      sidebarCollapsed: false,
      addApiToken: (apiToken) =>
        set((state) => {
          const token = apiToken.trim();
          if (!token) {
            return state;
          }

          return {
            apiToken: token,
            apiTokenLabel: "Gemini AI",
            apiTokens: [
              ...state.apiTokens.map((entry) => ({ ...entry, status: "Inactive" as const })),
              {
                id: createId(),
                type: "gemini",
                token,
                addedOn: new Date().toISOString(),
                status: "Active"
              }
            ]
          };
        }),
      applyDummyApiToken: () => set({ apiToken: "", apiTokenLabel: "dummy" }),
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
      toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }))
    }),
    {
      name: "novelai-ui"
    }
  )
);
