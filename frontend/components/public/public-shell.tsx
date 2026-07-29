"use client";

import { Suspense, useState } from "react";

import { PublicHeader } from "@/components/public/public-header";
import { PublicSidebar } from "@/components/public/public-sidebar";
import { PublicFooter } from "@/components/public/public-footer";

export function PublicShell({ children }: { children: React.ReactNode }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Skip link — first focusable element for keyboard users */}
      <a
        href="#main-content"
        className="skip-link"
      >
        Skip to main content
      </a>

      <Suspense fallback={null}>
        <PublicSidebar
          isOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />
      </Suspense>
      <Suspense fallback={null}>
        <PublicHeader onMenuClick={() => setMobileMenuOpen(true)} />
      </Suspense>
      <div id="main-content" className="flex-1" tabIndex={-1}>
        {children}
      </div>
      <PublicFooter />
    </div>
  );
}
