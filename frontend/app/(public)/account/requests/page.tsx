import { RequestControl } from "@/components/public/request-control";

export default function RequestsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <h1 className="text-lg font-semibold">My Requests</h1>
      <RequestControl />
    </div>
  );
}
