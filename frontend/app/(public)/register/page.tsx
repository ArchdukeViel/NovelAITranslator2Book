"use client";

import { useRouter } from "next/navigation";

import { LoginView } from "@/components/public/login-view";

export default function RegisterPage() {
  const router = useRouter();

  return (
    <main className="mx-auto max-w-md px-4 py-8">
      <header className="mb-4">
        <h1 className="text-3xl font-semibold tracking-normal">Register</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Public accounts are created through Google OAuth.
        </p>
      </header>
      <LoginView onClose={() => router.push("/home")} />
    </main>
  );
}
