import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";

import {
  HOME_QUERY_STALE_TIME_MS,
  prefetchHomeQueries,
} from "@/lib/public-home-data";

export const dynamic = "force-dynamic";

export default async function HomeLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { staleTime: HOME_QUERY_STALE_TIME_MS, retry: false },
    },
  });
  await prefetchHomeQueries(queryClient);

  return <HydrationBoundary state={dehydrate(queryClient)}>{children}</HydrationBoundary>;
}
