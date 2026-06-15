import { ContributionView } from "@/components/public/contribution-view";

/**
 * Contribution credentials are disabled until the gated backend phase exists.
 */
export default function ContributePage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <ContributionView />
    </div>
  );
}
