import type { Metadata } from "next";

import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "News",
  description: "Updates and announcements for Dokushodo.",
};

export default function NewsPage() {
  return (
    <StaticPage
      title="News"
      description="Dated changelog and announcements for Dokushodo."
      sections={[
        {
          title: "2026-08-02 — FAQ, news, and your reviews",
          body: "New FAQ and News pages are live and linked from the footer and the mobile Account hub. The Account sidebar now includes a Reviews page listing the reviews you have written, with links back to each novel and the ability to remove a review.",
        },
        {
          title: "2026-08-02 — Library board and account shell",
          body: "The account area gained a desktop sidebar and an overview page showing honest reading, history, and notification summaries. The library page now presents saved novels as a status board on desktop and a list on mobile, with search and sorting.",
        },
        {
          title: "2026-08-02 — Reader settings, progress, and resume",
          body: "The chapter reader gained font size, text width, and theme controls behind one settings panel, a fixed reading-progress bar, and account-backed progress that resumes exactly where you left off.",
        },
        {
          title: "2026-08-02 — Novel detail and chapter controls",
          body: "Novel detail pages now use a sticky action panel, Overview/Chapters/Reviews tabs, canonical taxonomy links, and chapter search with ordering, collapse, and first-unread navigation.",
        },
        {
          title: "2026-08-01 — Homepage rails and Spotlight",
          body: "The homepage now uses labeled, keyboard-scrollable rails for New Releases, Recently Updated, Continue Reading, and genres, with an honest eligibility-gated Spotlight and a working Surprise Me route.",
        },
        {
          title: "2026-08-01 — Browse layout and catalog routes",
          body: "Browse gained a desktop filter sidebar, mobile filter sheet, results count, sort, grid/list toggle, and canonical /tags, /genres, and /sources routes.",
        },
        {
          title: "2026-08-01 — Shared search overlay",
          body: "One search overlay now serves the desktop header, the mobile Search tab, and the / shortcut, with grouped results, keyboard navigation, cancellation, and recent searches.",
        },
        {
          title: "2026-07-31 — Navigation rework",
          body: "The hamburger drawer was replaced by inline desktop navigation and a mobile bottom tab bar, with a reader-quiet chapter experience.",
        },
        {
          title: "2026-07-31 — Accessibility pass",
          body: "Design tokens were verified against WCAG AA contrast (34 checks across light and dark) and primary buttons gained a two-layer focus treatment.",
        },
        {
          title: "2026-07-31 — Yokocho Lantern visual system",
          body: "The site moved to a dark-first warm night-market palette, a new font stack, refreshed brand mark, and semantic status colors.",
        },
      ]}
    />
  );
}
