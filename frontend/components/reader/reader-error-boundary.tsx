"use client";

import React, { Component, type ReactNode } from "react";
import Link from "next/link";
import { BookOpen, RefreshCw } from "lucide-react";

import { ErrorState } from "@/components/ui/page-state";
import { errorToProps } from "@/lib/api-error";
import { publicNovelHref } from "@/lib/public-routes";

export interface ReaderErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  novelSlug?: string;
  chapterId?: number | string;
  onReset?: () => void;
  onError?: (error: Error, info: React.ErrorInfo) => void;
}

interface ReaderErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Resilient Error Boundary for the novel chapter reader.
 * Catches runtime rendering, parser, or formatting errors in the reader view
 * and isolates them to prevent crashing the global app or public shell.
 */
export class ReaderErrorBoundary extends Component<
  ReaderErrorBoundaryProps,
  ReaderErrorBoundaryState
> {
  constructor(props: ReaderErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): ReaderErrorBoundaryState {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, info: React.ErrorInfo): void {
    this.props.onError?.(error, info);
    if (process.env.NODE_ENV === "development") {
      console.error("[ReaderErrorBoundary] Caught reader rendering error:", error, info);
    }
  }

  reset = (): void => {
    this.props.onReset?.();
    this.setState({ hasError: false, error: null });
  };

  override render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const { fallback, novelSlug } = this.props;
    const error = this.state.error ?? new Error("Reader rendering failed");

    if (typeof fallback === "function") {
      return fallback(error, this.reset);
    }
    if (fallback) {
      return fallback;
    }

    const { title, description } = errorToProps(error);

    return (
      <div className="mx-auto my-12 max-w-2xl px-4">
        <ErrorState
          title={title || "Unable to display this chapter"}
          description={
            description ||
            "An error occurred while rendering the reader interface. You can try refreshing or return to the novel directory."
          }
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={this.reset}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                <RefreshCw className="h-4 w-4" />
                Retry chapter
              </button>
              {novelSlug ? (
                <Link
                  href={publicNovelHref(novelSlug)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  <BookOpen className="h-4 w-4" />
                  Novel overview
                </Link>
              ) : null}
              <Link
                href="/browse-novels"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-muted px-5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                Browse catalog
              </Link>
            </div>
          }
        />
      </div>
    );
  }
}
