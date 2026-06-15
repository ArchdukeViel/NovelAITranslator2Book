"use client";

import { useRouter, useSearchParams } from "next/navigation";

const LANGUAGES = [
  { value: "", label: "All" },
  { value: "Japanese", label: "Japanese" },
  { value: "Korean", label: "Korean" },
  { value: "Chinese", label: "Chinese" },
  { value: "English", label: "English" },
] as const;

export function BrowseNav() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const current = searchParams.get("language") ?? "";

  function handleChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("language", value);
    } else {
      params.delete("language");
    }
    // Reset to page 1 when changing language filter
    params.delete("page");
    router.push(`/?${params.toString()}`);
  }

  return (
    <nav aria-label="Browse by language" className="flex items-center gap-1">
      {LANGUAGES.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => handleChange(value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
            current === value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
          aria-pressed={current === value}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
