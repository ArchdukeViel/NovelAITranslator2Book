import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Regression: Tailwind 4's import and legacy configuration/plugin bridges must
// be present in globals.css before the :root token block. Without them, the
// site renders as mostly unstyled HTML.
// ---------------------------------------------------------------------------

const cssPath = resolve(__dirname, "..", "globals.css");

function nonBlankTrimmed(src: string): string[] {
  return src
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("//"));
}

describe("Tailwind import regression guard", () => {
  const raw = readFileSync(cssPath, "utf-8");
  const lines = nonBlankTrimmed(raw);

  it("globals.css is readable", () => {
    expect(raw.length).toBeGreaterThan(0);
  });

  it("contains the Tailwind 4 import", () => {
    expect(lines).toContain('@import "tailwindcss";');
  });

  it("loads the preserved legacy theme configuration", () => {
    expect(lines).toContain('@config "../tailwind.config.ts";');
  });

  it("loads the animation plugin", () => {
    expect(lines).toContain('@plugin "tailwindcss-animate";');
  });

  it("Tailwind setup precedes :root", () => {
    const rootIdx = lines.indexOf(":root {");
    expect(rootIdx).not.toBe(-1);

    const importIdx = lines.indexOf('@import "tailwindcss";');
    const configIdx = lines.indexOf('@config "../tailwind.config.ts";');
    const pluginIdx = lines.indexOf('@plugin "tailwindcss-animate";');

    expect(importIdx).toBeLessThan(configIdx);
    expect(configIdx).toBeLessThan(pluginIdx);
    expect(pluginIdx).toBeLessThan(rootIdx);
  });
});
