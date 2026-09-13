import type { PublicGenreInfo } from "@/lib/public-types";
import { cn } from "@/lib/utils";

const PALETTES = [
  {
    bgStart: "#0f172a",
    bgEnd: "#1e293b",
    frame: "#38bdf8",
    accent: "#38bdf8",
    gold: "#7dd3fc",
    title: "#f8fafc",
    subtitle: "#94a3b8",
    markBg: "#1e293b",
    markBorder: "#38bdf8",
  },
  {
    bgStart: "#240c14",
    bgEnd: "#3b1320",
    frame: "#fb7185",
    accent: "#fb7185",
    gold: "#fde047",
    title: "#fff1f2",
    subtitle: "#fda4af",
    markBg: "#4c1022",
    markBorder: "#fb7185",
  },
  {
    bgStart: "#092017",
    bgEnd: "#133829",
    frame: "#34d399",
    accent: "#34d399",
    gold: "#fde047",
    title: "#ecfdf5",
    subtitle: "#6ee7b7",
    markBg: "#144230",
    markBorder: "#34d399",
  },
  {
    bgStart: "#1b0d2d",
    bgEnd: "#2f174e",
    frame: "#c084fc",
    accent: "#c084fc",
    gold: "#fcd34d",
    title: "#faf5ff",
    subtitle: "#d8b4fe",
    markBg: "#3b1d62",
    markBorder: "#c084fc",
  },
  {
    bgStart: "#231507",
    bgEnd: "#3b240c",
    frame: "#fbbf24",
    accent: "#fbbf24",
    gold: "#fef08a",
    title: "#fffbeb",
    subtitle: "#fcd34d",
    markBg: "#4a2d0f",
    markBorder: "#fbbf24",
  },
  {
    bgStart: "#18181b",
    bgEnd: "#27272a",
    frame: "#a1a1aa",
    accent: "#e4e4e7",
    gold: "#f4f4f5",
    title: "#fafafa",
    subtitle: "#a1a1aa",
    markBg: "#2e2e33",
    markBorder: "#71717a",
  },
] as const;

interface FallbackCoverProps {
  className?: string;
  genres?: PublicGenreInfo[] | null;
  language?: string | null;
  sourceTitle?: string | null;
  status?: string | null;
  title: string;
  aspectRatio?: "2/3" | "1/1";
}

function hashText(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function initialsFor(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "本";
  }

  const firstChar = Array.from(trimmed)[0];
  if (
    /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u.test(firstChar)
  ) {
    return firstChar;
  }

  const words = trimmed
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) {
    return "本";
  }

  return words
    .slice(0, 2)
    .map((word) => Array.from(word)[0])
    .join("")
    .toUpperCase();
}

function cleanText(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

function displayMeta(
  language: string | null | undefined,
  status: string | null | undefined,
): string {
  const items = [cleanText(language)?.toUpperCase(), cleanText(status)].filter(
    Boolean,
  );
  return items.join(" • ") || "DOKUSHODO";
}

function truncateText(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars - 1) + "…";
}

function wrapTitle(text: string, maxLineChars = 16, maxLines = 3): string[] {
  if (text.length <= maxLineChars) {
    return [text];
  }

  const words = text.split(/\s+/);
  const lines: string[] = [];
  let currentLine = "";

  for (const word of words) {
    const testLine = currentLine ? `${currentLine} ${word}` : word;
    if (testLine.length <= maxLineChars) {
      currentLine = testLine;
    } else {
      if (currentLine) {
        lines.push(currentLine);
      }
      if (word.length > maxLineChars) {
        let remaining = word;
        while (remaining.length > maxLineChars && lines.length < maxLines - 1) {
          lines.push(remaining.slice(0, maxLineChars));
          remaining = remaining.slice(maxLineChars);
        }
        currentLine = remaining;
      } else {
        currentLine = word;
      }
    }

    if (lines.length >= maxLines) {
      break;
    }
  }

  if (currentLine && lines.length < maxLines) {
    lines.push(currentLine);
  }

  if (lines.length > maxLines) {
    lines.length = maxLines;
  }

  const joined = lines.join(" ");
  if (joined.length < text.length && lines.length > 0) {
    const lastIdx = lines.length - 1;
    lines[lastIdx] =
      lines[lastIdx].slice(0, Math.max(1, maxLineChars - 3)) + "...";
  }

  return lines.length > 0 ? lines : [text];
}

