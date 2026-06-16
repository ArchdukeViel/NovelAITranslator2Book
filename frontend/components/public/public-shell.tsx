"use client";

import { Suspense, useState } from "react";

import { PublicHeader } from "@/components/public/public-header";
import { PublicSidebar } from "@/components/public/public-sidebar";
import { PublicFooter } from "@/components/public/public-footer";

export function PublicShell({ children }: { children: React.ReactNode }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Suspense fallback={null}>
        <PublicSidebar
          isOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />
      </Suspense>
      <div className="flex flex-1 flex-col">
        <Suspense fallback={null}>
          <PublicHeader onMenuClick={() => setMobileMenuOpen(true)} />
        </Suspense>
        <main className="flex-1">{children}</main>
        <PublicFooter />
      </div>
    </div>
  );
}
