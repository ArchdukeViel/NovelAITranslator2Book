import { BrowsePage } from "@/components/public/browse-page";

export default function BrowseNovelsPage() {
  return (
    <BrowsePage
      basePath="/browse-novels"
      title="Browse the library"
      description="Search by title or author, then narrow by status, genre, or chapter count."
    />
  );
}
