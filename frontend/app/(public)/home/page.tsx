import { BrowsePage } from "@/components/public/browse-page";

export default function HomePage() {
  return (
    <BrowsePage
      basePath="/home"
      title="Novel AI Reader"
      description="Browse and read translated web novels. Sign in to save novels, continue reading where you left off, and leave reviews."
    />
  );
}
