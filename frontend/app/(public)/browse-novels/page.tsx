import type { Metadata } from "next";
import { BrowsePage } from "@/components/public/browse-page";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const params = await searchParams;
  if (params.q?.trim()) {
    return {
      title: `Search results for "${params.q.trim()}"`,
      description: `Search results for "${params.q.trim()}" on Dokushodo.`,
    };
  }
  return {
    title: "Browse Novels",
    description: "Browse the translated novel library on Dokushodo — search by title or author, narrow by status, genre, or chapter count.",
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
