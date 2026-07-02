#!/usr/bin/env python3
"""
scripts/check_db2_permissions.py

Validates that the IBM DataStage service account has the required IBM Db2
Warehouse privileges for the AdventureWorks ingestion pipeline.

Expected environment variables:

  DB2_HOSTNAME
  DB2_PORT
  DB2_DATABASE
  DB2_USER
  DB2_PASSWORD
  DB2_SECURITY

Optional environment variables:

  TARGET_SERVICE_ACCOUNT
  TARGET_SCHEMA
  REQUIRED_TABLES

Example:

  TARGET_SERVICE_ACCOUNT=SVC_DATASTAGE_ADVENTUREWORKS \
  TARGET_SCHEMA=ADVENTUREWORKS \
  REQUIRED_TABLES=ORDERS,CUSTOMERS,SALES \
  python scripts/check_db2_permissions.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable

try:
    import ibm_db
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: ibm_db. Install with `pip install ibm-db`."
    ) from exc


TARGET_SERVICE_ACCOUNT = os.environ.get(
    "TARGET_SERVICE_ACCOUNT", "SVC_DATASTAGE_ADVENTUREWORKS"
).upper()

TARGET_SCHEMA = os.environ.get("TARGET_SCHEMA", "ADVENTUREWORKS").upper()

REQUIRED_TABLES = [
    table.strip().upper()
    for table in os.environ.get("REQUIRED_TABLES", "ORDERS,CUSTOMERS,SALES").split(",")
    if table.strip()
]


@dataclass(frozen=True)
class MissingPrivilege:
    scope: str
    object_name: str
    privilege: str


def build_connection_string() -> str:
    security = os.environ.get("DB2_SECURITY", "SSL")
    return (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOSTNAME']};"
        f"PORT={os.environ['DB2_PORT']};"
        f"PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
        f"SECURITY={security};"
    )


def fetch_one(conn, sql: str, params: Iterable[str]) -> tuple | None:
    stmt = ibm_db.prepare(conn, sql)
    for index, value in enumerate(params, start=1):
        ibm_db.bind_param(stmt, index, value)
    ibm_db.execute(stmt)
    return ibm_db.fetch_tuple(stmt)


def has_auth(value: object) -> bool:
    """Db2 catalog auth flags commonly use Y, G, or N."""
    return str(value or "").upper() in {"Y", "G"}


def check_database_connect(conn) -> list[MissingPrivilege]:
    sql = """
        SELECT CONNECTAUTH
        FROM SYSCAT.DBAUTH
        WHERE GRANTEE = ?
          AND GRANTEETYPE = 'U'
    """
    row = fetch_one(conn, sql, [TARGET_SERVICE_ACCOUNT])

    if not row or not has_auth(row[0]):
        return [
            MissingPrivilege(
                scope="DATABASE",
                object_name=os.environ["DB2_DATABASE"].upper(),
                privilege="CONNECT",
            )
        ]

    return []


def check_schema_privileges(conn) -> list[MissingPrivilege]:
    sql = """
        SELECT CREATEINAUTH, ALTERINAUTH
        FROM SYSCAT.SCHEMAAUTH
        WHERE GRANTEE = ?
          AND GRANTEETYPE = 'U'
          AND SCHEMANAME = ?
    """
    row = fetch_one(conn, sql, [TARGET_SERVICE_ACCOUNT, TARGET_SCHEMA])

    missing: list[MissingPrivilege] = []

    if not row:
        return [
            MissingPrivilege("SCHEMA", TARGET_SCHEMA, "CREATEIN"),
            MissingPrivilege("SCHEMA", TARGET_SCHEMA, "ALTERIN"),
        ]

    createin_auth, alterin_auth = row

    if not has_auth(createin_auth):
        missing.append(MissingPrivilege("SCHEMA", TARGET_SCHEMA, "CREATEIN"))

    if not has_auth(alterin_auth):
        missing.append(MissingPrivilege("SCHEMA", TARGET_SCHEMA, "ALTERIN"))

    return missing


def check_table_privileges(conn) -> list[MissingPrivilege]:
    sql = """
        SELECT SELECTAUTH, INSERTAUTH, UPDATEAUTH, DELETEAUTH
        FROM SYSCAT.TABAUTH
        WHERE GRANTEE = ?
          AND GRANTEETYPE = 'U'
          AND TABSCHEMA = ?
          AND TABNAME = ?
    """

    missing: list[MissingPrivilege] = []

    required = {
        "SELECT": 0,
        "INSERT": 1,
        "UPDATE": 2,
        "DELETE": 3,
    }

    for table in REQUIRED_TABLES:
        row = fetch_one(conn, sql, [TARGET_SERVICE_ACCOUNT, TARGET_SCHEMA, table])

        if not row:
            missing.extend(
                MissingPrivilege("TABLE", f"{TARGET_SCHEMA}.{table}", privilege)
                for privilege in required
            )
            continue

        for privilege, index in required.items():
            if not has_auth(row[index]):
                missing.append(
                    MissingPrivilege("TABLE", f"{TARGET_SCHEMA}.{table}", privilege)
                )

    return missing


def main() -> int:
    print("Validating IBM Db2 Warehouse privileges")
    print(f"Target service account: {TARGET_SERVICE_ACCOUNT}")
    print(f"Target schema: {TARGET_SCHEMA}")
    print(f"Required tables: {', '.join(REQUIRED_TABLES)}")

    try:
        conn = ibm_db.connect(build_connection_string(), "", "")
    except Exception as exc:
        print("Unable to connect to IBM Db2 Warehouse.")
        print(str(exc))
        return 2

    missing: list[MissingPrivilege] = []
    missing.extend(check_database_connect(conn))
    missing.extend(check_schema_privileges(conn))
    missing.extend(check_table_privileges(conn))

    ibm_db.close(conn)

    if missing:
        print("\nMissing required privileges:")
        for item in missing:
            print(f"- {item.privilege} on {item.scope} {item.object_name}")
        return 1

    print("\nAll required IBM Db2 Warehouse privileges are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
