"""
Shared SQL for "received to open" cycle time in business hours (8 AM–6 PM Mon–Fri).
Used by the cycle_time API router and by export_queries so API and export stay in sync.
"""


def _clip_start_sql() -> str:
    """SQL expression that clips document_created_at forward to the next
    business-hour boundary (Mon-Fri 8am-6pm)."""
    return """
        CASE
            -- Sunday -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 0 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '1 day' + INTERVAL '8 hours'
            -- Saturday -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 6 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '2 days' + INTERVAL '8 hours'
            -- Friday after 6pm -> next Monday 8am
            WHEN EXTRACT(DOW FROM document_created_at) = 5
                 AND EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '3 days' + INTERVAL '8 hours'
            -- Other weekday after 6pm -> next day 8am
            WHEN EXTRACT(HOUR FROM document_created_at) >= 18 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '1 day' + INTERVAL '8 hours'
            -- Before 8am -> same day 8am
            WHEN EXTRACT(HOUR FROM document_created_at) < 8 THEN
                DATE_TRUNC('day', document_created_at) + INTERVAL '8 hours'
            -- During business hours: keep as-is
            ELSE document_created_at
        END"""


def _clip_end_sql() -> str:
    """SQL expression that clips document_first_accessed_at backward to the
    most recent business-hour boundary (Mon-Fri 8am-6pm)."""
    return """
        CASE
            -- Sunday -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 0 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '2 days' + INTERVAL '18 hours'
            -- Saturday -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 6 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '1 day' + INTERVAL '18 hours'
            -- Monday before 8am -> previous Friday 6pm
            WHEN EXTRACT(DOW FROM document_first_accessed_at) = 1
                 AND EXTRACT(HOUR FROM document_first_accessed_at) < 8 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '3 days' + INTERVAL '18 hours'
            -- Other weekday before 8am -> previous day 6pm
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) < 8 THEN
                DATE_TRUNC('day', document_first_accessed_at) - INTERVAL '1 day' + INTERVAL '18 hours'
            -- After 6pm -> same day 6pm
            WHEN EXTRACT(HOUR FROM document_first_accessed_at) >= 18 THEN
                DATE_TRUNC('day', document_first_accessed_at) + INTERVAL '18 hours'
            -- During business hours: keep as-is
            ELSE document_first_accessed_at
        END"""


def _business_minutes_sql() -> str:
    """SQL expression that computes business minutes between the already-
    clipped biz_start and biz_end columns."""
    return """
        CASE
            WHEN biz_start >= biz_end THEN 0
            WHEN biz_start::date = biz_end::date THEN
                DATEDIFF(minute, biz_start, biz_end)
            ELSE
                -- Partial start day: biz_start -> 6 pm
                DATEDIFF(minute, biz_start,
                         DATE_TRUNC('day', biz_start) + INTERVAL '18 hours')
                -- Partial end day: 8 am -> biz_end
                + DATEDIFF(minute,
                           DATE_TRUNC('day', biz_end) + INTERVAL '8 hours',
                           biz_end)
                -- Full weekdays in between × 600 minutes each
                + (CASE
                    WHEN DATEDIFF(day, biz_start::date, biz_end::date) <= 1 THEN 0
                    ELSE (
                        (DATEDIFF(day, biz_start::date, biz_end::date) - 1) / 7 * 5
                        + MOD(DATEDIFF(day, biz_start::date, biz_end::date) - 1, 7)
                        - GREATEST(0, LEAST(
                            MOD(DATEDIFF(day, biz_start::date, biz_end::date) - 1, 7)
                            - 5 + EXTRACT(DOW FROM biz_start),
                            2))
                    )
                  END) * 600
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
          AND biz_mins < 6000  -- exclude outliers > ~2 business weeks
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
          AND biz_mins < 6000
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
          AND biz_mins < 6000
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
          AND biz_mins < 6000
        GROUP BY supplier_organization_id
    """
