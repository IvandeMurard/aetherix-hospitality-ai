"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DayPredictionDisplay } from "@/lib/types";

interface HeroCardProps {
  prediction: DayPredictionDisplay;
}

export function HeroCard({ prediction }: HeroCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <h2 className="text-lg font-semibold">Day forecast</h2>
        <Badge variant="secondary">{prediction.confidence_label}</Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          {prediction.predicted_covers} covers expected
        </p>
        <p className="mt-2 text-sm">
          Range: {prediction.range_min} – {prediction.range_max}
        </p>
        <p className="mt-1 text-sm">
          Servers: {prediction.servers}
        </p>
        <p className="mt-2 text-sm italic text-muted-foreground">
          {prediction.reasoning_summary}
        </p>
      </CardContent>
    </Card>
  );
}
