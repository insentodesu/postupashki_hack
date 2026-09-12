"use client";

import { FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export function LoginForm() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password: form.get("password") }),
      });
      const result = await response.json() as { ok: boolean; error?: string };
      if (!result.ok) {
        setError(result.error ?? "Не удалось войти. Попробуйте снова.");
        requestAnimationFrame(() => input.current?.focus());
        return;
      }
      router.replace("/");
      router.refresh();
    } catch {
      setError("Нет связи с сервером. Проверьте интернет и попробуйте снова.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <label htmlFor="dashboard-password">Пароль панели</label>
      <input
        ref={input}
        id="dashboard-password"
        name="password"
        type="password"
        autoComplete="current-password"
        placeholder="Введите пароль…"
        required
      />
      <button type="submit" disabled={pending}>
        {pending ? "Входим…" : "Открыть панель"}
      </button>
      <p className="form-status" aria-live="polite">{error}</p>
    </form>
  );
}
