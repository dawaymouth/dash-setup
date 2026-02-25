# Performance Optimization Recommendations

## Root Cause Fix (Query-Side, Implemented)

The accuracy endpoints were slow because the planner scanned `workflow.csr_inbox_state_data_audits` by `created_at` range (millions of rows) then joined to a small document set. The primary query-side fixes applied:

1. **Drive audit scan from documents_in_scope:** All audit CTEs now filter with `a.csr_inbox_state_id IN (SELECT csr_inbox_state_id FROM documents_in_scope)` so Redshift can restrict the audit scan to in-scope state_ids (especially effective if the table has a SORT KEY on `csr_inbox_state_id`).
2. **Single-scan pattern:** The shared CTEs use one `all_vals`-style CTE that computes both first system value and last value per (state_id, field_identifier) in a single pass, instead of two separate `first_values` and `last_values` scans.
3. **Tighter scope:** When `ai_intake_only=true`, `documents_in_scope` also filters by `id.is_ai_intake_enabled = true`, aligning with export bulk and reducing the document set.
4. **Date caps:** Document-level is capped at 30 days; trend/field-level-trend are capped at 30 days when no organization is selected.

Schema changes below (SORT KEY, materialized views) remain optional follow-ups for the DBA.

---

## Redshift Table Design (SORT KEY) for Accuracy Queries

**Note:** Redshift does not support `CREATE INDEX` like PostgreSQL. Use **SORT KEY** (and optionally DISTKEY) when creating or altering the table so that filtering by `csr_inbox_state_id` and `created_at` is efficient.

### Problem Statement

The accuracy trend queries can still benefit from table design: full table scans on `workflow.csr_inbox_state_data_audits` with window functions are expensive. A SORT KEY allows Redshift to skip blocks when filtering by `csr_inbox_state_id IN (...)` and `created_at` range.

### Recommended SORT KEYs

#### 1. Primary SORT KEY for In-Scope + Date
If the table can be altered, use a composite SORT KEY so that filtering by `csr_inbox_state_id` and `created_at` is efficient:

- **SORT KEY (csr_inbox_state_id, created_at)** — best when the query restricts by `csr_inbox_state_id IN (SELECT ... FROM documents_in_scope)` and then by `created_at` range. Redshift can then use the sort order to read only relevant blocks.

#### 2. Alternative: Date-First SORT KEY
- **SORT KEY (created_at, csr_inbox_state_id, field_identifier)** — helps date-range-first plans and partitioning for window functions.

**Queries affected:**
- `/accuracy/per-field`
- `/accuracy/document-level`
- `/accuracy/field-level-trend`
- `/accuracy/trend`

**Expected impact:** 5-10x improvement when combined with the IN filter and single-scan pattern above.

---

#### 3. Window Function Optimization (Table Design)
- **SORT KEY (csr_inbox_state_id, field_identifier, created_at)** — optimizes `PARTITION BY csr_inbox_state_id, field_identifier ORDER BY created_at` window functions.

**Expected impact:** 40-60% improvement for window function queries

---

### SORT KEY Priority

1. **High Priority:** SORT KEY (csr_inbox_state_id, created_at) — supports the IN filter and reduces rows read
2. **Medium Priority:** SORT KEY (csr_inbox_state_id, field_identifier, created_at) — window function optimization
3. **Low Priority:** (created_at, csr_inbox_state_id) — date-first plans

### Additional Optimization Options

#### Materialized View for Daily Accuracy
Consider creating a materialized view that pre-calculates daily accuracy metrics:

```sql
CREATE MATERIALIZED VIEW mv_daily_field_accuracy AS
SELECT 
    DATE_TRUNC('day', created_at)::date as date,
    record_type,
    field_identifier,
    COUNT(*) as total_docs,
    SUM(CASE WHEN first_value = last_value THEN 1 ELSE 0 END) as accurate_docs,
    ROUND(100.0 * SUM(CASE WHEN first_value = last_value THEN 1 ELSE 0 END) / COUNT(*), 2) as accuracy_pct
FROM (
    -- Query to get first and last values per document+field
    ...
)
GROUP BY 1, 2, 3;
```

**Refresh schedule:** Daily or hourly depending on data freshness requirements

**Expected impact:** Near-instant query response for trend graphs

---

#### Query Statistics Collection

To validate SORT KEY and query effectiveness, collect query statistics before and after:

```sql
-- Before optimization
EXPLAIN ANALYZE <query>;

-- Check current query performance
SELECT query, total_exec_time, rows 
FROM svl_qlog 
WHERE query LIKE '%csr_inbox_state_data_audits%' 
ORDER BY total_exec_time DESC 
LIMIT 10;
```

---

## Implementation Notes

1. **Redshift:** Use SORT KEY on table create/alter, not CREATE INDEX. Coordinate with DBA for existing tables.
2. **Storage/Write:** SORT KEY is the table’s physical order; no separate index storage. Monitor query performance after changes.

---

## Alternative: Query Rewrite

Instead of (or in addition to) indexes, consider rewriting the query to perform a single table scan:

```sql
WITH all_values AS (
    SELECT 
        a.csr_inbox_state_id,
        a.record_type,
        a.field_identifier,
        a.created_at,
        a.field_value,
        ROW_NUMBER() OVER (
            PARTITION BY a.csr_inbox_state_id, a.field_identifier 
            ORDER BY a.created_at ASC
        ) as rn_first,
        ROW_NUMBER() OVER (
            PARTITION BY a.csr_inbox_state_id, a.field_identifier 
            ORDER BY a.created_at DESC
        ) as rn_last,
        FIRST_VALUE(a.field_value) OVER (
            PARTITION BY a.csr_inbox_state_id, a.field_identifier 
            ORDER BY a.created_at ASC
        ) as first_value,
        FIRST_VALUE(a.field_value) OVER (
            PARTITION BY a.csr_inbox_state_id, a.field_identifier 
            ORDER BY a.created_at DESC
        ) as last_value
    FROM workflow.csr_inbox_state_data_audits a
    WHERE a.user_id IS NULL
      AND a.created_at >= :start_date
      AND a.created_at < :end_date
)
SELECT 
    record_type,
    field_identifier,
    COUNT(DISTINCT csr_inbox_state_id) as total_docs,
    SUM(CASE WHEN LOWER(COALESCE(first_value, '')) = LOWER(COALESCE(last_value, '')) 
        THEN 1 ELSE 0 END) as accurate_docs
FROM all_values
WHERE rn_first = 1 OR rn_last = 1
GROUP BY 1, 2;
```

**Benefits:** Single table scan instead of two separate scans

**Expected impact:** 40-50% improvement even without indexes

---

## Contact

For questions or to coordinate index creation, contact the development team.

**Date:** 2026-02-05
