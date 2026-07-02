# fix(adventureworks): restore IBM Db2 Warehouse grants and add DQ preflight safeguards

## Summary

This PR remediates incident `PTM-198`, where the `adventureworks` IBM DataStage ingestion job failed to load data into IBM Db2 Warehouse due to missing privileges on `IBM_STACK_1_BRONZE.ADVENTUREWORKS`.

The fix restores required Db2 Warehouse grants, codifies the access policy, updates IBM Knowledge Catalog contract metadata, adds source freshness checks, and introduces CI preflight validation to prevent future permission regressions from reaching production.

Closes #[ISSUE_NUMBER]

---

## Root cause

The IBM DataStage runtime service account `SVC_DATASTAGE_ADVENTUREWORKS` no longer had sufficient privileges on the IBM Db2 Warehouse destination database and schema.

Observed error:

```text
SQL0551N:
The statement failed because the authorization ID does not have the required authorization or privilege to perform the operation on object "IBM_STACK_1_BRONZE.ADVENTUREWORKS".
```

---

## What changed?

| Area | Change |
|---|---|
| IBM Db2 Warehouse grants | Restored required privileges for `SVC_DATASTAGE_ADVENTUREWORKS` |
| IBM Knowledge Catalog contract | Added freshness SLA, owners, access policy, and downstream lineage metadata |
| IBM DataStage config | Added explicit owner, SLA, and incident-routing metadata |
| Data quality checks | Added source freshness, row-count, schema, and referential integrity checks |
| CI/CD | Added Db2 Warehouse permission preflight validation |
| IBM Databand context | Added metadata for owner-aware incident routing |
| IBM Manta Data Lineage context | Added downstream blast-radius metadata |

---

## Files changed

```text
infra/db2/grants/adventureworks_datastage.sql
contracts/adventureworks/orders.yml
quality/adventureworks/checks.yml
pipelines/datastage/adventureworks_ingest.yml
scripts/check_db2_permissions.py
.github/workflows/data-quality-preflight.yml
runbooks/ibm_datastage_db2_privilege_failure.md
```

---

## Implementation details

### IBM Db2 Warehouse grant remediation

This PR restores the minimum required privileges for the AdventureWorks IBM DataStage service account.

```sql
CONNECT TO IBM_STACK_1_BRONZE;

GRANT CONNECT ON DATABASE
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

GRANT CREATEIN, ALTERIN ON SCHEMA ADVENTUREWORKS
TO USER SVC_DATASTAGE_ADVENTUREWORKS;

-- Grants on existing ingestion target tables are managed by:
-- infra/db2/grants/adventureworks_datastage.sql
```

---

## IBM Knowledge Catalog contract updates

The AdventureWorks contract now explicitly defines:

- Business owner
- Technical owner
- Escalation channel
- Freshness SLA
- Required IBM Db2 Warehouse access policy
- Downstream transformations
- Downstream dashboards
- Business and governance risk

Example metadata added:

```yaml
dataset: adventureworks.orders
environment: prod
catalog: ibm-knowledge-catalog

owners:
  business_owner: finance-analytics
  technical_owner: data-platform
  governance_owner: data-governance
  escalation_channel: "#data-platform-oncall"

freshness:
  loaded_at_field: ingestion_timestamp
  warn_after: 1 hour
  error_after: 2 hours
  severity: high

access_policy:
  warehouse: ibm-db2-warehouse
  database: IBM_STACK_1_BRONZE
  schema: ADVENTUREWORKS
  service_account: SVC_DATASTAGE_ADVENTUREWORKS
  required_privileges:
    - CONNECT_ON_DATABASE
    - CREATEIN_ON_SCHEMA
    - ALTERIN_ON_SCHEMA
    - DML_ON_EXISTING_TABLES
```

---

## Data quality checks added

This PR adds source freshness and quality checks for AdventureWorks data.

```yaml
dataset: adventureworks.orders
table: IBM_STACK_1_BRONZE.ADVENTUREWORKS.ORDERS

checks:
  - name: freshness_adventureworks_orders
    type: freshness
    field: ingestion_timestamp
    warn_after: 1 hour
    error_after: 2 hours
    severity: high

  - name: not_null_orders_order_id
    type: not_null
    field: order_id
    severity: high

  - name: unique_orders_order_id
    type: unique
    field: order_id
    severity: high

  - name: accepted_values_order_status
    type: accepted_values
    field: order_status
    values:
      - pending
      - processing
      - shipped
      - cancelled
      - returned
    severity: medium

  - name: row_count_anomaly_orders
    type: row_count_anomaly
    threshold_percent: 20
    lookback_days: 14
    severity: high
```

