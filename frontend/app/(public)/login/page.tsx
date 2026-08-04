"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { LoginView } from "@/components/public/login-view";

type LoginMode = "signin" | "signup";

function modeFromQuery(value: string | null): LoginMode {
  return value === "signup" ? "signup" : "signin";
}

/** Return the safe in-app destination a guest was headed to before sign-in. Supports next or callbackUrl. */
function nextFromQuery(nextVal: string | null, callbackVal: string | null): string {
  const value = callbackVal || nextVal;
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/home";
  }
  return value;
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const mode = modeFromQuery(searchParams.get("mode"));
  const next = nextFromQuery(searchParams.get("next"), searchParams.get("callbackUrl"));

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md items-center justify-center px-4 py-8">
      <LoginView
        initialMode={mode}
        onClose={() => router.push(next)}
        onSuccess={() => router.push(next)}
        onModeChange={(nextMode) => router.replace(`/login?mode=${nextMode}${next !== "/home" ? `&next=${encodeURIComponent(next)}` : ""}`, { scroll: false })}
      />
      <Link className="sr-only" href="/home">
        Return home
      </Link>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-[60vh] max-w-md items-center justify-center px-4 py-8" />
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
