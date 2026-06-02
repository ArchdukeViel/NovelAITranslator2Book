"use client";

import {
  Activity,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  FileEdit,
  Gauge,
  Languages,
  ListPlus,
  ListChecks,
  Moon,
  Radar,
  Search,
  Settings,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/lib/store";

const items = [
  { href: "/admin/dashboard", label: "Home", icon: Gauge },
  { href: "/admin/crawler", label: "Crawler", icon: Search },
  { href: "/admin/source-health", label: "Sources", icon: Radar },
  { href: "/admin/translation", label: "Translation", icon: Languages },
  { href: "/admin/jobs", label: "Jobs", icon: ListChecks },
  { href: "/admin/requests", label: "Requests", icon: ListPlus },
  { href: "/admin/editor", label: "Editor", icon: FileEdit },
  { href: "/admin/settings", label: "Settings", icon: Settings }
];

function currentSection(pathname: string) {
  const match = items
    .slice()
    .reverse()
    .find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  return match?.label ?? "Dashboard";
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { apiToken, apiTokenLabel, darkMode, sidebarCollapsed, toggleDarkMode, toggleSidebar } = useUiStore();
  const apiTokenStatus = apiTokenLabel?.trim() || (apiToken.trim() ? "Gemini AI" : "None");

  React.useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  return (
    <div className="min-h-screen bg-background">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-20 flex flex-col border-r bg-card transition-[width]",
          sidebarCollapsed ? "w-16" : "w-64"
        )}
      >
        <div className="flex h-14 items-center justify-between border-b px-3">
          <Link href="/admin/dashboard" className="flex min-w-0 items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            {!sidebarCollapsed && <span className="truncate text-sm font-semibold">Novel AI Admin</span>}
          </Link>
          <Button variant="ghost" size="icon" onClick={toggleSidebar} aria-label="Toggle sidebar">
            {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
        </div>

        <nav className="flex-1 space-y-1 px-2 py-3">
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex h-10 items-center gap-3 rounded-md px-3 text-sm transition-colors hover:bg-muted",
                  active && "bg-primary text-primary-foreground hover:bg-primary"
                )}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-3">
          <Link className="flex h-9 items-center gap-3 rounded-md px-3 text-sm hover:bg-muted" href="/">
            <BookOpen className="h-4 w-4" />
            {!sidebarCollapsed && <span>Public reader</span>}
          </Link>
        </div>
      </aside>

      <div className={cn("transition-[padding]", sidebarCollapsed ? "pl-16" : "pl-64")}>
        <header className="sticky top-0 z-10 flex min-h-14 items-center justify-between gap-3 border-b bg-background/95 px-5 backdrop-blur">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Activity className="h-4 w-4 text-primary" />
            <span>{currentSection(pathname)}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={toggleDarkMode}
              aria-label={darkMode ? "Dark mode" : "Light mode"}
              title={darkMode ? "Dark mode" : "Light mode"}
            >
              {darkMode ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </Button>
            <div className="flex min-w-fit items-center rounded-md border bg-card px-3 py-1.5 text-sm">
              <span className="text-muted-foreground">API Token:</span>
              <span className="ml-2 font-medium">{apiTokenStatus}</span>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-5 py-5">{children}</main>
      </div>
    </div>
  );
}
