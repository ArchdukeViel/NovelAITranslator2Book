import type { Metadata } from "next";
import { publicApi } from "@/lib/public-api";
import {
  buildCanonicalUrl,
  buildChapterJsonLd,
  buildChapterPageTitle,
  buildDescription,
} from "@/lib/seo";

type Props = {
  params: Promise<{ slug: string; chapterId: string }>;
  children: React.ReactNode;
};

export async function generateMetadata({
  params,
}: Props): Promise<Metadata> {
  const { slug, chapterId } = await params;
  const encodedSlug = encodeURIComponent(slug);
  const encodedChapterId = encodeURIComponent(chapterId);
  const canonicalUrl = buildCanonicalUrl(
    `/novels/${encodedSlug}/chapter/${encodedChapterId}`,
  );

  // Attempt server-side fetch for accurate chapter + novel metadata.
  let chapterTitle: string | null = null;
  let novelTitle: string | null = null;
  let chapterDescription: string | null = null;

  try {
    const data = await publicApi.chapter(slug, chapterId);
    chapterTitle = data.title ?? null;
    novelTitle = data.novel_title ?? null;
    if (data.text?.trim()) {
      chapterDescription = data.text
        .trim()
        .slice(0, 200)
        .replace(/\s+/g, " ");
    }
  } catch {
    // Server fetch failed — use fallback metadata
  }

  const title = buildChapterPageTitle(chapterTitle, novelTitle);
  const description = buildDescription(chapterDescription);

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    robots: { index: true, follow: true },
    openGraph: {
      title,
      description,
      url: canonicalUrl,
      type: "article",
      siteName: "Dokushodo",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default async function ChapterLayout({
  children,
  params,
}: Props) {
  const { slug, chapterId } = await params;
  const encodedSlug = encodeURIComponent(slug);
  const encodedChapterId = encodeURIComponent(chapterId);
  let data: { title?: string | null; novel_title?: string | null; text?: string } = {};
  try {
    data = await publicApi.chapter(slug, chapterId);
  } catch {
    // Metadata remains optional when public API is unavailable.
  }
  const jsonLd = buildChapterJsonLd(
    data.title ?? chapterId,
    data.novel_title ?? slug,
    data.text ? buildDescription(data.text) : undefined,
    buildCanonicalUrl(`/novels/${encodedSlug}/chapter/${encodedChapterId}`),
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
