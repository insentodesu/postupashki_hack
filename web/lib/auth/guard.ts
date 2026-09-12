import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "./session";

export async function hasValidSession(): Promise<boolean> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  return verifySession(token, process.env.SESSION_SECRET ?? "");
}

export async function requireApiSession(): Promise<Response | null> {
  return (await hasValidSession())
    ? null
    : Response.json({ ok: false, error: "Войдите в панель и повторите действие." }, { status: 401 });
}
