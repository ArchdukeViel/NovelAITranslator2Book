import type { MetadataRoute } from "next";
import { publicApi } from "@/lib/public-api";
import { getSiteUrl } from "@/lib/seo";

/** Static public pages suitable for indexing. */
function staticEntries(siteUrl: string): MetadataRoute.Sitemap {
  const base = siteUrl.replace(/\/+$/, "");
  return [
    { url: `${base}/`, changeFrequency: "daily", priority: 1.0 },
    { url: `${base}/home`, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/browse-novels`, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/about`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/privacy`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/terms`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/cookie-policy`, changeFrequency: "monthly", priority: 0.2 },
    { url: `${base}/legal`, changeFrequency: "monthly", priority: 0.2 },
  ];
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const siteUrl = getSiteUrl();
  const entries: MetadataRoute.Sitemap = staticEntries(siteUrl);

  // Try to fetch published novels for dynamic sitemap entries.
  // Falls back to static pages only if API is unreachable.
  try {
    const data = await publicApi.catalog({ page_size: 100 });
    if (Array.isArray(data.novels)) {
      for (const novel of data.novels) {
        if (!novel.slug) continue;

        const encodedSlug = encodeURIComponent(novel.slug);

        const lastModified =
          novel.latest_chapter_updated_at || novel.added_at || undefined;

        entries.push({
          url: `${siteUrl}/novels/${encodedSlug}`,
          changeFrequency: "weekly",
          priority: 0.8,
          lastModified: lastModified
            ? new Date(lastModified).toISOString()
            : undefined,
        });

        // ponytail: chapter-level sitemap entries require a separate
        // API call per novel. Add when chapter count grows enough to
        // justify the traffic cost.
      }
    }
  } catch {
    // API unreachable — return static pages only
  }

  return entries;
}
