export function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium"
  }).format(date);
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size >= 10 || unitIndex === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unitIndex]}`;
}

export function formatDisplayToken(value?: string | null): string {
  if (!value?.trim()) {
    return "-";
  }
  const token = value.trim();
  if (token.length <= 10) {
    return token;
  }
  return `${token.slice(0, 6)}...${token.slice(-4)}`;
}
