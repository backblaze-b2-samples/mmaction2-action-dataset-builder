import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BuilderStatsCards } from "@/components/dashboard/builder-stats-cards";
import { RecentBuildsTable } from "@/components/dashboard/recent-builds-table";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Raw footage, builds, and labeled action clips — all on Backblaze B2.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/builds/new">
            <Plus className="h-3.5 w-3.5" />
            New build
          </Link>
        </Button>
      </div>
      <BuilderStatsCards />
      <div className="animate-fade-in-up stagger-4">
        <RecentBuildsTable />
      </div>
    </div>
  );
}
