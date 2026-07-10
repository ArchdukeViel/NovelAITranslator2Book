"use client";

import { useMemo, useState } from "react";
import type { PublicGlossaryAnnotation } from "@/lib/public-types";

interface GlossaryAnnotationHighlighterProps {
  text: string;
  annotations: PublicGlossaryAnnotation[];
  onAnnotationClick?: (annotation: PublicGlossaryAnnotation) => void;
}

export function GlossaryAnnotationHighlighter({
  text,
  annotations,
  onAnnotationClick,
}: GlossaryAnnotationHighlighterProps) {
  const segments = useMemo(() => {
    if (!annotations.length) return [{ text, isAnnotation: false }];

    // Collect all matches with their annotation data
    const matches: Array<{
      start: number;
      end: number;
      annotation: PublicGlossaryAnnotation;
      surface: string;
    }> = [];

    for (const annotation of annotations) {
      for (const match of annotation.matches) {
        matches.push({
          start: match.start,
          end: match.end,
          annotation,
          surface: match.surface,
        });
      }
    }

    // Sort by start position
    matches.sort((a, b) => a.start - b.start);

    // Merge overlapping matches (keep the first one)
    const mergedMatches: typeof matches = [];
    for (const match of matches) {
      const last = mergedMatches[mergedMatches.length - 1];
      if (last && match.start < last.end) {
        // Overlapping - skip this one
        continue;
      }
      mergedMatches.push(match);
    }

    // Build segments
    const segments: Array<{ text: string; isAnnotation: boolean; annotation?: PublicGlossaryAnnotation }> = [];
    let lastEnd = 0;

    for (const match of mergedMatches) {
      if (match.start > lastEnd) {
        segments.push({ text: text.slice(lastEnd, match.start), isAnnotation: false });
      }
      segments.push({
        text: match.surface,
        isAnnotation: true,
        annotation: match.annotation,
      });
      lastEnd = match.end;
    }

    if (lastEnd < text.length) {
      segments.push({ text: text.slice(lastEnd), isAnnotation: false });
    }

    return segments;
  }, [text, annotations]);

  return (
    <span className="whitespace-pre-wrap break-words">
      {segments.map((segment, index) =>
        segment.isAnnotation && segment.annotation ? (
          <span
            key={index}
            className="relative inline"
            onClick={() => onAnnotationClick?.(segment.annotation!)}
          >
            <span className="glossary-annotation-highlight relative">
              {segment.text}
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary/30" />
            </span>
            <AnnotationTooltip annotation={segment.annotation!} />
          </span>
        ) : (
          <span key={index}>{segment.text}</span>
        )
      )}
    </span>
  );
}

function AnnotationTooltip({ annotation }: { annotation: PublicGlossaryAnnotation }) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
      tabIndex={0}
    >
      {isVisible && (
        <div
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 rounded-md bg-popover p-3 text-sm shadow-lg border border-border animate-in fade-in-0 zoom-in-95"
          role="tooltip"
        >
          <div className="font-medium text-foreground">{annotation.display_term}</div>
          {annotation.canonical_term !== annotation.display_term && (
            <div className="text-xs text-muted-foreground mt-0.5">
              Original: {annotation.canonical_term}
            </div>
          )}
          {annotation.reading && (
            <div className="text-xs text-muted-foreground mt-0.5">
              Reading: {annotation.reading}
            </div>
          )}
          {annotation.term_type && (
            <div className="text-xs text-muted-foreground mt-0.5 capitalize">
              Type: {annotation.term_type}
            </div>
          )}
          {annotation.short_definition && (
            <div className="mt-2 text-sm text-foreground">{annotation.short_definition}</div>
          )}
          {annotation.aliases && annotation.aliases.length > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              Also known as: {annotation.aliases.join(", ")}
            </div>
          )}
        </div>
      )}
    </span>
  );
}