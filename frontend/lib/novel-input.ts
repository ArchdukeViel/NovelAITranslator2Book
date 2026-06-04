export type NovelSourceKey =
  | "none"
  | "novel18_syosetu"
  | "syosetu_ncode"
  | "kakuyomu"
  | "generic";

const SOURCE_LABELS: Record<string, string> = {
  syosetu_ncode: "Syosetu",
  novel18_syosetu: "Novel18",
  kakuyomu: "Kakuyomu",
  generic: "Generic web"
};

export function cleanNovelInput(value: string): string {
  return value.trim();
}

export function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(cleanNovelInput(value));
}

export function parseNovelUrl(value: string): URL | null {
  if (!isHttpUrl(value)) {
    return null;
  }
  try {
    return new URL(cleanNovelInput(value));
  } catch {
    return null;
  }
}

export function detectSourceOrigin(value: string): NovelSourceKey {
  const input = cleanNovelInput(value);
  if (!input) {
    return "none";
  }

  const url = parseNovelUrl(input);
  if (url) {
    const host = url.hostname.toLowerCase();
    if (["novel18.syosetu.com", "noc.syosetu.com", "mnlt.syosetu.com", "mid.syosetu.com"].includes(host)) {
      return "novel18_syosetu";
    }
    if (host === "ncode.syosetu.com") {
      return "syosetu_ncode";
    }
    if (host === "kakuyomu.jp" && url.pathname.includes("/works/")) {
      return "kakuyomu";
    }
    return "generic";
  }

  if (/^n\d{4}[a-z]{2}$/i.test(input)) {
    return "novel18_syosetu";
  }
  if (/^\d{12,}$/.test(input)) {
    return "kakuyomu";
  }
  return "generic";
}

export function sanitizeNovelId(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/[^a-z0-9._-]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 120) || "novel"
  );
}

export function deriveNovelId(value: string, sourceKey: string): string {
  const input = cleanNovelInput(value);
  const url = parseNovelUrl(input);

  if (url) {
    if (sourceKey.includes("syosetu")) {
      const match = url.pathname.match(/\/(n\d{4}[a-z]{2})(?:\/|$)/i);
      if (match) {
        return match[1].toLowerCase();
      }
    }
    if (sourceKey === "kakuyomu") {
      const match = url.pathname.match(/\/works\/([^/?#]+)/i);
      if (match) {
        return match[1];
      }
    }
    return sanitizeNovelId(`${url.hostname}${url.pathname}`);
  }

  if (/^n\d{4}[a-z]{2}$/i.test(input)) {
    return input.toLowerCase();
  }
  return sanitizeNovelId(input);
}

export function sourceLabel(sourceKey: string, input = ""): string {
  if (sourceKey === "none") {
    return "None";
  }
  if (sourceKey === "novel18_syosetu") {
    return "Novel18 -> Syosetu fallback (auto)";
  }
  if (sourceKey === "syosetu_ncode") {
    return "Syosetu -> Novel18 fallback (auto)";
  }
  return SOURCE_LABELS[sourceKey] ? `${SOURCE_LABELS[sourceKey]} (${sourceKey})` : sourceKey || detectSourceOrigin(input);
}
