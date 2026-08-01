import type { Metadata } from "next";

import { BrowsePage } from "@/components/public/browse-page";

function label(slug: string): string {
  return slug.split("-").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export async function generateMetadata({ params }: { params: Promise<{ genre: string }> }): Promise<Metadata> {
  const genre = decodeURIComponent((await params).genre);
  return {
    title: `${label(genre)} novels`,
    description: `Browse ${label(genre)} translated novels on Dokushodo.`,
    alternates: { canonical: `/genres/${encodeURIComponent(genre)}` },
  };
}

export default async function GenrePage({ params }: { params: Promise<{ genre: string }> }) {
  const genre = decodeURIComponent((await params).genre);
  return <BrowsePage basePath={`/genres/${encodeURIComponent(genre)}`} title={`${label(genre)} novels`} description={`Translated novels in ${label(genre)}.`} preset={{ genre_include: genre }} />;
}
