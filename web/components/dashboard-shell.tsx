import Link from "next/link";
import { ActionDock } from "./action-dock";
import { buildRomiRows, unknownRevenue } from "@/lib/measurement/romi";
import type { DashboardSnapshot, DataOrigin } from "@/lib/measurement/types";
import { buildDeepLink } from "@/lib/measurement/tracking";

const rub = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("ru-RU");
const pct = (value: number | null) => value == null ? "N/A" : `${Math.round(value * 100)}%`;
const date = (value: string) => new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
const originLabel: Record<DataOrigin, string> = { real: "real", synthetic: "synthetic", demo: "demo" };

export function DashboardShell({ snapshot, view, origin, connected, warning, botUsername }: { snapshot: DashboardSnapshot; view: string; origin: string; connected: boolean; warning: string | null; botUsername: string }) {
  const totalRevenue = snapshot.orders.reduce((sum, item) => sum + item.amount, 0);
  const attributedRevenue = snapshot.attributions.filter(a => a.placementId).reduce((sum, item) => sum + item.revenueCredit, 0);
  const unknown = unknownRevenue(snapshot.orders, snapshot.attributions);
  const romi = buildRomiRows(snapshot.placements, snapshot.attributions);
  const nav = [{ id: "overview", label: "Сводка" }, { id: "registry", label: "Реестр" }, { id: "operations", label: "Операции" }];
  return <div className="app-shell"><a className="skip-link" href="#main-content">К содержанию</a>
    <aside className="sidebar">
      <Link href="/?view=overview" className="brand"><span className="brand-mark">П</span><span><b>Поступашки</b><small>measurement desk</small></span></Link>
      <nav aria-label="Основная навигация">{nav.map(item => <Link key={item.id} href={`/?view=${item.id}&origin=${origin}`} aria-current={view === item.id ? "page" : undefined}>{item.label}<span>↗</span></Link>)}</nav>
      <div className="sidebar-foot"><span className={`status-dot ${connected ? "online" : ""}`} />{connected ? "Postgres подключён" : "Демо-режим"}<small>Attribution ≠ incrementality</small></div>
    </aside>
    <main className="workspace" id="main-content">
      <header className="topbar"><div><span className="eyebrow">Marketing measurement</span><h1>{view === "registry" ? "Реестр доказательств" : view === "operations" ? "Операционный контур" : "Что принесло выручку"}</h1></div><div className="topbar-actions"><span className={`connection ${connected ? "connected" : ""}`}>{connected ? "Live data" : "Demo slice"}</span><form action="/api/auth/logout" method="post"><button className="quiet-button">Выйти</button></form></div></header>
      {warning && <p className="notice" role="status">{warning}</p>}
      <div className="filter-row" aria-label="Фильтр происхождения данных"><span>Источник</span>{["all","real","synthetic","demo"].map(item => <Link key={item} href={`/?view=${view}&origin=${item}`} className={origin === item ? "selected" : ""}>{item === "all" ? "все" : item}</Link>)}</div>
      {view === "registry" ? <Registry snapshot={snapshot} botUsername={botUsername} /> : view === "operations" ? <ActionDock campaigns={snapshot.campaigns} placements={snapshot.placements} /> : <Overview snapshot={snapshot} totalRevenue={totalRevenue} attributedRevenue={attributedRevenue} unknown={unknown} romi={romi} />}
      <footer><span>Last-touch · окно 30 дней · revenue-based ROMI</span><span>ROMI_inc недоступен без эксперимента</span></footer>
    </main>
  </div>;
}