export function FallbackCover({
  className,
  genres,
  language,
  sourceTitle,
  status,
  title,
  aspectRatio = "2/3",
}: FallbackCoverProps) {
  const safeTitle = cleanText(title) ?? "Untitled novel";
  const safeSourceTitle = cleanText(sourceTitle);
  const subtitle =
    safeSourceTitle && safeSourceTitle !== safeTitle ? safeSourceTitle : null;
  const genreSeed =
    genres
      ?.map((g) => g.slug)
      .filter(Boolean)
      .join("|") ?? "";
  const seed = hashText(`${safeTitle}|${subtitle ?? ""}|${genreSeed}`);
  const palette = PALETTES[seed % PALETTES.length];
  const gradId = `bg-grad-${seed.toString(36)}`;

  const isSquare = aspectRatio === "1/1";
  const height = isSquare ? 200 : 300;
  const centerX = 108;

  const titleLines = wrapTitle(safeTitle, 16, 3);
  let titleFontSize =
    titleLines.length === 1 ? 13 : titleLines.length === 2 ? 11.5 : 10;
  if (isSquare) {
    titleFontSize = Math.min(titleFontSize, 10);
  }

  const lineHeight = isSquare ? 13 : 15;
  const titleY = isSquare
    ? subtitle
      ? 96
      : 105
    : subtitle
      ? titleLines.length === 1
        ? 142
        : titleLines.length === 2
          ? 134
          : 126
      : titleLines.length === 1
        ? 154
        : titleLines.length === 2
          ? 144
          : 136;

  const subY =
    titleY + (titleLines.length - 1) * lineHeight + (isSquare ? 13 : 16);

  const headerY = isSquare ? 28 : 34;
  const sealSize = isSquare ? 34 : 42;
  const sealY = isSquare ? 43 : 58;
  const sealX = centerX - sealSize / 2;
  const sealCenterY = sealY + sealSize / 2;

  const footerY = isSquare ? 182 : 272;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 200 ${height}`}
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={`Generated Dokushodo bookplate for ${safeTitle}`}
      className={cn("block h-full w-full select-none", className)}
    >
      <title>{safeTitle}</title>
      {subtitle && <desc>{subtitle}</desc>}

      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={palette.bgStart} />
          <stop offset="100%" stopColor={palette.bgEnd} />
        </linearGradient>
        <linearGradient id={`${gradId}-spine`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#000000" stopOpacity="0.45" />
          <stop offset="85%" stopColor="#000000" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Main Cover Base */}
      <rect width="200" height={height} rx="4" fill={`url(#${gradId})`} />

      {/* Subtle Background Geometric Lattice */}
      <circle
        cx={centerX}
        cy={isSquare ? 100 : 135}
        r="75"
        fill="none"
        stroke={palette.accent}
        strokeWidth="0.75"
        strokeOpacity="0.08"
        strokeDasharray="4 4"
      />
      <circle
        cx={centerX}
        cy={isSquare ? 100 : 135}
        r="90"
        fill="none"
        stroke={palette.accent}
        strokeWidth="0.5"
        strokeOpacity="0.05"
      />

      {/* Book Spine Crease on Left */}
      <rect
        x="0"
        y="0"
        width="16"
        height={height}
        rx="2"
        fill={`url(#${gradId}-spine)`}
      />
      <line
        x1="16"
        y1="0"
        x2="16"
        y2={height}
        stroke="#000000"
        strokeWidth="1"
        strokeOpacity="0.5"
      />
      <line
        x1="17"
        y1="0"
        x2="17"
        y2={height}
        stroke="#ffffff"
        strokeWidth="0.6"
        strokeOpacity="0.1"
      />

      {/* Japanese Binding Stitches (Wa-toji) */}
      <line
        x1="2"
        y1={height * 0.15}
        x2="14"
        y2={height * 0.15}
        stroke={palette.accent}
        strokeWidth="1"
        strokeOpacity="0.3"
      />
      <line
        x1="2"
        y1={height * 0.38}
        x2="14"
        y2={height * 0.38}
        stroke={palette.accent}
        strokeWidth="1"
        strokeOpacity="0.3"
      />
      <line
        x1="2"
        y1={height * 0.62}
        x2="14"
        y2={height * 0.62}
        stroke={palette.accent}
        strokeWidth="1"
        strokeOpacity="0.3"
      />
      <line
        x1="2"
        y1={height * 0.85}
        x2="14"
        y2={height * 0.85}
        stroke={palette.accent}
        strokeWidth="1"
        strokeOpacity="0.3"
      />

      {/* Bookplate Framing Borders */}
      <rect
        x="23"
        y="12"
        width="166"
        height={height - 24}
        rx="3"
        fill="none"
        stroke={palette.frame}
        strokeWidth="1"
        strokeOpacity="0.45"
      />
      <rect
        x="27"
        y="16"
        width="158"
        height={height - 32}
        rx="2"
        fill="none"
        stroke={palette.frame}
        strokeWidth="0.5"
        strokeOpacity="0.25"
      />

      {/* Corner Rosettes (Hishigata) */}
      <polygon
        points="27,13 30,16 27,19 24,16"
        fill={palette.gold}
        fillOpacity="0.75"
      />
      <polygon
        points="185,13 188,16 185,19 182,16"
        fill={palette.gold}
        fillOpacity="0.75"
      />
      <polygon
        points={`27,${height - 19} 30,${height - 16} 27,${height - 13} 24,${height - 16}`}
        fill={palette.gold}
        fillOpacity="0.75"
      />
      <polygon
        points={`185,${height - 19} 188,${height - 16} 185,${height - 13} 182,${height - 16}`}
        fill={palette.gold}
        fillOpacity="0.75"
      />

      {/* Header Brand */}
      <text
        x={centerX}
        y={headerY}
        textAnchor="middle"
        fill={palette.gold}
        fontSize="6.5"
        fontWeight="600"
        letterSpacing="3"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        opacity="0.9"
      >
        DOKUSHODO
      </text>
      <line
        x1="62"
        y1={headerY + 7}
        x2="96"
        y2={headerY + 7}
        stroke={palette.gold}
        strokeWidth="0.5"
        strokeOpacity="0.35"
      />
      <polygon
        points={`${centerX},${headerY + 5} ${centerX + 2.5},${headerY + 7} ${centerX},${headerY + 9} ${centerX - 2.5},${headerY + 7}`}
        fill={palette.gold}
        fillOpacity="0.6"
      />
      <line
        x1="120"
        y1={headerY + 7}
        x2="154"
        y2={headerY + 7}
        stroke={palette.gold}
        strokeWidth="0.5"
        strokeOpacity="0.35"
      />

      {/* Central Hanko / Seal Emblem */}
      <rect
        x={sealX}
        y={sealY}
        width={sealSize}
        height={sealSize}
        rx="6"
        fill={palette.markBg}
        stroke={palette.markBorder}
        strokeWidth="1.2"
      />
      <rect
        x={sealX + 3}
        y={sealY + 3}
        width={sealSize - 6}
        height={sealSize - 6}
        rx="4"
        fill="none"
        stroke={palette.gold}
        strokeWidth="0.6"
        strokeOpacity="0.5"
      />
      <text
        x={centerX}
        y={sealCenterY + 1}
        textAnchor="middle"
        dominantBaseline="central"
        fill={palette.gold}
        fontSize={isSquare ? 15 : 18}
        fontWeight="700"
        fontFamily="serif"
      >
        {initialsFor(subtitle ?? safeTitle)}
      </text>

      {/* Title Section */}
      {titleLines.length === 1 ? (
        <text
          x={centerX}
          y={titleY}
          textAnchor="middle"
          fill={palette.title}
          fontSize={titleFontSize}
          fontWeight="700"
          fontFamily="serif"
        >
          {titleLines[0]}
        </text>
      ) : (
        <text
          x={centerX}
          y={titleY}
          textAnchor="middle"
          fill={palette.title}
          fontSize={titleFontSize}
          fontWeight="700"
          fontFamily="serif"
        >
          {titleLines.map((line, idx) => (
            <tspan key={idx} x={centerX} dy={idx === 0 ? 0 : lineHeight}>
              {line}
            </tspan>
          ))}
        </text>
      )}

      {/* Subtitle / Source Title */}
      {subtitle && (
        <text
          x={centerX}
          y={subY}
          textAnchor="middle"
          fill={palette.subtitle}
          fontSize={isSquare ? 7.5 : 8.5}
          opacity="0.9"
          fontFamily="serif"
        >
          {truncateText(subtitle, 22)}
        </text>
      )}

      {/* Footer Ornament & Metadata */}
      <path
        d={`M${centerX - 6},${footerY - 18} C${centerX - 3},${footerY - 20} ${centerX - 1},${footerY - 20} ${centerX},${footerY - 19} C${centerX + 1},${footerY - 20} ${centerX + 3},${footerY - 20} ${centerX + 6},${footerY - 18} L${centerX + 6},${footerY - 13} C${centerX + 3},${footerY - 15} ${centerX + 1},${footerY - 15} ${centerX},${footerY - 14} C${centerX - 1},${footerY - 15} ${centerX - 3},${footerY - 15} ${centerX - 6},${footerY - 13} Z`}
        fill="none"
        stroke={palette.gold}
        strokeWidth="0.8"
        opacity="0.5"
      />
      <line
        x1="70"
        y1={footerY - 9}
        x2="146"
        y2={footerY - 9}
        stroke={palette.frame}
        strokeWidth="0.5"
        strokeOpacity="0.3"
      />
      <text
        x={centerX}
        y={footerY}
        textAnchor="middle"
        fill={palette.subtitle}
        fontSize={isSquare ? 6 : 6.8}
        letterSpacing="1"
        opacity="0.75"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
      >
        {displayMeta(language, status)}
      </text>
    </svg>
  );
}
