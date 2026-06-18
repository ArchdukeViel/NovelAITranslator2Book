"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { LoginView } from "@/components/public/login-view";

type LoginMode = "signin" | "signup";

function modeFromQuery(value: string | null): LoginMode {
  return value === "signup" ? "signup" : "signin";
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const mode = modeFromQuery(searchParams.get("mode"));

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md items-center justify-center px-4 py-8">
      <LoginView
        initialMode={mode}
        onClose={() => router.push("/home")}
        onSuccess={() => router.push("/home")}
        onModeChange={(nextMode) => router.replace(`/login?mode=${nextMode}`, { scroll: false })}
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
