import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { publicApi } from "@/lib/public-api";

export const metadata: Metadata = {
  title: "Surprise Me",
  robots: { index: false, follow: true },
};

export default async function RandomNovelPage() {
  try {
    const summary = await publicApi.catalog({ page_size: 1 });
    if (summary.total > 0) {
      const page = Math.floor(Math.random() * summary.total) + 1;
      const catalog = page === 1 ? summary : await publicApi.catalog({ page, page_size: 1 });
      const novel = catalog.novels[0];
      if (!novel) redirect("/browse-novels?notice=empty");
      redirect(`/novels/${encodeURIComponent(novel.slug)}`);
    }
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error) throw error;
  }
  redirect("/browse-novels?notice=empty");
}
