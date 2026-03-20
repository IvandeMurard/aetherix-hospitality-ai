"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  History,
  Settings,
  Sparkles,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/context/AppContext";
import type { ServiceType } from "@/lib/types";

const navigation = [
  { name: "Forecast", href: "/forecast", icon: BarChart3 },
  { name: "History", href: "/history", icon: History },
  { name: "Settings", href: "/settings", icon: Settings },
];

const serviceTypes: { value: ServiceType; label: string }[] = [
  { value: "lunch", label: "Lunch" },
  { value: "brunch", label: "Brunch" },
  { value: "dinner", label: "Dinner" },
];

export function Sidebar() {
  const pathname = usePathname();
  const {
    restaurants,
    selectedRestaurantId,
    setSelectedRestaurantId,
    selectedServiceType,
    setSelectedServiceType,
    restaurantProfile,
    isLoadingProfile,
  } = useApp();

  return (
    <aside className="flex w-64 flex-col bg-green-900 text-white">
      <div className="p-6">
        <h1 className="text-2xl font-bold">Aetherix</h1>
        <p className="text-sm text-green-300">Intelligent forecasting</p>
      </div>

      <nav className="space-y-1 px-4">
        <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-green-400">
          Navigation
        </p>
        {navigation.map((item) => {
          const isActive =
            pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-green-800 text-white" : "text-green-100 hover:bg-green-800/50"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="mt-8 space-y-4 px-4">
        <p className="px-3 text-xs font-semibold uppercase tracking-wider text-green-400">
          Context
        </p>
        <div className="space-y-2">
          <label className="px-3 text-xs text-green-300">Restaurant</label>
          <Select
            value={selectedRestaurantId ?? undefined}
            onValueChange={setSelectedRestaurantId}
          >
            <SelectTrigger className="border-green-700 bg-green-800 text-white">
              <SelectValue placeholder="Select restaurant" />
            </SelectTrigger>
            <SelectContent>
              {restaurants.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <label className="px-3 text-xs text-green-300">Service</label>
          <Select
            value={selectedServiceType}
            onValueChange={(v) => setSelectedServiceType(v as ServiceType)}
          >
            <SelectTrigger className="border-green-700 bg-green-800 text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {serviceTypes.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="mt-8 px-4">
        <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-green-400">
          Data
        </p>
        <div className="space-y-1 px-3 text-sm text-green-200">
          {isLoadingProfile ? (
            <p className="text-green-400">Loading...</p>
          ) : restaurantProfile ? (
            <>
              <p>Seats: {restaurantProfile.total_seats}</p>
              <p>
                Break-even:{" "}
                {restaurantProfile.breakeven_covers ?? "—"}
              </p>
              <p>Target: {restaurantProfile.target_covers ?? "—"}</p>
            </>
          ) : (
            <>
              <p>Patterns: 495</p>
              <p>Period: 2015-2017</p>
            </>
          )}
        </div>
      </div>

      <div className="mt-8 px-4">
        <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-green-400">
          Coming Soon
        </p>
        <div className="space-y-1">
          {["PMS Integration", "Staff Planner", "Inventory", "Alerts"].map(
            (item) => (
              <div
                key={item}
                className="flex items-center gap-2 px-3 py-1 text-sm text-green-300"
              >
                <Sparkles className="h-3 w-3" />
                {item}
              </div>
            )
          )}
        </div>
      </div>

      <div className="flex-1" />

      <div className="border-t border-green-800 p-4">
        <div className="flex items-center justify-between text-sm text-green-300">
          <span>? Help</span>
          <Select defaultValue="en">
            <SelectTrigger className="w-20 border-green-700 bg-green-800 text-xs text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">EN</SelectItem>
              <SelectItem value="fr">FR</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </aside>
  );
}
