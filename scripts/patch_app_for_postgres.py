from pathlib import Path

APP = Path("app.py")

START = "# ============================================================\n# UI-level write helpers"
END = "# ============================================================\n# Page: Обзор"

replacement = """# ============================================================
# UI-level write helpers -> PostgreSQL adapter
# ============================================================

def update_campaign(campaign_id: str, **fields) -> None:
    db.update_campaign(campaign_id, **fields)


def delete_campaign(campaign_id: str) -> None:
    db.delete_campaign(campaign_id)


def update_placement(placement_id: str, **fields) -> None:
    db.update_placement(placement_id, **fields)


def delete_placement(placement_id: str) -> None:
    db.delete_placement(placement_id)


def clear_all_data() -> None:
    db.clear_all_data()


"""

text = APP.read_text(encoding="utf-8")

start = text.find(START)
end = text.find(END)

if start == -1 or end == -1 or end <= start:
    raise SystemExit(
        "app.py markers were not found. Do not patch automatically; "
        "inspect the current app.py and update the DB helper block manually."
    )

new_text = text[:start] + replacement + text[end:]
APP.write_text(new_text, encoding="utf-8")
print("app.py DB helper block patched for PostgreSQL.")
