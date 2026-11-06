"""Offline structural gate for the *draft* PostgreSQL V1 files.

Checks text patterns only. NOT a PostgreSQL SQL parser and NOT a runtime test.
Run from the repository root:
    python -B -m database.tests.Database_Schema_V1_Static_Gate
SQL files are resolved from database/schema, independently of the working directory.
"""
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parents[2]
schema = BASE / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql"
rbac = BASE / "database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql"

EXPECTED = {"tables": 14, "references": 28, "functions": 52, "triggers": 24}


def count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.I | re.M))


def main() -> int:
    if not schema.is_file() or not rbac.is_file():
        print("Keep the latest V1 draft SQL and RBAC template in database/schema.")
        return 2
    sql = schema.read_text(encoding="utf-8")
    priv = rbac.read_text(encoding="utf-8")
    found = {
        "tables": count(sql, r"^CREATE TABLE\s+\w+"),
        "references": count(sql, r"\bREFERENCES\s+\w+\s*\("),
        "functions": count(sql, r"^CREATE FUNCTION\s+"),
        "triggers": count(sql, r"^CREATE (?:CONSTRAINT )?TRIGGER\s+"),
    }
    print("Database Schema V1 static gate (no database connection)")
    for field, expect in EXPECTED.items():
        print(field, found[field], "/ expected", expect, "PASS" if found[field] == expect else "FAIL")
    checks = {
        "Project DELETE guard present": "R-01: Project deletion is forbidden in V1" in sql,
        "No DELETE grant for projects": not bool(re.search(r"\bGRANT\s+DELETE\s+ON\s+(?:TABLE\s+)?(?:public\.)?projects\b", priv, re.I)),
        "RBAC preflight present": "DO $preflight$" in priv,
        "RBAC postflight present": "DO $postflight$" in priv,
        "Default PUBLIC function EXECUTE revoked": "REVOKE ALL ON FUNCTION" in sql,
    }
    for label, ok in checks.items():
        print(label, "PASS" if ok else "FAIL")
    good = all(found[k] == v for k, v in EXPECTED.items()) and all(checks.values())
    print("RESULT:", "STATIC COUNTS/PATTERNS PASS (not PostgreSQL-validated)" if good else "STATIC GATE FAILED")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
