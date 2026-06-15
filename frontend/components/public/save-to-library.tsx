"use client";

import Link from "next/link";
import { Bookmark, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import {
  useAddToLibrary,
  useLibraryItem,
  useRemoveFromLibrary,
  usePublicAuth,
} from "@/hooks/public";
import { ApiError } from "@/lib/api";

interface SaveToLibraryProps {
  slug: string;
}

export function SaveToLibrary({ slug }: SaveToLibraryProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const libraryItem = useLibraryItem(slug);
  const addToLibrary = useAddToLibrary(slug);
  const removeFromLibrary = useRemoveFromLibrary(slug);

  if (authPending) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking session
      </Button>
    );
  }

  if (!isAuthenticated) {
    return <LoginPrompt />;
  }

  const isMissing =
    libraryItem.isError &&
    libraryItem.error instanceof ApiError &&
    libraryItem.error.status === 404;
  const isSaved = !!libraryItem.data && !isMissing;
  const isBusy =
    libraryItem.isPending || addToLibrary.isPending || removeFromLibrary.isPending;
  const error =
    addToLibrary.error ||
    removeFromLibrary.error ||
    (!isMissing ? libraryItem.error : null);

  const onClick = () => {
    if (!slug || isBusy) {
      return;
    }
    if (isSaved) {
      removeFromLibrary.mutate();
    } else {
      addToLibrary.mutate();
    }
  };

  return (
    <div className="flex flex-col gap-1">
      {isSaved ? (
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!slug || isBusy}
            onClick={onClick}
            type="button"
          >
            {isBusy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Bookmark className="h-4 w-4 fill-current" />
            )}
            Saved
          </Button>
          <Link
            href="/account/library"
            className="text-xs text-muted-foreground underline hover:text-foreground transition-colors"
          >
            View Library
          </Link>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          disabled={!slug || isBusy}
          onClick={onClick}
          type="button"
        >
          {isBusy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Bookmark className="h-4 w-4" />
          )}
          Save to Library
        </Button>
      )}
      {error && (
        <p className="text-xs text-destructive">
          Could not update library. Try again later.
        </p>
      )}
    </div>
  );
}
