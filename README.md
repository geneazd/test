# AdventureWorks IBM Data Quality Remediation PR

This mock repository package contains a copy/paste-ready GitHub Issue, Pull Request body, and repo-style files for a data quality remediation workflow using IBM data products.

## Scenario

The `adventureworks` IBM DataStage ingestion job failed to load data into IBM Db2 Warehouse because the `SVC_DATASTAGE_ADVENTUREWORKS` service account lost required privileges on the `IBM_STACK_1_BRONZE.ADVENTUREWORKS` schema.

The incident was detected through IBM Databand, enriched with IBM Knowledge Catalog contract context, and scoped using IBM Manta Data Lineage.

## IBM product mapping

| Capability | IBM product |
|---|---|
| Ingestion | IBM DataStage |
| Optional replication | IBM Data Replication |
| Warehouse | IBM Db2 Warehouse |
| Data contract / catalog | IBM Knowledge Catalog |
| Observability | IBM Databand |
| Lineage | IBM Manta Data Lineage |
| Governance context | IBM watsonx.governance |

## Files

```text
GITHUB_ISSUE.md
PULL_REQUEST_TEMPLATE.md
infra/db2/grants/adventureworks_datastage.sql
contracts/adventureworks/orders.yml
quality/adventureworks/checks.yml
pipelines/datastage/adventureworks_ingest.yml
scripts/check_db2_permissions.py
.github/workflows/data-quality-preflight.yml
runbooks/ibm_datastage_db2_privilege_failure.md
```

## How to use

1. Copy `GITHUB_ISSUE.md` into a new GitHub Issue.
2. Copy `PULL_REQUEST_TEMPLATE.md` into the PR description.
3. Add the repo files to a feature branch.
4. Configure the GitHub Actions secrets for IBM Db2 Warehouse:
   - `DB2_HOSTNAME`
   - `DB2_PORT`
   - `DB2_DATABASE`
   - `DB2_USER`
   - `DB2_PASSWORD`
   - `DB2_SECURITY`
5. Open the remediation PR.
6. Validate the DataStage job, data quality checks, and impacted dashboards.

## Suggested branch name

```text
fix/adventureworks-ibm-db2-dq-remediation
```

## Suggested PR title

```text
fix(adventureworks): restore IBM Db2 Warehouse grants and add DQ preflight safeguards
```
