"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createBuild,
  deleteBuild,
  deleteFile,
  getBuild,
  getBuilderStats,
  getBuildDataset,
  getBuildJobs,
  getBuilds,
  getClipPreviewUrl,
  getFiles,
  getFileStats,
  getPreviewUrl,
  getSources,
  getUploadActivity,
  runBuild,
  updateBuild,
  type BuildInput,
} from "@/lib/api-client";
import type {
  Build,
  BuilderStatsSummary,
  BuildJob,
  BuildSummary,
  ClassGroup,
  FileMetadata,
  SourceVideo,
} from "@mmaction2-action-dataset-builder/shared";

// Single source of truth for query keys. Keep these tightly scoped so that
// invalidating "files" doesn't blow away unrelated caches, and so an IDE
// "find usages" of `qk.files` reveals every consumer.
export const qk = {
  all: ["b2"] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  stats: () => [...qk.all, "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  builds: () => [...qk.all, "builds"] as const,
  build: (id: string) => [...qk.all, "builds", id] as const,
  buildDataset: (id: string) => [...qk.all, "builds", id, "dataset"] as const,
  builderStats: () => [...qk.all, "builds", "stats"] as const,
  sources: () => [...qk.all, "builds", "sources"] as const,
  jobs: () => [...qk.all, "builds", "jobs"] as const,
  clipPreview: (buildId: string, clipId: string) =>
    [...qk.all, "builds", buildId, "clip", clipId] as const,
};

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
  });
}

export function useFileStats() {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    // After delete, blow away every cached file list + stats. Cheap and
    // correct — the dashboard re-fetches lazily as components remount.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Action-dataset builder ---

export function useSources() {
  return useQuery<SourceVideo[], ApiError>({
    queryKey: qk.sources(),
    queryFn: getSources,
  });
}

export function useBuilderStats() {
  return useQuery<BuilderStatsSummary, ApiError>({
    queryKey: qk.builderStats(),
    queryFn: getBuilderStats,
  });
}

export function useBuilds() {
  return useQuery<BuildSummary[], ApiError>({
    queryKey: qk.builds(),
    queryFn: getBuilds,
  });
}

export function useBuild(id: string | undefined, enabled = true) {
  return useQuery<Build, ApiError>({
    queryKey: qk.build(id ?? ""),
    queryFn: () => getBuild(id as string),
    enabled: enabled && !!id,
  });
}

export function useBuildDataset(id: string | undefined, enabled = true) {
  return useQuery<ClassGroup[], ApiError>({
    queryKey: qk.buildDataset(id ?? ""),
    queryFn: () => getBuildDataset(id as string),
    enabled: enabled && !!id,
  });
}

export function useClipPreviewUrl(
  buildId: string,
  clipId: string | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: qk.clipPreview(buildId, clipId ?? ""),
    queryFn: () => getClipPreviewUrl(buildId, clipId as string),
    enabled: enabled && !!clipId,
    staleTime: 60_000,
  });
}

// Polls while any build is still running so progress badges + the detail page
// refresh live as the background pipeline advances.
export function useBuildJobs(poll = false) {
  return useQuery<BuildJob[], ApiError>({
    queryKey: qk.jobs(),
    queryFn: getBuildJobs,
    refetchInterval: poll ? 2000 : false,
  });
}

export function useCreateBuild() {
  const qc = useQueryClient();
  return useMutation<Build, ApiError, BuildInput>({
    mutationFn: (input) => createBuild(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.builds() });
      qc.invalidateQueries({ queryKey: qk.builderStats() });
    },
  });
}

export function useUpdateBuild(id: string) {
  const qc = useQueryClient();
  return useMutation<Build, ApiError, Partial<BuildInput>>({
    mutationFn: (input) => updateBuild(id, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.builds() });
      qc.invalidateQueries({ queryKey: qk.build(id) });
    },
  });
}

export function useDeleteBuild() {
  const qc = useQueryClient();
  return useMutation<
    { deleted: boolean; id: string; objects: number },
    ApiError,
    string
  >({
    mutationFn: (id) => deleteBuild(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

export function useRunBuild() {
  const qc = useQueryClient();
  return useMutation<BuildJob, ApiError, string>({
    mutationFn: (id) => runBuild(id),
    onSuccess: (_job, id) => {
      qc.invalidateQueries({ queryKey: qk.jobs() });
      qc.invalidateQueries({ queryKey: qk.build(id) });
      qc.invalidateQueries({ queryKey: qk.builds() });
    },
  });
}
