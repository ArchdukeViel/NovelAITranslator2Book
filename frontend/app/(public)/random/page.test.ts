import { beforeEach, describe, expect, it, vi } from "vitest";

import RandomNovelPage from "./page";
import { publicApi } from "@/lib/public-api";

const redirectMock = vi.hoisted(() => vi.fn((href: string) => {
  const error = new Error(`REDIRECT:${href}`) as Error & { digest: string };
  error.digest = `NEXT_REDIRECT;replace;${href}`;
  throw error;
}));

vi.mock("next/navigation", () => ({ redirect: redirectMock }));

describe("RandomNovelPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("redirects directly to a loaded novel", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    vi.spyOn(publicApi, "catalog").mockResolvedValue({ novels: [{ slug: "dragon" }] as never, total: 1, page: 1, page_size: 1 });
    await expect(RandomNovelPage()).rejects.toThrow("REDIRECT:/novels/dragon");
  });

  it("redirects to honest catalog recovery when empty", async () => {
    vi.spyOn(publicApi, "catalog").mockResolvedValue({ novels: [], total: 0, page: 1, page_size: 1 });
    await expect(RandomNovelPage()).rejects.toThrow("REDIRECT:/browse-novels?notice=empty");
  });
});
