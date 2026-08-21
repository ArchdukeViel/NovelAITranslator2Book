"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, BarChart3, BookOpen } from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/public/section-header";
import { usePublicRankings } from "@/hooks/public";
import type { PublicRankingPeriod } from "@/lib/public-types";
import { publicNovelHref } from "@/lib/public-routes";
import { cn } from "@/lib/utils";

const PERIODS: { value: PublicRankingPeriod; label: string; description: string }[] = [
  { value: "daily", label: "Daily", description: "Distinct novel-detail viewers in the last 24 hours." },
  { value: "weekly", label: "Weekly", description: "Distinct novel-detail viewers in the last 7 days." },
  { value: "monthly", label: "Monthly", description: "Distinct novel-detail viewers in the last 30 days." },
];

export default function RankingClient() {
  const [period, setPeriod] = useState<PublicRankingPeriod>("weekly");
  const query = usePublicRankings(period, 50);
  const selected = PERIODS.find((item) => item.value === period) ?? PERIODS[1];

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-10 max-w-4xl">
        <p className="font-metadata text-xs uppercase tracking-[0.22em] text-accent">
          物語の順位
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="font-literary text-4xl font-medium tracking-normal text-foreground md:text-5xl">
            Ranking
          </h1>
          <Badge tone={query.data?.available ? "green" : "neutral"} className="font-metadata">
            {query.isPending ? "Loading" : query.data?.available ? "Unique views" : "Data unavailable"}
          </Badge>
        </div>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          Rankings use distinct authenticated users and privacy-safe anonymous
          viewer tokens for novel-detail views. Chapter navigation does not
          increase this score.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3" aria-label="Ranking periods">
        {PERIODS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            className={cn(
              "rounded-lg bg-card/70 p-4 text-left ring-1 ring-border transition-colors hover:bg-muted/60",
              period === item.value && "ring-2 ring-primary",
            )}
          >
            <p className="font-literary text-lg font-medium">{item.label}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.description}</p>
          </button>
        ))}
      </section>

      <section className="mt-10 rounded-lg bg-card/75 p-5 shadow-sm ring-1 ring-border sm:p-6 lg:p-8">
        <SectionHeader
          eyebrow="Ranking List"
          title={`${selected.label} unique novel views`}
          description={selected.description}
        />

        {query.isPending ? (
          <div className="mt-8 rounded-lg bg-secondary/60 px-4 py-14 text-center text-sm text-muted-foreground">
            Loading ranking data…
          </div>
        ) : !query.data?.available ? (
          <div className="mt-8 flex flex-col items-center justify-center rounded-lg bg-secondary/60 px-4 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <BarChart3 className="h-7 w-7" />
            </span>
            <h2 className="mt-5 font-literary text-2xl font-medium">No ranking data available</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              {query.data?.reason === "analytics_disabled"
                ? "Analytics are disabled on this deployment. Rankings will appear after the operator enables the approved analytics configuration."
                : "No distinct novel-detail viewers have been recorded for this period yet."}
            </p>
            <Link
              href="/browse-novels"
              className="mt-6 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <BookOpen className="h-4 w-4" /> Browse novels
            </Link>
          </div>
        ) : (
          <ol className="mt-8 space-y-3" aria-label={`${selected.label} ranking results`}>
            {query.data.items.map((item) => (
              <li key={item.novel.novel_id}>
                <Link
                  href={publicNovelHref(item.novel.slug)}
                  className="group flex items-center gap-4 rounded-lg border border-border/70 bg-background/60 p-3 transition-colors hover:border-primary/50 hover:bg-muted/40"
                >
                  <span className="w-8 text-center font-literary text-2xl font-bold text-muted-foreground">
                    {item.rank}
                  </span>
                  <div className="w-14 shrink-0 overflow-hidden rounded">
                    <FallbackCover
                      title={item.novel.title}
                      sourceTitle={item.novel.source_title}
                      language={item.novel.language}
                      status={item.novel.publication_status}
                      genres={item.novel.genres}
                      className="rounded"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate font-literary text-lg font-medium transition-colors group-hover:text-primary">
                      {item.novel.title}
                    </h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {item.unique_views.toLocaleString()} distinct novel-detail viewers
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}
