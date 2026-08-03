import type { Metadata } from "next";
import { BrowsePage } from "@/components/public/browse-page";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q.trim() : "";
  const entries = Object.entries(params).sort(([left], [right]) => left.localeCompare(right));
  const utilityFilters = entries.filter(
    ([key, value]) =>
      !["sort_by", "order", "page", "view"].includes(key) &&
      typeof value === "string" &&
      value.length > 0,
  );
  const canonicalParams = new URLSearchParams();
  for (const [key, value] of entries) {
    if (["sort_by", "order", "view"].includes(key) || typeof value !== "string" || !value) continue;
    canonicalParams.set(key, value);
  }
  const canonicalQuery = canonicalParams.toString();
  const canonical = `/browse-novels${canonicalQuery ? `?${canonicalQuery}` : ""}`;
  if (q) {
    return {
      title: `Search results for "${q}"`,
      description: `Search results for "${q}" on Dokushodo.`,
      robots: { index: false, follow: true },
      alternates: { canonical },
    };
  }
  return {
    title: "Browse Novels",
    description: "Browse the translated novel library on Dokushodo: search by title or author, narrow by status, genre, or chapter count.",
    robots: utilityFilters.length ? { index: false, follow: true } : undefined,
    alternates: { canonical },
  };
}

export default function BrowseNovelsPage() {
  return (
    <BrowsePage
      basePath="/browse-novels"
      title="Browse the library"
      description="Search by title or author, then narrow by status, genre, or chapter count."
    />
  );
}
