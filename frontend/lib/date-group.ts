/**
 * Group a date string into a human-friendly relative label.
 *
 * Returns null for invalid/missing dates so callers can fall back to
 * showing nothing rather than inventing a time label.
 */

export function groupDateLabel(dateValue: string | null | undefined): string | null {
  if (!dateValue) return null;

  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return null;

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  const diffDays = Math.round(
    (todayStart.getTime() - dateStart.getTime()) / (1000 * 60 * 60 * 24)
  );

  if (diffDays < 0) return null;
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "1 week ago";
  if (diffDays <= 14) return "2 weeks ago";
  if (diffDays <= 21) return "3 weeks ago";

  // Older than 3 weeks — use day-based thresholds for predictable grouping
  if (diffDays <= 30) return "1 month ago";
  if (diffDays <= 60) return "2 months ago";
  if (diffDays <= 90) return "3 months ago";

  // "Mon YYYY" for very old dates
  return date.toLocaleDateString(undefined, {
    month: "short",
    year: "numeric",
  });
}

/**
 * Returns a formatted time label for today items.
 * Returns null for non-today, missing, or invalid dates.
 *
 * Example output: "14:30" for a 2:30 PM update today.
 */
export function todayTimeLabel(dateValue: string | null | undefined): string | null {
  if (!dateValue) return null;

  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return null;

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  const diffDays = Math.round(
    (todayStart.getTime() - dateStart.getTime()) / (1000 * 60 * 60 * 24)
  );

  // Only show time for today items
  if (diffDays !== 0) return null;

  // Format as locale time (short)
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}
