"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  LogIn,
  LogOut,
  Loader2,
  User,
  Settings,
  HeartHandshake,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";
import { PublicThemeSegmentedControl } from "@/components/public/public-theme-toggle";
import { cn } from "@/lib/utils";

interface CurrentUserIndicatorProps {
  /** Callback after a navigation action (used by mobile menu to close). */
  onNavigate?: () => void;
}

/**
 * User Profile Dropdown Menu for Public Header.
 * Replaces simple inline links with a dropdown container holding account items,
 * theme controls, and sign in/out.
 */
export function CurrentUserIndicator({
  onNavigate,
}: CurrentUserIndicatorProps) {
  const { isAuthenticated, user } = usePublicAuth();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click & Escape key
  useEffect(() => {
    if (!open) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleClose = () => {
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={
          isAuthenticated
            ? `User menu (${user?.email ?? "Signed in"})`
            : "User account and theme menu"
        }
        className={cn(
          "h-9 w-9 rounded-full border border-border/40 transition-colors",
          open && "bg-muted text-foreground",
        )}
      >
        <User className="h-4 w-4" aria-hidden="true" />
      </Button>

      {open && (
        <div
          role="menu"
          aria-label="User menu"
          className="absolute right-0 top-full z-50 mt-2 w-56 origin-top-right rounded-lg border border-border/80 bg-popover p-1.5 text-popover-foreground shadow-lg transition-all"
        >
          {isAuthenticated ? (
            <>
              <div className="flex flex-col gap-0.5">
                <Link
                  href="/account/settings"
                  onClick={handleClose}
                  role="menuitem"
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  <Settings className="h-4 w-4 text-muted-foreground" />
                  <span>Settings</span>
                </Link>
                <Link
                  href="/account/contributions"
                  onClick={handleClose}
                  role="menuitem"
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  <HeartHandshake className="h-4 w-4 text-muted-foreground" />
                  <span>Contributions</span>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    handleClose();
                    logout.mutate();
                  }}
                  disabled={logout.isPending}
                  role="menuitem"
                  aria-label="Sign out"
                  className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
                >
                  {logout.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <LogOut className="h-4 w-4" />
                  )}
                  <span>{logout.isPending ? "Signing out…" : "Sign out"}</span>
                </button>
              </div>

              <div className="my-1.5 border-t border-border/40" />

              <div className="px-1 py-0.5">
                <PublicThemeSegmentedControl />
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-0.5">
                <Link
                  href="/account/settings"
                  onClick={handleClose}
                  role="menuitem"
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  <Settings className="h-4 w-4 text-muted-foreground" />
                  <span>Settings</span>
                </Link>
                <Link
                  href="/account/contributions"
                  onClick={handleClose}
                  role="menuitem"
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  <HeartHandshake className="h-4 w-4 text-muted-foreground" />
                  <span>Contributions</span>
                </Link>
                <Link
                  href="/login?mode=signin"
                  onClick={handleClose}
                  role="menuitem"
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  <LogIn className="h-4 w-4 text-muted-foreground" />
                  <span>Sign in</span>
                </Link>
              </div>

              <div className="my-1.5 border-t border-border/40" />

              <div className="px-1 py-0.5">
                <PublicThemeSegmentedControl />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
