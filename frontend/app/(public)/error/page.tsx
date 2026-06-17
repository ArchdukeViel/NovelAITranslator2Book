import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen } from "lucide-react";

export const metadata: Metadata = {
  title: "Error",
  description: "Something went wrong on Dokushodo.",
  robots: { index: false, follow: false },
};

export default function ErrorRoutePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16 text-center">
      <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
      <h1 className="mt-6 text-3xl font-semibold tracking-normal font-literary">Something went wrong</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        An unexpected error occurred. Try refreshing the page or returning home.
      </p>
      <div className="mt-8 flex items-center justify-center gap-4">
        <Link
          className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          href="/home"
        >
          Return home
        </Link>
        <Link
          className="inline-flex h-10 items-center justify-center rounded-md border border-border bg-card px-5 text-sm font-medium transition-colors hover:bg-muted"
          href="/browse-novels"
        >
          Browse catalog
        </Link>
      </div>
    </main>
  );
}
