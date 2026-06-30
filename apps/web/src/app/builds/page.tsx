import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BuildsList } from "@/components/builds/builds-list";

export default function BuildsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Builds</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Each build turns one raw video into a labeled action-recognition
            dataset on B2 — segment, clip, label with MMAction2, package.
          </p>
        </div>
        <Button asChild size="sm" className="h-8 shrink-0">
          <Link href="/builds/new">
            <Plus aria-hidden="true" className="h-3.5 w-3.5" />
            New build
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <BuildsList />
      </div>
    </div>
  );
}
