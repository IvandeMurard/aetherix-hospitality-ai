import { redirect } from "next/navigation";

// Root route: redirect straight to the dashboard (Story 1.3 will add auth guard)
export default function HomePage() {
  redirect("/dashboard");
}
