"use client";

import { useState } from "react";
import Link from "next/link";
import { Film, Inbox } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Button } from "@/components/ui/button";
import { useBuilds, useBuildDataset } from "@/lib/queries";
import { ClipRow } from "@/components/builds/clip-row";

export function DatasetExplorer() {
  const { data: builds = [], isLoading: buildsLoading } = useBuilds();
  const complete = builds.filter((b) => b.status === "complete");
  // The selector is uncontrolled until the user picks; default to the most
  // recent completed build via a derived value (no setState-in-effect).
  const [picked, setPicked] = useState<string>("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const buildId = picked || complete[0]?.id || "";

  const { data: groups = [], isLoading, error, refetch } = useBuildDataset(
    buildId || undefined,
    !!buildId,
  );

  if (buildsLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (complete.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <EmptyState
            icon={Inbox}
            title="No completed builds yet"
            description="Run a build to fan a raw video out into labeled action clips, then browse them here grouped by class."
            action={
              <Button asChild size="sm">
                <Link href="/builds">Go to Builds</Link>
              </Button>
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-muted-foreground">Build:</span>
        <Select value={buildId} onValueChange={(v) => { setPicked(v); setPlayingId(null); }}>
          <SelectTrigger className="w-72">
            <SelectValue placeholder="Pick a completed build…" />
          </SelectTrigger>
          <SelectContent>
            {complete.map((b) => (
              <SelectItem key={b.id} value={b.id}>
                {b.name} ({b.clips_total} clips)
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : groups.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={Film}
              title="No clips in this build"
              description="This build produced no clips above the confidence threshold."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <Card key={group.action}>
              <CardHeader className="border-b border-border py-4 px-5">
                <CardTitle className="card-title flex items-center gap-2">
                  <Film className="h-4 w-4 text-muted-foreground" />
                  {group.action}
                  <Badge variant="secondary" className="ml-1">{group.count}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {group.clips.map((clip) => (
                    <ClipRow
                      key={clip.clip_id}
                      buildId={buildId}
                      clip={clip}
                      playing={playingId === clip.clip_id}
                      onPlay={() => setPlayingId(clip.clip_id)}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
