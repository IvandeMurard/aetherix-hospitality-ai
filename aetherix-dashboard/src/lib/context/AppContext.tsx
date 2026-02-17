"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import { getRestaurantProfile } from "@/lib/api";
import type { ServiceType, RestaurantProfile } from "@/lib/types";

interface Restaurant {
  id: string;
  name: string;
}

interface AppContextType {
  restaurants: Restaurant[];
  selectedRestaurantId: string | null;
  setSelectedRestaurantId: (id: string) => void;
  selectedServiceType: ServiceType;
  setSelectedServiceType: (type: ServiceType) => void;
  restaurantProfile: RestaurantProfile | null;
  isLoadingProfile: boolean;
  profileError: string | null;
  isReady: boolean;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [restaurants] = useState<Restaurant[]>([
    { id: "hotel_main", name: "Main Restaurant" },
    { id: "hotel_bar", name: "Bar" },
    { id: "hotel_terrace", name: "Terrace" },
  ]);
  const [selectedRestaurantId, setSelectedRestaurantId] = useState<
    string | null
  >("hotel_main");
  const [selectedServiceType, setSelectedServiceType] =
    useState<ServiceType>("dinner");
  const [restaurantProfile, setRestaurantProfile] =
    useState<RestaurantProfile | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRestaurantId) {
      setRestaurantProfile(null);
      return;
    }
    let cancelled = false;
    setIsLoadingProfile(true);
    setProfileError(null);
    getRestaurantProfile(selectedRestaurantId)
      .then((profile) => {
        if (!cancelled) setRestaurantProfile(profile);
      })
      .catch((err) => {
        if (!cancelled) {
          setProfileError(err instanceof Error ? err.message : "Failed to load profile");
          setRestaurantProfile(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingProfile(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRestaurantId]);

  const value: AppContextType = {
    restaurants,
    selectedRestaurantId,
    setSelectedRestaurantId,
    selectedServiceType,
    setSelectedServiceType,
    restaurantProfile,
    isLoadingProfile,
    profileError,
    isReady: selectedRestaurantId !== null,
  };

  return (
    <AppContext.Provider value={value}>{children}</AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (ctx === undefined)
    throw new Error("useApp must be used within an AppProvider");
  return ctx;
}

export function usePredictionParams() {
  const { selectedRestaurantId, selectedServiceType, isReady } = useApp();
  if (!isReady || !selectedRestaurantId)
    throw new Error("Restaurant must be selected before making predictions");
  return {
    restaurantId: selectedRestaurantId,
    serviceType: selectedServiceType,
  };
}
