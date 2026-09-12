import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySession } from "@/lib/auth/session";

const publicPaths = ["/login", "/api/auth/login", "/api/telegram/webhook", "/api/health"];

export default async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isPublic = publicPaths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const valid = await verifySession(token, process.env.SESSION_SECRET ?? "");

  if (!isPublic && !valid) return NextResponse.redirect(new URL("/login", request.url));
  if (pathname === "/login" && valid) return NextResponse.redirect(new URL("/", request.url));
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp)$).*)"],
};
