import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  CONTRIBUTOR_TOKEN_STORAGE_KEY,
  CONTRIBUTOR_TOKEN_TTL_MS,
  getStoredContributorToken,
  purgeStoredContributorToken,
  saveStoredContributorToken,
} from "../page";

describe("Contributor Token Storage Lifecycle (Finding 8.1, REQ-13, AC-13)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("stores token with 30-day expiresAt and cachedAt timestamps", () => {
    const now = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(now);

    saveStoredContributorToken("test-gemini-key");

    const raw = window.localStorage.getItem(CONTRIBUTOR_TOKEN_STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed).toEqual({
      token: "test-gemini-key",
      cachedAt: now,
      expiresAt: now + CONTRIBUTOR_TOKEN_TTL_MS,
    });
    expect(CONTRIBUTOR_TOKEN_TTL_MS).toBe(30 * 24 * 60 * 60 * 1000);
  });

  it("retrieves valid unexpired token", () => {
    const now = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(now);

    saveStoredContributorToken("valid-token");

    // Advance 15 days
    vi.spyOn(Date, "now").mockReturnValue(now + 15 * 24 * 60 * 60 * 1000);

    const retrieved = getStoredContributorToken();
    expect(retrieved).toBe("valid-token");
    expect(window.localStorage.getItem(CONTRIBUTOR_TOKEN_STORAGE_KEY)).toBeTruthy();
  });

  it("automatically purges expired token and returns null when past 30 days", () => {
    const now = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(now);

    saveStoredContributorToken("expiring-token");

    // Advance 31 days (past 30 days TTL)
    vi.spyOn(Date, "now").mockReturnValue(now + 31 * 24 * 60 * 60 * 1000);

    const retrieved = getStoredContributorToken();
    expect(retrieved).toBeNull();
    expect(window.localStorage.getItem(CONTRIBUTOR_TOKEN_STORAGE_KEY)).toBeNull();
  });

  it("purges token on explicit purge call", () => {
    saveStoredContributorToken("token-to-purge");
    expect(window.localStorage.getItem(CONTRIBUTOR_TOKEN_STORAGE_KEY)).toBeTruthy();

    purgeStoredContributorToken();
    expect(window.localStorage.getItem(CONTRIBUTOR_TOKEN_STORAGE_KEY)).toBeNull();
  });
});
