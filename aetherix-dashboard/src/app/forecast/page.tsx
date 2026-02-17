"use client";

import { useState, useEffect } from "react";
import { format, startOfWeek, addDays } from "date-fns";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useApp } from "@/lib/context/AppContext";
import {
  getPredictionDay,
  getPredictionWeek,
  getPredictionMonth,
  transformPredictionForDisplay,
} from "@/lib/api";
import type { DayPrediction, BatchPredictionWithSummary } from "@/lib/types";
import { HeroCard } from "@/components/forecast/HeroCard";
import { KPICards } from "@/components/forecast/KPICards";
import { ForecastChart } from "@/components/forecast/ForecastChart";
import { WhyThisForecast } from "@/components/forecast/WhyThisForecast";

type ViewType = "day" | "week" | "month";

function confidenceToLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

export default function ForecastPage() {
  const { selectedRestaurantId, selectedServiceType, isReady } = useApp();
  const [viewType, setViewType] = useState<ViewType>("day");
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [dayPrediction, setDayPrediction] = useState<DayPrediction | null>(null);
  const [weekPrediction, setWeekPrediction] =
    useState<BatchPredictionWithSummary | null>(null);
  const [monthPrediction, setMonthPrediction] =
    useState<BatchPredictionWithSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !selectedRestaurantId) return;

    const dateStr = format(selectedDate, "yyyy-MM-dd");
    setIsLoading(true);
    setError(null);

    if (viewType === "day") {
      getPredictionDay(
        selectedRestaurantId,
        dateStr,
        selectedServiceType
      )
        .then(setDayPrediction)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to fetch")
        )
        .finally(() => setIsLoading(false));
    } else if (viewType === "week") {
      const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const weekStartStr = format(weekStart, "yyyy-MM-dd");
      getPredictionWeek(
        selectedRestaurantId,
        weekStartStr,
        selectedServiceType
      )
        .then(setWeekPrediction)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to fetch")
        )
        .finally(() => setIsLoading(false));
    } else {
      const month = selectedDate.getMonth() + 1;
      const year = selectedDate.getFullYear();
      getPredictionMonth(
        selectedRestaurantId,
        month,
        year,
        selectedServiceType
      )
        .then(setMonthPrediction)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to fetch")
        )
        .finally(() => setIsLoading(false));
    }
  }, [
    selectedRestaurantId,
    selectedServiceType,
    selectedDate,
    viewType,
    isReady,
  ]);

  const navigatePrev = () => {
    if (viewType === "day") setSelectedDate((d) => addDays(d, -1));
    else if (viewType === "week") setSelectedDate((d) => addDays(d, -7));
    else
      setSelectedDate(
        (d) => new Date(d.getFullYear(), d.getMonth() - 1, 1)
      );
  };

  const navigateNext = () => {
    if (viewType === "day") setSelectedDate((d) => addDays(d, 1));
    else if (viewType === "week") setSelectedDate((d) => addDays(d, 7));
    else
      setSelectedDate(
        (d) => new Date(d.getFullYear(), d.getMonth() + 1, 1)
      );
  };

  const getDateLabel = () => {
    if (viewType === "day")
      return format(selectedDate, "EEEE, MMMM d, yyyy");
    if (viewType === "week") {
      const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const weekEnd = addDays(weekStart, 6);
      return `${format(weekStart, "MMM d")} – ${format(weekEnd, "MMM d, yyyy")}`;
    }
    return format(selectedDate, "MMMM yyyy");
  };

  if (!isReady) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Please select a restaurant</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Tabs value={viewType} onValueChange={(v) => setViewType(v as ViewType)}>
          <TabsList>
            <TabsTrigger value="day">Day</TabsTrigger>
            <TabsTrigger value="week">Week</TabsTrigger>
            <TabsTrigger value="month">Month</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedDate(new Date())}
          >
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={navigatePrev}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[200px] text-center text-sm font-medium">
            {getDateLabel()}
          </span>
          <Button variant="outline" size="icon" onClick={navigateNext}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full" />
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        </div>
      )}

      {!isLoading && viewType === "day" && dayPrediction && (
        <div className="space-y-6">
          <KPICards
            covers={dayPrediction.predicted_covers}
            range={`${dayPrediction.accuracy_metrics?.prediction_interval?.[0] ?? dayPrediction.predicted_covers - 10} – ${dayPrediction.accuracy_metrics?.prediction_interval?.[1] ?? dayPrediction.predicted_covers + 10}`}
            staff={`${dayPrediction.staff_recommendation.servers.recommended} servers`}
            confidence={confidenceToLabel(dayPrediction.confidence)}
          />
          <HeroCard prediction={transformPredictionForDisplay(dayPrediction)} />
          <WhyThisForecast reasoning={dayPrediction.reasoning} />
        </div>
      )}

      {!isLoading && viewType === "week" && weekPrediction && (
        <div className="space-y-6">
          <KPICards
            covers={weekPrediction.summary.total_covers}
            range={`${weekPrediction.summary.daily_avg} avg/day`}
            staff={weekPrediction.summary.peak_day.date}
            confidence={confidenceToLabel(weekPrediction.summary.avg_confidence)}
            labels={{
              covers: "Total Week",
              range: "Daily Avg",
              staff: "Peak Day",
              confidence: "Avg Confidence",
            }}
          />
          <ForecastChart
            title="Weekly Forecast"
            data={weekPrediction.predictions.map((p) => ({
              label: format(
                new Date(p.date ?? p.service_date ?? ""),
                "EEE"
              ),
              covers: p.predicted_covers,
            }))}
            average={weekPrediction.summary.daily_avg}
          />
        </div>
      )}

      {!isLoading && viewType === "month" && monthPrediction && (
        <div className="space-y-6">
          <KPICards
            covers={monthPrediction.summary.total_covers}
            range={`${monthPrediction.summary.daily_avg} avg/day`}
            staff={monthPrediction.summary.peak_day.date}
            confidence={confidenceToLabel(monthPrediction.summary.avg_confidence)}
            labels={{
              covers: "Total Month",
              range: "Daily Avg",
              staff: "Peak Day",
              confidence: "Avg Confidence",
            }}
          />
          <ForecastChart
            title="Monthly Forecast"
            data={monthPrediction.predictions.map((p) => ({
              label: format(
                new Date(p.date ?? p.service_date ?? ""),
                "d"
              ),
              covers: p.predicted_covers,
            }))}
            average={monthPrediction.summary.daily_avg}
          />
        </div>
      )}
    </div>
  );
}
