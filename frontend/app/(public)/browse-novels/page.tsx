import { BrowsePage } from "@/components/public/browse-page";

export default function BrowseNovelsPage() {
  return (
    <BrowsePage
      basePath="/browse-novels"
      title="Browse Novels"
      description="Search the public catalog, filter by language, and find the latest translated releases available to read."
    />
  );
}
