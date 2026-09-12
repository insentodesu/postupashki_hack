"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import type { Campaign, Placement } from "@/lib/measurement/types";

type Action = "campaign" | "placement" | "payment" | "simulate" | "import";
export function ActionDock({ campaigns, placements }: { campaigns: Campaign[]; placements: Placement[] }) {
  const router = useRouter(); const [action, setAction] = useState<Action>("campaign");
  const [message, setMessage] = useState(""); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage("");
    const form = event.currentTarget; const data = new FormData(form);
    const endpoints: Record<Action, string> = { campaign: "/api/campaigns", placement: "/api/placements", payment: "/api/orders", simulate: "/api/simulate", import: "/api/import" };
    const payload = action === "import" ? data : Object.fromEntries(data.entries());
    try {
      const response = await fetch(endpoints[action], { method: "POST", ...(action === "import" ? { body: payload as FormData } : { headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }) });
      const result = await response.json(); if (!response.ok) throw new Error(result.error ?? "Действие не выполнено");
      setMessage(result.deepLink ? `Готово: ${result.deepLink}` : action === "import" ? `Импортировано: ${result.imported}, пропущено: ${result.skipped}` : "Готово — данные и атрибуция обновлены.");
      form.reset(); router.refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось выполнить действие"); }
    finally { setPending(false); }
  }
  return <section className="action-dock" aria-labelledby="action-title">
    <div className="section-heading"><div><span className="eyebrow">Рабочая зона</span><h2 id="action-title">Добавить факт в цепочку</h2></div><span className="section-note">Все изменения пересчитывают отчёт</span></div>
    <div className="action-layout"><div className="action-tabs" role="tablist" aria-label="Выберите действие">
      {([['campaign','Кампания'],['placement','Размещение'],['payment','Оплата'],['simulate','Симуляция'],['import','Импорт Excel']] as [Action,string][]).map(([id,label]) => <button key={id} type="button" role="tab" aria-controls="action-form" aria-selected={action === id} className={action === id ? "is-active" : ""} onClick={() => { setAction(id); setMessage(""); }}>{label}</button>)}
    </div><form id="action-form" className="action-form" onSubmit={submit} autoComplete="off">
      {action === "campaign" && <><label>Название<input name="name" required minLength={2} placeholder="Например, осенний набор…" /></label><label>Целевой курс<input name="targetCourse" placeholder="Например, Python-разработчик…" /></label><label>Бюджет, ₽<input name="budget" type="number" min="0" step="100" placeholder="25 000…" /></label><input type="hidden" name="dataOrigin" value="real" /></>}
      {action === "placement" && <><label>Кампания<select name="campaignId" required defaultValue=""><option value="" disabled>Выберите кампанию</option>{campaigns.map(c => <option key={c.campaignId} value={c.campaignId}>{c.name}</option>)}</select></label><label>Канал<input name="channel" required placeholder="Например, Telegram…" /></label><label>Стоимость, ₽<input name="cost" type="number" min="0" step="100" required placeholder="10 000…" /></label><label>Курс<input name="targetCourse" placeholder="Например, Python-разработчик…" /></label><input type="hidden" name="dataOrigin" value="real" /></>}
      {action === "payment" && <><label>User key<input name="userKey" spellCheck={false} placeholder="Пусто = unknown…" /></label><label>Сумма, ₽<input name="amount" type="number" min="1" required placeholder="20 000…" /></label><label>Курс<input name="course" placeholder="Например, Python-разработчик…" /></label><input type="hidden" name="dataOrigin" value="real" /></>}
      {action === "simulate" && <><label>Размещение<select name="placementId" required defaultValue=""><option value="" disabled>Выберите placement</option>{placements.map(p => <option key={p.placementId} value={p.placementId}>{p.channel} · {p.placementId}</option>)}</select></label><label>Сумма оплаты, ₽<input name="amount" type="number" min="1" required defaultValue="20000" /></label><input type="hidden" name="dataOrigin" value="demo" /></>}
      {action === "import" && <label className="file-field">Excel с продажами<input name="file" type="file" accept=".xlsx" required /><span>Русские и английские колонки · до 10&nbsp;МБ</span></label>}
      <div className="form-footer"><button className="primary-button" disabled={pending}>{pending ? "Сохраняем…" : "Сохранить факт"}</button><p role="status" aria-live="polite">{message}</p></div>
    </form></div>
  </section>;
}
