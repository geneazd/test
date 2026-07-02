# Runbook: IBM DataStage / IBM Db2 Warehouse Privilege Failure

## Purpose

Use this runbook when an IBM DataStage ingestion job fails while writing to IBM Db2 Warehouse due to missing authorization or database privileges.

Example error:

```text
SQL0551N:
The statement failed because the authorization ID does not have the required authorization or privilege to perform the operation on object "IBM_STACK_1_BRONZE.ADVENTUREWORKS".
```

---

## Affected pipeline

| Field | Value |
|---|---|
| Pipeline | `datastage/adventureworks_ingest` |
| Runtime | IBM DataStage |
| Warehouse | IBM Db2 Warehouse |
| Database | `IBM_STACK_1_BRONZE` |
| Schema | `ADVENTUREWORKS` |
| Service account | `SVC_DATASTAGE_ADVENTUREWORKS` |
| Observability | IBM Databand |
| Catalog | IBM Knowledge Catalog |
| Lineage | IBM Manta Data Lineage |

---

## Immediate triage

1. Confirm the failing IBM DataStage job.
2. Capture the failed stage name and Db2 error message.
3. Confirm whether bronze tables are stale.
4. Check IBM Databand for freshness and row-count anomalies.
5. Use IBM Manta Data Lineage to identify downstream impacted assets.
6. Notify the owning data platform and analytics teams.

---

## Validate required privileges

Run the CI preflight script locally or in the deployment environment:

```bash
export DB2_HOSTNAME="<hostname>"
export DB2_PORT="50001"
export DB2_DATABASE="IBM_STACK_1_BRONZE"
export DB2_USER="<admin-or-security-user>"
export DB2_PASSWORD="<password>"
export DB2_SECURITY="SSL"

export TARGET_SERVICE_ACCOUNT="SVC_DATASTAGE_ADVENTUREWORKS"
export TARGET_SCHEMA="ADVENTUREWORKS"
export REQUIRED_TABLES="ORDERS,CUSTOMERS,SALES"

python scripts/check_db2_permissions.py
```

Expected result:

```text
All required IBM Db2 Warehouse privileges are present.
```

---

## Restore service

Apply the grant script:

```bash
db2 -tvf infra/db2/grants/adventureworks_datastage.sql
```

Then:

1. Re-run `datastage/adventureworks_ingest`.
2. Confirm `ADVENTUREWORKS.ORDERS`, `ADVENTUREWORKS.CUSTOMERS`, and `ADVENTUREWORKS.SALES` are refreshed.
3. Confirm `ingestion_timestamp` is within the two-hour freshness SLA.
4. Rebuild downstream transformations.
5. Validate dashboards.

---

## Validation checks

- [ ] IBM DataStage job succeeds
- [ ] Db2 grant validation passes
- [ ] Source freshness check passes
- [ ] Row-count anomaly check passes
- [ ] Schema contract check passes
- [ ] Referential integrity check passes
- [ ] Downstream marts are rebuilt
- [ ] Executive and finance dashboards are fresh

---

## Stakeholder notification

Notify:

- `#data-platform-oncall`
- Finance Analytics
- Revenue Operations
- Data Governance

Suggested message:

```text
AdventureWorks ingestion has recovered. The IBM DataStage service account permissions were restored for IBM Db2 Warehouse. Bronze tables are refreshed, data quality checks have passed, and downstream dashboards are being validated.
```

---

## Prevention

After service is restored:

- Keep Db2 grants in version control.
- Require CI permission validation before merging changes.
- Keep access requirements in IBM Knowledge Catalog contract metadata.
- Attach IBM Databand alerts to owners, runbooks, and lineage.
- Review similar IBM DataStage service accounts for the same privilege regression pattern.
