"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface NovelRailProps {
  title: string;
  ariaLabel: string;
  seeAllHref?: string;
  children: React.ReactNode;
}

const CARD_GAP = 16;
export function NovelRail({
  title,
  ariaLabel,
  seeAllHref,
  children,
}: NovelRailProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const scrollBehaviorRef = useRef<ScrollBehavior>("smooth");

  useEffect(() => {
    if (typeof matchMedia === "undefined") return;
    const mql = matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      scrollBehaviorRef.current = mql.matches ? "auto" : "smooth";
    };
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);

  const checkScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 4);
  }, []);

  useEffect(() => {
    checkScroll();
    const el = listRef.current;
    if (!el) return;
    el.addEventListener("scroll", checkScroll, { passive: true });
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(checkScroll);
    observer?.observe(el);
    return () => {
      el.removeEventListener("scroll", checkScroll);
      observer?.disconnect();
    };
  }, [checkScroll]);

  const scroll = useCallback((dir: "prev" | "next") => {
    const el = listRef.current;
    if (!el) return;
    const card = el.querySelector<HTMLElement>(":scope > *");
    if (!card) return;
    const cardWidth = card.offsetWidth + CARD_GAP;
    const amount = dir === "prev" ? -cardWidth : cardWidth;
    el.scrollBy({ left: amount, behavior: scrollBehaviorRef.current });
  }, []);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        scroll("prev");
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        scroll("next");
      }
    },
    [scroll],
  );

  return (
    <section role="region" aria-label={ariaLabel} className="relative">
      <div className="mb-3 flex items-center justify-between pr-12">
        <h2 className="font-literary text-xl font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        {seeAllHref && (
          <Link
            href={seeAllHref}
            className="inline-flex min-h-[44px] items-center rounded-sm bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
          >
            See all
          </Link>
        )}
      </div>
      <div className="relative group">
        {canScrollLeft && (
          <button
            type="button"
            onClick={() => scroll("prev")}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-border/40 bg-background/90 shadow-md opacity-90 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 focus:opacity-100 transition-all duration-200 ease-out hover:scale-105 active:scale-95 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary motion-reduce:hover:scale-100 motion-reduce:transition-none"
            aria-label="Previous items"
          >
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </button>
        )}
        <div
          ref={listRef}
          role="list"
          tabIndex={0}
          onKeyDown={onKeyDown}
          className="flex gap-4 overflow-x-auto overscroll-x-contain scrollbar-hide snap-x snap-mandatory scroll-smooth py-2 -my-2 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 rounded-lg motion-reduce:scroll-auto"
        >
          {children}
        </div>
        {canScrollRight && (
          <button
            type="button"
            onClick={() => scroll("next")}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-border/40 bg-background/90 shadow-md opacity-90 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 focus:opacity-100 transition-all duration-200 ease-out hover:scale-105 active:scale-95 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary motion-reduce:hover:scale-100 motion-reduce:transition-none"
            aria-label="Next items"
          >
            <ChevronRight className="h-5 w-5" aria-hidden="true" />
          </button>
        )}
      </div>
    </section>
  );
}
