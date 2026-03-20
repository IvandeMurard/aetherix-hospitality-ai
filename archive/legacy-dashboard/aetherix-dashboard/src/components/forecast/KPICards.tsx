"use client";

import { Card, CardContent } from "@/components/ui/card";

interface KPICardsProps {
  covers: number;
  range: string;
  staff: string;
  confidence: string;
  labels?: {
    covers?: string;
    range?: string;
    staff?: string;
    confidence?: string;
  };
}

export function KPICards({
  covers,
  range,
  staff,
  confidence,
  labels = {},
}: KPICardsProps) {
  const {
    covers: coversLabel = "Covers",
    range: rangeLabel = "Range",
    staff: staffLabel = "Staff",
    confidence: confidenceLabel = "Confidence",
  } = labels;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {coversLabel}
          </p>
          <p className="text-2xl font-bold">{covers}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {rangeLabel}
          </p>
          <p className="text-2xl font-bold">{range}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {staffLabel}
          </p>
          <p className="text-2xl font-bold">{staff}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {confidenceLabel}
          </p>
          <p className="text-2xl font-bold">{confidence}</p>
        </CardContent>
      </Card>
    </div>
  );
}
