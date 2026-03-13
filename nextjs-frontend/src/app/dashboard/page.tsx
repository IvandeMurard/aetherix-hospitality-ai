'use client';

import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Users, TrendingUp, Calendar, AlertCircle, Sparkles } from 'lucide-react';

export default function DashboardPage() {
  const [data, setData] = useState<{
    occupancy: number;
    revenue: number;
    recommendation: {
      covers: number;
      staffing: { servers: number; kitchen: number; hosts: number };
      rationale: string;
    };
  } | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch forecast and recent metrics
        const res = await fetch('http://localhost:8000/api/v1/predictions/today?property_id=pilot_hotel');
        const result = await res.json();
        
        // Mocking the sync data and prediction combine for the dashboard
        setData({
          occupancy: 92, // Mocked from recent sync
          revenue: 2750.0,
          recommendation: {
            covers: result.prediction.covers,
            staffing: result.staffing,
            rationale: result.reasoning.summary
          }
        });
      } catch (error) {
        console.error('Failed to load dashboard data', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <main className="container mx-auto py-10 px-4 max-w-6xl space-y-8 animate-in fade-in duration-1000">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/40 bg-clip-text text-transparent">
            Operations Center
          </h1>
          <p className="text-muted-foreground flex items-center gap-2">
            <Calendar className="w-4 h-4 text-primary/60" />
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <Badge variant="secondary" className="px-3 py-1 text-sm bg-primary/10 text-primary border-primary/20">
          <Sparkles className="w-3 h-3 mr-1" /> AI Engine Active
        </Badge>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-gradient-to-br from-background to-primary/10 border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">HOTEL OCCUPANCY</CardTitle>
            <AlertCircle className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data?.occupancy}%</div>
            <p className="text-xs text-muted-foreground mt-1">+2.1% from yesterday</p>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-background to-green-500/10 border-green-500/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">F&B REVENUE (SYNC)</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">${data?.revenue.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">Live from Apaleo</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-background to-amber-500/10 border-amber-500/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">PREDICTED COVERS</CardTitle>
            <Users className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data?.recommendation.covers}</div>
            <p className="text-xs text-muted-foreground mt-1">Dinner Tonight</p>
          </CardContent>
        </Card>
      </div>

      {/* Staffing Insight */}
      <Card className="border-primary/20 shadow-lg overflow-hidden">
        <div className="bg-primary/5 px-6 py-4 border-b border-primary/10">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            AI Staffing Intelligence
          </h2>
        </div>
        <CardContent className="pt-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Recommendations</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg bg-accent/30 border">
                  <span className="text-sm font-medium">Servers</span>
                  <Badge variant="outline" className="text-lg px-3">{data?.recommendation.staffing.servers}</Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-accent/30 border">
                  <span className="text-sm font-medium">Kitchen Staff</span>
                  <Badge variant="outline" className="text-lg px-3">{data?.recommendation.staffing.kitchen}</Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-accent/30 border">
                  <span className="text-sm font-medium">Hosts</span>
                  <Badge variant="outline" className="text-lg px-3">{data?.recommendation.staffing.hosts}</Badge>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">The "Why"</h3>
              <div className="p-4 rounded-xl bg-primary/5 border border-primary/10 text-sm leading-relaxed italic text-foreground/80">
                "{data?.recommendation.rationale}"
              </div>
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground px-1">
                <AlertCircle className="w-3 h-3" />
                This recommendation is based on historical F&B patterns, hotel occupancy, and local weather forecasts.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
