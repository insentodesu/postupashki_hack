from datetime import datetime, timezone, timedelta
import db

DEFAULT_WINDOW_DAYS = 30

CONFIDENCE_RANK = {
    "deterministic": 3,
    "self_reported": 2,
    "modelled": 1,
    "unknown": 0,
}


def _parse(ts):
    if not ts:
        return None
    ts = ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def run_attribution(window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    Для каждого заказа:
      - если нет user_key → unknown
      - иначе ищем последний eligible touch в [order.ts - window, order.ts]
      - пишем строку в attributions с методом и confidence
    """
    db.clear_attributions()
    orders = db.list_orders()
    touches = db.list_touches()

    by_user = {}
    for t in touches:
        by_user.setdefault(t["user_key"], []).append(t)

    summary = {"deterministic": 0, "self_reported": 0, "modelled": 0, "unknown": 0}

    for order in orders:
        order_ts = _parse(order["ts"])
        user_key = order["user_key"]

        if not user_key or not order_ts:
            db.add_attribution(order["order_id"], None, "unknown", "unknown",
                               order["amount"], window_days)
            summary["unknown"] += 1
            continue

        cutoff = order_ts - timedelta(days=window_days)
        candidates = []
        for t in by_user.get(user_key, []):
            t_ts = _parse(t["ts"])
            if t_ts and cutoff <= t_ts <= order_ts:
                candidates.append((t, t_ts))

        if not candidates:
            db.add_attribution(order["order_id"], None, "unknown", "unknown",
                               order["amount"], window_days)
            summary["unknown"] += 1
            continue

        candidates.sort(
            key=lambda x: (x[1], CONFIDENCE_RANK.get(x[0]["confidence"], 0)),
            reverse=True,
        )
        winner, _ = candidates[0]
        method = winner["confidence"]
        db.add_attribution(order["order_id"], winner["placement_id"], method,
                           winner["confidence"], order["amount"], window_days)
        summary[method] = summary.get(method, 0) + 1

    return summary