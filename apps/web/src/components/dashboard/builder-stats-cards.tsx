"use client";

import { Film, Database, Layers, Tag, HardDrive } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useBuilderStats } from "@/lib/queries";

export function BuilderStatsCards() {
  const { data: stats, isLoading, error, refetch } = useBuilderStats();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    { title: "Footage ingested", value: stats?.footage_ingested ?? 0, icon: Film },
    { title: "Builds", value: stats?.builds_total ?? 0, icon: Database },
    { title: "Builds complete", value: stats?.builds_complete ?? 0, icon: Layers },
    { title: "Labeled clips", value: stats?.total_clips ?? 0, icon: Tag },
    {
      title: "Dataset storage",
      value: stats?.storage_used_human ?? "0 B",
      icon: HardDrive,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card, i) => (
        <Card key={card.title} className={`card-hover animate-fade-in-up stagger-${i + 1}`}>
          <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {card.title}
            </CardTitle>
            <div className="stat-icon-wrap">
              <card.icon className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <div className="stat-value">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
