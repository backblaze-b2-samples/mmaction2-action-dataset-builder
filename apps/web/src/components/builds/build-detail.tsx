"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Layers, Pencil, Play, Loader2, Film } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useBuild, useBuildJobs, useRunBuild } from "@/lib/queries";
import { recognizerLabel, strategyLabel } from "@/lib/build-format";
import { ClipRow } from "./clip-row";

export function BuildDetail({ buildId }: { buildId: string }) {
  const { data: b, isLoading, error, refetch } = useBuild(buildId);
  const { data: jobs = [] } = useBuildJobs(true);
  const runMutation = useRunBuild();
  const [playingId, setPlayingId] = useState<string | null>(null);

  const job = jobs.find((j) => j.build_id === buildId);
  const busy =
    b?.status === "running" ||
    (!!job && job.status !== "complete" && job.status !== "failed");

  const handleRun = () => {
    runMutation.mutate(buildId, {
      onSuccess: () => toast.success("Build started"),
      onError: (err) => toast.error(err.message || "Failed to start build"),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (error || !b) {
    return <ErrorState error={error ?? new Error("Not found")} onRetry={() => refetch()} />;
  }

  const stats = b.stats;
  const latestRelease = b.releases[b.releases.length - 1];

  return (
    <div className="space-y-6">
      <div className="animate-fade-in border-b border-border pb-5">
        <Button asChild variant="ghost" size="sm" className="h-7 -ml-2 mb-2 text-xs">
          <Link href="/builds">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Builds
          </Link>
        </Button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="page-title flex items-center gap-2">
              <Layers className="h-5 w-5 text-muted-foreground" />
              {b.name}
            </h1>
            {b.description && (
              <p className="text-sm text-muted-foreground mt-1.5">{b.description}</p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="outline">{recognizerLabel(b.config.recognizer_model)}</Badge>
              <Badge variant="outline">{strategyLabel(b.config.strategy)}</Badge>
              <Badge variant="outline" className="capitalize">{b.status}</Badge>
              {busy && job && (
                <Badge variant="secondary" className="gap-1 capitalize">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {job.status} {Math.round(job.progress * 100)}%
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm" className="h-8">
              <Link href={`/builds/${b.id}/edit`}>
                <Pencil className="h-3.5 w-3.5" />
                Edit
              </Link>
            </Button>
            <Button size="sm" className="h-8" disabled={busy} onClick={handleRun}>
              <Play className="h-3.5 w-3.5" />
              {b.status === "complete" ? "Rebuild" : "Run build"}
            </Button>
          </div>
        </div>
      </div>

      {b.status === "failed" && b.error && (
        <Card className="border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">
            Build failed: {b.error}
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Segments", value: stats.segments_total },
          { label: "Labeled clips", value: stats.clips_total },
          { label: "Action classes", value: stats.classes_seen.length },
          {
            label: "Avg confidence",
            value: stats.clips_total ? `${(stats.avg_confidence * 100).toFixed(0)}%` : "—",
          },
        ].map((s) => (
          <Card key={s.label} className="card-hover">
            <CardHeader className="pt-4 pb-2 px-4">
              <CardTitle className="text-xs font-semibold text-muted-foreground">
                {s.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-5 px-4">
              <div className="stat-value">{s.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Per-class label distribution */}
      {Object.keys(stats.class_distribution).length > 0 && (
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Label distribution</CardTitle>
          </CardHeader>
          <CardContent className="p-5 flex flex-wrap gap-2">
            {Object.entries(stats.class_distribution)
              .sort((a, c) => c[1] - a[1])
              .map(([action, count]) => (
                <Badge key={action} variant="secondary" className="gap-1.5">
                  {action}
                  <span className="font-mono tabular-nums text-muted-foreground">{count}</span>
                </Badge>
              ))}
          </CardContent>
        </Card>
      )}

      {/* Release artifacts */}
      {latestRelease && (
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Release {latestRelease.version} on B2
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground mb-2">
              {latestRelease.clip_count} clips · train/val/test CSVs + metadata,
              all under the build&apos;s release prefix.
            </p>
            <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs font-mono">
              {latestRelease.metadata_key}
              {"\n"}
              {latestRelease.manifest_key}
              {"\n"}
              {latestRelease.annotation_keys.join("\n")}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Clips with in-browser video playback */}
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title flex items-center gap-2">
            <Film className="h-4 w-4 text-muted-foreground" />
            Labeled clips ({b.clips.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {b.clips.length === 0 ? (
            <EmptyState
              icon={Film}
              title="No clips yet"
              description={
                b.status === "draft"
                  ? "Run this build to segment, clip, label with MMAction2, and package."
                  : "This build produced no clips above the confidence threshold."
              }
            />
          ) : (
            <div className="divide-y divide-border">
              {b.clips.map((clip) => (
                <ClipRow
                  key={clip.clip_id}
                  buildId={b.id}
                  clip={clip}
                  playing={playingId === clip.clip_id}
                  onPlay={() => setPlayingId(clip.clip_id)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
