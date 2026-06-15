"use client";

import { AuthGate } from "@/components/public/auth-gate";
import { ContributionView } from "@/components/public/contribution-view";

/**
 * Account contribution page — gated behind AuthGate so that
 * guests see the LoginPrompt and authenticated users see the
 * ContributionView.
 *
 * Requirements validated: 17.1, 17.2, 17.3
 */
export default function ContributePage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Contribute a Translation Key</h1>
      <AuthGate>
        <ContributionView />
      </AuthGate>
    </div>
  );
}
