"""PostgreSQL-backed attribution entry point used by the existing Streamlit UI."""

import db

DEFAULT_WINDOW_DAYS = 30


def run_attribution(window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    Persist last eligible touch attribution for the selected window.

    Historical orders without user-level touches remain unknown; no fake
    attribution row is written for them.
    """
    return db.recompute_last_touch(window_days=window_days)
