"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { LoginView } from "@/components/public/login-view";

export default function LoginPage() {
  const router = useRouter();

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md items-center justify-center px-4 py-8">
      <LoginView onClose={() => router.push("/home")} />
      <Link className="sr-only" href="/home">
        Return home
      </Link>
    </main>
  );
}
