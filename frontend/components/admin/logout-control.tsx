"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { adminAuth } from "@/lib/api";

/**
 * LogoutControl — ends the Owner_Session by calling POST /api/auth/logout.
 * Requirements: 4.6
 */
export function LogoutControl() {
  const router = useRouter();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const logoutMutation = useMutation({
    mutationFn: () => adminAuth.logout(),
    onSuccess: () => {
      const reauth = (window as Window & { __adminReauth?: () => void }).__adminReauth;
      if (reauth) {
        reauth();
      } else {
        router.refresh();
      }
    },
    onError: () => {
      setErrorMessage("Unable to sign out. Please refresh and try again.");
    },
    onMutate: () => {
      setErrorMessage(null);
    }
  });

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => logoutMutation.mutate()}
        disabled={logoutMutation.isPending}
        aria-label="Sign out"
      >
        <LogOut className="h-4 w-4" />
        <span className="sr-only sm:not-sr-only">Sign Out</span>
      </Button>
      {errorMessage && (
        <span className="text-xs text-destructive" role="alert">
          {errorMessage}
        </span>
      )}
    </div>
  );
}
