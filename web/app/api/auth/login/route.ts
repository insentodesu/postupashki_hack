import { NextResponse } from "next/server";
import { createSessionToken, passwordMatches, SESSION_COOKIE } from "@/lib/auth/session";

export async function POST(request: Request) {
  const expected = process.env.APP_PASSWORD;
  const secret = process.env.SESSION_SECRET;
  if (!expected || !secret) {
    return NextResponse.json(
      { ok: false, error: "Панель не настроена. Добавьте APP_PASSWORD и SESSION_SECRET." },
      { status: 503 },
    );
  }
  const body = await request.json().catch(() => ({})) as { password?: unknown };
  const supplied = typeof body.password === "string" ? body.password.trim() : "";
  if (!(await passwordMatches(supplied, expected))) {
    return NextResponse.json(
      { ok: false, error: "Пароль не подошёл. Проверьте его и попробуйте снова." },
      { status: 401 },
    );
  }
  const expiresAt = Date.now() + 12 * 60 * 60 * 1000;
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, await createSessionToken(secret, expiresAt), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
  return response;
}
