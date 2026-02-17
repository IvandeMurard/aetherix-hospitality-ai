"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface ForecastChartProps {
  title: string;
  data: { label: string; covers: number }[];
  average?: number;
}

export function ForecastChart({ title, data, average }: ForecastChartProps) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="mb-4 text-lg font-semibold">{title}</h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="label" className="text-xs" />
            <YAxis className="text-xs" />
            <Tooltip
              contentStyle={{ borderRadius: "6px" }}
              formatter={(value: number) => [value, "Covers"]}
            />
            {average != null && (
              <ReferenceLine
                y={average}
                stroke="hsl(var(--primary))"
                strokeDasharray="3 3"
                label={{ value: "Avg", position: "right" }}
              />
            )}
            <Bar
              dataKey="covers"
              fill="hsl(var(--primary))"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
