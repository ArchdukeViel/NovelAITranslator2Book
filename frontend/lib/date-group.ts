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
  if (diffDays <= 60) return "Last month";

  // Older: "Mon YYYY"
  return date.toLocaleDateString(undefined, {
    month: "short",
    year: "numeric",
  });
}
