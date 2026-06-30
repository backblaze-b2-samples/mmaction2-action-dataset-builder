"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Layers, Inbox, Loader2, Play, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  useBuilds,
  useBuildJobs,
  useRunBuild,
  useDeleteBuild,
} from "@/lib/queries";
import { recognizerLabel } from "@/lib/build-format";
import type { BuildJob, BuildSummary } from "@mmaction2-action-dataset-builder/shared";

function StatusBadge({ b, job }: { b: BuildSummary; job: BuildJob | undefined }) {
  if (job && job.status !== "complete" && job.status !== "failed") {
    return (
      <Badge variant="secondary" className="gap-1 capitalize">
        <Loader2 className="h-3 w-3 animate-spin" />
        {job.status}
        {job.progress > 0 ? ` ${Math.round(job.progress * 100)}%` : ""}
      </Badge>
    );
  }
  if (b.status === "complete") {
    return (
      <Badge variant="outline" className="gap-1 border-[var(--success)] text-[var(--success)]">
        Complete
      </Badge>
    );
  }
  if (b.status === "failed") return <Badge variant="destructive">Failed</Badge>;
  if (b.status === "running") return <Badge variant="secondary">Running…</Badge>;
  return <Badge variant="secondary">Draft</Badge>;
}

export function BuildsList() {
  const { data: builds = [], isLoading, error, refetch } = useBuilds();
  const anyRunning = builds.some((b) => b.status === "running");
  const { data: jobs = [] } = useBuildJobs(anyRunning || builds.length > 0);
  const runMutation = useRunBuild();
  const deleteMutation = useDeleteBuild();
  const [pendingDelete, setPendingDelete] = useState<BuildSummary | null>(null);

  const jobByBuild = useMemo(() => {
    const map = new Map<string, BuildJob>();
    for (const j of jobs) if (!map.has(j.build_id)) map.set(j.build_id, j);
    return map;
  }, [jobs]);

  const handleRun = (b: BuildSummary) => {
    runMutation.mutate(b.id, {
      onSuccess: () => toast.success(`Build started for ${b.name}`),
      onError: (err) => toast.error(err.message || "Failed to start build"),
    });
  };

  const handleDelete = () => {
    if (!pendingDelete) return;
    const b = pendingDelete;
    deleteMutation.mutate(b.id, {
      onSuccess: () => toast.success(`Deleted ${b.name}`),
      onError: (err) => toast.error(err.message || "Delete failed"),
    });
    setPendingDelete(null);
  };

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Builds</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : builds.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No builds yet"
            description="Create a build from an ingested video, then run it to label its action clips."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Name
                </TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Recognizer
                </TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Clips
                </TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Status
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {builds.map((b) => {
                const job = jobByBuild.get(b.id);
                const busy =
                  b.status === "running" ||
                  (!!job && job.status !== "complete" && job.status !== "failed");
                return (
                  <TableRow key={b.id} className="table-row-hover">
                    <TableCell className="font-medium">
                      <Link
                        href={`/builds/${b.id}`}
                        className="flex items-center gap-2 truncate hover:underline"
                      >
                        <Layers className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{b.name}</span>
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground whitespace-nowrap">
                      {recognizerLabel(b.recognizer_model)}
                    </TableCell>
                    <TableCell className="font-mono text-xs tabular-nums text-muted-foreground">
                      {b.clips_total}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <StatusBadge b={b} job={job} />
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          disabled={busy || runMutation.isPending}
                          onClick={() => handleRun(b)}
                        >
                          <Play className="h-3 w-3" />
                          {b.status === "complete" ? "Rerun" : "Run"}
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          onClick={() => setPendingDelete(b)}
                          aria-label={`Delete ${b.name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete build?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes <strong>{pendingDelete?.name}</strong> and
              every clip, annotation, and release under its{" "}
              <code>builds/{pendingDelete?.id}/</code> prefix on B2. Raw videos
              and other builds are untouched. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
