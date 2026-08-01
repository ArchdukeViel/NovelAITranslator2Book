import { describe, expect, it, vi } from "vitest";

import { generateMetadata as browseMetadata } from "./page";
import { generateMetadata as sourceMetadata } from "../sources/[sourceKey]/page";
import { publicApi } from "@/lib/public-api";

describe("catalog metadata", () => {
  it("marks arbitrary browse filters noindex and preserves page canonicals", async () => {
    const metadata = await browseMetadata({
      searchParams: Promise.resolve({ genre_include: "fantasy", page: "2" }),
    });

    expect(metadata.robots).toEqual({ index: false, follow: true });
    expect(metadata.alternates).toEqual({ canonical: "/browse-novels?genre_include=fantasy&page=2" });
  });

  it("canonicalizes sort-only variants to the unsorted catalog", async () => {
    const metadata = await browseMetadata({
      searchParams: Promise.resolve({ sort_by: "title", order: "asc" }),
    });

    expect(metadata.robots).toBeUndefined();
    expect(metadata.alternates).toEqual({ canonical: "/browse-novels" });
  });

  it("indexes source pages only when at least one novel is proven", async () => {
    vi.spyOn(publicApi, "catalog").mockResolvedValueOnce({ novels: [], total: 1, page: 1, page_size: 1 });
    const populated = await sourceMetadata({ params: Promise.resolve({ sourceKey: "syosetu" }) });
    vi.spyOn(publicApi, "catalog").mockRejectedValueOnce(new Error("offline"));
    const unknown = await sourceMetadata({ params: Promise.resolve({ sourceKey: "unknown" }) });

    expect(populated.robots).toEqual({ index: true, follow: true });
    expect(unknown.robots).toEqual({ index: false, follow: true });
  });
});
