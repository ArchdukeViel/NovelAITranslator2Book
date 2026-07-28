import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("admin API quarantine", () => {
  it("keeps the active provider credential status method", () => {
    const adminApi = readFileSync("lib/api.ts", "utf8");

    expect(adminApi).toContain("export const adminApi");
    expect(adminApi).toContain("providerCredential");
    expect(adminApi).toContain("/admin/providers/");
  });

  it("exports implemented user management methods", () => {
    const adminApi = readFileSync("lib/api.ts", "utf8");

    expect(adminApi).toContain("listUsers");
    expect(adminApi).toContain("getUser");
    expect(adminApi).toContain("updateUserActive");
    expect(adminApi).toContain("updateUserRole");
    expect(adminApi).toContain("revokeUserSessions");
  });

  it("does not export future admin API methods for missing contracts", () => {
    const adminApi = readFileSync("lib/api.ts", "utf8");

    // User management is now implemented — only quarantined futures remain
    expect(adminApi).not.toContain("/admin/controls");
    expect(adminApi).not.toContain("/admin/contributed-credentials");
    expect(adminApi).not.toContain("runRequest");
    expect(adminApi).not.toContain("activateProviderCredential");
    expect(adminApi).not.toContain("contributedCredentials");
    expect(adminApi).not.toContain("controlConfig");
  });

  it("does not keep types that only supported quarantined future admin methods", () => {
    const apiTypes = readFileSync("lib/api-types.ts", "utf8");

    expect(apiTypes).not.toContain("UserRecord");
    expect(apiTypes).not.toContain("UserMutation");
    expect(apiTypes).not.toContain("NovelRequestRecordAdmin");
    expect(apiTypes).not.toContain("ContributedCredential");
    expect(apiTypes).not.toContain("ControlConfig");
    expect(apiTypes).toContain("ProviderCredential");
  });
});
