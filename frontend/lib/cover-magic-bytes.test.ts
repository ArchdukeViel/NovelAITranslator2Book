import { describe, expect, it } from "vitest";

import { validateImageMagicBytes } from "./cover-magic-bytes";

function hex(bytes: number[]): Uint8Array {
  return new Uint8Array(bytes);
}

describe("validateImageMagicBytes (Finding 9.3, REQ-15, AC-15, SEC-2)", () => {
  it("accepts a PNG signature", () => {
    const png = hex([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d]);
    expect(validateImageMagicBytes(png)).toEqual({ ok: true, kind: "png" });
  });

  it("accepts a JPEG signature", () => {
    const jpeg = hex([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01]);
    expect(validateImageMagicBytes(jpeg)).toEqual({ ok: true, kind: "jpeg" });
  });

  it("accepts a WEBP signature (RIFF...WEBP)", () => {
    const webp = hex([
      0x52, 0x49, 0x46, 0x46, // RIFF
      0x1a, 0x00, 0x00, 0x00, // size (irrelevant)
      0x57, 0x45, 0x42, 0x50, // WEBP
      0x56, 0x50, 0x38, 0x4c, // VP8L
    ]);
    expect(validateImageMagicBytes(webp)).toEqual({ ok: true, kind: "webp" });
  });

  it("rejects an HTML file renamed to .png", () => {
    // <!DOCTYPE html> in raw ASCII bytes
    const html = hex([0x3c, 0x21, 0x44, 0x4f, 0x43, 0x54, 0x59, 0x50, 0x45, 0x20, 0x68, 0x74, 0x6d, 0x6c, 0x3e]);
    const result = validateImageMagicBytes(html);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toMatch(/does not match PNG/);
    }
  });

  it("rejects a script file renamed to .jpg", () => {
    // #!/bin/sh
    const script = hex([0x23, 0x21, 0x2f, 0x62, 0x69, 0x6e, 0x2f, 0x73, 0x68, 0x0a, 0x65, 0x63, 0x68, 0x6f]);
    const result = validateImageMagicBytes(script);
    expect(result.ok).toBe(false);
  });

  it("rejects a RIFF container that is not WEBP", () => {
    // RIFF....WAVE (a WAV file, not WEBP)
    const wav = hex([
      0x52, 0x49, 0x46, 0x46,
      0x24, 0x00, 0x00, 0x00,
      0x57, 0x41, 0x56, 0x45, // WAVE
    ]);
    const result = validateImageMagicBytes(wav);
    expect(result.ok).toBe(false);
  });

  it("rejects truncated PNG signature", () => {
    const truncated = hex([0x89, 0x50, 0x4e, 0x47]); // missing tail
    expect(validateImageMagicBytes(truncated).ok).toBe(false);
  });

  it("rejects empty and null inputs", () => {
    expect(validateImageMagicBytes(new Uint8Array(0)).ok).toBe(false);
    expect(validateImageMagicBytes(null).ok).toBe(false);
    expect(validateImageMagicBytes(undefined).ok).toBe(false);
  });

  it("returns a string reason suitable for inline error display", () => {
    const result = validateImageMagicBytes(hex([0x00, 0x00, 0x00, 0x00]));
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(typeof result.reason).toBe("string");
      expect(result.reason.length).toBeGreaterThan(0);
    }
  });
});
