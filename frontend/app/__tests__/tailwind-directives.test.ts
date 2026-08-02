import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Regression: the three @tailwind directives must be present in globals.css
// before the :root token block, in order base → components → utilities.
// Without them, Tailwind 3 produces no utility classes and the site renders
// as mostly unstyled HTML.
// ---------------------------------------------------------------------------

const cssPath = resolve(__dirname, "..", "globals.css");

function nonBlankTrimmed(src: string): string[] {
  return src
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("//"));
}

describe("@tailwind directive regression guard", () => {
  const raw = readFileSync(cssPath, "utf-8");
  const lines = nonBlankTrimmed(raw);

  it("globals.css is readable", () => {
    expect(raw.length).toBeGreaterThan(0);
  });

  it("contains @tailwind base;", () => {
    expect(lines).toContain("@tailwind base;");
  });

  it("contains @tailwind components;", () => {
    expect(lines).toContain("@tailwind components;");
  });

  it("contains @tailwind utilities;", () => {
    expect(lines).toContain("@tailwind utilities;");
  });

  it("directives precede :root in correct order", () => {
    const rootIdx = lines.indexOf(":root {");
    expect(rootIdx).not.toBe(-1);

    const baseIdx = lines.indexOf("@tailwind base;");
    const compIdx = lines.indexOf("@tailwind components;");
    const utilIdx = lines.indexOf("@tailwind utilities;");

    expect(baseIdx).toBeLessThan(compIdx);
    expect(compIdx).toBeLessThan(utilIdx);
    expect(utilIdx).toBeLessThan(rootIdx);
  });
});
