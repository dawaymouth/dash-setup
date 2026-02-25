"""
Shared SQL for "received to open" cycle time in business hours (8 AM–6 PM Mon–Fri).
Used by the cycle_time API router and by export_queries so API and export stay in sync.

Logic matches colleague's definition:
- Clip received (document_created_at) forward; clip opened (document_first_accessed_at) backward.
- Business minutes: same-day DATEDIFF; multi-day = first partial + last partial + full weekdays * 600.
- Filter: biz_mins > 0 AND biz_mins <= 6000. Median over qualifying rows.
"""


def _clip_start_sql() -> str:
    """SQL expression that clips document_created_at forward to the next
    business-hour boundary (Mon-Fri 8am-6pm). Matches colleague definition."""
    return """
        CASE
            WHEN EXTRACT(DOW FROM document_created_at) IN (0, 6) THEN
                DATE_TRUNC('day', document_created_at)
                + ((8 - EXTRACT(DOW FROM document_created_at)) % 7) * INTERVAL '1 day'
                + INTERVAL '8 hours'
            WHEN EXTRACT(HOUR FROM document_created_at) < 8 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '8 hours'
            WHEN EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                DATE_TRUNC('day', document_created_at + INTERVAL '1 day') + INTERVAL '8 hours'
            ELSE document_created_at
        END"""


def _clip_end_sql() -> str:
    """SQL expression that clips document_first_accessed_at backward to the
    most recent business-hour boundary. Matches colleague's exact formula:
    weekend uses - ((dow + 1) % 7) * 1 day + 18 hour (Sun->Fri 6pm, Sat->Sat 6pm)."""
    return """
        CASE
            WHEN EXTRACT(DOW FROM document_first_accessed_at) IN (0, 6) THEN
                DATE_TRUNC('day', document_first_accessed_at)
                - ((EXTRACT(DOW FROM document_first_accessed_at) + 1) % 7) * INTERVAL '1 day'
                + INTERVAL '18 hours'
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) < 8 THEN
                DATE_TRUNC('day', document_first_accessed_at) + INTERVAL '18 hours'
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) >= 18 THEN
                DATE_TRUNC('day', document_first_accessed_at) + INTERVAL '18 hours'
            ELSE document_first_accessed_at
        END"""


def _business_minutes_sql() -> str:
    """SQL expression that computes business minutes between the already-
    clipped biz_start and biz_end columns. Matches colleague definition:
    same-day vs multi-day with first/last partial days and full weekdays × 600."""
    return """
        CASE
            WHEN biz_start >= biz_end THEN 0
            WHEN DATEDIFF(day, biz_start::date, biz_end::date) = 0 THEN
                DATEDIFF(minute, biz_start, biz_end)
            ELSE
                DATEDIFF(minute, biz_start,
                         DATE_TRUNC('day', biz_start) + INTERVAL '18 hours')
                + DATEDIFF(minute,
                           DATE_TRUNC('day', biz_end) + INTERVAL '8 hours',
                           biz_end)
                + (
                    (DATEDIFF(day, biz_start::date, biz_end::date) - 1)
                    - 2 * ((DATEDIFF(day, biz_start::date, biz_end::date) - 1) / 7)
                    - CASE WHEN EXTRACT(DOW FROM biz_start) = 0 THEN 1 ELSE 0 END
                    - CASE WHEN EXTRACT(DOW FROM biz_end) = 6 THEN 1 ELSE 0 END
                ) * 600
        END"""


def build_received_to_open_business_hours_query(where_sql: str) -> str:
    """Grouped query: median business-minutes per day per supplier."""
    return f"""
        WITH clipped AS (
            SELECT
                document_created_at,
                document_first_accessed_at,
                supplier_id,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                document_created_at,
                supplier_id,
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            DATE_TRUNC('day', document_created_at)::date AS date,
            supplier_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS avg_minutes,
            COUNT(*) AS count
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins <= 6000
        GROUP BY 1, 2
        ORDER BY 1, 2
    """


def build_received_to_open_business_hours_overall_query(where_sql: str) -> str:
    """Scalar query: overall median business-minutes across all documents."""
    return f"""
        WITH clipped AS (
            SELECT
                document_created_at,
                document_first_accessed_at,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS median_minutes
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins <= 6000
    """


def build_received_to_open_business_hours_bulk_query(where_sql: str) -> str:
    """Bulk grouped query: median business-minutes per org, date, supplier."""
    return f"""
        WITH clipped AS (
            SELECT
                supplier_organization_id,
                document_created_at,
                document_first_accessed_at,
                supplier_id,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                supplier_organization_id,
                document_created_at,
                supplier_id,
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            supplier_organization_id,
            DATE_TRUNC('day', document_created_at)::date AS date,
            supplier_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS avg_minutes,
            COUNT(*) AS count
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins <= 6000
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """


def build_received_to_open_business_hours_bulk_overall_query(where_sql: str) -> str:
    """Bulk overall query: one median per supplier_organization_id."""
    return f"""
        WITH clipped AS (
            SELECT
                supplier_organization_id,
                document_created_at,
                document_first_accessed_at,
                {_clip_start_sql()} AS biz_start,
                {_clip_end_sql()} AS biz_end
            FROM analytics.intake_documents
            WHERE {where_sql}
        ),
        biz AS (
            SELECT
                supplier_organization_id,
                {_business_minutes_sql()} AS biz_mins
            FROM clipped
        )
        SELECT
            supplier_organization_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_mins) AS median_minutes
        FROM biz
        WHERE biz_mins > 0
          AND biz_mins <= 6000
        GROUP BY supplier_organization_id
    """
