"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function SearchEntry() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/?q=${encodeURIComponent(trimmed)}`);
    } else {
      router.push("/");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <Input
        type="search"
        placeholder="Search novels…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-40 sm:w-56"
        aria-label="Search novels"
      />
      <Button type="submit" variant="ghost" size="icon" aria-label="Submit search">
        <Search className="h-4 w-4" />
      </Button>
    </form>
  );
}
