"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";

import { PublicHeader } from "@/components/public/public-header";
import { PublicFooter } from "@/components/public/public-footer";
import { MobileTabBar } from "@/components/public/mobile-tab-bar";
import { SearchOverlay } from "@/components/public/search-overlay";

export function PublicShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Quiet chrome while reading: header, tab bar, and footer are suppressed
  // on chapter reader routes (DESIGN.md — Reader, "both go quiet while
  // reading"). Derived inline so the first render matches the final render
  // (no flash of chrome on a chapter page).
  const isChapterRoute = pathname.includes("/chapter/");
  const isNovelDetailRoute = /^\/novels\/[^/]+\/?$/.test(pathname);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Skip link — first focusable element for keyboard users */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {!isChapterRoute && (
        <>
          <Suspense fallback={null}>
            <PublicHeader />
          </Suspense>
          {/* Header spacer since PublicHeader is fixed */}
          <div className="h-14 shrink-0" aria-hidden="true" />
          {!isNovelDetailRoute && (
            <Suspense fallback={null}>
              <MobileTabBar />
            </Suspense>
          )}
        </>
      )}

      <div id="main-content" className="flex-1" tabIndex={-1}>
        {children}
      </div>

      {!isChapterRoute && <PublicFooter />}

      {/* Shared search overlay — mounted outside the chrome-suppression block
          so the `/` shortcut and overlay work on reader pages too. */}
      <SearchOverlay />
    </div>
  );
}
