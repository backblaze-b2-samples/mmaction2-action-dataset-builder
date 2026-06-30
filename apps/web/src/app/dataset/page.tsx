import { DatasetExplorer } from "@/components/dataset/dataset-explorer";

export default function DatasetPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Dataset</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Browse a completed build&apos;s labeled clips grouped by Kinetics-400
          action class, scoped to its own output prefix on B2. The Files page is
          the separate full-bucket browser.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <DatasetExplorer />
      </div>
    </div>
  );
}
