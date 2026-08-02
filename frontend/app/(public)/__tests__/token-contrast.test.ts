import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

type Rgb = [number, number, number];

const css = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");

const pairs = [
  ["foreground", "background"],
  ["card-foreground", "card"],
  ["popover-foreground", "popover"],
  ["primary-foreground", "primary"],
  ["secondary-foreground", "secondary"],
  ["accent-foreground", "accent"],
  ["destructive-foreground", "destructive"],
  ["success-foreground", "success"],
  ["warning-foreground", "warning"],
  ["info-foreground", "info"],
  ["muted-foreground", "muted"],
  ["primary-text", "background"],
  ["destructive-text", "background"],
  ["success-text", "background"],
  ["warning-text", "background"],
  ["info-text", "background"],
  ["foreground", "card"],
] as const;

function tokenBlock(selector: ":root" | ".dark"): Map<string, string> {
  const escaped = selector.replace(".", "\\.");
  const body = css.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`))?.[1];
  if (!body) throw new Error(`Missing ${selector} token block`);

  return new Map(
    [...body.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2].trim()]),
  );
}

function hsl(value: string): Rgb {
  const match = value.match(/^([\d.]+)\s+([\d.]+)%\s+([\d.]+)%$/);
  if (!match) throw new Error(`Unsupported HSL token: ${value}`);

  const hue = Number(match[1]) / 360;
  const saturation = Number(match[2]) / 100;
  const lightness = Number(match[3]) / 100;
  if (saturation === 0) return [lightness, lightness, lightness];

  const q = lightness < 0.5
    ? lightness * (1 + saturation)
    : lightness + saturation - lightness * saturation;
  const p = 2 * lightness - q;
  const channel = (offset: number) => {
    const t = (hue + offset + 1) % 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [channel(1 / 3), channel(0), channel(-1 / 3)];
}

function luminance(rgb: Rgb): number {
  const linear = rgb.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(left: Rgb, right: Rgb): number {
  const [lighter, darker] = [luminance(left), luminance(right)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("Yokocho Lantern token contrast", () => {
  for (const selector of [":root", ".dark"] as const) {
    const tokens = tokenBlock(selector);

    it(`${selector} passes all 17 WCAG AA text pairs`, () => {
      expect(pairs).toHaveLength(17);
      for (const [foreground, background] of pairs) {
        const foregroundValue = tokens.get(foreground);
        const backgroundValue = tokens.get(background);
        if (!foregroundValue || !backgroundValue) {
          throw new Error(`${selector}: missing --${foreground} or --${background}`);
        }
        const ratio = contrast(hsl(foregroundValue), hsl(backgroundValue));
        expect(
          ratio,
          `${selector}: --${foreground} on --${background} is ${ratio.toFixed(2)}:1`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    });
  }
});
