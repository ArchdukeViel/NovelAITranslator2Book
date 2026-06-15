import Link from "next/link";

export function PublicFooter() {
  return (
    <footer className="border-t border-border bg-background">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:justify-between">
        <p>&copy; {new Date().getFullYear()} Novel AI</p>
        <nav className="flex gap-4">
          <Link href="/" className="hover:text-foreground transition-colors">
            Browse
          </Link>
          <Link href="/account/history" className="hover:text-foreground transition-colors">
            History
          </Link>
          <Link href="/account/requests" className="hover:text-foreground transition-colors">
            Requests
          </Link>
        </nav>
      </div>
    </footer>
  );
}
