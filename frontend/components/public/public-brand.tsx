import Link from "next/link";

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
          "flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-sm bg-primary",
          markClassName
        )}
        aria-hidden="true"
      >
        <img
          src="/assets/dokushodo/brand/dokushodo-mark.png"
          alt=""
          className="h-full w-full object-cover"
        />
      </span>
      <span className="flex min-w-0 flex-col leading-none">
        <span className="font-literary text-base font-semibold tracking-normal text-foreground">
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
