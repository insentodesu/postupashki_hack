import { redirect } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { hasValidSession } from "@/lib/auth/guard";
import { postgresRepository } from "@/lib/db/repository";
import { demoSnapshot } from "@/lib/demo";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<{ view?: string; origin?: string }> }) {
  if (!await hasValidSession()) redirect("/login");
  const query = await searchParams;
  let snapshot = demoSnapshot; let connected = false; let warning: string | null = null;
  if (process.env.DATABASE_URL) {
    try { snapshot = await postgresRepository().dashboardSnapshot(); connected = true; }
    catch { warning = "База временно недоступна — показываем безопасный демо-срез."; }
  }
  const origins = new Set(["real", "synthetic", "demo"]);
  const origin = origins.has(query.origin ?? "") ? query.origin! : "all";
  if (origin !== "all") {
    const orders = snapshot.orders.filter((item) => item.dataOrigin === origin);
    const orderIds = new Set(orders.map((item) => item.orderId));
    snapshot = {
      campaigns: snapshot.campaigns.filter((item) => item.dataOrigin === origin),
      placements: snapshot.placements.filter((item) => item.dataOrigin === origin),
      touches: snapshot.touches.filter((item) => item.dataOrigin === origin),
      leads: snapshot.leads.filter((item) => item.dataOrigin === origin),
      orders,
      attributions: snapshot.attributions.filter((item) => orderIds.has(item.orderId)),
    };
  }
  return <DashboardShell snapshot={snapshot} view={query.view ?? "overview"} origin={origin} connected={connected} warning={warning} botUsername={process.env.BOT_USERNAME ?? "postupashki_demo_bot"} />;
}
