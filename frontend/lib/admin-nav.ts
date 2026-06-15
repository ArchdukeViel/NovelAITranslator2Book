import * as React from "react";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

/**
 * Select the active nav item using most-specific (longest prefix) matching.
 * Returns at most one active item.
 */
export function selectActiveNav(pathname: string, items: NavItem[]): NavItem | undefined {
  let bestMatch: NavItem | undefined;
  let bestMatchLength = -1;

  for (const item of items) {
    if (pathname === item.href || pathname.startsWith(`${item.href}/`)) {
      const matchLength = item.href.length;
      if (matchLength > bestMatchLength) {
        bestMatchLength = matchLength;
        bestMatch = item;
      }
    }
  }

  return bestMatch;
}
