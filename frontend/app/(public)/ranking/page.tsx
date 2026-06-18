import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, BarChart3, BookOpen, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/public/section-header";

export const metadata: Metadata = {
  title: "Ranking",
  description: "Dokushodo ranking page — ranking data is not yet available.",
};

const PLANNED_PERIODS = ["Daily", "Weekly", "Monthly", "All Time"] as const;

export default function RankingPage() {
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
          <Badge tone="neutral" className="font-metadata">
            Ranking is not live yet
          </Badge>
        </div>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          Dokushodo does not display ranking data until real aggregated
          metrics are available. This page stays quiet instead of showing
          numbers the app does not have.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-4" aria-label="Planned ranking periods">
        {PLANNED_PERIODS.map((period) => (
          <div
            key={period}
            className="rounded-lg bg-card/70 p-4 ring-1 ring-border"
          >
            <p className="font-literary text-lg font-medium">{period}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Waiting for real ranking data.
            </p>
          </div>
        ))}
      </section>

      <section className="mt-10 rounded-lg bg-card/75 p-5 shadow-sm ring-1 ring-border sm:p-6 lg:p-8">
        <SectionHeader
          eyebrow="Ranking List"
          title="No ranking data yet"
          description="The public catalog is available, but ranked popularity data is not shown here yet."
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
          <div className="flex flex-col items-center justify-center rounded-lg bg-secondary/60 px-4 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <BarChart3 className="h-7 w-7" />
            </span>
            <h2 className="mt-5 font-literary text-2xl font-medium">
              Rankings are not live
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              No views, likes, ratings, trend movement, or popularity scores are
              shown because those metrics are not currently available here.
            </p>
            <Link
              href="/browse-novels"
              className="mt-6 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <BookOpen className="h-4 w-4" />
              Browse novels
            </Link>
          </div>

          <aside className="space-y-4">
            <div className="rounded-lg bg-background/70 p-4 ring-1 ring-border">
              <div className="flex items-start gap-3">
                <Clock className="mt-0.5 h-4 w-4 text-accent" />
                <div>
                  <h3 className="text-sm font-medium">Not available yet</h3>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    Ranking requires real aggregated data that is not
                    shown on the public site yet.
                  </p>
                </div>
              </div>
            </div>
            <Link
              href="/home"
              className="inline-flex items-center gap-1 text-sm text-accent transition-colors hover:text-foreground"
            >
              Return home
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </aside>
        </div>
      </section>
    </main>
  );
}
