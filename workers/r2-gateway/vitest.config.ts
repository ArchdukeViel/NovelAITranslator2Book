import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/index.test.ts"],
    environment: "node",
  },
});
