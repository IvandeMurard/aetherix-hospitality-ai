"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Reasoning } from "@/lib/types";

interface WhyThisForecastProps {
  reasoning: Reasoning;
}

export function WhyThisForecast({ reasoning }: WhyThisForecastProps) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Why this forecast</h2>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{reasoning.summary}</p>
        {reasoning.confidence_factors && reasoning.confidence_factors.length > 0 && (
          <ul className="list-inside list-disc text-sm text-muted-foreground">
            {reasoning.confidence_factors.map((factor, i) => (
              <li key={i}>{factor}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
