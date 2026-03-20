# Aetherix Dashboard

Next.js dashboard for Aetherix F&B forecasting. Connects to the fb-agent-mvp API.

## Setup

```bash
cd aetherix-dashboard
npm install
cp .env.local.example .env.local   # optional, .env.local already has API URL
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The app redirects to `/forecast`.

## Environment

- `NEXT_PUBLIC_API_URL` — API base URL (default: `https://ivandemurard-fb-agent-api.hf.space`)

## Features

- **Sidebar**: Restaurant and service (lunch / brunch / dinner) selection; profile loaded via `/api/restaurant/profile/by-name/{outlet_name}`
- **Forecast page**: Day / Week / Month views; predictions use `restaurant_id`, `service_date`, `service_type`; batch summary computed client-side
- **Types**: Aligned with backend (e.g. `staff_recommendation.servers.recommended`, `confidence` 0–1, `prediction_interval` as `[number, number]`)

## Build

**Depuis la racine du repo** (fb-agent-mvp) :
```bash
npm run build
```

**Ou depuis le dashboard** :
```bash
cd aetherix-dashboard
npm run build
npm start
```

### Si erreur EBUSY / EPERM sous Windows

Un processus (serveur dev, Cursor, autre terminal) garde un verrou sur `node_modules`. À faire :
1. Arrêter tout `npm run dev` (Ctrl+C) et fermer les terminaux qui pointent sur `aetherix-dashboard`.
2. Fermer Cursor (ou au moins le dossier `aetherix-dashboard`) si des fichiers sont ouverts.
3. Supprimer `node_modules` et réinstaller :
   ```bash
   cd aetherix-dashboard
   rmdir /s /q node_modules
   npm install
   npm run build
   ```
4. Ne pas utiliser `npm audit fix --force` : cela peut casser les versions. Next.js est en 15.1.11 (version corrigée).

## Reference

- Migration prompt: `../docs/NEXTJS_MIGRATION_PROMPT.md`
- Backend: `../backend/`
