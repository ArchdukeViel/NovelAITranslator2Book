/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.{test,spec}.{ts,tsx}"],
    pool: "forks",
    // Single fork on CI: measured on the 2-core GitHub runner, maxWorkers: 2 made
    // frontend-check SLOWER (89s vs 62s) — duplicated module transform and
    // jsdom environment setup per fork outweigh the 2-core parallelism.
    // Locally, allow default parallelism if not in CI.
    maxWorkers: process.env.CI ? 1 : undefined,
    fileParallelism: !process.env.CI,
  },
});
