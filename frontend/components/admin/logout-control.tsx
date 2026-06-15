"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { adminAuth } from "@/lib/api";

/**
 * LogoutControl — ends the Owner_Session by calling POST /api/auth/logout.
 * Requirements: 4.6
 */
export function LogoutControl() {
  const router = useRouter();

  const logoutMutation = useMutation({
    mutationFn: () => adminAuth.logout(),
    onSuccess: () => {
      router.refresh();
    },
  });

  return (
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
  );
}