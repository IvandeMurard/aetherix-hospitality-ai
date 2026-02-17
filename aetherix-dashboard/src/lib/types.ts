// src/lib/types.ts — Aligned with backend fb-agent-mvp

export type ServiceType = "lunch" | "dinner" | "brunch";

export interface StaffRoleRecommendation {
  recommended: number;
  usual: number;
  delta: number;
}

export interface StaffRecommendation {
  servers: StaffRoleRecommendation;
  hosts: StaffRoleRecommendation;
  kitchen: StaffRoleRecommendation;
  rationale: string;
  covers_per_staff: number;
}

export interface Pattern {
  pattern_id: string;
  date: string;
  actual_covers: number;
  similarity: number;
  event_type?: string;
}

export interface Reasoning {
  summary: string;
  patterns_used: Pattern[];
  confidence_factors: string[];
}

export interface AccuracyMetrics {
  method?: string;
  prediction_interval?: [number, number];
}

export interface DayPrediction {
  date?: string;
  service_date?: string;
  predicted_covers: number;
  confidence: number;
  staff_recommendation: StaffRecommendation;
  reasoning: Reasoning;
  accuracy_metrics?: AccuracyMetrics;
}

export interface BatchPredictionResponse {
  predictions: DayPrediction[];
  count: number;
  service_type: ServiceType;
  restaurant_id: string;
}

export interface BatchSummary {
  total_covers: number;
  daily_avg: number;
  peak_day: { date: string; covers: number };
  avg_confidence: number;
}

export interface BatchPredictionWithSummary extends BatchPredictionResponse {
  summary: BatchSummary;
}

export interface RestaurantProfile {
  id?: string;
  property_name: string;
  outlet_name: string;
  outlet_type: string;
  total_seats: number;
  breakeven_covers: number | null;
  target_covers: number | null;
  covers_per_server: number;
  covers_per_host: number;
  covers_per_runner: number;
  covers_per_kitchen: number;
  min_foh_staff: number;
  min_boh_staff: number;
}

export interface DayPredictionDisplay {
  date: string;
  predicted_covers: number;
  confidence_label: string;
  confidence_score: number;
  range_min: number;
  range_max: number;
  servers: number;
  reasoning_summary: string;
}
