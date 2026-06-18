import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { authApi, googleOAuthStartUrl } from "@/lib/public-api";

describe("public auth API", () => {
  it("builds a Google OAuth start URL with a safe relative return path", () => {
    const url = authApi.googleStart("/novel/demo?chapter=1#reader");

    expect(url).toContain("/api/auth/google/start?");
    expect(url).toContain("next=%2Fnovel%2Fdemo%3Fchapter%3D1%23reader");
  });

  it("falls back for unsafe external return paths", () => {
    expect(googleOAuthStartUrl("https://example.com/phish")).toContain(
      "next=%2F"
    );
    expect(googleOAuthStartUrl("//example.com/phish")).toContain("next=%2F");
    expect(googleOAuthStartUrl("relative/path")).toContain("next=%2F");
  });

  it("has public email auth available without owner bootstrap login", () => {
    expect(authApi.passwordLogin).toBeDefined();
    expect(typeof authApi.passwordLogin).toBe("function");
    expect(authApi.register).toBeDefined();
    expect(typeof authApi.register).toBe("function");
    expect("login" in authApi).toBe(false);
  });

  it("does not restore non-reading public user APIs", () => {
    const source = readFileSync("lib/public-api.ts", "utf8");

    expect(source).not.toContain("userApi");
    expect(source).not.toContain("/api/user/contributions");
  });
});
