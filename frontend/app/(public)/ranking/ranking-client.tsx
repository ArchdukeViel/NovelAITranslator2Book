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

const PERIODS: {
  value: PublicRankingPeriod;
  label: string;
  description: string;
}[] = [
  {
    value: "daily",
    label: "Daily",
    description: "Active readers discovering stories in the last 24 hours.",
  },
  {
    value: "weekly",
    label: "Weekly",
    description: "Active readers discovering stories over the past 7 days.",
  },
  {
    value: "monthly",
    label: "Monthly",
    description: "Active readers discovering stories over the past 30 days.",
  },
];

export default function RankingClient() {
  const [period, setPeriod] = useState<PublicRankingPeriod>("weekly");
  const query = usePublicRankings(period, 50);
  const selected = PERIODS.find((item) => item.value === period) ?? PERIODS[1];

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-10 max-w-4xl">
        <p
          lang="ja"
          className="font-metadata text-xs uppercase tracking-[0.22em] text-accent"
        >
          物語の順位
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="font-literary text-4xl font-medium tracking-normal text-foreground md:text-5xl">
            Ranking
          </h1>
          <Badge
            tone={query.data?.available ? "green" : "neutral"}
            className="font-metadata"
          >
            {query.isPending
              ? "Loading"
              : query.data?.available
                ? "Active readers"
                : "Data unavailable"}
          </Badge>
        </div>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          Rankings reflect real reader interest across the catalog, measuring
          unique readers exploring each novel title over time.
        </p>
      </header>

      <section
        className="grid gap-4 md:grid-cols-3"
        aria-label="Ranking periods"
      >
        {PERIODS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            aria-pressed={period === item.value}
            className={cn(
              "min-h-[44px] rounded-lg bg-card/70 p-4 text-left ring-1 ring-border transition-all duration-200 ease-out hover:bg-muted/60 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transition-none cursor-pointer",
              period === item.value &&
                "bg-card shadow-card ring-2 ring-primary",
            )}
          >
            <p className="font-literary text-lg font-medium">{item.label}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {item.description}
            </p>
          </button>
        ))}
      </section>

      <section className="mt-10 rounded-lg bg-card/75 p-5 shadow-sm ring-1 ring-border sm:p-6 lg:p-8">
        <SectionHeader
          title={`${selected.label} Reader Rankings`}
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
            <h2 className="mt-5 font-literary text-2xl font-medium">
              No ranking data available
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              {query.data?.reason === "analytics_disabled"
                ? "Analytics are disabled on this deployment. Rankings will appear after the operator enables the approved analytics configuration."
                : "No reader activity recorded for this period yet."}
            </p>
            <Link
              href="/browse-novels"
              className="mt-6 inline-flex min-h-[44px] h-11 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <BookOpen className="h-4 w-4" /> Browse novels
            </Link>
          </div>
        ) : (
          <ol
            className="mt-8 space-y-3"
            aria-label={`${selected.label} ranking results`}
          >
            {query.data.items.map((item) => (
              <li key={item.novel.novel_id}>
                <Link
                  href={publicNovelHref(item.novel.slug)}
                  className="group flex min-h-[44px] items-center gap-4 rounded-lg border border-border/70 bg-background/60 p-3 transition-colors duration-150 hover:border-primary/50 hover:bg-muted/40 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transition-none"
                >
                  <span className="w-8 text-center font-literary text-2xl font-bold text-muted-foreground tabular-nums">
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
                    <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                      {item.unique_views.toLocaleString()} active readers
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
