import { StaticPage } from "@/components/public/static-page";

export default function RankingPage() {
  return (
    <StaticPage
      title="Ranking"
      description="Public ranking and trending views are planned, but the metrics and anti-abuse rules are not connected yet."
      sections={[
        {
          title: "Pending metrics",
          body: "This page will use real public reading and catalog signals after the ranking contract is designed.",
        },
      ]}
    />
  );
}
