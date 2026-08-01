import type { Metadata } from "next";

import { BrowsePage } from "@/components/public/browse-page";

export async function generateMetadata({ params }: { params: Promise<{ tag: string }> }): Promise<Metadata> {
  const tag = decodeURIComponent((await params).tag);
  return {
    title: `Novels tagged ${tag}`,
    description: `Browse translated novels tagged ${tag} on Dokushodo.`,
    alternates: { canonical: `/tags/${encodeURIComponent(tag)}` },
  };
}

export default async function TagPage({ params }: { params: Promise<{ tag: string }> }) {
  const tag = decodeURIComponent((await params).tag);
  return <BrowsePage basePath={`/tags/${encodeURIComponent(tag)}`} title={`Tagged ${tag}`} description={`Translated novels tagged ${tag}.`} preset={{ tag_include: tag }} />;
}
