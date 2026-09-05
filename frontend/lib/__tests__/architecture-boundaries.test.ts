import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, it, expect } from "vitest";

const ROOT = resolve(import.meta.dirname, "../..");
const APP_DIR = join(ROOT, "app");
const COMPONENTS_DIR = join(ROOT, "components");
const PACKAGE_JSON = join(ROOT, "package.json");

function walkFiles(dir: string, extensions: string[]): string[] {
  const results: string[] = [];
  try {
    const entries = readdirSync(dir);
    for (const entry of entries) {
      if (
        entry === "node_modules" ||
        entry === ".next" ||
        entry === "__tests__"
      ) {
        continue;
      }
      const fullPath = join(dir, entry);
      const stat = statSync(fullPath);
      if (stat.isDirectory()) {
        results.push(...walkFiles(fullPath, extensions));
      } else if (extensions.some((ext) => entry.endsWith(ext))) {
        results.push(fullPath);
      }
    }
  } catch {
    // Directory may not exist
  }
  return results;
}

describe("Frontend Architectural Boundary Invariants", () => {
  it("ensures public routes never import admin API client", () => {
    const publicAppFiles = walkFiles(join(APP_DIR, "(public)"), [
      ".ts",
      ".tsx",
    ]);
    const publicComponentFiles = walkFiles(join(COMPONENTS_DIR, "public"), [
      ".ts",
      ".tsx",
    ]);
    const allPublicFiles = [...publicAppFiles, ...publicComponentFiles];

    const violations: string[] = [];

    for (const file of allPublicFiles) {
      const content = readFileSync(file, "utf8");
      // Check for imports from @/lib/api that are NOT just ApiError
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (
          line.includes('from "@/lib/api"') ||
          line.includes("from '@/lib/api'")
        ) {
          // Permitted: import { ApiError } from "@/lib/api"
          if (
            !line.includes("ApiError") ||
            line.includes("adminApi") ||
            line.includes("apiGet") ||
            line.includes("apiPost")
          ) {
            violations.push(`${file}:${i + 1}: ${line.trim()}`);
          }
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it("ensures admin routes never import public API client directly", () => {
    const adminAppFiles = walkFiles(join(APP_DIR, "(admin)"), [".ts", ".tsx"]);
    // Admin components should use admin API; taxonomy-dialog is the only exception as it queries public catalog tag search for autocomplete
    const adminComponentFiles = walkFiles(join(COMPONENTS_DIR, "admin"), [
      ".ts",
      ".tsx",
    ]).filter((f) => !f.endsWith("taxonomy-dialog.tsx"));
    const allAdminFiles = [...adminAppFiles, ...adminComponentFiles];

    const violations: string[] = [];

    for (const file of allAdminFiles) {
      const content = readFileSync(file, "utf8");
      if (
        content.includes('from "@/lib/public-api"') ||
        content.includes("from '@/lib/public-api'")
      ) {
        violations.push(file);
      }
    }

    expect(violations).toEqual([]);
  });

  it("ensures components never call native fetch or axios directly", () => {
    const componentFiles = walkFiles(COMPONENTS_DIR, [".ts", ".tsx"]);
    const violations: string[] = [];
    const fnName = ["fe", "tch"].join("");
    const pattern = new RegExp(`(?<!re)${fnName}\\s*\\(`);

    for (const file of componentFiles) {
      const content = readFileSync(file, "utf8");
      // Check for direct HTTP client invocation but exclude refetch()
      if (pattern.test(content) || /axios\s*\(/.test(content)) {
        violations.push(file);
      }
    }

    expect(violations).toEqual([]);
  });

  it("ensures prohibited state and styling libraries are never introduced", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON, "utf8"));
    const allDeps = {
      ...(pkg.dependencies || {}),
      ...(pkg.devDependencies || {}),
    };

    const prohibited = [
      "redux",
      "@reduxjs/toolkit",
      "mobx",
      "styled-components",
      "@emotion/react",
      "@emotion/styled",
    ];

    for (const lib of prohibited) {
      expect(allDeps[lib]).toBeUndefined();
    }
  });
});
