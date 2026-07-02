# [SEV-2][DQ Incident] AdventureWorks ingestion blocked by IBM Db2 Warehouse privilege regression

## Summary

The `adventureworks` ingestion pipeline failed to load data into IBM Db2 Warehouse because the IBM DataStage service account no longer had sufficient privileges on the `IBM_STACK_1_BRONZE` database and `ADVENTUREWORKS` schema.

This caused stale bronze-layer source data, failed data quality checks, and downstream impact across sales, customer, finance, and executive reporting assets.

Detected incident: `PTM-198`  
Severity: `SEV-2`  
Environment: `production`  
Primary system boundary: `IBM DataStage → IBM Db2 Warehouse`

---

## What happened?

The `adventureworks` ingestion job failed during execution in IBM DataStage with an IBM Db2 Warehouse authorization error.

```text
SQL0551N:
The statement failed because the authorization ID does not have the required authorization or privilege to perform the operation on object "IBM_STACK_1_BRONZE.ADVENTUREWORKS".
```

Because the bronze layer was not refreshed, downstream transformation jobs and reporting assets continued to use stale source data.

The incident was detected through IBM Databand observability alerts and correlated with metadata from IBM Knowledge Catalog and lineage from IBM Manta Data Lineage.

---

## Why did it happen?

The IBM DataStage runtime service account, `SVC_DATASTAGE_ADVENTUREWORKS`, was missing required privileges on the target IBM Db2 Warehouse database and schema.

Likely root cause:

```text
A recent database role cleanup, access policy change, or manual privilege update removed required grants from the AdventureWorks ingestion service account.
```

Contributing factors:

- Required IBM Db2 Warehouse privileges were not fully managed in version control.
- CI did not validate ingestion service account permissions before deployment.
- The data contract in IBM Knowledge Catalog defined freshness expectations but did not explicitly enforce required warehouse access.
- IBM Databand detected the failed ingestion job, but remediation was not automatically mapped to the owning repository, grant file, and service account.
- IBM Manta Data Lineage showed downstream impact, but the blast radius was not attached directly to the remediation workflow.

---

## Where did it happen?

| Field | Value |
|---|---|
| Source system | `AdventureWorks` |
| Ingestion product | `IBM DataStage` |
| Optional replication product | `IBM Data Replication` |
| Target warehouse | `IBM Db2 Warehouse` |
| Catalog / contract | `IBM Knowledge Catalog` |
| Observability | `IBM Databand` |
| Lineage | `IBM Manta Data Lineage` |
| Database | `IBM_STACK_1_BRONZE` |
| Schema | `ADVENTUREWORKS` |
| Service account | `SVC_DATASTAGE_ADVENTUREWORKS` |
| Layer | `Bronze` |
| Environment | `production` |

---

## What was impacted?

### Directly impacted assets

| Asset | Impact |
|---|---|
| `datastage/adventureworks_ingest` | Ingestion job failed |
| `IBM_STACK_1_BRONZE.ADVENTUREWORKS` | Bronze tables stale |
| `ADVENTUREWORKS.ORDERS` | Not refreshed |
| `ADVENTUREWORKS.CUSTOMERS` | Not refreshed |
| Source freshness SLA | Breached |

### Downstream models impacted

| Layer | Asset | Impact |
|---|---|---|
| Staging | `stg_adventureworks_orders` | Stale order data |
| Staging | `stg_adventureworks_customers` | Stale customer data |
| Intermediate | `int_sales_order_enriched` | Incomplete or stale enrichment |
| Mart | `fct_sales` | Stale revenue metrics |
| Mart | `dim_customer` | Stale customer attributes |

### Data quality checks impacted

| Check | Expected | Actual |
|---|---|---|
| `freshness_adventureworks_orders` | Source data refreshed within 2 hours | Failed |
| `row_count_anomaly_fct_sales` | Row count within expected range | Failed or at risk |
| `not_null_orders_order_id` | Passing | At risk due stale upstream |
| `referential_integrity_sales_customer` | Passing | At risk due stale upstream |
| `schema_contract_adventureworks_orders` | Schema matches contract | At risk due incomplete ingestion |

---

## IBM product context synthesized

### IBM Knowledge Catalog

The registered data contract for `adventureworks.orders` defines:

- Required fields
- Primary key expectations
- Freshness SLA
- Data owner
- Technical owner
- Critical downstream consumers

### IBM Databand

IBM Databand detected:

