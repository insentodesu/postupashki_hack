export function GET() {
  return Response.json({ ok: true, service: "postupashki-measurement", databaseConfigured: Boolean(process.env.DATABASE_URL) });
}
