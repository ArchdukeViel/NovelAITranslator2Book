import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { maskToken, containsSecret } from "../mask-token";

// Feature: admin-ui-rework, Property 5: Credentials are always masked and raw values are never rendered

describe("maskToken", () => {
  // Property 5: For any token string, assert masking reveals at most a short prefix/suffix 
  // and never the obscured middle verbatim. Min 100 iterations.
  it("reveals at most a short prefix and suffix, never emits the obscured middle verbatim", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 200 }), (value) => {
        // Skip empty strings after generation
        if (value.length === 0) return true;

        const masked = maskToken(value);

        // Should never return the original value if it's long enough
        const minMaskedLength = 4 + 1 + 4; // prefix + min middle + suffix
        if (value.length > minMaskedLength) {
          expect(masked).not.toBe(value);
        }

        // Prefix should be at most the first 4 characters
        if (value.length >= 4 && masked.length > 0) {
          expect(masked.slice(0, 4)).toBe(value.slice(0, 4));
        }

        // Suffix should be at most the last 4 characters
        if (value.length >= 4 && masked.length > 4) {
          const suffixStart = Math.max(0, masked.length - 4);
          expect(masked.slice(suffixStart)).toBe(value.slice(-4));
        }

        // The middle should be asterisks, never the original middle
        if (value.length > 12) {
          const prefix = value.slice(0, 4);
          const suffix = value.slice(-4);
          const originalMiddle = value.slice(4, -4);
          const maskedMiddle = masked.slice(4, -4);
          
          // The masked middle should NOT contain the original middle verbatim
          expect(maskedMiddle).not.toContain(originalMiddle);
          
          // The masked middle should contain asterisks
          expect(maskedMiddle).toMatch(/^\*+$/);
        }
      }),
      { numRuns: 100 }
    );
  });

  it("handles edge cases: null, undefined, empty string", () => {
    expect(maskToken(null)).toBe("");
    expect(maskToken(undefined)).toBe("");
    expect(maskToken("")).toBe("");
  });

  it("returns short strings as-is (they're not secrets)", () => {
    expect(maskToken("abc")).toBe("abc");
    expect(maskToken("ab")).toBe("ab");
    expect(maskToken("a")).toBe("a");
    expect(maskToken("short")).toBe("short");
  });

  it("handles known secret patterns correctly", () => {
    // Google API key: length 28, prefix=AIza, suffix=6789, middle=20 chars -> 8 asterisks
    expect(maskToken("AIzaSyD_example_key_123456789")).toBe("AIza********6789");
    
    // OpenAI key: length 24, prefix=sk-1 (first 4), suffix=ghij, middle=16 chars -> 8 asterisks  
    expect(maskToken("sk-1234567890abcdefghij")).toBe("sk-1********ghij");
    
    // Generic long token: length 28, prefix=very, suffix=2345 (last 4 chars), middle=20 chars -> 8 asterisks
    expect(maskToken("very-long-secret-token-12345")).toBe("very********2345");
  });

  it("never reveals the full middle portion of any token", () => {
    // Test with various lengths
    const tokens = [
      "short-token",
      "medium-length-token-here",
      "very-long-token-string-that-should-be-masked",
      "AIzaSyD1234567890abcdefghijklmnop",
      "sk-proj-1234567890abcdefghijklmnop",
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ",
    ];

    for (const token of tokens) {
      const masked = maskToken(token);
      
      if (token.length > 12) {
        const prefix = token.slice(0, 4);
        const suffix = token.slice(-4);
        const middle = token.slice(4, -4);
        
        // The masked version should start with prefix
        expect(masked.startsWith(prefix)).toBe(true);
        // The masked version should end with suffix
        expect(masked.endsWith(suffix)).toBe(true);
        // The masked middle should NOT contain the original middle
        expect(masked.includes(middle)).toBe(false);
      }
    }
  });
});

describe("containsSecret", () => {
  it("detects Bearer tokens", () => {
    expect(containsSecret("Bearer sk-1234567890abcdef")).toBe(true);
    expect(containsSecret("Authorization: Bearer token123")).toBe(true);
  });

  it("detects Authorization headers", () => {
    expect(containsSecret("Authorization: Basic abc123")).toBe(true);
    expect(containsSecret("header Authorization: Bearer token")).toBe(true);
  });

  it("detects cookie strings", () => {
    expect(containsSecret("cookie: session_id=abc123")).toBe(true);
    expect(containsSecret("Cookie: token=xyz789")).toBe(true);
  });

  it("detects Google API keys", () => {
    expect(containsSecret("AIzaSyD1234567890abcdefghij")).toBe(true);
  });

  it("detects OpenAI keys", () => {
    expect(containsSecret("sk-1234567890abcdefghij")).toBe(true);
    expect(containsSecret("sk-proj-1234567890abcdefghijklmn")).toBe(true);
  });

  it("returns false for safe strings", () => {
    expect(containsSecret("Hello, world!")).toBe(false);
    expect(containsSecret("This is a normal error message")).toBe(false);
    expect(containsSecret("User data: name=John, age=30")).toBe(false);
  });

  it("handles null/undefined/empty", () => {
    expect(containsSecret(null)).toBe(false);
    expect(containsSecret(undefined)).toBe(false);
    expect(containsSecret("")).toBe(false);
  });
});