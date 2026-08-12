/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.{test,spec}.{ts,tsx}"],
    pool: "forks",
    // Single fork: measured on the 2-core GitHub runner, maxWorkers: 2 made
    // frontend-check SLOWER (89s vs 62s) — duplicated module transform and
    // jsdom environment setup per fork outweigh the 2-core parallelism.
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
  },
});
