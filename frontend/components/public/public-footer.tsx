"use client";

import Link from "next/link";
import { usePublicAuth } from "@/hooks/public/use-auth";

export function PublicFooter() {
  const { isAuthenticated } = usePublicAuth();

  return (
    <footer className="border-t border-border bg-background">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:justify-between">
        <p>&copy; {new Date().getFullYear()} Novel AI</p>
        <nav className="flex flex-wrap justify-center gap-4">
          <Link href="/browse-novels" className="hover:text-foreground transition-colors">
            Browse
          </Link>
          <Link href="/ranking" className="hover:text-foreground transition-colors">
            Ranking
          </Link>
          <Link href="/request-novel" className="hover:text-foreground transition-colors">
            Request
          </Link>
          <Link href="/contribute" className="hover:text-foreground transition-colors">
            Contribute
          </Link>
          {isAuthenticated && (
            <>
              <Link href="/account/library" className="hover:text-foreground transition-colors">
                Library
              </Link>
              <Link href="/account/requests" className="hover:text-foreground transition-colors">
                Requests
              </Link>
              <Link href="/account/contributions" className="hover:text-foreground transition-colors">
                Contributions
              </Link>
            </>
          )}
          <Link href="/about" className="hover:text-foreground transition-colors">
            About
          </Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-foreground transition-colors">
            Terms
          </Link>
          <Link href="/dmca" className="hover:text-foreground transition-colors">
            DMCA
          </Link>
          <Link href="/contact" className="hover:text-foreground transition-colors">
            Contact
          </Link>
          <Link href="/cookie-policy" className="hover:text-foreground transition-colors">
            Cookies
          </Link>
        </nav>
      </div>
    </footer>
  );
}
