export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Action-dataset builder ---

export type JobStatus =
  | "queued"
  | "segmenting"
  | "clipping"
  | "labeling"
  | "packaging"
  | "complete"
  | "failed";

export type BuildStatus = "draft" | "running" | "complete" | "failed";
export type SegmentStrategy = "fixed-stride" | "scene-detect";
export type SplitPreset = "70/15/15" | "80/10/10" | "60/20/20";
export type Split = "train" | "val" | "test";

export interface BuildConfig {
  source_key: string;
  strategy: SegmentStrategy;
  window_seconds: number;
  stride_seconds: number;
  recognizer_model: string;
  confidence_threshold: number;
  split_preset: SplitPreset;
  version_tag: string;
  max_clips: number;
}

export interface LabeledClip {
  clip_id: string;
  action: string;
  confidence: number;
  split: Split;
  start: number;
  end: number;
  duration: number;
  clip_key: string;
}

export interface BuildStats {
  segments_total: number;
  clips_total: number;
  clips_dropped: number;
  classes_seen: string[];
  class_distribution: Record<string, number>;
  split_distribution: Record<string, number>;
  avg_confidence: number;
}

export interface Release {
  version: string;
  manifest_key: string;
  metadata_key: string;
  annotation_keys: string[];
  clip_count: number;
  created_at: string;
}

export interface Build {
  id: string;
  name: string;
  description: string;
  status: BuildStatus;
  config: BuildConfig;
  stats: BuildStats;
  clips: LabeledClip[];
  releases: Release[];
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuildSummary {
  id: string;
  name: string;
  description: string;
  status: BuildStatus;
  source_key: string;
  recognizer_model: string;
  clips_total: number;
  classes_total: number;
  release_count: number;
  created_at: string;
  updated_at: string;
}

export interface BuildJob {
  id: string;
  build_id: string;
  status: JobStatus;
  progress: number;
  message: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuilderStatsSummary {
  footage_ingested: number;
  builds_total: number;
  builds_complete: number;
  total_clips: number;
  total_classes: number;
  storage_used_human: string;
}

export interface SourceVideo {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
}

export interface ClassGroup {
  action: string;
  count: number;
  clips: LabeledClip[];
}
