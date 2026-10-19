'use client';

import { use, useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// ---------------------------------------------------------------------------
// Types mirroring backend ReceiptPayload / ReceiptLine / MemoryHitSummary
// and KPI endpoint (HOS-177)
// ---------------------------------------------------------------------------

interface DailyRate {
  date: string;
  rate: number | null;
}

interface TrustKpiData {
  rolling_rate: number | null;
  trend: 'up' | 'down' | 'flat';
  daily: DailyRate[];
}

interface MemoryHitSummary {
  memory_id: string;
  reflection_snippet: string;
  manager_feedback: string | null;
  memory_type: string;
  created_at: string;
}

interface ReceiptLine {
  timestamp: string;
  tool_name: string;
  status: string;
  request_id: string;
  latency_ms: number | null;
  error_code: string | null;
  dedup_hit: boolean | null;
  top_similarity: number | null;
  memory_hits: MemoryHitSummary[];
}

interface ReceiptPayload {
  hotel_id: string;
  receipt_date: string;
  generated_at: string;
  total_actions: number;
  counts_by_status: Record<string, number>;
  counts_by_tool: Record<string, number>;
  lines: ReceiptLine[];
}

// ---------------------------------------------------------------------------
// Status badge color mapping
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === 'ok'
      ? 'default'
      : status === 'rate_limited' || status === 'rate_limit_fallback'
      ? 'secondary'
      : 'destructive';
  return <Badge variant={variant as 'default' | 'secondary' | 'destructive' | 'outline'}>{status}</Badge>;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ReceiptDrillDownPage({
  params,
}: {
  params: Promise<{ hotel: string; date: string }>;
}) {
  // Next 15+ passes route params as a Promise.
  const { hotel, date } = use(params);
  const [payload, setPayload] = useState<ReceiptPayload | null>(null);
  const [trustKpi, setTrustKpi] = useState<TrustKpiData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = typeof window !== 'undefined'
      ? new URLSearchParams(window.location.search).get('token')
      : null;

    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const receiptUrl = `${baseUrl}/api/v1/receipts/${hotel}/${date}`;
    const kpiUrl = `${baseUrl}/api/v1/kpi/${hotel}/recommendation_acceptance?days=7`;

    const receiptFetch = fetch(receiptUrl, { headers })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `HTTP ${res.status}`);
        }
        return res.json() as Promise<ReceiptPayload>;
      })
      .then(setPayload);

    const kpiFetch = fetch(kpiUrl, { headers })
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json() as TrustKpiData;
        setTrustKpi(data);
      })
      .catch(() => undefined); // KPI card is non-blocking; silently skip on error

    Promise.all([receiptFetch, kpiFetch])
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [hotel, date]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-10 px-4 max-w-3xl">
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive font-medium">Failed to load receipt: {error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!payload) return null;

  return (
    <main className="container mx-auto py-8 px-4 max-w-3xl space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">
          Daily Receipt — {payload.receipt_date}
        </h1>
        <p className="text-sm text-muted-foreground">Hotel: {payload.hotel_id}</p>
      </div>

      {/* Trust KPI — 7-day rolling acceptance rate (HOS-177) */}
      {trustKpi && (
        <Card>
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
              7-Day Trust Rate
            </p>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold">
                {trustKpi.rolling_rate !== null
                  ? `${(trustKpi.rolling_rate * 100).toFixed(0)}%`
                  : '—'}
              </p>
              <Badge
                variant={
                  trustKpi.trend === 'up'
                    ? 'default'
                    : trustKpi.trend === 'down'
                    ? 'destructive'
                    : 'secondary'
                }
              >
                {trustKpi.trend === 'up' ? '▲' : trustKpi.trend === 'down' ? '▼' : '—'}
              </Badge>
              {trustKpi.rolling_rate !== null && trustKpi.rolling_rate < 0.30 && (
                <Badge variant="destructive" className="text-xs">below 30% threshold</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Actions</p>
            <p className="text-2xl font-bold">{payload.total_actions}</p>
          </CardContent>
        </Card>
        {Object.entries(payload.counts_by_status).map(([status, count]) => (
          <Card key={status}>
            <CardContent className="pt-4 pb-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{status}</p>
              <p className="text-2xl font-bold">{count}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Action timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Agent Action Timeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {payload.lines.length === 0 && (
            <p className="text-sm text-muted-foreground">No actions recorded for this date.</p>
          )}
          {payload.lines.map((line, idx) => (
            <div key={`${line.request_id}-${idx}`} className="border rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="text-sm font-medium">{line.tool_name}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={line.status} />
                  {line.latency_ms != null && (
                    <span className="text-xs text-muted-foreground">{line.latency_ms} ms</span>
                  )}
                </div>
              </div>

              <div className="text-xs text-muted-foreground flex flex-wrap gap-3">
                <span>{new Date(line.timestamp).toLocaleTimeString()}</span>
                {line.dedup_hit && <Badge variant="outline" className="text-xs">dedup hit</Badge>}
                {line.top_similarity != null && (
                  <span>similarity: {(line.top_similarity * 100).toFixed(0)}%</span>
                )}
              </div>

              {/* Memory hits */}
              {line.memory_hits.length > 0 && (
                <div className="mt-2 space-y-1.5 border-t pt-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Memory Hits ({line.memory_hits.length})
                  </p>
                  {line.memory_hits.map((hit) => (
                    <div
                      key={hit.memory_id}
                      className="rounded bg-muted/50 px-3 py-2 text-xs space-y-1"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">{hit.memory_type}</Badge>
                        {hit.manager_feedback && (
                          <Badge variant="secondary" className="text-xs">{hit.manager_feedback}</Badge>
                        )}
                      </div>
                      <p className="text-muted-foreground leading-snug">{hit.reflection_snippet}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground text-center pb-4">
        Generated at {new Date(payload.generated_at).toLocaleString()}
      </p>
    </main>
  );
}
