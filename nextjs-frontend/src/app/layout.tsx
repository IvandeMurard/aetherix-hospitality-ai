import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aetherix",
  description: "F&B Operations Agent — AI-powered staffing predictions",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
