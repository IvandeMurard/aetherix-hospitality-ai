import type { Metadata } from "next";
import { AppProvider } from "@/lib/context/AppContext";
import { Sidebar } from "@/components/layout/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aetherix — Intelligent F&B Forecasting",
  description: "AI-powered demand prediction for hotel F&B operations",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProvider>
          <div className="flex h-screen bg-slate-50">
            <Sidebar />
            <main className="flex-1 overflow-auto p-8">{children}</main>
          </div>
        </AppProvider>
      </body>
    </html>
  );
}
