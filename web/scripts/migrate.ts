import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { neonConfig, Pool } from "@neondatabase/serverless";
import ws from "ws";

if (typeof globalThis.WebSocket === "undefined") neonConfig.webSocketConstructor = ws;

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) throw new Error("DATABASE_URL не задан. Получите окружение Vercel перед миграцией.");
  const schemaPath = fileURLToPath(new URL("../lib/db/schema.sql", import.meta.url));
  const schema = await readFile(schemaPath, "utf8");
  const statements = schema.split("-- statement-breakpoint").map((statement) => statement.trim()).filter(Boolean);
  const pool = new Pool({ connectionString });
  try { for (const statement of statements) await pool.query(statement); }
  finally { await pool.end(); }
  console.log(`Measurement schema ready (${statements.length} statements).`);
}

main().catch((error) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
