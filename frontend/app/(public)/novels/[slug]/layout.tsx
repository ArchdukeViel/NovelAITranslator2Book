import type { Metadata } from "next";
import { publicApi } from "@/lib/public-api";
import {
  buildCanonicalUrl,
  buildNovelJsonLd,
  buildNovelPageTitle,
  buildDescription,
} from "@/lib/seo";

type Props = {
  params: Promise<{ slug: string }>;
  children: React.ReactNode;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const encodedSlug = encodeURIComponent(slug);
  const canonicalUrl = buildCanonicalUrl(`/novels/${encodedSlug}`);

  // Attempt server-side fetch for accurate novel metadata.
  // Falls back to safe slug-based metadata if API unreachable.
  let novelTitle: string | null = null;
  let novelDescription: string | null = null;

  try {
    const data = await publicApi.novel(slug);
    novelTitle = data.title ?? null;
    novelDescription = data.synopsis ?? null;
  } catch {
    // Server fetch failed — use fallback metadata
  }

  const title = buildNovelPageTitle(novelTitle);
  const description = buildDescription(novelDescription);

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    robots: { index: true, follow: true },
    openGraph: {
      title,
      description,
      url: canonicalUrl,
      type: "book",
      siteName: "Dokushodo",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default async function NovelSlugLayout({
  children,
  params,
}: Props) {
  const { slug } = await params;
  const encodedSlug = encodeURIComponent(slug);
  let data: { title?: string; synopsis?: string | null; author?: string | null } = {};
  try {
    data = await publicApi.novel(slug);
  } catch {
    // Metadata remains optional when public API is unavailable.
  }
  const jsonLd = buildNovelJsonLd(
    data.title ?? slug,
    data.synopsis,
    buildCanonicalUrl(`/novels/${encodedSlug}`),
    data.author,
  );
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      {children}
    </>
  );
}
