// src/lib/api.ts — API client aligned with backend fb-agent-mvp

import type {
  ServiceType,
  DayPrediction,
  BatchPredictionResponse,
  BatchPredictionWithSummary,
  BatchSummary,
  RestaurantProfile,
  DayPredictionDisplay,
} from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://ivandemurard-fb-agent-api.hf.space";

function computeRange(prediction: DayPrediction): { min: number; max: number } {
  const interval = prediction.accuracy_metrics?.prediction_interval;
  if (interval && Array.isArray(interval) && interval.length >= 2) {
    return { min: interval[0], max: interval[1] };
  }
  const margin = Math.round(prediction.predicted_covers * 0.15);
  return {
    min: Math.max(0, prediction.predicted_covers - margin),
    max: prediction.predicted_covers + margin,
  };
}

function confidenceToLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

export function transformPredictionForDisplay(
  prediction: DayPrediction
): DayPredictionDisplay {
  const range = computeRange(prediction);
  const dateStr = prediction.date ?? prediction.service_date ?? "";
  return {
    date: dateStr,
    predicted_covers: prediction.predicted_covers,
    confidence_label: confidenceToLabel(prediction.confidence),
    confidence_score: prediction.confidence,
    range_min: range.min,
    range_max: range.max,
    servers: prediction.staff_recommendation.servers.recommended,
    reasoning_summary: prediction.reasoning.summary,
  };
}

export function computeBatchSummary(
  predictions: DayPrediction[]
): BatchSummary {
  if (predictions.length === 0) {
    return {
      total_covers: 0,
      daily_avg: 0,
      peak_day: { date: "", covers: 0 },
      avg_confidence: 0,
    };
  }
  const total_covers = predictions.reduce(
    (sum, p) => sum + p.predicted_covers,
    0
  );
  const daily_avg = Math.round(total_covers / predictions.length);
  const peak = predictions.reduce((max, p) =>
    p.predicted_covers > max.predicted_covers ? p : max
  );
  const avg_confidence =
    predictions.reduce((sum, p) => sum + p.confidence, 0) /
    predictions.length;
  return {
    total_covers,
    daily_avg,
    peak_day: {
      date: peak.date ?? peak.service_date ?? "",
      covers: peak.predicted_covers,
    },
    avg_confidence: Math.round(avg_confidence * 100) / 100,
  };
}

export async function getPredictionDay(
  restaurantId: string,
  serviceDate: string,
  serviceType: ServiceType
): Promise<DayPrediction> {
  const res = await fetch(`${API_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      restaurant_id: restaurantId,
      service_date: serviceDate,
      service_type: serviceType,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Prediction failed: ${err}`);
  }
  const data = await res.json();
  if (!data.date && data.service_date) data.date = data.service_date;
  return data;
}

export async function getPredictionBatch(
  restaurantId: string,
  dates: string[],
  serviceType: ServiceType
): Promise<BatchPredictionWithSummary> {
  const res = await fetch(`${API_URL}/predict/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      restaurant_id: restaurantId,
      dates,
      service_type: serviceType,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Batch prediction failed: ${err}`);
  }
  const data: BatchPredictionResponse = await res.json();
  return {
    ...data,
    summary: computeBatchSummary(data.predictions),
  };
}

function generateDateRange(startDate: string, days: number): string[] {
  const dates: string[] = [];
  const start = new Date(startDate);
  for (let i = 0; i < days; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    dates.push(d.toISOString().split("T")[0]);
  }
  return dates;
}

/** Week predictions (7 days). startDate: YYYY-MM-DD */
export async function getPredictionWeek(
  restaurantId: string,
  startDate: string,
  serviceType: ServiceType
): Promise<BatchPredictionWithSummary> {
  const dates = generateDateRange(startDate, 7);
  return getPredictionBatch(restaurantId, dates, serviceType);
}

/** Month predictions. month 1-12 (January=1, December=12) */
export async function getPredictionMonth(
  restaurantId: string,
  month: number,
  year: number,
  serviceType: ServiceType
): Promise<BatchPredictionWithSummary> {
  const daysInMonth = new Date(year, month, 0).getDate();
  const dates: string[] = [];
  for (let day = 1; day <= daysInMonth; day++) {
    dates.push(
      `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
    );
  }
  return getPredictionBatch(restaurantId, dates, serviceType);
}

export async function getRestaurantProfile(
  outletName: string
): Promise<RestaurantProfile> {
  const res = await fetch(
    `${API_URL}/api/restaurant/profile/by-name/${outletName}`
  );
  if (!res.ok) {
    if (res.status === 404)
      throw new Error(`Restaurant "${outletName}" not found`);
    throw new Error("Failed to fetch restaurant profile");
  }
  return res.json();
}
