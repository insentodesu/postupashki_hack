import { neonConfig, Pool } from "@neondatabase/serverless";
import ws from "ws";

if (typeof globalThis.WebSocket === "undefined") neonConfig.webSocketConstructor = ws;

let pool: Pool | undefined;

export function databasePool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL не задан. Подключите Postgres к проекту Vercel.");
  }
  pool ??= new Pool({ connectionString });
  return pool;
}