- Failed DataStage job execution
- Freshness SLA breach
- Abnormal row-count behavior in downstream assets
- Delayed completion of dependent pipelines

### IBM Manta Data Lineage

IBM Manta Data Lineage identified downstream assets impacted by stale source tables:

- Staging transformations
- Sales fact table
- Customer dimension
- Executive dashboards
- Finance reporting workflows

### IBM watsonx.governance

The incident increases governance risk because certified business metrics may be generated from stale or incomplete data.

---

## Who was impacted?

Primary impacted teams:

- Finance Analytics
- Revenue Operations
- Sales Leadership
- Customer Success Operations
- Executive Reporting Consumers
- Data Governance

Primary impacted use cases:

- Daily revenue reporting
- Sales performance monitoring
- Finance close preparation
- Customer retention reporting
- Executive KPI dashboards
- Certified metric reporting

---

## Associated cost or risk

### Business risk

Revenue, sales, and customer reporting may be stale or incomplete. Stakeholders could make business decisions using outdated metrics.

### Governance risk

Certified data products in IBM Knowledge Catalog may no longer meet declared freshness and quality expectations.

### Operational risk

The same privilege regression pattern could affect other IBM DataStage or IBM Data Replication jobs if Db2 Warehouse grants are not codified and validated consistently.

### Estimated impact

| Metric | Estimate |
|---|---:|
| Downstream pipelines affected | 55 |
| Production dashboards stale | 4 |
| Freshness delay | 6+ hours |
| Engineering remediation | 2–4 hours |
| Analyst validation | 2–6 hours |
| Potential reporting delay | 1 business day |
| Governance severity | High |

---

## Recommended next step

Open a remediation PR that:

1. Restores required IBM Db2 Warehouse privileges for `SVC_DATASTAGE_ADVENTUREWORKS`.
2. Moves the required database grants into version-controlled infrastructure.
3. Adds a CI preflight check that fails when ingestion privileges are missing.
4. Updates the AdventureWorks data contract metadata for IBM Knowledge Catalog.
5. Adds validation steps for freshness, data quality, lineage, and dashboard recovery.
6. Adds observability metadata so IBM Databand alerts route to the correct owning team.

---

## Remediation tasks

### Phase 1 — Restore service

- [ ] Restore required IBM Db2 Warehouse grants for `SVC_DATASTAGE_ADVENTUREWORKS`
- [ ] Re-run `datastage/adventureworks_ingest`
- [ ] Confirm bronze tables are updating
- [ ] Confirm `ADVENTUREWORKS.ORDERS` and `ADVENTUREWORKS.CUSTOMERS` were refreshed
- [ ] Run source freshness checks
- [ ] Backfill or rerun impacted downstream transformations

### Phase 2 — Validate data quality

- [ ] Validate row counts for `ORDERS`, `CUSTOMERS`, and `SALES`
- [ ] Confirm source freshness is within SLA
- [ ] Run data quality checks against the IBM Knowledge Catalog contract
- [ ] Validate impacted downstream marts
- [ ] Confirm dashboards are no longer stale
- [ ] Notify Finance Analytics and Revenue Operations

### Phase 3 — Prevent recurrence

- [ ] Add Db2 Warehouse grants to version-controlled infrastructure
- [ ] Add ingestion permission preflight check in CI
- [ ] Add required access policy to the IBM Knowledge Catalog contract metadata
- [ ] Add lineage-aware incident metadata from IBM Manta Data Lineage
- [ ] Add IBM Databand alert routing metadata
- [ ] Add runbook link for IBM DataStage / Db2 Warehouse access failures

---

## Acceptance criteria

- [ ] `datastage/adventureworks_ingest` completes successfully in production
- [ ] `IBM_STACK_1_BRONZE.ADVENTUREWORKS` tables are refreshed
- [ ] Source freshness checks pass
- [ ] Downstream transformations complete successfully
- [ ] Impacted dashboards show current data
- [ ] IBM Db2 Warehouse grants are defined in version control
- [ ] CI fails if required grants are removed
- [ ] IBM Knowledge Catalog contract includes owner, freshness SLA, access policy, and downstream lineage
- [ ] IBM Databand alert includes failed job, failed check, owner, lineage, risk, and recommended remediation
- [ ] Incident is closed with validation evidence

---

## Suggested labels

`incident`, `data-quality`, `ibm`, `db2-warehouse`, `datastage`, `databand`, `knowledge-catalog`, `lineage`, `sev-2`, `needs-remediation`
