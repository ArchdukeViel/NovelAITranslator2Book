import Link from "next/link";

import { cn } from "@/lib/utils";

interface PublicBrandProps {
  className?: string;
  markClassName?: string;
  showPoweredBy?: boolean;
}

export function PublicBrand({ className, markClassName }: PublicBrandProps) {
  return (
    <Link
      href="/home"
      className={cn("flex items-center text-foreground font-literary text-xl font-bold tracking-tight", className)}
      aria-label="Dokushodo home"
    >
      <span className={cn("text-primary font-literary", markClassName)}>Dokushodo</span>
    </Link>
  );
}
