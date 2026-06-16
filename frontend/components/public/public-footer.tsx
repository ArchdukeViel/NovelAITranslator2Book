"use client";

import Link from "next/link";
import { PublicBrand } from "@/components/public/public-brand";

export function PublicFooter() {
  return (
    <footer className="border-t border-border/60 bg-background">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 text-sm text-muted-foreground sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:px-8">
        <div className="flex flex-col gap-3">
          <PublicBrand showPoweredBy markClassName="h-8 w-8" />
          <p>&copy; {new Date().getFullYear()} Dokushodo</p>
        </div>

        <nav className="grid gap-2" aria-label="Footer navigation">
          <p className="font-metadata text-xs uppercase tracking-wide text-foreground">
            Read
          </p>
          <Link href="/browse-novels" className="transition-colors hover:text-foreground">
            Browse Novels
          </Link>
          <Link href="/ranking" className="transition-colors hover:text-foreground">
            Ranking
          </Link>
          <Link href="/request-novel" className="transition-colors hover:text-foreground">
            Request Novel
          </Link>
          <Link href="/contribute" className="transition-colors hover:text-foreground">
            Contribute
          </Link>
        </nav>

        <nav className="grid gap-2" aria-label="Legal navigation">
          <p className="font-metadata text-xs uppercase tracking-wide text-foreground">
            Trust
          </p>
          <Link href="/about" className="transition-colors hover:text-foreground">
            About
          </Link>
          <Link href="/privacy" className="transition-colors hover:text-foreground">
            Privacy
          </Link>
          <Link href="/terms" className="transition-colors hover:text-foreground">
            Terms
          </Link>
          <Link href="/dmca" className="transition-colors hover:text-foreground">
            DMCA
          </Link>
          <Link href="/contact" className="transition-colors hover:text-foreground">
            Contact
          </Link>
          <Link href="/cookie-policy" className="transition-colors hover:text-foreground">
            Cookie Policy
          </Link>
        </nav>
      </div>
    </footer>
  );
}
