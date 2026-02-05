# Performance Optimization Recommendations

## Database Indexes for Accuracy Queries

### Problem Statement

The accuracy trend queries are experiencing slow performance due to full table scans on the `workflow.csr_inbox_state_data_audits` table with expensive window functions. These queries scan millions of rows to calculate first and last values for each document+field combination.

### Recommended Indexes

#### 1. Primary Composite Index for Date Range Queries
```sql
CREATE INDEX idx_audit_created_doc_field 
ON workflow.csr_inbox_state_data_audits (created_at, csr_inbox_state_id, field_identifier);
```

**Purpose:** Optimizes date range filtering and partitioning for window functions.

**Queries affected:**
- `/accuracy/per-field`
- `/accuracy/document-level`
- `/accuracy/field-level-trend`
- `/accuracy/trend`

**Expected impact:** 5-10x improvement for date-filtered queries

---

#### 2. System Value Filter Index
```sql
CREATE INDEX idx_audit_user_created 
ON workflow.csr_inbox_state_data_audits (user_id, created_at) 
WHERE user_id IS NULL;
```

**Purpose:** Partial index to quickly filter system-preselected values (where `user_id IS NULL`).

**Queries affected:** All accuracy endpoints that filter by `user_id IS NULL`

**Expected impact:** 3-5x improvement when combined with date filters

---

#### 3. Window Function Optimization Index
```sql
CREATE INDEX idx_audit_doc_field_created 
ON workflow.csr_inbox_state_data_audits (csr_inbox_state_id, field_identifier, created_at);
```

**Purpose:** Optimizes `PARTITION BY csr_inbox_state_id, field_identifier ORDER BY created_at` window functions used to find first and last values.

**Queries affected:**
- `/accuracy/field-level-trend` (most critical)
- `/accuracy/per-field`

**Expected impact:** 40-60% improvement for window function queries

---

### Index Priority

1. **High Priority:** `idx_audit_doc_field_created` - Will have immediate impact on slow trend query
2. **Medium Priority:** `idx_audit_created_doc_field` - General purpose improvement
3. **Low Priority:** `idx_audit_user_created` - Useful but less critical with other indexes

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

To validate index effectiveness, collect query statistics before and after:

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

1. **Index Creation Timing:** Create indexes during low-traffic periods as they may lock the table
2. **Storage Impact:** Each index will consume additional storage (estimate 5-15% of table size per index)
3. **Write Performance:** Indexes will slightly slow down INSERT/UPDATE operations on the audits table
4. **Monitoring:** Monitor query performance after index creation to validate improvements

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
