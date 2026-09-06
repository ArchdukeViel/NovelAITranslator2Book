"use client";

import Link from "next/link";

export function PublicFooter() {
  return (
    <footer className="w-full border-t border-primary/15 bg-muted/10 py-12">
      <div className="mx-auto flex max-w-2xl flex-col items-center justify-center gap-6 px-4 text-center">
        <Link
          href="/home"
          className="flex items-center justify-center text-foreground font-literary text-2xl font-bold tracking-tight text-primary"
          aria-label="Dokushodo home"
        >
          Dokushodo
        </Link>

        <nav
          className="flex flex-col items-center gap-2.5"
          aria-label="Footer navigation"
        >
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2.5 font-metadata text-xs text-muted-foreground">
            <Link href="/about" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              About
            </Link>
            <Link href="/support" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              Support &amp; Contact
            </Link>
            <Link href="/faq" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              FAQ
            </Link>
            <Link href="/news" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              News
            </Link>
          </div>
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2.5 font-metadata text-xs text-muted-foreground">
            <Link href="/dmca" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              DMCA
            </Link>
            <Link href="/cookie-policy" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              Cookie Policy
            </Link>
            <Link href="/privacy" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              Privacy Policy
            </Link>
            <Link href="/terms" className="inline-flex min-h-[44px] items-center px-2 transition-colors hover:text-foreground hover:underline hover:decoration-primary">
              Terms of Use
            </Link>
          </div>
        </nav>
        <span className="font-metadata text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} Dokushodo. The Way of Reading.
        </span>
      </div>
    </footer>
  );
}
