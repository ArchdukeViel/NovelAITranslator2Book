import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, BookOpen, RefreshCw } from "lucide-react";

export const metadata: Metadata = {
  title: "System Error",
  description: "Something went wrong on Dokushodo.",
  robots: { index: false, follow: false },
};

export default function ErrorRoutePage() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-3xl flex-col items-center justify-center px-4 py-16 text-center">
      <div className="relative mb-6 flex h-24 w-24 items-center justify-center rounded-2xl bg-card shadow-card dark:ring-1 dark:ring-white/5">
        <div className="absolute inset-0 bg-gradient-to-br from-destructive/10 via-transparent to-transparent rounded-2xl" />
        <AlertTriangle className="h-10 w-10 text-destructive" />
      </div>

      <span className="font-metadata text-xs font-semibold uppercase tracking-widest text-destructive">
        System Interruption
      </span>

      <h1 className="mt-2 font-literary text-3xl font-semibold tracking-tight sm:text-4xl text-foreground">
        Something Went Wrong
      </h1>

      <p className="mt-3 max-w-md text-base leading-relaxed text-muted-foreground font-sans">
        An unexpected system condition occurred while rendering this view. Your reading data remains safe.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground shadow-sm transition-all duration-200 hover:bg-primary/90 hover:shadow-raised"
          href="/home"
        >
          <RefreshCw className="h-4 w-4" />
          Reload home
        </Link>
        <Link
          className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-card px-6 text-sm font-medium text-foreground shadow-card transition-all duration-200 hover:bg-muted hover:shadow-raised dark:ring-1 dark:ring-white/5"
          href="/browse-novels"
        >
          <BookOpen className="h-4 w-4 text-primary" />
          Browse catalog
        </Link>
      </div>
    </main>
  );
}
