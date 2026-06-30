import { BuildForm } from "@/components/builds/build-form";

export default function NewBuildPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New build</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Configure a dataset build from an ingested video. Run it once created
          to fan the source out into labeled action clips.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <BuildForm />
      </div>
    </div>
  );
}
