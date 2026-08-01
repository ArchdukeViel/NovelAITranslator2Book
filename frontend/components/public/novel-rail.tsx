"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

interface NovelRailProps {
  title: string;
  ariaLabel: string;
  seeAllHref?: string;
  children: React.ReactNode;
}

const CARD_GAP = 16;
export function NovelRail({ title, ariaLabel, seeAllHref, children }: NovelRailProps) {
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
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(checkScroll);
    observer?.observe(el);
    return () => {
      el.removeEventListener("scroll", checkScroll);
      observer?.disconnect();
    };
  }, [checkScroll]);

  const scroll = useCallback(
    (dir: "prev" | "next") => {
      const el = listRef.current;
      if (!el) return;
      const card = el.querySelector<HTMLElement>(":scope > *");
      if (!card) return;
      const cardWidth = card.offsetWidth + CARD_GAP;
      const amount = dir === "prev" ? -cardWidth : cardWidth;
      el.scrollBy({ left: amount, behavior: scrollBehaviorRef.current });
    },
    []
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowLeft") { e.preventDefault(); scroll("prev"); }
      if (e.key === "ArrowRight") { e.preventDefault(); scroll("next"); }
    },
    [scroll]
  );

  return (
    <section role="region" aria-label={ariaLabel} className="relative">
      <div className="mb-3 flex items-center justify-between pr-12">
        <h2 className="text-xl font-bold tracking-tight">{title}</h2>
        {seeAllHref && (
          <Link
            href={seeAllHref}
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
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
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-background/80 shadow-md opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity"
            aria-label="Previous items"
          >
            ‹
          </button>
        )}
        <div
          ref={listRef}
          role="list"
          tabIndex={0}
          onKeyDown={onKeyDown}
          className="flex gap-4 overflow-x-auto scrollbar-hide snap-x snap-mandatory"
        >
          {children}
        </div>
        {canScrollRight && (
          <button
            type="button"
            onClick={() => scroll("next")}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-background/80 shadow-md opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity"
            aria-label="Next items"
          >
            ›
          </button>
        )}
      </div>
    </section>
  );
}