---

## IBM DataStage pipeline metadata added

This PR updates the AdventureWorks ingestion pipeline metadata so observability and incident workflows can route failures correctly.

```yaml
pipeline: datastage/adventureworks_ingest
runtime: ibm-datastage
environment: prod

source:
  system: AdventureWorks
  objects:
    - orders
    - customers

target:
  system: ibm-db2-warehouse
  database: IBM_STACK_1_BRONZE
  schema: ADVENTUREWORKS

service_account: SVC_DATASTAGE_ADVENTUREWORKS

observability:
  product: ibm-databand
  owner: data-platform
  escalation_channel: "#data-platform-oncall"
  severity_on_freshness_breach: high

lineage:
  product: ibm-manta-data-lineage
  downstream_assets:
    - stg_adventureworks_orders
    - stg_adventureworks_customers
    - int_sales_order_enriched
    - fct_sales
    - dim_customer

contract:
  product: ibm-knowledge-catalog
  path: contracts/adventureworks/orders.yml
```

---

## CI preflight validation

This PR adds a CI job that validates required IBM Db2 Warehouse privileges before changes are merged.

The check fails if `SVC_DATASTAGE_ADVENTUREWORKS` is missing required access to:

- `IBM_STACK_1_BRONZE`
- `ADVENTUREWORKS` schema
- Required table-level DML privileges
- Required schema-level create or alter privileges

---

## Test plan

- [ ] Applied Db2 grant script in lower environment
- [ ] Ran permission preflight check successfully
- [ ] Re-ran IBM DataStage job `datastage/adventureworks_ingest`
- [ ] Confirmed `ingestion_timestamp` updated in bronze tables
- [ ] Ran freshness check for `ADVENTUREWORKS.ORDERS`
- [ ] Ran data quality checks for `ORDERS` and `CUSTOMERS`
- [ ] Rebuilt impacted downstream transformations
- [ ] Confirmed impacted dashboards are no longer stale
- [ ] Confirmed IBM Databand no longer reports freshness breach
- [ ] Confirmed IBM Manta Data Lineage blast radius is resolved

---

## Validation evidence

| Check | Result |
|---|---|
| IBM DataStage job execution | Pending |
| Db2 Warehouse grant validation | Pending |
| Source freshness | Pending |
| Data quality checks | Pending |
| Downstream transformation rebuild | Pending |
| Dashboard freshness validation | Pending |
| IBM Databand incident status | Pending |
| IBM Manta lineage validation | Pending |

---

## Risk

Risk level: `Low to Medium`

The grant changes are scoped to:

```text
Service account: SVC_DATASTAGE_ADVENTUREWORKS
Database: IBM_STACK_1_BRONZE
Schema: ADVENTUREWORKS
```

No broad instance-level or admin privileges are introduced.

The main risk is over-permissioning the ingestion service account. This PR limits access to the AdventureWorks bronze schema and only grants the privileges required for ingestion.

---

## Rollback plan

If this change causes unexpected behavior:

1. Revoke newly added grants from `SVC_DATASTAGE_ADVENTUREWORKS`.
2. Revert this PR.
3. Pause the IBM DataStage job `datastage/adventureworks_ingest` if ingestion behavior is unsafe.
4. Restore the previous Db2 Warehouse role configuration from access history.
5. Re-run source freshness and downstream data quality checks after rollback.

---

## Reviewer checklist

- [ ] Grants are scoped only to `IBM_STACK_1_BRONZE.ADVENTUREWORKS`
- [ ] No broad database admin or instance-level privileges were introduced
- [ ] Required privileges match IBM DataStage ingestion requirements
- [ ] Freshness SLA matches the IBM Knowledge Catalog contract
- [ ] Contract includes owner, escalation channel, access policy, governance risk, and lineage
- [ ] CI check fails closed when grants are missing
- [ ] IBM Databand alerting metadata routes to the correct owner
- [ ] IBM Manta lineage metadata includes downstream impacted assets
- [ ] Runbook exists for future IBM DataStage / Db2 Warehouse access failures

---

## Post-merge checklist

- [ ] Apply grants in production
- [ ] Re-run AdventureWorks IBM DataStage ingestion job
- [ ] Confirm bronze tables are refreshed
- [ ] Rebuild impacted downstream transformations
- [ ] Validate dashboards
- [ ] Update incident `PTM-198`
- [ ] Notify impacted stakeholders
