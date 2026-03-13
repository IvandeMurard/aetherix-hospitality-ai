'use client';

import PmsStatusCard from '@/components/features/PmsStatusCard';

export default function SettingsPage() {
  return (
    <main className="container mx-auto py-10 px-4 max-w-4xl space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="space-y-2">
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
          Settings
        </h1>
        <p className="text-muted-foreground">
          Configure your property details and integration preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PMS Section */}
        <PmsStatusCard />

        {/* Placeholder for future settings sections (Story 4.1) */}
        <div className="rounded-xl border bg-card/50 text-card-foreground shadow-sm flex flex-col items-center justify-center p-8 border-dashed opacity-60">
          <p className="text-sm text-center text-muted-foreground">
            More settings coming soon in Story 4.1<br/>
            (WhatsApp, Notifications, and Geofencing)
          </p>
        </div>
      </div>
    </main>
  );
}
