# Cursor Prompt — Next.js Migration (Final)

## Corrections applied vs original prompt

| Élément | Avant (faux) | Après (correct) |
|--------|--------------|-----------------|
| Restaurant profile endpoint | `GET /api/restaurant/profile` | `GET /api/restaurant/profile/by-name/{outlet_name}` |
| Service types | lunch, dinner, brunch, breakfast | lunch, dinner, brunch **uniquement** |
| `staff_recommendation.servers` | `2` (number) | `{ recommended: 2, usual: 3, delta: -1 }` (object) |
| `confidence` | `"High"` (string) | `0.85` (number 0-1) |
| `reasoning` | `{ day_of_week_pattern, ... }` | `{ summary, patterns_used, confidence_factors }` |
| Batch response | `{ predictions, summary }` | `{ predictions, count }` — **summary calculé côté client** |
| `breakeven_covers` | `break_even_covers` | `breakeven_covers` (pas d'underscore) |
| `prediction_interval` | `{ lower, upper }` | `[number, number]` (array) |
| `covers_per_staff` | `Record<string, number>` | `number` (float) |
| `patterns_used` | `number` | `Array<Pattern>` (liste d'objets) |
| `RestaurantProfile` | `min_kitchen_staff` | `min_boh_staff` |
| Single prediction | `date` | `service_date` (backend) — mapper en `date` côté client |

---

## Architecture

```
AppProvider (Context)
├── selectedRestaurantId: string (outlet_name)
├── selectedServiceType: "lunch" | "dinner" | "brunch"
├── restaurantProfile: from API (by-name endpoint)
└── isReady: boolean

Sidebar
├── Restaurant dropdown → setSelectedRestaurantId
├── Service dropdown → setSelectedServiceType (3 options seulement)
└── Navigation links

ForecastPage
├── useApp() pour lire restaurantId, serviceType
├── API calls avec transformation
└── Summary calculé côté client pour batch
```

---

## Task 1: Create Project

```bash
npx create-next-app@latest aetherix-dashboard --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
cd aetherix-dashboard
npx shadcn-ui@latest init
npx shadcn-ui@latest add card button select tabs skeleton badge separator
npm install recharts lucide-react date-fns
```

---

## Task 2: File Structure

```
src/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   ├── page.tsx              # Redirect to /forecast
│   └── forecast/
│       └── page.tsx
├── components/
│   ├── layout/
│   │   └── Sidebar.tsx
│   ├── forecast/
│   │   ├── HeroCard.tsx
│   │   ├── KPICards.tsx
│   │   ├── ForecastChart.tsx
│   │   └── WhyThisForecast.tsx
│   └── ui/
└── lib/
    ├── api.ts
    ├── types.ts
    ├── utils.ts
    └── context/
        └── AppContext.tsx
```

---

## Task 3: Environment

`.env.local`:
```
NEXT_PUBLIC_API_URL=https://ivandemurard-fb-agent-api.hf.space
```

---

## Task 4: Types (`src/lib/types.ts`)

**Types alignés avec le backend fb-agent-mvp.**

```typescript
export type ServiceType = "lunch" | "dinner" | "brunch";
// PAS de "breakfast"

// --- Staff (nested objects) ---
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
  covers_per_staff: number;  // float, PAS Record<string, number>
}

// --- Reasoning ---
export interface Pattern {
  pattern_id: string;
  date: string;
  actual_covers: number;
  similarity: number;
  event_type?: string;
}

export interface Reasoning {
  summary: string;
  patterns_used: Pattern[];  // Liste d'objets, PAS number
  confidence_factors: string[];
}

// --- Accuracy ---
export interface AccuracyMetrics {
  method?: string;
  prediction_interval?: [number, number];  // [low, high] — array, PAS { lower, upper }
}

// --- Day Prediction ---
export interface DayPrediction {
  date?: string;             // Batch: présent | Single: utiliser service_date
  service_date?: string;      // Single: backend renvoie ceci
  predicted_covers: number;
  confidence: number;         // 0-1, PAS string
  staff_recommendation: StaffRecommendation;
  reasoning: Reasoning;
  accuracy_metrics?: AccuracyMetrics;
}

// --- Batch ---
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

// --- Restaurant Profile ---
export interface RestaurantProfile {
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
  min_boh_staff: number;      // PAS min_kitchen_staff
}

// --- UI transform ---
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
```

---

## Task 5: API Client (`src/lib/api.ts`)

**Points clés :**
- `prediction_interval` est `[low, high]` — utiliser `[0]` et `[1]`
- Single prediction : mapper `service_date` → `date` si besoin
- `computeBatchSummary()` côté client
- `transformPredictionForDisplay()` pour les composants UI

```typescript
function computeRange(prediction: DayPrediction): { min: number; max: number } {
  const interval = prediction.accuracy_metrics?.prediction_interval;
  if (interval && Array.isArray(interval) && interval.length >= 2) {
    return { min: interval[0], max: interval[1] };
  }
  const margin = Math.round(prediction.predicted_covers * 0.15);
  return {
    min: prediction.predicted_covers - margin,
    max: prediction.predicted_covers + margin,
  };
}

export function transformPredictionForDisplay(prediction: DayPrediction): DayPredictionDisplay {
  const range = computeRange(prediction);
  const dateStr = prediction.date ?? prediction.service_date ?? "";
  return {
    date: dateStr,
    predicted_covers: prediction.predicted_covers,
    confidence_label: confidence >= 0.8 ? "High" : confidence >= 0.5 ? "Medium" : "Low",
    confidence_score: prediction.confidence,
    range_min: range.min,
    range_max: range.max,
    servers: prediction.staff_recommendation.servers.recommended,
    reasoning_summary: prediction.reasoning.summary,
  };
}

export async function getRestaurantProfile(outletName: string): Promise<RestaurantProfile> {
  const res = await fetch(`${API_URL}/api/restaurant/profile/by-name/${outletName}`);
  if (!res.ok) throw new Error("Profile not found");
  return res.json();
}

// getPredictionBatch : après res.json(), ajouter summary: computeBatchSummary(data.predictions)
```

**`getPredictionMonth(month, year)`** : `month` en 1–12 (January=1, December=12). Documenter dans le code.

---

## Task 6: Context (`src/lib/context/AppContext.tsx`)

- `selectedRestaurantId` = `outlet_name` (ex: `"hotel_main"`)
- `selectedServiceType` = `"lunch" | "dinner" | "brunch"` uniquement
- Profile : `getRestaurantProfile(selectedRestaurantId)`
- Hook `usePredictionParams()` pour garantir les paramètres

---

## Task 7: Sidebar

- Service types : 3 options (lunch, brunch, dinner) — **PAS breakfast**
- Select : `value={selectedRestaurantId || undefined}` (PAS `""`)
- `restaurantProfile.breakeven_covers` peut être `null` — gérer l'affichage

---

## Task 8: Forecast Page

```typescript
// confidence: nombre 0-1 → label
const confidenceLabel = prediction.confidence >= 0.8 ? "High"
  : prediction.confidence >= 0.5 ? "Medium" : "Low";

// servers: objet → nombre
const servers = prediction.staff_recommendation.servers.recommended;

// Single prediction: utiliser service_date si date absent
const dateStr = prediction.date ?? prediction.service_date ?? "";
```

---

## Task 9: Home Redirect

`src/app/page.tsx`:
```typescript
import { redirect } from "next/navigation";
export default function Home() { redirect("/forecast"); }
```

---

## Validation Checklist

- [ ] Service dropdown : 3 options (lunch, brunch, dinner) — PAS breakfast
- [ ] Restaurant profile : `/api/restaurant/profile/by-name/{id}`
- [ ] `confidence` (0-1) converti en label pour l'UI
- [ ] `staff_recommendation.servers.recommended` utilisé (pas `.servers` direct)
- [ ] Batch summary calculé via `computeBatchSummary()`
- [ ] Select value : `undefined` pas `""`
- [ ] `prediction_interval` lu comme `interval[0]` et `interval[1]`
- [ ] Single prediction : `date` ou `service_date` géré
- [ ] `RestaurantProfile` : `min_boh_staff`, `breakeven_covers` nullable

---

## DO NOT

- Ajouter "breakfast" aux service types
- Utiliser `GET /api/restaurant/profile` (endpoint incorrect)
- Attendre `summary` dans la réponse batch
- Traiter `confidence` comme string
- Accéder à `staff_recommendation.servers` comme number
- Utiliser `prediction_interval.lower` / `.upper` (c'est un array)
- Utiliser `min_kitchen_staff` (backend: `min_boh_staff`)
