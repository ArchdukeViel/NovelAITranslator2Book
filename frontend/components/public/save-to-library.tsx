"use client";

import { useState } from "react";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";

import { useLibraryItem, useAddToLibrary, useRemoveFromLibrary } from "@/hooks/public";
import { toReaderError } from "@/lib/public-format";

interface SaveToLibraryProps {
  slug: string;
}

/**
 * Save-to-library toggle for authenticated users.
 * The caller is responsible for wrapping this component in AuthGate.
 *
 * Requirements validated: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
 */
export function SaveToLibrary({ slug }: SaveToLibraryProps) {
  const library = useLibraryItem(slug, true);
  const addToLibrary = useAddToLibrary();
  const removeFromLibrary = useRemoveFromLibrary();

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const inLibrary = library.data?.inLibrary ?? false;

  function handleAdd() {
    setErrorMessage(null);
    addToLibrary.mutate(slug, {
      onError: (error) => {
        setErrorMessage(toReaderError(error));
      },
    });
  }

  function handleRemove() {
    setErrorMessage(null);
    removeFromLibrary.mutate(slug, {
      onError: (error) => {
        setErrorMessage(toReaderError(error));
      },
    });
  }

  // Loading state while initial library membership check is pending
  if (library.isPending) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Checking library…</span>
      </div>
    );
  }

  const isMutating = addToLibrary.isPending || removeFromLibrary.isPending;

  return (
    <div className="flex flex-col gap-1">
      {inLibrary ? (
        <button
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          disabled={isMutating}
          onClick={handleRemove}
          type="button"
        >
          <BookmarkCheck className="h-4 w-4 text-primary" />
          {isMutating ? "Removing…" : "Remove from Library"}
        </button>
      ) : (
        <button
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          disabled={isMutating}
          onClick={handleAdd}
          type="button"
        >
          <Bookmark className="h-4 w-4" />
          {isMutating ? "Adding…" : "Add to Library"}
        </button>
      )}
      {errorMessage && (
        <p className="text-xs text-destructive">{errorMessage}</p>
      )}
    </div>
  );
}
