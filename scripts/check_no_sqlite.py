from pathlib import Path
import re
import sys

targets = [Path("app.py"), *Path("src").glob("*.py")]
problems = []

for path in targets:
    if path.name == "db.py":
        continue
    text = path.read_text(encoding="utf-8", errors="replace")

    checks = [
        ("sqlite3 import/reference", r"\bsqlite3\b"),
        ("legacy SQLite file", r"measurement\.db"),
        ("SQLite PRAGMA", r"\bPRAGMA\b"),
        ("raw db.get_conn outside adapter", r"\bdb\.get_conn\s*\("),
    ]

    for label, pattern in checks:
        for match in re.finditer(pattern, text):
            line = text.count("\n", 0, match.start()) + 1
            problems.append(f"{path}:{line}: {label}")

if problems:
    print("Potential PostgreSQL migration leftovers:")
    for p in problems:
        print(" -", p)
    sys.exit(1)

print("OK: no obvious SQLite coupling outside src/db.py.")
