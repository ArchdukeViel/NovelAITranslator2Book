"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { clampReaderFontSize } from "@/lib/public-format";

type ReaderPrefsState = {
  theme: "light" | "dark" | "sepia";
  fontSize: number;
  width: "compact" | "comfortable" | "wide";
  setTheme: (theme: "light" | "dark" | "sepia") => void;
  setFontSize: (size: number) => void;
  setWidth: (width: "compact" | "comfortable" | "wide") => void;
};

export const useReaderPrefsStore = create<ReaderPrefsState>()(
  persist(
    (set) => ({
      theme: "light",
      fontSize: 18,
      width: "comfortable",
      setTheme: (theme) => set({ theme }),
      setFontSize: (size) => set({ fontSize: clampReaderFontSize(size) }),
      setWidth: (width) => set({ width }),
    }),
    {
      name: "novelai-reader",
    }
  )
);
