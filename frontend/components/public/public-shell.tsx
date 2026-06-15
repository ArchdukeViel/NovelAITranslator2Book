"use client";

import { Suspense } from "react";

import { useAuthMe } from "@/hooks/public/use-auth";
import { PublicHeader } from "@/components/public/public-header";
import { PublicFooter } from "@/components/public/public-footer";

export function PublicShell({ children }: { children: React.ReactNode }) {
  // Mount the auth query once for the whole public subtree so it starts
  // fetching immediately and is shared by all descendants via React Query cache.
  useAuthMe();

  return (
    <div className="flex min-h-screen flex-col">
      <Suspense fallback={null}>
        <PublicHeader />
      </Suspense>
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