function Overview({ snapshot, totalRevenue, attributedRevenue, unknown, romi }: { snapshot: DashboardSnapshot; totalRevenue: number; attributedRevenue: number; unknown: number; romi: ReturnType<typeof buildRomiRows> }) {
  const unknownShare = totalRevenue ? unknown / totalRevenue : 0;
  const attributionByOrder = new Map(snapshot.attributions.map((item) => [item.orderId, item]));
  return <div className="view-stack">
    <section className="metric-grid" aria-label="Ключевые показатели">
      <Metric label="Выручка" value={rub.format(totalRevenue)} note={`${num.format(snapshot.orders.length)} оплат`} tone="ink" />
      <Metric label="Атрибутировано" value={rub.format(attributedRevenue)} note={`${Math.round((totalRevenue ? attributedRevenue / totalRevenue : 0) * 100)}% выручки связано`} tone="blue" />
      <Metric label="Unknown revenue" value={rub.format(unknown)} note={`${Math.round(unknownShare * 100)}% требует расследования`} tone="amber" />
      <Metric label="Лиды" value={num.format(snapshot.leads.length)} note={`${snapshot.touches.length} касаний`} tone="green" />
    </section>
    <section className="ledger-card flow-card"><div className="section-heading"><div><span className="eyebrow">North Star</span><h2>Доказательная цепочка</h2></div><span className="section-note">от публикации до оплаты</span></div><div className="flow-rail">
      {[['01','Placement',snapshot.placements.length,'метки созданы'],['02','Touch',snapshot.touches.length,'переходы связаны'],['03','Lead',snapshot.leads.length,'интерес зафиксирован'],['04','Revenue',rub.format(totalRevenue),'оплаты подтверждены']].map(([step,label,value,note], index) => <div className="flow-step" key={String(label)}><span>{step}</span><b>{label}</b><strong>{value}</strong><small>{note}</small>{index < 3 && <i aria-hidden="true">→</i>}</div>)}
    </div></section>
    <section className="two-column"><div className="ledger-card"><div className="section-heading"><div><span className="eyebrow">Channel evidence</span><h2>ROMI по размещениям</h2></div><span className="section-note">на выручке</span></div><div className="table-wrap"><table><thead><tr><th>Канал</th><th>Затраты</th><th>Выручка</th><th>ROMI</th><th>Доказательство</th></tr></thead><tbody>{romi.map(row => <tr key={row.placementId}><td><b>{row.channel}</b><small>{row.placementId}</small></td><td>{rub.format(row.spend)}</td><td>{rub.format(row.attributedRevenue)}</td><td className={row.romi != null && row.romi >= 0 ? "positive" : ""}>{pct(row.romi)}</td><td><Confidence mix={row.confidenceMix} /></td></tr>)}</tbody></table></div></div>
      <div className="ledger-card"><div className="section-heading"><div><span className="eyebrow">Latest facts</span><h2>Свежие оплаты</h2></div></div><ol className="event-list">{snapshot.orders.length ? snapshot.orders.slice(0,5).map(order => { const a = attributionByOrder.get(order.orderId); return <li key={order.orderId}><span className={`event-mark ${a?.placementId ? "verified" : "unknown"}`} /><div><b>{rub.format(order.amount)}</b><small>{order.course ?? "Курс не указан"} · {date(order.ts)}</small></div><span className={`pill ${a?.confidence ?? "unknown"}`}>{a?.confidence ?? "unknown"}</span></li>; }) : <li className="empty-state">Оплат пока нет</li>}</ol></div>
    </section>
  </div>;
}

function Registry({ snapshot, botUsername }: { snapshot: DashboardSnapshot; botUsername: string }) {
  const campaignById = new Map(snapshot.campaigns.map((item) => [item.campaignId, item]));
  return <div className="view-stack"><section className="ledger-card"><div className="section-heading"><div><span className="eyebrow">Ad registry</span><h2>Кампании и deep links</h2></div><span className="section-note">{snapshot.placements.length} размещений</span></div><div className="table-wrap"><table><thead><tr><th>Кампания</th><th>Канал</th><th>Стоимость</th><th>Источник</th><th>Ссылка</th></tr></thead><tbody>{snapshot.placements.map(p => <tr key={p.placementId}><td><b>{campaignById.get(p.campaignId)?.name ?? p.campaignId}</b><small>{p.targetCourse ?? "Без курса"}</small></td><td>{p.channel}</td><td>{rub.format(p.cost)}</td><td><span className={`origin ${p.dataOrigin}`}>{originLabel[p.dataOrigin]}</span></td><td><a className="deep-link" href={buildDeepLink(botUsername, p.trackingToken)} target="_blank" rel="noreferrer">Открыть ↗</a></td></tr>)}</tbody></table></div></section>
    <section className="ledger-card"><div className="section-heading"><div><span className="eyebrow">Event ledger</span><h2>Касания и лиды</h2></div></div><div className="table-wrap"><table><thead><tr><th>Время</th><th>User key</th><th>Placement</th><th>Источник</th><th>Уверенность</th></tr></thead><tbody>{snapshot.touches.map(t => <tr key={t.touchId}><td>{date(t.ts)}</td><td><code>{t.userKey}</code></td><td>{t.placementId ?? "organic"}</td><td>{t.source}</td><td><span className={`pill ${t.confidence}`}>{t.confidence}</span></td></tr>)}</tbody></table></div></section></div>;
}

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone: string }) { return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>; }
function Confidence({ mix }: { mix: ReturnType<typeof buildRomiRows>[number]["confidenceMix"] }) { const key = Object.keys(mix)[0] ?? "unknown"; return <span className={`pill ${key}`}>{key.replace("_", " ")}</span>; }
