"use client";

import { Loader2, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useClipPreviewUrl } from "@/lib/queries";
import { formatTimestamp } from "@/lib/build-format";
import type { LabeledClip } from "@mmaction2-action-dataset-builder/shared";

export function ClipRow({
  buildId,
  clip,
  playing,
  onPlay,
}: {
  buildId: string;
  clip: LabeledClip;
  playing: boolean;
  onPlay: () => void;
}) {
  // Fetch the presigned clip URL once the user opens this clip for playback.
  const { data, isLoading } = useClipPreviewUrl(buildId, clip.clip_id, playing);
  const videoUrl = data?.url;
  const timecode = `${formatTimestamp(clip.start)}–${formatTimestamp(clip.end)}`;

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-sm">{clip.action}</span>
        <Badge variant="outline" className="text-[10px] uppercase">
          {clip.split}
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          {(clip.confidence * 100).toFixed(0)}%
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          {clip.duration.toFixed(1)}s
        </Badge>
        <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
          {timecode}
        </span>
      </div>
      {playing ? (
        isLoading || !videoUrl ? (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading clip…
          </span>
        ) : (
          // Native player paints the decoded frame once the presigned URL resolves.
          <video
            controls
            autoPlay
            muted
            playsInline
            src={videoUrl}
            className="w-full max-w-sm rounded-md border border-border bg-black"
          />
        )
      ) : (
        <button
          type="button"
          onClick={onPlay}
          className="flex w-fit items-center gap-1.5 text-xs font-medium text-primary hover:underline"
        >
          <Play className="h-3 w-3" /> Play clip
        </button>
      )}
    </div>
  );
}
