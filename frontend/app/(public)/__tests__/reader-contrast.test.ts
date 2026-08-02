import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

type Rgb = [number, number, number];

const css = readFileSync(resolve(process.cwd(), "app/(public)/reader.css"), "utf8");

/** Parse hex color (#rrggbb) to normalized RGB [0-1]. */
function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

function luminance(rgb: Rgb): number {
  const linear = rgb.map((c) =>
    c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(a: Rgb, b: Rgb): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

/** Extract reader theme block by data-reader-theme selector. */
function themeBlock(theme: string): { background: string; foreground: string; secondary: string } {
  const pattern = new RegExp(
    `\\[data-reader-theme="${theme}"\\]\\s*\\{([^}]+)\\}`,
  );
  const body = css.match(pattern)?.[1];
  if (!body) throw new Error(`Missing [data-reader-theme="${theme}"] block`);

  const bg = body.match(/background:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const fg = body.match(/color:\s*(#[0-9a-fA-F]{6})/)?.[1];
  const secondary = body.match(/--reader-secondary:\s*(#[0-9a-fA-F]{6})/)?.[1];

  if (!bg || !fg || !secondary) {
    throw new Error(`Missing background, color, or --reader-secondary in "${theme}" theme`);
  }

  return { background: bg, foreground: fg, secondary };
}

describe("Reader theme contrast", () => {
  for (const theme of ["light", "dark", "sepia"] as const) {
    const { background, foreground, secondary } = themeBlock(theme);

    it(`${theme}: foreground on background meets WCAG AA (4.5:1)`, () => {
      const ratio = contrast(hexToRgb(foreground), hexToRgb(background));
      expect(
        ratio,
        `${theme}: foreground ${foreground} on ${background} is ${ratio.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(4.5);
    });

    it(`${theme}: secondary on background meets WCAG AA (4.5:1)`, () => {
      const ratio = contrast(hexToRgb(secondary), hexToRgb(background));
      expect(
        ratio,
        `${theme}: secondary ${secondary} on ${background} is ${ratio.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(4.5);
    });
  }
});
