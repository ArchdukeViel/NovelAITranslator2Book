import type { Metadata } from "next";

import { BrowsePage } from "@/components/public/browse-page";
import { publicApi } from "@/lib/public-api";

export async function generateMetadata({ params }: { params: Promise<{ sourceKey: string }> }): Promise<Metadata> {
  const sourceKey = decodeURIComponent((await params).sourceKey);
  let hasNovels = false;
  try {
    hasNovels = (await publicApi.catalog({ source_key: sourceKey, page_size: 1 })).total > 0;
  } catch {
    // Fail closed for indexing when source existence cannot be proven.
  }
  return {
    title: `${sourceKey} novels`,
    description: `Browse translated novels sourced from ${sourceKey} on Dokushodo.`,
    alternates: { canonical: `/sources/${encodeURIComponent(sourceKey)}` },
    robots: { index: hasNovels, follow: true },
  };
}

export default async function SourcePage({ params }: { params: Promise<{ sourceKey: string }> }) {
  const sourceKey = decodeURIComponent((await params).sourceKey);
  return <BrowsePage basePath={`/sources/${encodeURIComponent(sourceKey)}`} title={`${sourceKey} novels`} description={`Translated novels sourced from ${sourceKey}.`} preset={{ source_key: sourceKey }} />;
}
