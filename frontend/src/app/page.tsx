import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  BellRing,
  Brain,
  CheckCircle,
  ChevronRight,
  Code2,
  MessageSquare,
  Plug,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="border-b">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="font-bold text-xl tracking-tight">Aetherix</span>
          <Button size="sm">Request Early Access</Button>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <Badge variant="secondary" className="mb-6">
            Agent-First · Human-in-the-Loop · MCP-Ready
          </Badge>
          <h1 className="text-5xl font-bold tracking-tight mb-6 leading-tight">
            The AI agent that sees F&amp;B problems
            <span className="text-primary"> before your managers do</span>
          </h1>
          <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
            Aetherix forecasts covers, detects staffing gaps, and sends
            proactive recommendations via WhatsApp — with full reasoning.
            Human-in-the-loop by design.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Button size="lg">
              Request Early Access{" "}
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline">
              See How It Works
            </Button>
          </div>

          {/* Mock WhatsApp Alert */}
          <div className="mt-16 max-w-sm mx-auto">
            <Card className="text-left border-2">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
                    <MessageSquare className="h-4 w-4 text-white" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold">
                      Aetherix · WhatsApp
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Today, 7:14 AM
                    </p>
                  </div>
                </div>
                <p className="text-sm font-medium mb-1">
                  Staffing alert — Saturday dinner
                </p>
                <p className="text-sm text-muted-foreground mb-3">
                  Forecast: +34 covers vs. last Saturday (+22%). Current
                  schedule covers 68% of demand. Recommended: +2 servers for
                  18h–21h shift.
                </p>
                <div className="flex gap-2">
                  <Badge className="text-xs cursor-pointer bg-primary/10 text-primary hover:bg-primary/20 border-0">
                    Apply reco
                  </Badge>
                  <Badge variant="outline" className="text-xs cursor-pointer">
                    Adjust
                  </Badge>
                  <Badge variant="outline" className="text-xs cursor-pointer">
                    Dismiss
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="py-20 px-6 bg-muted/40">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">
            F&amp;B operations run on gut feeling
          </h2>
          <p className="text-center text-muted-foreground mb-12 max-w-2xl mx-auto">
            Most hotels still plan staffing and prep based on last week's
            numbers and experience. The result is predictable.
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                stat: "30–50%",
                label: "of staffing shifts are over or under-resourced",
                detail:
                  "Overtime costs or poor guest experience — both hit the P&L.",
              },
              {
                stat: "25%",
                label: "of food prepared is wasted on average",
                detail:
                  "ADEME/Accor: ~115g per cover. Invisible cost until you measure it.",
              },
              {
                stat: "0h",
                label: "of advance warning before service peaks",
                detail:
                  "Managers react. Aetherix anticipates — 48h ahead by default.",
              },
            ].map((item) => (
              <Card key={item.stat}>
                <CardContent className="p-6">
                  <p className="text-4xl font-bold text-primary mb-2">
                    {item.stat}
                  </p>
                  <p className="font-semibold mb-2">{item.label}</p>
                  <p className="text-sm text-muted-foreground">{item.detail}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">
            How Aetherix works
          </h2>
          <p className="text-center text-muted-foreground mb-12 max-w-xl mx-auto">
            Three steps. No dashboards to check. Recommendations land where
            managers already are.
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "01",
                icon: <Plug className="h-6 w-6" />,
                title: "Connect your PMS",
                description:
                  "Apaleo or Mews. OAuth2, read-only. Setup in under 10 minutes. Historical data ingested automatically.",
              },
              {
                step: "02",
                icon: <TrendingUp className="h-6 w-6" />,
                title: "Forecast + detect gaps",
                description:
                  "Prophet model + Claude Sonnet reason over occupancy, weather, local events, and your hotel's own history.",
              },
              {
                step: "03",
                icon: <BellRing className="h-6 w-6" />,
                title: "Act with confidence",
                description:
                  "Recommendations arrive on WhatsApp with full reasoning. One tap to apply, adjust, or dismiss. You stay in control.",
              },
            ].map((item) => (
              <div key={item.step} className="flex flex-col gap-4">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono text-muted-foreground">
                    {item.step}
                  </span>
                  <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                    {item.icon}
                  </div>
                </div>
                <h3 className="text-lg font-semibold">{item.title}</h3>
                <p className="text-sm text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6 bg-muted/40">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            Built for F&amp;B operations
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                icon: <TrendingUp className="h-5 w-5 text-primary" />,
                title: "F&B Forecasting",
                description:
                  "Cover predictions per service (breakfast, lunch, dinner) with <15% MAPE. Regressors: occupancy, local events, weather, day-of-week patterns.",
              },
              {
                icon: <BellRing className="h-5 w-5 text-primary" />,
                title: "Proactive WhatsApp Alerts",
                description:
                  "Push-first, UI-less delivery. Managers receive actionable alerts 48h ahead — not a dashboard to refresh. Ambient intelligence.",
              },
              {
                icon: <Users className="h-5 w-5 text-primary" />,
                title: "Human-in-the-Loop",
                description:
                  "No auto-actions. 63% of managers want control. Every recommendation requires one conscious decision — which also becomes training data.",
              },
              {
                icon: <Brain className="h-5 w-5 text-primary" />,
                title: "Adaptive Memory per Property",
                description:
                  "Aetherix learns what works specifically for your hotel — capture rates, manager preferences, local patterns. Private memory that compounds over time.",
              },
            ].map((feature) => (
              <Card key={feature.title}>
                <CardContent className="p-6 flex gap-4">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    {feature.icon}
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">{feature.title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {feature.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* For Builders */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 justify-center mb-4">
            <Code2 className="h-5 w-5 text-primary" />
            <Badge variant="secondary">For Apaleo &amp; Mews Builders</Badge>
          </div>
          <h2 className="text-3xl font-bold text-center mb-4">
            A primitive in your agent stack
          </h2>
          <p className="text-center text-muted-foreground mb-12 max-w-2xl mx-auto">
            Aetherix isn&apos;t just a product — it&apos;s an agent-callable
            capability. MCP-ready, so your agents can call it directly.
          </p>
          <div className="grid md:grid-cols-2 gap-8 items-start">
            <div className="space-y-4">
              {[
                {
                  label: "PMS-agnostic",
                  detail:
                    "Apaleo + Mews. OAuth2, read-only. Swap PMS without touching Aetherix.",
                },
                {
                  label: "MCP Server (Phase 0.5)",
                  detail:
                    "forecast_occupancy, get_stock_alerts, recommend_menu, get_fb_kpis — callable by any MCP-compatible agent.",
                },
                {
                  label: "A2A Communication",
                  detail:
                    "Your revenue agent detects +18% occupancy → calls Aetherix → staffing reco updates in real time.",
                },
                {
                  label: "Agent SEO metrics",
                  detail:
                    "tool_success_rate >99.5%, p95_latency <500ms, schema_stability = 0 breaking changes per sprint.",
                },
                {
                  label: "OpenAPI auto-generated",
                  detail:
                    "FastAPI + Pydantic v2. Full schema available. Clients generated from spec.",
                },
              ].map((item) => (
                <div key={item.label} className="flex gap-3">
                  <CheckCircle className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">{item.label}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      — {item.detail}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <Card className="font-mono text-sm bg-foreground text-background">
              <CardContent className="p-6">
                <p className="text-muted-foreground mb-4">
                  # MCP call example
                </p>
                <p>
                  <span className="text-primary">tool</span>:
                  forecast_occupancy
                </p>
                <p>
                  <span className="text-primary">params</span>:
                </p>
                <p className="pl-4">
                  hotel_id:{" "}
                  <span className="text-green-400">&quot;hotel_abc&quot;</span>
                </p>
                <p className="pl-4">
                  date_range:{" "}
                  <span className="text-green-400">
                    &quot;2026-03-25/2026-03-31&quot;
                  </span>
                </p>
                <br />
                <p className="text-muted-foreground"># Response</p>
                <p>
                  <span className="text-primary">covers_forecast</span>: 847
                </p>
                <p>
                  <span className="text-primary">confidence</span>: 0.91
                </p>
                <p>
                  <span className="text-primary">staffing_gap</span>:{" "}
                  <span className="text-yellow-400">+2 servers</span>
                </p>
                <p>
                  <span className="text-primary">latency_ms</span>: 312
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* KPIs */}
      <section className="py-20 px-6 bg-primary text-primary-foreground">
        <div className="max-w-5xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-12">Target outcomes</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: "–3–8%", label: "Labor cost vs baseline" },
              { value: "–30–50%", label: "Staffing incidents" },
              { value: "<15%", label: "Forecast MAPE on covers" },
              { value: "48h", label: "Alert lead time" },
            ].map((kpi) => (
              <div key={kpi.label}>
                <p className="text-4xl font-bold mb-2">{kpi.value}</p>
                <p className="text-sm text-primary-foreground/70">
                  {kpi.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <Zap className="h-10 w-10 text-primary mx-auto mb-6" />
          <h2 className="text-4xl font-bold mb-4">
            Ready to make F&amp;B proactive?
          </h2>
          <p className="text-muted-foreground mb-8">
            We&apos;re onboarding early hotel partners. If you manage F&amp;B
            operations or build on top of Apaleo/Mews, let&apos;s talk.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Button size="lg">
              Request Early Access{" "}
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline">
              View on GitHub
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-6">
            Built with FastAPI · Claude Sonnet · Prophet · Qdrant · Next.js
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">Aetherix</span>
          <span>F&amp;B Operations Agent · Agent-First · Human-in-the-Loop</span>
        </div>
      </footer>
    </div>
  );
}
