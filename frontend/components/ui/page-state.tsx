import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type StateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

function State({
  title,
  description,
  action,
  className,
  role = "status",
}: StateProps & { role?: "alert" | "status" }) {
  return (
    <section
      aria-live={role === "alert" ? "assertive" : "polite"}
      className={cn("rounded-lg border border-border bg-card px-6 py-10 text-center", className)}
      role={role}
    >
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {description ? <p className="mt-2 text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </section>
  );
}

export function LoadingState({
  label = "Loading...",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      aria-live="polite"
      className={cn("flex items-center justify-center gap-3 py-10 text-sm text-muted-foreground", className)}
      role="status"
    >
      <span aria-hidden="true" className="h-5 w-5 animate-spin rounded-full border-2 border-muted border-t-foreground" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState(props: StateProps) {
  return <State {...props} />;
}

export function ErrorState(props: StateProps) {
  return <State {...props} role="alert" />;
}

export function UnavailableState({
  title = "Temporarily unavailable",
  description = "This service is temporarily unavailable. Please try again later.",
  ...props
}: Partial<Pick<StateProps, "title" | "description">> & Omit<StateProps, "title" | "description">) {
  return <ErrorState {...props} title={title} description={description} />;
}

export function NotFoundState({
  title = "Not found",
  description = "We could not find that page or it is no longer available.",
  ...props
}: Partial<Pick<StateProps, "title" | "description">> & Omit<StateProps, "title" | "description">) {
  return <State {...props} title={title} description={description} />;
}

export function UnauthorizedState({
  title = "Sign in required",
  description = "Please sign in to continue.",
  ...props
}: Partial<Pick<StateProps, "title" | "description">> & Omit<StateProps, "title" | "description">) {
  return <State {...props} title={title} description={description} />;
}

export function ForbiddenState({
  title = "Permission required",
  description = "You do not have permission to view this page.",
  ...props
}: Partial<Pick<StateProps, "title" | "description">> & Omit<StateProps, "title" | "description">) {
  return <State {...props} title={title} description={description} />;
}

export function PartialErrorState({
  title = "Part of this page is unavailable",
  ...props
}: Partial<Pick<StateProps, "title">> & Omit<StateProps, "title">) {
  return <State {...props} title={title} />;
}
