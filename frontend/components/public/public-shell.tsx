"use client";

import { Suspense, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { PublicHeader } from "@/components/public/public-header";
import { PublicFooter } from "@/components/public/public-footer";
import { MobileTabBar } from "@/components/public/mobile-tab-bar";
import { cn } from "@/lib/utils";

export function PublicShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isChapterRoute, setIsChapterRoute] = useState(false);

  useEffect(() => {
    setIsChapterRoute(pathname.includes("/chapter/"));
  }, [pathname]);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Skip link — first focusable element for keyboard users */}
      <a
        href="#main-content"
        className="skip-link"
      >
        Skip to main content
      </a>

      {!isChapterRoute && (
        <>
          <Suspense fallback={null}>
            <PublicHeader />
          </Suspense>
          <Suspense fallback={null}>
            <MobileTabBar />
          </Suspense>
        </>
      )}

      <div id="main-content" className="flex-1" tabIndex={-1}>
        {children}
      </div>

      {!isChapterRoute && <PublicFooter />}
    </div>
  );
}
