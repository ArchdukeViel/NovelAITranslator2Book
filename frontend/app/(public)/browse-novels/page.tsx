import { BrowsePage } from "@/components/public/browse-page";

export default function BrowseNovelsPage() {
  return (
    <BrowsePage
      basePath="/browse-novels"
      title="Browse Novels"
      description="Browse the catalog by title, author, status, or chapter count."
    />
  );
}
