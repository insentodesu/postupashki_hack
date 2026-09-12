import pandas as pd
import db
import attribution as attr


def build_romi_table(window_days=30):
    placements = db.list_placements()
    attrs = db.list_attributions()
    orders = {o["order_id"]: o for o in db.list_orders()}

    rows = []
    for p in placements:
        pid = p["placement_id"]
        p_attr = [a for a in attrs if a["placement_id"] == pid]

        revenue = sum(a["revenue_credit"] for a in p_attr)
        order_ids = {a["order_id"] for a in p_attr}
        conversions = len(order_ids)
        spend = float(p["cost"] or 0)

        cac = spend / conversions if conversions else None
        romi = (revenue - spend) / spend if spend else None

        rows.append({
            "placement_id": pid,
            "channel": p["channel"],
            "creative_id": p["creative_id"],
            "target_course": p["target_course"],
            "spend": spend,
            "conversions": conversions,
            "attributed_revenue": revenue,
            "cac": cac,
            "romi_attr": romi,
            "confidence_mix": _confidence_mix(p_attr),
        })

    df = pd.DataFrame(rows)

    unknown = [a for a in attrs if not a["placement_id"]]
    unknown_df = pd.DataFrame([{
        "order_id": a["order_id"],
        "revenue": a["revenue_credit"],
        "course": orders.get(a["order_id"], {}).get("course"),
        "ts": orders.get(a["order_id"], {}).get("ts"),
    } for a in unknown])

    return df, unknown_df


def _confidence_mix(attrs):
    mix = {}
    for a in attrs:
        mix[a["confidence"]] = mix.get(a["confidence"], 0) + 1
    return mix


def run_attribution_with_sensitivity(windows=(7, 14, 30)):
    result = {}
    for w in windows:
        attr.run_attribution(window_days=w)
        attrs = db.list_attributions()
        total_attr = sum(a["revenue_credit"] for a in attrs if a["placement_id"])
        unknown = sum(a["revenue_credit"] for a in attrs if not a["placement_id"])
        result[w] = {"attributed_revenue": total_attr, "unknown_revenue": unknown}
    attr.run_attribution(window_days=attr.DEFAULT_WINDOW_DAYS)
    return result