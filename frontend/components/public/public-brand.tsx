import Link from "next/link";
import { BookOpen } from "lucide-react";

import { cn } from "@/lib/utils";

interface PublicBrandProps {
  className?: string;
  markClassName?: string;
  showPoweredBy?: boolean;
}

export function PublicBrand({
  className,
  markClassName,
  showPoweredBy = false,
}: PublicBrandProps) {
  return (
    <Link
      href="/home"
      className={cn("inline-flex items-center gap-2 text-foreground", className)}
      aria-label="Dokushodo home"
    >
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded bg-primary text-primary-foreground",
          markClassName
        )}
        aria-hidden="true"
      >
        <BookOpen className="h-5 w-5" />
      </span>
      <span className="flex min-w-0 flex-col leading-none">
        <span className="font-literary text-base font-semibold tracking-normal">
          読書道
        </span>
        <span className="mt-1 text-xs font-medium text-muted-foreground">
          Dokushodo
        </span>
        {showPoweredBy && (
          <span className="mt-1 text-[0.68rem] text-muted-foreground">
            Dokushodo is powered by Novel AI.
          </span>
        )}
      </span>
    </Link>
  );
}
