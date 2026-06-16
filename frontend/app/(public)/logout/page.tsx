"use client";

import Link from "next/link";
import { useEffect } from "react";

import { useLogout } from "@/hooks/public";

export default function LogoutPage() {
  const { mutate } = useLogout();

  useEffect(() => {
    mutate();
  }, [mutate]);

  return (
    <main className="mx-auto max-w-md px-4 py-16 text-center">
      <h1 className="text-3xl font-semibold tracking-normal">Signing out</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Your public reader session is being cleared.
      </p>
      <Link className="mt-6 inline-flex text-sm font-medium underline" href="/home">
        Return home
      </Link>
    </main>
  );
}
