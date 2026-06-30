"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useBuild } from "@/lib/queries";
import { BuildForm } from "./build-form";

export function BuildEdit({ buildId }: { buildId: string }) {
  const { data: build, isLoading, error, refetch } = useBuild(buildId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (error || !build) {
    return <ErrorState error={error ?? new Error("Not found")} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Edit build</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          {build.status === "draft"
            ? "Adjust the configuration before running this build."
            : "This build has already run, so its config is read-only. You can still rename it."}
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <BuildForm build={build} />
      </div>
    </div>
  );
}
