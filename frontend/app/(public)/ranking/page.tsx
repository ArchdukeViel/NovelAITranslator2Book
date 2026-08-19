import type { Metadata } from "next";

import RankingClient from "./ranking-client";

export const metadata: Metadata = {
  title: "Ranking",
  description: "Public rankings based on distinct novel-detail views.",
};

export default function RankingPage() {
  return <RankingClient />;
}
