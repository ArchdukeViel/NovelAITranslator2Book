"use client";

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
      <Button
        variant={isSaved ? "secondary" : "outline"}
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
        {isSaved ? "Remove from Library" : "Save to Library"}
      </Button>
      {error && (
        <p className="text-xs text-destructive">Library update failed.</p>
      )}
    </div>
  );
}
