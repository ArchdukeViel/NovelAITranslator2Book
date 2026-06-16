"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { BookOpen, FileText, Heart, Home, Library, Trophy } from "lucide-react";

import { usePublicAuth } from "@/hooks/public/use-auth";
import { cn } from "@/lib/utils";

const mainNavItems = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse Novels", icon: BookOpen },
  { href: "/ranking", label: "Ranking", icon: Trophy },
  { href: "/request-novel", label: "Request Novel", icon: FileText },
  { href: "/contribute", label: "Contribute", icon: Heart },
  { href: "/account/library", label: "Library", icon: Library },
];

const accountNavItems = [
  { href: "/account/requests", label: "Requests" },
  { href: "/account/contributions", label: "Contributions" },
  { href: "/account/settings", label: "Settings" },
];

export function PublicSidebar({
  isOpen,
  onClose,
}: {
  isOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const { isAuthenticated } = usePublicAuth();

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r border-border bg-sidebar transition-transform duration-200 ease-in-out md:static md:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col p-4">
          <nav className="flex-1 space-y-1">
            {mainNavItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/home" && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-accent"
                      : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {isAuthenticated && (
            <div className="mt-4 border-t border-border pt-4">
              <p className="px-3 text-xs font-medium uppercase text-muted-foreground">
                Account
              </p>
              <div className="mt-2 space-y-1">
                {accountNavItems.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        isActive
                          ? "bg-sidebar-accent text-accent"
                          : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
                      )}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
