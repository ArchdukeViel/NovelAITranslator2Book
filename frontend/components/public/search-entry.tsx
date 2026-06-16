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
      router.push(`/browse-novels?q=${encodeURIComponent(trimmed)}`);
    } else {
      router.push("/browse-novels");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full items-center gap-2 md:max-w-md">
      <Input
        type="search"
        placeholder="Search novels…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="min-w-0 flex-1 bg-muted/70"
        aria-label="Search novels"
      />
      <Button type="submit" variant="ghost" size="icon" aria-label="Submit search">
        <Search className="h-4 w-4" />
      </Button>
    </form>
  );
}
