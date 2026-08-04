import type { Metadata } from "next";
import Link from "next/link";
import { Wrench, ShieldCheck, Clock, BookOpen } from "lucide-react";

export const metadata: Metadata = {
  title: "Scheduled Maintenance - Dokushodo",
  description: "Dokushodo system status and maintenance notice.",
  robots: { index: false, follow: false },
};

export default function MaintenancePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-16">
      <div className="rounded-xl bg-card p-8 shadow-card transition-all duration-300 dark:ring-1 dark:ring-white/5 sm:p-12">
        <div className="flex flex-col items-center text-center">
          <div className="relative flex h-24 w-24 items-center justify-center rounded-2xl bg-muted/60 shadow-card">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent rounded-2xl" />
            <Wrench className="h-10 w-10 text-primary" />
          </div>

          <span className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 font-metadata text-xs font-semibold uppercase tracking-wider text-primary">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            System Upgrade In Progress
          </span>

          <h1 className="mt-4 font-literary text-3xl font-semibold tracking-tight sm:text-4xl text-foreground">
            Improving Your Reading Experience
          </h1>

          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground font-sans">
            We are performing scheduled maintenance to upgrade database performance and reader infrastructure.
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg bg-muted/40 p-5 shadow-card dark:ring-1 dark:ring-white/5">
            <div className="flex items-center gap-3 font-literary text-base font-semibold text-foreground">
              <ShieldCheck className="h-5 w-5 text-primary" />
              <span>Data Integrity Safe</span>
            </div>
            <p className="mt-2 text-xs font-sans leading-normal text-muted-foreground">
              Your bookmarks, reading progress, and account history are completely secure during this window.
            </p>
          </div>

          <div className="rounded-lg bg-muted/40 p-5 shadow-card dark:ring-1 dark:ring-white/5">
            <div className="flex items-center gap-3 font-literary text-base font-semibold text-foreground">
              <Clock className="h-5 w-5 text-primary" />
              <span>Estimated Duration</span>
            </div>
            <p className="mt-2 text-xs font-sans leading-normal text-muted-foreground">
              Services are expected to resume shortly. Thank you for your patience while we complete this update.
            </p>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3 border-t border-border/40 pt-8">
          <Link
            href="/home"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground shadow-sm transition-all duration-200 hover:bg-primary/90 hover:shadow-raised"
          >
            Check reader status
          </Link>
          <Link
            href="/browse-novels"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-card px-6 text-sm font-medium text-foreground shadow-card transition-all duration-200 hover:bg-muted hover:shadow-raised dark:ring-1 dark:ring-white/5"
          >
            <BookOpen className="h-4 w-4 text-primary" />
            Browse catalog
          </Link>
        </div>
      </div>
    </main>
  );
}
